"""Task A9 — SmolVMReconciler:spec §4.4 启动对账矩阵,表驱动全分支。"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from smolvm.types import VMState

from hagent.sandbox.smolvm.lifecycle import SandboxAdoptError
from hagent.sandbox.smolvm.reconciler import SmolVMReconciler


# ---------------------------------------------------------------------------
# 替身
# ---------------------------------------------------------------------------


@dataclass
class FakeVMInfo:
    vm_id: str
    status: VMState
    pid: int | None = 1000


@dataclass
class FakeLease:
    project_id: str
    sandbox_kind: str = "smolvm"
    sandbox_id: str | None = None
    sandbox_state: str | None = "running"


class FakeSmolVMManager:
    def __init__(self, vms: list[FakeVMInfo] | None = None):
        self.vms = vms or []
        self.deleted: list[str] = []
        self.reconciled = 0
        self.reconcile_result: list[str] = []

    def list_vms(self, status=None):
        if status is None:
            return list(self.vms)
        return [v for v in self.vms if v.status == status]

    def delete(self, vm_id: str) -> None:
        self.deleted.append(vm_id)

    def reconcile(self) -> list[str]:
        self.reconciled += 1
        return list(self.reconcile_result)


class FakeLeases:
    def __init__(self, leases: list[FakeLease] | None = None):
        self.leases = leases or []
        self.state_updates: list[tuple[str, dict]] = []
        self.cleared: list[str] = []

    def list(self):
        return list(self.leases)

    def update_state(self, pid: str, *, state=None, desired_state=None):
        self.state_updates.append((pid, {"state": state, "desired_state": desired_state}))

    def clear_sandbox(self, project_id: str):
        self.cleared.append(project_id)


@dataclass
class Harness:
    manager: FakeSmolVMManager
    leases: FakeLeases
    adopted: list[str] = field(default_factory=list)
    adopt_registered: list[tuple[str, object]] = field(default_factory=list)
    adopt_error: Exception | None = None
    alive_pids: set[int] = field(default_factory=lambda: {1000})

    def build(self) -> SmolVMReconciler:
        def adopt_fn(vm_id: str):
            self.adopted.append(vm_id)
            if self.adopt_error is not None:
                raise self.adopt_error
            return f"sandbox:{vm_id}"

        return SmolVMReconciler(
            manager=self.manager,
            leases=self.leases,
            adopt_fn=adopt_fn,
            on_adopted=lambda pid, sb: self.adopt_registered.append((pid, sb)),
            pid_alive=lambda pid: pid in self.alive_pids,
        )


def run_reconcile(harness: Harness) -> None:
    reconciler = harness.build()
    for action in reconciler.plan():
        reconciler.apply(action)


# ---------------------------------------------------------------------------
# 对账矩阵表驱动(spec §4.4)
# ---------------------------------------------------------------------------

PID = "abcd1234efgh5678"
VMID = "hagent-abcd1234-a1b2c3"


@pytest.mark.parametrize(
    ("vm_status", "pid_alive", "has_session", "expect"),
    [
        # 1. RUNNING + pid 活 + active session → 收养
        (VMState.RUNNING, True, True, "adopt"),
        # 2. RUNNING + pid 活 + 无匹配 session → 清场
        (VMState.RUNNING, True, False, "reclaim"),
        # 3. RUNNING + pid 死 + 有 session → 清场 + 标 orphaned
        (VMState.RUNNING, False, True, "reclaim+orphan"),
        # 4. PAUSED + pid 死 + 有 session → 清场 + 标 orphaned
        (VMState.PAUSED, False, True, "reclaim+orphan"),
        # 5. PAUSED + pid 活 + active session → 收养(adopt 内部 resume)
        (VMState.PAUSED, True, True, "adopt"),
        # 6/7/8. CREATED / STOPPED / ERROR 残留 → 清场
        (VMState.CREATED, False, False, "reclaim"),
        (VMState.STOPPED, False, False, "reclaim"),
        (VMState.ERROR, False, True, "reclaim"),
    ],
)
def test_reconcile_matrix(vm_status, pid_alive, has_session, expect):
    vm = FakeVMInfo(vm_id=VMID, status=vm_status, pid=1000 if pid_alive else 999)
    leases = [FakeLease(project_id=PID, sandbox_id=VMID)] if has_session else []
    h = Harness(manager=FakeSmolVMManager([vm]), leases=FakeLeases(leases))
    run_reconcile(h)

    if expect == "adopt":
        assert h.adopted == [VMID]
        assert h.adopt_registered == [(PID, f"sandbox:{VMID}")]
        assert h.manager.deleted == []
    elif expect == "reclaim":
        assert h.adopted == []
        assert h.manager.deleted == [VMID]
    elif expect == "reclaim+orphan":
        assert h.manager.deleted == [VMID]
        assert (PID, {"state": "orphaned", "desired_state": None}) in h.leases.state_updates


def test_session_running_without_vm_marked_orphaned():
    # 矩阵第 9 分支:(无 VM)× session 标 running → orphaned,数据保留等重建
    h = Harness(
        manager=FakeSmolVMManager([]),
        leases=FakeLeases([FakeLease(project_id=PID, sandbox_id=VMID)]),
    )
    run_reconcile(h)
    assert (PID, {"state": "orphaned", "desired_state": None}) in h.leases.state_updates
    assert h.leases.cleared == [PID]
    assert h.manager.deleted == []


def test_snapshotted_session_without_vm_not_orphaned():
    """Task C2 回归:快照持久化后 VM 记录消失是常态,不得误标 orphaned。

    snapshotted 不在 _CLAIMING_STATES:该 session 对 VM 无主张,
    其恢复走消息路径的 acquire_restored,与对账矩阵无关。
    """
    h = Harness(
        manager=FakeSmolVMManager([]),
        leases=FakeLeases(
            [FakeLease(project_id=PID, sandbox_id=VMID, sandbox_state="snapshotted")]
        ),
    )
    run_reconcile(h)
    assert h.leases.state_updates == []
    assert h.manager.deleted == []


def test_adopt_failure_falls_back_to_reclaim_plus_orphan():
    # 收养探针不过 → 清场 + 标 orphaned(不上抛:这是矩阵内处理过的结局)
    vm = FakeVMInfo(vm_id=VMID, status=VMState.RUNNING, pid=1000)
    h = Harness(
        manager=FakeSmolVMManager([vm]),
        leases=FakeLeases([FakeLease(project_id=PID, sandbox_id=VMID)]),
    )
    h.adopt_error = SandboxAdoptError("probe failed")
    run_reconcile(h)
    assert h.manager.deleted == [VMID]
    assert (PID, {"state": "orphaned", "desired_state": None}) in h.leases.state_updates
    assert h.adopt_registered == []


def test_pool_owned_idle_vm_not_reclaimed():
    # 暖池 VM 没有 session 是常态,reaper 不得当无主清场(e2e 曾因此 500)
    vm = FakeVMInfo(vm_id=VMID, status=VMState.RUNNING, pid=1000)
    h = Harness(manager=FakeSmolVMManager([vm]), leases=FakeLeases([]))
    reconciler = SmolVMReconciler(
        manager=h.manager,
        leases=h.leases,
        adopt_fn=lambda vm_id: None,
        on_adopted=lambda pid, sb: None,
        pid_alive=lambda pid: True,
        protected_vm_ids=lambda: {VMID},
    )
    actions = reconciler.plan()
    assert actions == [], f"池在册 VM 不参与对账,got {actions}"


def test_pool_owned_leased_vm_not_readopted():
    # 已租借 VM 有匹配 session,但已被本进程管理,不得重复收养
    vm = FakeVMInfo(vm_id=VMID, status=VMState.RUNNING, pid=1000)
    h = Harness(
        manager=FakeSmolVMManager([vm]),
        leases=FakeLeases([FakeLease(project_id=PID, sandbox_id=VMID)]),
    )
    reconciler = SmolVMReconciler(
        manager=h.manager,
        leases=h.leases,
        adopt_fn=lambda vm_id: None,
        on_adopted=lambda pid, sb: None,
        pid_alive=lambda pid: True,
        protected_vm_ids=lambda: {VMID},
    )
    actions = reconciler.plan()
    assert actions == []


def test_protected_vm_session_not_marked_orphaned():
    # 在册 VM 的 session 不能因「跳过对账」而被误标 orphaned
    vm = FakeVMInfo(vm_id=VMID, status=VMState.RUNNING, pid=1000)
    h = Harness(
        manager=FakeSmolVMManager([vm]),
        leases=FakeLeases([FakeLease(project_id=PID, sandbox_id=VMID)]),
    )
    reconciler = SmolVMReconciler(
        manager=h.manager,
        leases=h.leases,
        adopt_fn=lambda vm_id: None,
        on_adopted=lambda pid, sb: None,
        pid_alive=lambda pid: True,
        protected_vm_ids=lambda: {VMID},
    )
    for action in reconciler.plan():
        reconciler.apply(action)
    assert h.leases.state_updates == []


def test_non_hagent_vms_ignored():
    vms = [
        FakeVMInfo(vm_id="sbx-user-vm", status=VMState.RUNNING, pid=1000),
        FakeVMInfo(vm_id="openclaw-1", status=VMState.ERROR, pid=None),
    ]
    h = Harness(manager=FakeSmolVMManager(vms), leases=FakeLeases([]))
    run_reconcile(h)
    assert h.manager.deleted == [], "非 hagent- 前缀的 VM 不得动"


def test_closed_project_lease_vm_reclaimed():
    # 项目租约关闭后其 VM 视为无主并清场。
    vm = FakeVMInfo(vm_id=VMID, status=VMState.RUNNING, pid=1000)
    h = Harness(
        manager=FakeSmolVMManager([vm]),
        leases=FakeLeases(
            [FakeLease(project_id=PID, sandbox_id=VMID, sandbox_state="closed")]
        ),
    )
    run_reconcile(h)
    assert h.manager.deleted == [VMID]


def test_reap_errors_reconciles_then_deletes_error_rows():
    # F3:reconcile() 只降级不释放,ERROR 行必须补 delete() 才还 TAP/IP 租约
    error_vm = FakeVMInfo(vm_id=VMID, status=VMState.ERROR, pid=None)
    other = FakeVMInfo(vm_id="sbx-user", status=VMState.ERROR, pid=None)
    h = Harness(manager=FakeSmolVMManager([error_vm, other]), leases=FakeLeases([]))
    reconciler = h.build()
    reconciler.reap_errors()
    assert h.manager.reconciled == 1
    assert VMID in h.manager.deleted
    assert "sbx-user" not in h.manager.deleted


# ---------------------------------------------------------------------------
# 无主 VM 两轮复核(创建窗口防误杀,Phase B 生产事故回归)
#
# 事故形态:pool.acquire 的 VM 启动需 1–2s,期间 VM 已在 SmolVM DB、
# 但尚未进池保护集、session 元数据也未写 —— reaper 恰好扫到即被当
# 「无主活 VM」清场 → 池发出死句柄 → 上传 500。
# 语义:启动对账(首轮)立即清场不变(彼时本进程无创建中 VM);
# 周期轮对无主/残留 VM 首见缓刑、连续两轮无主才清;pid 死是确证,不缓刑。
# ---------------------------------------------------------------------------


def test_reaper_defers_fresh_unclaimed_vm_then_reclaims():
    h = Harness(manager=FakeSmolVMManager([]), leases=FakeLeases([]))
    reconciler = h.build()
    assert reconciler.plan() == []  # 启动轮(空场)

    h.manager.vms.append(FakeVMInfo(vm_id=VMID, status=VMState.RUNNING, pid=1000))
    assert reconciler.plan() == [], "周期轮首见无主活 VM:缓刑,不得清场"
    plan3 = reconciler.plan()
    assert [a.kind for a in plan3] == ["reclaim"], "连续两轮无主才清场"


def test_startup_scan_reclaims_unclaimed_immediately():
    vm = FakeVMInfo(vm_id=VMID, status=VMState.RUNNING, pid=1000)
    h = Harness(manager=FakeSmolVMManager([vm]), leases=FakeLeases([]))
    plan1 = h.build().plan()
    assert [a.kind for a in plan1] == ["reclaim"], "启动对账首轮维持立即清场"


def test_deferred_vm_claimed_before_second_scan_is_adopted():
    h = Harness(manager=FakeSmolVMManager([]), leases=FakeLeases([]))
    reconciler = h.build()
    reconciler.plan()  # 启动轮
    h.manager.vms.append(FakeVMInfo(vm_id=VMID, status=VMState.RUNNING, pid=1000))
    assert reconciler.plan() == []  # 缓刑
    # 创建完成:session 元数据落库(sandbox_id 关联)
    h.leases.leases.append(FakeLease(project_id=PID, sandbox_id=VMID))
    plan3 = reconciler.plan()
    assert [a.kind for a in plan3] == ["adopt"], "缓刑期完成认领的 VM 应收养而非清场"


def test_pid_dead_not_deferred_on_periodic_scan():
    h = Harness(manager=FakeSmolVMManager([]), leases=FakeLeases([]))
    reconciler = h.build()
    reconciler.plan()  # 启动轮
    h.manager.vms.append(FakeVMInfo(vm_id=VMID, status=VMState.RUNNING, pid=999))  # pid 死
    h.leases.leases.append(FakeLease(project_id=PID, sandbox_id=VMID))
    kinds = sorted(a.kind for a in reconciler.plan())
    assert kinds == ["orphan", "reclaim"], "pid 死是确证故障,不缓刑"


def test_residue_state_deferred_on_periodic_scan():
    h = Harness(manager=FakeSmolVMManager([]), leases=FakeLeases([]))
    reconciler = h.build()
    reconciler.plan()  # 启动轮
    # CREATED 是 from_image 刚落库、start() 未完成的最早形态,恰是要保护的窗口
    h.manager.vms.append(FakeVMInfo(vm_id=VMID, status=VMState.CREATED, pid=None))
    assert reconciler.plan() == [], "CREATED 残留首见缓刑(可能正在创建)"
    plan3 = reconciler.plan()
    assert [a.kind for a in plan3] == ["reclaim"]
