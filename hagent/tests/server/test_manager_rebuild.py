from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hagent.sandbox import SandboxKind
from hagent.sandbox.pool import SandboxLease
from hagent.server.leases import LeaseStore, SandboxState
from hagent.server.manager import SessionManager
from hagent.server.sessions import SessionStore


class FakeSandbox:
    def __init__(self):
        self.id = "smolvm-project"
        self.workspace_dir = "/workspace"
        self.manifest = MagicMock(
            container_id="hagent-projecta-a1b2c3",
            image_tag="hagent-sandbox",
            runtime="firecracker",
            paused=False,
        )
        self.uploaded: list[tuple[str, bytes]] = []

    def upload_files(self, files):
        self.uploaded.extend(files)
        return [MagicMock(error=None) for _ in files]


class FakePool:
    node_id = "local"

    def __init__(self):
        self.sandbox = FakeSandbox()
        self.acquire_error: Exception | None = None
        self.evicted: list[str] = []
        self.drained = False

    def acquire(self, *, project_id: str) -> SandboxLease:
        if self.acquire_error is not None:
            raise self.acquire_error
        return SandboxLease(sandbox=self.sandbox, project_id=project_id)

    def evict(self, project_id: str) -> bool:
        self.evicted.append(project_id)
        return True

    def drain(self) -> None:
        self.drained = True

    def shutdown(self) -> None:
        pass


@pytest.fixture
def mgr_env(tmp_path):
    db = tmp_path / "hagent.db"
    sessions = SessionStore(db)
    leases = LeaseStore(db)
    pool = FakePool()
    manager = SessionManager(
        store=sessions,
        lease_store=leases,
        sandbox_pool=pool,
        workspace_root=tmp_path / "workspaces",
    )
    session = manager.create_session(
        project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM
    )
    return manager, sessions, leases, pool, session


def test_orphaned_project_rebuilds_and_reinstalls_canonical_files(mgr_env, tmp_path):
    manager, _, leases, pool, session = mgr_env
    workspace = tmp_path / "workspaces" / "projects" / "project-alpha" / "workspace"
    (workspace / "sub").mkdir(parents=True)
    (workspace / "a.txt").write_bytes(b"alpha")
    (workspace / "sub" / "b.bin").write_bytes(b"\x00\x01")
    leases.update_state("project-alpha", state=SandboxState.ORPHANED.value)

    sandbox = manager.ensure_sandbox(session.id)

    assert sandbox is pool.sandbox
    assert dict(pool.sandbox.uploaded)["/workspace/a.txt"] == b"alpha"
    assert dict(pool.sandbox.uploaded)["/workspace/sub/b.bin"] == b"\x00\x01"
    saved = leases.get("project-alpha")
    assert saved.sandbox_state == SandboxState.RUNNING.value
    assert saved.sandbox_id == "hagent-projecta-a1b2c3"


def test_live_project_lease_resumes_when_paused(mgr_env):
    manager, _, _, pool, session = mgr_env
    manager._leases["project-alpha"] = SandboxLease(
        sandbox=pool.sandbox, project_id="project-alpha"
    )
    pool.sandbox.manifest.paused = True
    pool.sandbox.resume = MagicMock()

    assert manager.ensure_sandbox(session.id) is pool.sandbox
    pool.sandbox.resume.assert_called_once()


def test_rebuild_failure_keeps_project_orphaned(mgr_env):
    manager, _, leases, pool, session = mgr_env
    leases.update_state("project-alpha", state=SandboxState.ORPHANED.value)
    pool.acquire_error = RuntimeError("capacity")

    with pytest.raises(RuntimeError, match="capacity"):
        manager.ensure_sandbox(session.id)

    assert leases.get("project-alpha").sandbox_state == SandboxState.ORPHANED.value


def test_drop_sandbox_evicts_by_project_and_invalidates_all_session_agents(
    mgr_env, monkeypatch
):
    import hagent.server.agents as agents_mod

    manager, _, _, pool, session = mgr_env
    second = manager.create_session(
        project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM
    )
    manager._leases["project-alpha"] = SandboxLease(
        sandbox=pool.sandbox, project_id="project-alpha"
    )
    monkeypatch.setitem(agents_mod._agents, session.id, MagicMock())
    monkeypatch.setitem(agents_mod._agents, second.id, MagicMock())

    manager.drop_sandbox("project-alpha")

    assert pool.evicted == ["project-alpha"]
    assert session.id not in agents_mod._agents
    assert second.id not in agents_mod._agents


def test_health_targets_and_drain_use_project_identity(mgr_env):
    manager, _, leases, pool, _ = mgr_env
    manager._leases["project-alpha"] = SandboxLease(
        sandbox=pool.sandbox, project_id="project-alpha"
    )

    assert manager.live_sandboxes() == [("project-alpha", pool.sandbox)]
    manager.drain()

    assert pool.drained is True
    assert leases.get("project-alpha").sandbox_state == SandboxState.PAUSED.value


# ---------------------------------------------------------------------------
# run-hold / 取消登记 / 通道内唤醒的 manager 侧
# ---------------------------------------------------------------------------


def _mgr_with_runs(tmp_path, pool):
    from hagent.server.runs import RunStore

    db = tmp_path / "hagent.db"
    sessions = SessionStore(db)
    leases = LeaseStore(db)
    runs = RunStore(db)
    manager = SessionManager(
        store=sessions,
        lease_store=leases,
        sandbox_pool=pool,
        workspace_root=tmp_path / "workspaces",
        run_store=runs,
        run_hold_max_seconds=3600,
    )
    session = manager.create_session(project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM)
    return manager, runs, session


def test_has_active_runs_respects_hold_cap(tmp_path):
    from hagent.server.runs import RunStatus

    manager, runs, session = _mgr_with_runs(tmp_path, FakePool())
    assert manager.has_active_runs("project-alpha") is False
    run = runs.create_chat_turn(
        project_id="project-alpha", session_id=session.id, base_revision=None, summary="t"
    )
    assert manager.has_active_runs("project-alpha") is True
    runs.finish(run.id, status=RunStatus.COMMITTED)
    assert manager.has_active_runs("project-alpha") is False
    # 超过 hold 上限的活跃 Run 不再阻止降档(防卡死 Run 霸占 VM)
    stale = runs.create_chat_turn(
        project_id="project-alpha", session_id=session.id, base_revision=None, summary="t"
    )
    manager._run_hold_max_seconds = 0
    assert manager.has_active_runs("project-alpha") is False
    assert runs.get(stale.id).status is RunStatus.PENDING, "状态本身不改,由流/启动对账终结"


def test_manager_wires_active_run_fn_into_pool(tmp_path):
    from hagent.sandbox.pool import SandboxPool

    pool = SandboxPool(sandbox_factory=lambda: FakeSandbox(), min_size=0, max_size=1)
    manager, runs, session = _mgr_with_runs(tmp_path, pool)
    assert pool._active_run_fn == manager.has_active_runs
    runs.create_chat_turn(
        project_id="project-alpha", session_id=session.id, base_revision=None, summary="t"
    )
    assert pool._has_active_run("project-alpha") is True
    pool.shutdown()


def test_drop_sandbox_interrupts_all_active_runs_and_registers_cancel(tmp_path):
    from hagent.server.runs import RunStatus

    pool = FakePool()
    manager, runs, session = _mgr_with_runs(tmp_path, pool)
    manager._leases["project-alpha"] = SandboxLease(sandbox=pool.sandbox, project_id="project-alpha")
    r1 = runs.create_chat_turn(
        project_id="project-alpha", session_id=session.id, base_revision=None, summary="a"
    )
    r2 = runs.create_chat_turn(
        project_id="project-alpha", session_id=session.id, base_revision=None, summary="b"
    )
    # 模拟健康抢救(before_drop)在动作过程中把 r1 终结:它的消息流同样要收尾
    def rescue():
        runs.finish(r1.id, status=RunStatus.INTERRUPTED, error="rescue")

    assert manager.drop_sandbox("project-alpha", before_drop=rescue) is True
    assert runs.get(r1.id).error == "rescue", "已终结的 Run 不被二次改写"
    assert runs.get(r2.id).status is RunStatus.INTERRUPTED
    assert manager.run_cancel_reason(r1.id)
    assert manager.run_cancel_reason(r2.id)
    manager.clear_run_cancel(r2.id)
    assert manager.run_cancel_reason(r2.id) is None


def test_checkpoint_project_error_contains_reason(tmp_path):
    from hagent.server.runs import RunStatus

    pool = FakePool()
    manager, runs, session = _mgr_with_runs(tmp_path, pool)
    calls: list[tuple[str, bool, str | None]] = []

    class FakeCheckpointer:
        def checkpoint(self, run_id, *, sandbox=None, interrupted=False, error=None):
            calls.append((run_id, interrupted, error))
            runs.finish(run_id, status=RunStatus.INTERRUPTED, error=error)

    manager._workspace_checkpointer = FakeCheckpointer()
    run = runs.create_chat_turn(
        project_id="project-alpha", session_id=session.id, base_revision=None, summary="a"
    )
    manager.checkpoint_project("project-alpha", pool.sandbox, reason="drain")
    assert calls == [(run.id, True, "sandbox 生命周期动作(drain)触发兜底 checkpoint")]


def test_live_project_lease_resumes_via_ensure_running_and_records_state(mgr_env):
    """新 provider:唤醒经 sandbox.ensure_running → 生命周期回调 → 租约 RUNNING + SSE。"""
    from hagent.server import sse as sse_mod

    manager, _, leases, pool, session = mgr_env
    manager._leases["project-alpha"] = SandboxLease(sandbox=pool.sandbox, project_id="project-alpha")
    leases.update_state("project-alpha", state=SandboxState.PAUSED.value)
    pool.sandbox.manifest.paused = True

    def ensure_running():
        pool.sandbox.manifest.paused = False
        # 真实 provider 由 pool._bind_project 绑定的回调把 "resumed" 送回 manager
        manager.handle_sandbox_lifecycle("resumed", "project-alpha", pool.sandbox)

    pool.sandbox.ensure_running = ensure_running
    pool.sandbox.resume = MagicMock()

    assert manager.ensure_sandbox(session.id) is pool.sandbox
    pool.sandbox.resume.assert_not_called()
    assert leases.get("project-alpha").sandbox_state == SandboxState.RUNNING.value
    events = sse_mod.drain_sandbox_events(session.id)
    assert [e.kind for e in events] == ["resumed"]
