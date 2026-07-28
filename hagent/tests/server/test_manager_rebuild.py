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
