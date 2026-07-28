from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hagent.sandbox import SandboxKind
from hagent.sandbox.ledger import CapacityExceeded
from hagent.sandbox.pool import PoolExhausted, SandboxLease
from hagent.server.leases import LeaseStore, SandboxState
from hagent.server.manager import SessionManager
from hagent.server.sessions import SessionStore


class FakeSandbox:
    def __init__(self, vm_id="hagent-projecta-a1b2c3"):
        self.id = f"smolvm-{vm_id}"
        self.workspace_dir = "/workspace"
        self.manifest = MagicMock(
            container_id=vm_id,
            image_tag="hagent-sandbox",
            runtime="firecracker",
        )
        self.persist_error: Exception | None = None

    def persist_to_snapshot(self) -> str:
        if self.persist_error is not None:
            raise self.persist_error
        return "snap-project-alpha-1"

    def upload_files(self, files):
        return [MagicMock(error=None) for _ in files]


class FakePool:
    node_id = "local"

    def __init__(self):
        self.sandbox = FakeSandbox()
        self.restored = FakeSandbox("hagent-projecta-rest01")
        self.restore_error: Exception | None = None
        self.restore_calls: list[tuple[str, str]] = []
        self.acquire_calls: list[str] = []
        self.released: list[SandboxLease] = []

    def acquire(self, *, project_id: str) -> SandboxLease:
        self.acquire_calls.append(project_id)
        return SandboxLease(self.sandbox, project_id)

    def acquire_restored(self, *, project_id: str, snapshot_id: str) -> SandboxLease:
        self.restore_calls.append((project_id, snapshot_id))
        if self.restore_error is not None:
            raise self.restore_error
        return SandboxLease(self.restored, project_id)

    def release(self, lease: SandboxLease) -> None:
        self.released.append(lease)

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


def test_persist_snapshot_is_recorded_on_project_lease(mgr_env):
    manager, _, leases, pool, session = mgr_env
    runtime_lease = SandboxLease(pool.sandbox, "project-alpha")
    manager._leases["project-alpha"] = runtime_lease

    assert manager.persist_sandbox(runtime_lease) is True

    saved = leases.get("project-alpha")
    assert saved.sandbox_state == SandboxState.SNAPSHOTTED.value
    assert saved.snapshot_id == "snap-project-alpha-1"
    assert saved.sandbox_id is None
    assert manager.get_sandbox(session.id) is None


def test_persist_failure_keeps_running_project_lease(mgr_env):
    manager, _, leases, pool, _ = mgr_env
    leases.update_state("project-alpha", state=SandboxState.PAUSED.value)
    runtime_lease = SandboxLease(pool.sandbox, "project-alpha")
    manager._leases["project-alpha"] = runtime_lease
    pool.sandbox.persist_error = RuntimeError("no space")

    assert manager.persist_sandbox(runtime_lease) is False
    assert leases.get("project-alpha").sandbox_state == SandboxState.PAUSED.value


def test_snapshotted_project_restores_for_any_session(mgr_env):
    manager, _, leases, pool, session = mgr_env
    second = manager.create_session(
        project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM
    )
    leases.update_snapshot("project-alpha", "snap-old")
    leases.update_state("project-alpha", state=SandboxState.SNAPSHOTTED.value)

    assert manager.ensure_sandbox(second.id) is pool.restored
    assert manager.get_sandbox(session.id) is pool.restored
    assert pool.restore_calls == [("project-alpha", "snap-old")]
    assert leases.get("project-alpha").snapshot_id is None


@pytest.mark.parametrize("error", [CapacityExceeded("full"), PoolExhausted("full")])
def test_restore_capacity_error_falls_back_to_fresh_project_vm(
    mgr_env, error, monkeypatch
):
    manager, _, leases, pool, session = mgr_env
    leases.update_snapshot("project-alpha", "snap-old")
    leases.update_state("project-alpha", state=SandboxState.SNAPSHOTTED.value)
    pool.restore_error = error
    deleted: list[str] = []
    monkeypatch.setattr("hagent.server.manager._delete_snapshot_quiet", deleted.append)

    assert manager.ensure_sandbox(session.id) is pool.sandbox

    saved = leases.get("project-alpha")
    assert deleted == ["snap-old"]
    assert pool.acquire_calls == ["project-alpha"]
    assert saved.snapshot_id is None
    assert saved.sandbox_state == SandboxState.RUNNING.value


def test_genuine_restore_failure_falls_back_to_fresh_project_vm(mgr_env, monkeypatch):
    manager, _, leases, pool, session = mgr_env
    leases.update_snapshot("project-alpha", "snap-bad")
    leases.update_state("project-alpha", state=SandboxState.SNAPSHOTTED.value)
    pool.restore_error = RuntimeError("corrupt")
    deleted: list[str] = []
    monkeypatch.setattr("hagent.server.manager._delete_snapshot_quiet", deleted.append)

    assert manager.ensure_sandbox(session.id) is pool.sandbox
    assert deleted == ["snap-bad"]
    assert pool.acquire_calls == ["project-alpha"]


def test_deleting_one_session_does_not_delete_project_snapshot(mgr_env, monkeypatch):
    manager, _, leases, _, session = mgr_env
    leases.update_snapshot("project-alpha", "snap-project")
    leases.update_state("project-alpha", state=SandboxState.SNAPSHOTTED.value)
    deleted: list[str] = []
    monkeypatch.setattr("hagent.server.manager._delete_snapshot_quiet", deleted.append)

    manager.delete_session(session.id)

    assert deleted == []
    assert leases.get("project-alpha").snapshot_id == "snap-project"


def test_releasing_project_cleans_snapshot_and_closes_lease(mgr_env, monkeypatch):
    manager, _, leases, pool, _ = mgr_env
    leases.update_snapshot("project-alpha", "snap-project")
    deleted: list[str] = []
    monkeypatch.setattr("hagent.server.manager._delete_snapshot_quiet", deleted.append)

    manager.release_project("project-alpha")
    manager.handle_sandbox_lifecycle("evicted", "project-alpha", pool.sandbox)

    assert deleted == ["snap-project"]
    assert leases.get("project-alpha").sandbox_state == SandboxState.CLOSED.value


def test_stale_pause_event_cannot_downgrade_replacement_lease(mgr_env):
    manager, _, leases, pool, _ = mgr_env
    manager._leases["project-alpha"] = SandboxLease(
        pool.restored,
        "project-alpha",
    )
    leases.update_state("project-alpha", state=SandboxState.RUNNING.value)

    manager.handle_sandbox_lifecycle("paused", "project-alpha", pool.sandbox)

    assert leases.get("project-alpha").sandbox_state == SandboxState.RUNNING.value
