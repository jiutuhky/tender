"""按项目沙箱租约执行 SmolVM 启动对账。"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable

from smolvm import VMNotFoundError
from smolvm.types import VMState

from hagent.sandbox.smolvm.lifecycle import SandboxAdoptError, describe_sdk_error
from hagent.server.leases import SandboxState

logger = logging.getLogger(__name__)

VM_ID_PREFIX = "hagent-"
_CLAIMING_STATES = {
    SandboxState.CREATING.value,
    SandboxState.RUNNING.value,
    SandboxState.PAUSED.value,
}


@dataclass
class ReconcileAction:
    kind: str
    vm_id: str | None = None
    project_id: str | None = None
    reason: str = ""


def _default_pid_alive(pid: int | None) -> bool:
    return pid is not None and os.path.exists(f"/proc/{pid}")


class SmolVMReconciler:
    def __init__(
        self,
        *,
        manager,
        leases,
        adopt_fn: Callable[[str], object],
        on_adopted: Callable[[str, object], None],
        pid_alive: Callable[[int | None], bool] = _default_pid_alive,
        protected_vm_ids: Callable[[], set[str]] | None = None,
        on_orphaned: Callable[[str, str], None] | None = None,
    ) -> None:
        self._manager = manager
        self._leases = leases
        self._adopt_fn = adopt_fn
        self._on_adopted = on_adopted
        self._pid_alive = pid_alive
        self._protected_vm_ids = protected_vm_ids or (lambda: set())
        self._on_orphaned = on_orphaned
        self._scans = 0
        self._unclaimed_seen: set[str] = set()

    def plan(self) -> list[ReconcileAction]:
        self._scans += 1
        startup_scan = self._scans == 1
        actions: list[ReconcileAction] = []
        deferred: set[str] = set()
        active_leases = [
            lease
            for lease in self._leases.list()
            if lease.sandbox_kind == "smolvm"
            and lease.sandbox_state != SandboxState.CLOSED.value
        ]
        by_vm_id = {
            lease.sandbox_id: lease for lease in active_leases if lease.sandbox_id
        }

        def reclaim_or_defer(vm_id: str, reason: str) -> None:
            if startup_scan or vm_id in self._unclaimed_seen:
                actions.append(ReconcileAction(kind="reclaim", vm_id=vm_id, reason=reason))
            else:
                deferred.add(vm_id)
                logger.info("首见无主 VM %s(%s):缓刑一轮,防创建窗口误杀", vm_id, reason)

        vms = [
            vm for vm in self._manager.list_vms() if vm.vm_id.startswith(VM_ID_PREFIX)
        ]
        protected = self._protected_vm_ids()
        seen_vm_ids: set[str] = set()
        for vm in vms:
            seen_vm_ids.add(vm.vm_id)
            if vm.vm_id in protected:
                continue
            lease = by_vm_id.get(vm.vm_id)
            alive = self._pid_alive(vm.pid)
            if vm.status in (VMState.RUNNING, VMState.PAUSED) and alive:
                if lease is not None:
                    actions.append(
                        ReconcileAction(
                            kind="adopt",
                            vm_id=vm.vm_id,
                            project_id=lease.project_id,
                            reason=f"{vm.status.value} + pid 活 + project lease",
                        )
                    )
                else:
                    reclaim_or_defer(vm.vm_id, "无主活 VM")
            elif vm.status in (VMState.RUNNING, VMState.PAUSED):
                actions.append(
                    ReconcileAction(kind="reclaim", vm_id=vm.vm_id, reason="pid 已死")
                )
                if lease is not None:
                    actions.append(
                        ReconcileAction(
                            kind="orphan",
                            project_id=lease.project_id,
                            reason="VM 进程消失",
                        )
                    )
            else:
                reclaim_or_defer(vm.vm_id, f"残留状态 {vm.status.value}")
        self._unclaimed_seen = deferred

        for lease in active_leases:
            if (
                lease.sandbox_id
                and lease.sandbox_id not in seen_vm_ids
                and (lease.sandbox_state or "") in _CLAIMING_STATES
            ):
                actions.append(
                    ReconcileAction(
                        kind="orphan",
                        project_id=lease.project_id,
                        reason="VM 记录不存在",
                    )
                )
        return actions

    def apply(self, action: ReconcileAction) -> None:
        if action.kind == "adopt":
            self._apply_adopt(action)
        elif action.kind == "reclaim":
            self._apply_reclaim(action)
        elif action.kind == "orphan":
            self._apply_orphan(action)
        else:
            raise ValueError(f"未知对账动作: {action.kind!r}")

    def _apply_adopt(self, action: ReconcileAction) -> None:
        assert action.vm_id is not None and action.project_id is not None
        try:
            sandbox = self._adopt_fn(action.vm_id)
        except SandboxAdoptError as exc:
            logger.warning("收养 %s 失败,转清场: %s", action.vm_id, exc)
            self._delete_vm(action.vm_id)
            self._leases.update_state(
                action.project_id, state=SandboxState.ORPHANED.value
            )
            return
        self._on_adopted(action.project_id, sandbox)
        self._leases.update_state(action.project_id, state=SandboxState.RUNNING.value)
        logger.info("收养 VM %s → project %s", action.vm_id, action.project_id)

    def _apply_reclaim(self, action: ReconcileAction) -> None:
        assert action.vm_id is not None
        self._delete_vm(action.vm_id)
        logger.info("清场 VM %s(%s)", action.vm_id, action.reason)

    def _apply_orphan(self, action: ReconcileAction) -> None:
        assert action.project_id is not None
        self._leases.update_state(action.project_id, state=SandboxState.ORPHANED.value)
        clear_sandbox = getattr(self._leases, "clear_sandbox", None)
        if callable(clear_sandbox):
            clear_sandbox(action.project_id)
        if self._on_orphaned is not None:
            self._on_orphaned(action.project_id, action.reason)
        logger.info("project %s 标 orphaned(%s)", action.project_id, action.reason)

    def _delete_vm(self, vm_id: str) -> None:
        try:
            self._manager.delete(vm_id)
        except VMNotFoundError:
            pass

    def reap_errors(self) -> None:
        try:
            stale = self._manager.reconcile()
            if stale:
                logger.info("SDK reconcile 降级 %d 个死 VM: %s", len(stale), stale)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SDK reconcile 失败: %s", describe_sdk_error(exc))
        for vm in self._manager.list_vms(VMState.ERROR):
            if not vm.vm_id.startswith(VM_ID_PREFIX):
                continue
            try:
                self._manager.delete(vm.vm_id)
                logger.info("补 delete ERROR 行 %s", vm.vm_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ERROR 行 %s 清理失败: %s", vm.vm_id, describe_sdk_error(exc))
