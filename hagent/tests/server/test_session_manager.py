from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import MagicMock

from hagent.sandbox import SandboxKind
from hagent.sandbox.pool import SandboxPool
from hagent.server.leases import LeaseStore
from hagent.server.manager import SessionManager
from hagent.server.sessions import SessionStatus, SessionStore


def _manager(tmp_path, pool=None):
    db = tmp_path / "hagent.db"
    store = SessionStore(db)
    leases = LeaseStore(db)
    manager = SessionManager(
        store=store,
        lease_store=leases,
        sandbox_pool=pool,
        workspace_root=tmp_path / "workspaces",
    )
    return manager, store, leases


def _runtime_lease(project_id: str):
    lease = MagicMock()
    lease.project_id = project_id
    lease.sandbox.id = f"smolvm-{project_id}"
    lease.sandbox.manifest.container_id = f"hagent-{project_id[:8]}-a1b2c3"
    return lease


def test_two_sessions_in_one_project_lazily_share_one_sandbox(tmp_path):
    runtime_lease = _runtime_lease("project-alpha")
    pool = MagicMock(node_id="local")
    pool.acquire.return_value = runtime_lease
    manager, _, _ = _manager(tmp_path, pool)

    first = manager.create_session(
        project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM
    )
    second = manager.create_session(
        project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM
    )
    pool.acquire.assert_not_called()

    assert manager.ensure_sandbox(first.id) is runtime_lease.sandbox
    assert manager.ensure_sandbox(second.id) is runtime_lease.sandbox
    pool.acquire.assert_called_once_with(project_id="project-alpha")


def test_concurrent_first_runs_in_one_project_single_flight_vm_acquire(tmp_path):
    runtime_lease = _runtime_lease("project-alpha")
    pool = MagicMock(node_id="local")

    def acquire(*, project_id: str):
        time.sleep(0.05)
        return runtime_lease

    pool.acquire.side_effect = acquire
    manager, _, _ = _manager(tmp_path, pool)
    first = manager.create_session(
        project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM
    )
    second = manager.create_session(
        project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        sandboxes = list(
            executor.map(manager.ensure_sandbox, [first.id, second.id])
        )

    assert sandboxes == [runtime_lease.sandbox, runtime_lease.sandbox]
    pool.acquire.assert_called_once_with(project_id="project-alpha")


def test_persist_and_ensure_concurrency_keeps_replacement_runtime_lease(tmp_path):
    old_sandbox = _runtime_lease("project-alpha").sandbox
    old_sandbox.persist_to_snapshot.return_value = "snap-project-alpha"
    replacement = _runtime_lease("project-alpha").sandbox
    replacement.manifest.container_id = "hagent-projecta-new001"
    pool = SandboxPool(
        sandbox_factory=lambda: old_sandbox,
        min_size=0,
        max_size=2,
        restore_factory=lambda _snapshot_id, _project_id: replacement,
    )
    manager, _, _ = _manager(tmp_path, pool)
    first = manager.create_session(
        project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM
    )
    second = manager.create_session(
        project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM
    )
    manager.ensure_sandbox(first.id)
    runtime_lease = manager._leases["project-alpha"]
    callback_done = Event()
    allow_pool_cleanup = Event()

    def persist_with_window(lease):
        persisted = manager.persist_sandbox(lease)
        callback_done.set()
        assert allow_pool_cleanup.wait(timeout=2)
        return persisted

    pool.set_persist_fn(persist_with_window)

    with ThreadPoolExecutor(max_workers=2) as executor:
        future = executor.submit(pool._try_persist, runtime_lease)
        assert callback_done.wait(timeout=2)
        ensure_future = executor.submit(manager.ensure_sandbox, second.id)
        time.sleep(0.05)
        assert ensure_future.done() is False
        allow_pool_cleanup.set()
        assert future.result(timeout=2) is True
        assert ensure_future.result(timeout=2) is replacement

    assert manager.get_sandbox(first.id) is replacement
    assert pool.stats()["leased"] == 1
    assert pool.evict("project-alpha") is True
    old_sandbox.close.assert_called_once()
    replacement.close.assert_called_once()


def test_gc_evict_holds_project_guard_until_manager_drops_old_sandbox(tmp_path):
    close_started = Event()
    allow_close = Event()
    old_sandbox = _runtime_lease("project-alpha").sandbox
    old_sandbox.manifest.paused = False
    replacement = _runtime_lease("project-alpha").sandbox
    replacement.manifest.paused = False

    def blocking_close():
        close_started.set()
        assert allow_close.wait(timeout=2)

    old_sandbox.close.side_effect = blocking_close
    sandboxes = iter((old_sandbox, replacement))
    pool = SandboxPool(
        sandbox_factory=lambda: next(sandboxes),
        min_size=0,
        max_size=1,
    )
    manager, _, leases = _manager(tmp_path, pool)
    session = manager.create_session(
        project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM
    )
    assert manager.ensure_sandbox(session.id) is old_sandbox

    with ThreadPoolExecutor(max_workers=2) as executor:
        evict_future = executor.submit(pool.evict, "project-alpha")
        assert close_started.wait(timeout=2)
        ensure_future = executor.submit(manager.ensure_sandbox, session.id)
        time.sleep(0.05)
        assert ensure_future.done() is False
        allow_close.set()
        assert evict_future.result(timeout=2) is True
        assert ensure_future.result(timeout=2) is replacement

    assert old_sandbox.close.call_count == 1
    assert leases.get("project-alpha").sandbox_state == "running"
    manager.shutdown()


def test_different_projects_get_different_runtime_leases(tmp_path):
    pool = MagicMock(node_id="local")
    pool.acquire.side_effect = lambda *, project_id: _runtime_lease(project_id)
    manager, _, _ = _manager(tmp_path, pool)
    first = manager.create_session(project_id="project-a", sandbox_kind=SandboxKind.SMOLVM)
    second = manager.create_session(project_id="project-b", sandbox_kind=SandboxKind.SMOLVM)

    assert manager.ensure_sandbox(first.id) is not manager.ensure_sandbox(second.id)
    assert pool.acquire.call_count == 2


def test_delete_session_keeps_shared_project_lease(tmp_path):
    runtime_lease = _runtime_lease("project-alpha")
    pool = MagicMock(node_id="local")
    pool.acquire.return_value = runtime_lease
    manager, store, _ = _manager(tmp_path, pool)
    first = manager.create_session(project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM)
    second = manager.create_session(project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM)
    manager.ensure_sandbox(first.id)

    manager.delete_session(first.id)

    assert store.get(first.id).status == SessionStatus.ENDED
    assert manager.get_sandbox(second.id) is runtime_lease.sandbox
    pool.release.assert_not_called()


def test_host_project_skips_pool_and_uses_project_workspace(tmp_path):
    pool = MagicMock(node_id="local")
    manager, _, _ = _manager(tmp_path, pool)
    session = manager.create_session(project_id="project-host", sandbox_kind=SandboxKind.NONE)

    assert manager.ensure_sandbox(session.id) is None
    assert manager.workspace_dir(session.id).endswith(
        "projects/project-host/workspace"
    )
    pool.acquire.assert_not_called()


def test_shutdown_passes_through_to_pool(tmp_path):
    pool = MagicMock()
    manager, _, _ = _manager(tmp_path, pool)
    manager.shutdown()
    pool.shutdown.assert_called_once()
