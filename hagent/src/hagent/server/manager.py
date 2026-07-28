"""把对话会话解析到项目级沙箱租约。"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from threading import Lock, RLock
from typing import TYPE_CHECKING

from hagent.sandbox import SandboxKind
from hagent.sandbox.pool import SandboxLease, SandboxPool
from hagent.server.leases import LeaseStore, ProjectLeaseState, SandboxState
from hagent.server.sessions import SessionState, SessionStatus, SessionStore
from hagent.server.sse import SandboxEvent, push_sandbox_event

if TYPE_CHECKING:
    from hagent.sandbox.protocol import HagentSandboxProtocol
    from hagent.server.project_workspace import ProjectWorkspace
    from hagent.server.runs import RunState, RunStore
    from hagent.server.workspace_checkpoint import CheckpointResult, WorkspaceCheckpointer
    from hagent.server.workspace_materialization import WorkspaceMaterializer

logger = logging.getLogger(__name__)


def _delete_snapshot_quiet(snapshot_id: str) -> None:
    try:
        from hagent.sandbox.smolvm.lifecycle import delete_snapshot_quiet

        delete_snapshot_quiet(snapshot_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("快照 %s 清理失败(忽略): %s", snapshot_id, exc)


def _close_agent_quiet(session_id: str) -> None:
    try:
        from hagent.server.agents import close_agent

        close_agent(session_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("session %s agent 缓存失效失败: %s", session_id, exc)


class SessionManager:
    """管理对话会话与项目级运行时租约。"""

    def __init__(
        self,
        *,
        store: SessionStore,
        lease_store: LeaseStore,
        sandbox_pool: SandboxPool | None,
        workspace_root: Path | str,
        workspace_materializer: WorkspaceMaterializer | None = None,
        project_workspace: ProjectWorkspace | None = None,
        run_store: RunStore | None = None,
        workspace_checkpointer: WorkspaceCheckpointer | None = None,
    ) -> None:
        self._store = store
        self._lease_store = lease_store
        self._pool = sandbox_pool
        self._workspace_root = Path(workspace_root)
        self._workspace_materializer = workspace_materializer
        self._project_workspace = project_workspace
        self._run_store = run_store
        self._workspace_checkpointer = workspace_checkpointer
        self._leases: dict[str, SandboxLease] = {}
        self._project_locks: dict[str, RLock] = {}
        self._project_locks_guard = Lock()
        if self._pool is not None:
            set_lifecycle_fn = getattr(self._pool, "set_lifecycle_fn", None)
            if callable(set_lifecycle_fn):
                set_lifecycle_fn(self.handle_sandbox_lifecycle)
            set_project_guard_fn = getattr(self._pool, "set_project_guard_fn", None)
            if callable(set_project_guard_fn):
                set_project_guard_fn(self._lock_for)
            set_activity_fns = getattr(self._pool, "set_activity_fns", None)
            if callable(set_activity_fns):
                set_activity_fns(
                    touch_fn=self._touch_project_activity,
                    last_activity_fn=self._lease_store.last_activity_timestamp,
                )
            set_checkpoint_fn = getattr(self._pool, "set_checkpoint_fn", None)
            if callable(set_checkpoint_fn):
                set_checkpoint_fn(self.checkpoint_project)

    @property
    def store(self) -> SessionStore:
        return self._store

    @property
    def lease_store(self) -> LeaseStore:
        return self._lease_store

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    @property
    def project_workspace(self) -> ProjectWorkspace | None:
        return self._project_workspace

    @property
    def run_store(self) -> RunStore | None:
        return self._run_store

    def workspace_dir(self, session_id: str) -> str:
        session = self._store.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return str(self._workspace_root / "projects" / session.project_id / "workspace")

    def create_session(
        self,
        *,
        project_id: str,
        sandbox_kind: SandboxKind = SandboxKind.NONE,
    ) -> SessionState:
        node = getattr(self._pool, "node_id", None) if self._pool is not None else None
        self._lease_store.ensure(
            project_id,
            sandbox_kind=sandbox_kind.value,
            node=node if isinstance(node, str) else None,
        )
        # VM 获取刻意延迟到项目第一次运行或发送消息时。
        return self._store.create(project_id=project_id)

    def delete_session(self, session_id: str) -> None:
        # 会话只拥有对话；同项目的其他会话继续使用共享 VM 与快照。
        self._store.delete(session_id)

    def release_project(self, project_id: str) -> None:
        """释放软删除项目的算力，同时保留工作区数据。"""
        with self._lock_for(project_id):
            runtime_lease = self._leases.pop(project_id, None)
            if runtime_lease is not None and self._pool is not None:
                self._pool.release(runtime_lease)
            lease = self._lease_store.get(project_id)
            if lease is None:
                return
            if lease.snapshot_id:
                _delete_snapshot_quiet(lease.snapshot_id)
                self._lease_store.update_snapshot(project_id, None)
            self._lease_store.clear_sandbox(project_id)
            self._lease_store.update_state(
                project_id,
                state=SandboxState.CLOSED.value,
                desired_state=SandboxState.CLOSED.value,
            )
            self._close_project_agents(project_id)

    def get_sandbox(self, session_id: str):
        session = self._store.get(session_id)
        if session is None:
            return None
        return self.get_project_sandbox(session.project_id)

    def get_project_sandbox(self, project_id: str):
        with self._lock_for(project_id):
            lease = self._leases.get(project_id)
            return lease.sandbox if lease is not None else None

    def live_sandboxes(self) -> list[tuple[str, object]]:
        """返回健康巡检与指标循环使用的 ``(project_id, sandbox)`` 目标。"""
        return [
            (project_id, lease.sandbox)
            for project_id, lease in list(self._leases.items())
        ]

    def touch_activity(self, session_id: str) -> None:
        session = self._store.get(session_id)
        if session is not None:
            self._touch_project_activity(session.project_id)

    def create_chat_turn(self, session_id: str, *, summary: str) -> RunState:
        if self._run_store is None or self._project_workspace is None:
            raise RuntimeError("RunStore 尚未装配")
        session = self._store.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return self._run_store.create_chat_turn(
            project_id=session.project_id,
            session_id=session_id,
            base_revision=self._project_workspace.head(session.project_id),
            summary=summary,
        )

    def mark_run_running(self, run_id: str) -> RunState:
        if self._run_store is None:
            raise RuntimeError("RunStore 尚未装配")
        return self._run_store.mark_running(run_id)

    def reject_run(self, run_id: str, error: str) -> None:
        if self._run_store is None:
            return
        from hagent.server.runs import RunStatus

        self._run_store.finish(run_id, status=RunStatus.REJECTED, error=error)

    def checkpoint_run(
        self,
        run_id: str,
        *,
        sandbox: HagentSandboxProtocol | None = None,
        interrupted: bool = False,
        error: str | None = None,
    ) -> CheckpointResult:
        if self._workspace_checkpointer is None:
            raise RuntimeError("WorkspaceCheckpointer 尚未装配")
        return self._workspace_checkpointer.checkpoint(
            run_id,
            sandbox=sandbox,
            interrupted=interrupted,
            error=error,
        )

    def interrupt_run_best_effort(
        self,
        run_id: str,
        *,
        sandbox: HagentSandboxProtocol | None,
        error: str,
    ) -> None:
        try:
            self.checkpoint_run(
                run_id,
                sandbox=sandbox,
                interrupted=True,
                error=error,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("run %s 异常 checkpoint 失败: %s", run_id, exc)

    def checkpoint_project(
        self,
        project_id: str,
        sandbox: HagentSandboxProtocol | None = None,
    ) -> None:
        """生命周期动作前 best-effort 保存项目所有未终态 Run。"""
        if self._run_store is None or self._workspace_checkpointer is None:
            return
        if sandbox is None:
            sandbox = self.get_project_sandbox(project_id)
        for run in self._run_store.active_for_project(project_id):
            try:
                self._workspace_checkpointer.checkpoint(
                    run.id,
                    sandbox=sandbox,
                    interrupted=True,
                    error="sandbox 生命周期动作触发兜底 checkpoint",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "project %s run %s 生命周期 checkpoint 失败: %s",
                    project_id,
                    run.id,
                    exc,
                )

    def interrupt_unrecovered_runs(self) -> None:
        """启动对账后终结没有可抢救 VM 的遗留 Run。"""
        if self._run_store is None:
            return
        self._run_store.interrupt_active(error="server 重启中断未完成 Run")

    def _touch_project_activity(self, project_id: str) -> None:
        with self._lock_for(project_id):
            self._lease_store.touch_activity(project_id)

    def drop_sandbox(
        self,
        project_id: str,
        expected_sandbox=None,
        before_drop: Callable[[], None] | None = None,
        after_drop: Callable[[], None] | None = None,
    ) -> bool:
        with self._lock_for(project_id):
            runtime_lease = self._leases.get(project_id)
            if runtime_lease is None:
                return False
            if (
                expected_sandbox is not None
                and runtime_lease.sandbox is not expected_sandbox
            ):
                return False
            if before_drop is not None:
                before_drop()
            if self._pool is not None:
                evict = getattr(self._pool, "evict", None)
                if callable(evict) and not evict(project_id):
                    return False
            self._leases.pop(project_id, None)
            self._close_project_agents(project_id)
            if after_drop is not None:
                after_drop()
            return True

    def persist_sandbox(self, runtime_lease: SandboxLease) -> bool:
        with self._lock_for(runtime_lease.project_id):
            return self._persist_sandbox_locked(runtime_lease)

    def _persist_sandbox_locked(self, runtime_lease: SandboxLease) -> bool:
        project_id = runtime_lease.project_id
        if self._leases.get(project_id) is not runtime_lease:
            return False
        sandbox = runtime_lease.sandbox
        persist = getattr(sandbox, "persist_to_snapshot", None)
        if not callable(persist):
            return False
        try:
            snapshot_id = persist()
        except Exception as exc:  # noqa: BLE001
            logger.warning("project %s 快照持久化失败(退回驱逐): %s", project_id, exc)
            return False
        self._leases.pop(project_id, None)
        self._close_project_agents(project_id)
        self._lease_store.update_snapshot(project_id, snapshot_id)
        self._lease_store.clear_sandbox(project_id)
        self._lease_store.update_state(project_id, state=SandboxState.SNAPSHOTTED.value)
        self.emit_project_event(
            "snapshotted", project_id, sandbox, reason="idle 超阈值,已休眠到快照"
        )
        logger.info("project %s 已快照持久化: %s", project_id, snapshot_id)
        return True

    def ensure_sandbox(self, session_id: str):
        session = self._store.get(session_id)
        if session is None or session.status != SessionStatus.ACTIVE:
            return None
        project_id = session.project_id
        with self._lock_for(project_id):
            return self._ensure_project_sandbox(project_id)

    def _ensure_project_sandbox(self, project_id: str):
        sandbox = self.get_project_sandbox(project_id)
        if sandbox is not None:
            self._resume_if_paused(project_id, sandbox)
            self._materialize_workspace(project_id, sandbox)
            self._lease_store.touch_activity(project_id)
            return sandbox
        lease = self._lease_store.get(project_id)
        if lease is None or lease.sandbox_kind == SandboxKind.NONE.value or self._pool is None:
            return None
        if lease.sandbox_state == SandboxState.SNAPSHOTTED.value:
            sandbox = self._restore_sandbox(lease)
            self._materialize_workspace(project_id, sandbox)
        else:
            sandbox = self._acquire_new_sandbox(lease)
        self._lease_store.touch_activity(project_id)
        return sandbox

    def sync_project_workspace(self, project_id: str) -> bool:
        """宿主直写 workspace 后（如项目上传）把活跃租约的 VM 追平到 HEAD。

        只复用已存在的 runtime lease，绝不触发 VM 创建/快照恢复；
        无租约时返回 False，追平留给下一次 ensure 自愈。
        """
        with self._lock_for(project_id):
            runtime_lease = self._leases.get(project_id)
            if runtime_lease is None:
                return False
            sandbox = runtime_lease.sandbox
            self._resume_if_paused(project_id, sandbox)
            self._materialize_workspace(project_id, sandbox)
            self._lease_store.touch_activity(project_id)
            return True

    def _resume_if_paused(self, project_id: str, sandbox) -> None:
        manifest = getattr(sandbox, "manifest", None)
        if not getattr(manifest, "paused", False):
            return
        resume = getattr(sandbox, "resume", None)
        if not callable(resume):
            return
        try:
            resume()
            self._lease_store.update_state(project_id, state=SandboxState.RUNNING.value)
            self.emit_project_event("resumed", project_id, sandbox)
        except Exception as exc:  # noqa: BLE001
            logger.warning("project %s 唤醒 paused 沙箱失败: %s", project_id, exc)

    def _restore_sandbox(self, lease: ProjectLeaseState):
        project_id = lease.project_id
        if not lease.snapshot_id:
            self._lease_store.update_state(project_id, state=SandboxState.ORPHANED.value)
            fresh = self._lease_store.get(project_id)
            assert fresh is not None
            return self._acquire_new_sandbox(fresh)
        snapshot_id = lease.snapshot_id
        self._lease_store.update_state(
            project_id,
            state=SandboxState.CREATING.value,
            desired_state=SandboxState.RUNNING.value,
        )
        try:
            runtime_lease = self._pool.acquire_restored(
                project_id=project_id, snapshot_id=snapshot_id
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "project %s 快照 %s 恢复失败,回退全新重建: %s",
                project_id,
                snapshot_id,
                exc,
            )
            _delete_snapshot_quiet(snapshot_id)
            self._lease_store.update_snapshot(project_id, None)
            self._lease_store.update_state(project_id, state=SandboxState.ORPHANED.value)
            fresh = self._lease_store.get(project_id)
            assert fresh is not None
            return self._acquire_new_sandbox(fresh)
        self._leases[project_id] = runtime_lease
        self._close_project_agents(project_id)
        self._lease_store.update_snapshot(project_id, None)
        self._record_running_lease(project_id, runtime_lease)
        self.emit_project_event("restored", project_id, runtime_lease.sandbox, reason="从快照恢复")
        return runtime_lease.sandbox

    def _acquire_new_sandbox(self, lease: ProjectLeaseState):
        project_id = lease.project_id
        # 旧 VM 身份一旦进入重建路径就不再有效；先清引用，避免 reaper 在
        # 新 VM 创建窗口拿旧 sandbox_id 再次把本项目误判 orphaned。
        self._lease_store.clear_sandbox(project_id)
        self._lease_store.update_state(
            project_id,
            state=SandboxState.CREATING.value,
            desired_state=SandboxState.RUNNING.value,
        )
        try:
            runtime_lease = self._pool.acquire(project_id=project_id)
        except Exception:
            self._lease_store.update_state(project_id, state=SandboxState.ORPHANED.value)
            raise
        self._leases[project_id] = runtime_lease
        if self._workspace_materializer is not None:
            self._close_project_agents(project_id)
            try:
                self._materialize_workspace(
                    project_id, runtime_lease.sandbox, force_full=True
                )
            except Exception:
                self._discard_failed_materialization(project_id)
                raise
        elif lease.sandbox_state == SandboxState.ORPHANED.value:
            self._close_project_agents(project_id)
            self._reinstall_files(project_id, runtime_lease.sandbox)
        self._record_running_lease(project_id, runtime_lease)
        self.emit_project_event("created", project_id, runtime_lease.sandbox)
        return runtime_lease.sandbox

    def _materialize_workspace(
        self,
        project_id: str,
        sandbox: HagentSandboxProtocol,
        *,
        force_full: bool = False,
    ) -> None:
        if self._workspace_materializer is None:
            return
        lease = self._lease_store.get(project_id)
        if lease is None:
            raise KeyError(project_id)
        revision = self._workspace_materializer.materialize(
            project_id,
            sandbox,
            previous_revision=lease.materialized_revision,
            force_full=force_full,
        )
        self._lease_store.update_metadata(
            project_id, materialized_revision=revision
        )

    def _discard_failed_materialization(self, project_id: str) -> None:
        if self._pool is not None:
            try:
                self._pool.evict(project_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "project %s 物化失败后的沙箱驱逐失败: %s", project_id, exc
                )
        self._leases.pop(project_id, None)
        self._lease_store.clear_sandbox(project_id)
        self._lease_store.update_state(
            project_id, state=SandboxState.ORPHANED.value
        )
        self._close_project_agents(project_id)

    def _record_running_lease(self, project_id: str, runtime_lease: SandboxLease) -> None:
        sandbox = runtime_lease.sandbox
        manifest = getattr(sandbox, "manifest", None)
        vm_id = getattr(manifest, "container_id", None) or getattr(sandbox, "id", None)
        image_tag = getattr(manifest, "image_tag", None)
        runtime = getattr(manifest, "runtime", None)
        metadata = {
            "image_tag": image_tag if isinstance(image_tag, str) else None,
            "runtime": runtime if isinstance(runtime, str) else None,
        }
        self._lease_store.update_state(project_id, state=SandboxState.RUNNING.value)
        self._lease_store.update_metadata(
            project_id,
            sandbox_id=vm_id,
            node=getattr(self._pool, "node_id", None),
            metadata_json=json.dumps(metadata, ensure_ascii=False),
        )

    def _reinstall_files(self, project_id: str, sandbox) -> None:
        host_root = self._workspace_root / "projects" / project_id / "workspace"
        if not host_root.is_dir():
            return
        guest_root = getattr(sandbox, "workspace_dir", "/workspace").rstrip("/")
        try:
            files = [
                (f"{guest_root}/{path.relative_to(host_root).as_posix()}", path.read_bytes())
                for path in sorted(host_root.rglob("*"))
                if path.is_file() and ".git" not in path.relative_to(host_root).parts
            ]
        except OSError as exc:
            logger.warning("project %s files 重灌读取失败: %s", project_id, exc)
            return
        if not files:
            return
        try:
            results = sandbox.upload_files(files)
        except Exception as exc:  # noqa: BLE001
            logger.warning("project %s files 重灌失败: %s", project_id, exc)
            return
        failed = [result for result in results if getattr(result, "error", None)]
        if failed:
            logger.warning("project %s files 重灌:%d/%d 个文件失败", project_id, len(failed), len(files))

    def adopt_sandbox(self, project_id: str, sandbox) -> None:
        if self._pool is None:
            return
        with self._lock_for(project_id):
            runtime_lease = self._pool.register_external(sandbox, project_id=project_id)
            self._leases[project_id] = runtime_lease
            self._record_running_lease(project_id, runtime_lease)
            self.checkpoint_project(project_id, sandbox)
            self.emit_project_event("adopted", project_id, sandbox)

    def drain(self) -> None:
        if self._pool is None:
            return
        self._pool.drain()
        for project_id in list(self._leases):
            with self._lock_for(project_id):
                self._lease_store.update_state(project_id, state=SandboxState.PAUSED.value)

    def handle_sandbox_lifecycle(self, kind: str, project_id: str, sandbox) -> None:
        with self._lock_for(project_id):
            lease_state = self._lease_store.get(project_id)
            if (
                lease_state is None
                or lease_state.sandbox_state == SandboxState.CLOSED.value
            ):
                return
            runtime_lease = self._leases.get(project_id)
            if kind == "paused":
                if runtime_lease is None or runtime_lease.sandbox is not sandbox:
                    return
                self._lease_store.update_state(project_id, state=SandboxState.PAUSED.value)
            elif kind == "evicted":
                if runtime_lease is not None and runtime_lease.sandbox is not sandbox:
                    return
                if runtime_lease is None:
                    sandbox_id = getattr(
                        getattr(sandbox, "manifest", None),
                        "container_id",
                        None,
                    )
                    if (
                        lease_state.sandbox_id is None
                        or lease_state.sandbox_id != sandbox_id
                    ):
                        return
                self._leases.pop(project_id, None)
                self._lease_store.clear_sandbox(project_id)
                self._lease_store.update_state(project_id, state=SandboxState.EVICTED.value)
                self._close_project_agents(project_id)
            self.emit_project_event(kind, project_id, sandbox)

    def emit_project_event(
        self,
        kind: str,
        project_id: str,
        sandbox=None,
        reason: str | None = None,
    ) -> None:
        for session in self._store.list(project_id=project_id):
            if session.status != SessionStatus.ACTIVE:
                continue
            try:
                push_sandbox_event(
                    SandboxEvent(
                        kind=kind,
                        session_id=session.id,
                        sandbox_id=getattr(sandbox, "id", None),
                        reason=reason,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("sandbox SSE 事件发射失败(忽略): %s", exc)

    def shutdown(self) -> None:
        if self._pool is not None:
            self._pool.shutdown()

    def _close_project_agents(self, project_id: str) -> None:
        for session in self._store.list(project_id=project_id):
            _close_agent_quiet(session.id)

    def _lock_for(self, project_id: str) -> RLock:
        with self._project_locks_guard:
            lock = self._project_locks.get(project_id)
            if lock is None:
                lock = RLock()
                self._project_locks[project_id] = lock
            return lock
