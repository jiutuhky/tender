from __future__ import annotations

from unittest.mock import MagicMock

from hagent.sandbox import SandboxKind
from hagent.server.leases import LeaseStore, SandboxState
from hagent.server.manager import SessionManager
from hagent.server.sessions import SessionStore


def _manager(tmp_path, pool=None):
    db = tmp_path / "hagent.db"
    sessions = SessionStore(db)
    leases = LeaseStore(db)
    return (
        SessionManager(
            store=sessions,
            lease_store=leases,
            sandbox_pool=pool,
            workspace_root=tmp_path / "workspaces",
        ),
        leases,
    )


def test_create_session_creates_idle_project_lease_without_vm(tmp_path):
    pool = MagicMock()
    pool.node_id = "local"
    manager, leases = _manager(tmp_path, pool)

    session = manager.create_session(
        project_id="project-1", sandbox_kind=SandboxKind.SMOLVM
    )

    lease = leases.get(session.project_id)
    assert lease.sandbox_kind == "smolvm"
    assert lease.sandbox_state is None
    assert lease.last_activity_at is not None
    pool.acquire.assert_not_called()


def test_first_message_advances_lease_to_running(tmp_path):
    sandbox = MagicMock()
    sandbox.id = "smolvm-p1"
    sandbox.manifest.container_id = "hagent-project1-a1b2c3"
    runtime_lease = MagicMock(sandbox=sandbox, project_id="project-1")
    pool = MagicMock()
    pool.node_id = "local"
    pool.acquire.return_value = runtime_lease
    manager, leases = _manager(tmp_path, pool)
    session = manager.create_session(
        project_id="project-1", sandbox_kind=SandboxKind.SMOLVM
    )

    manager.ensure_sandbox(session.id)

    lease = leases.get("project-1")
    assert lease.sandbox_state == SandboxState.RUNNING.value
    assert lease.sandbox_id == "hagent-project1-a1b2c3"


def test_message_activity_updates_project_lease(tmp_path):
    manager, leases = _manager(tmp_path)
    session = manager.create_session(project_id="project-1")
    before = leases.get("project-1").last_activity_at

    manager.touch_activity(session.id)

    assert leases.get("project-1").last_activity_at >= before
