"""Task B2 — smolvm 健康巡检:health_check 探针 + 杀重建处置(清残留/标 orphaned/记事件)。"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock

import pytest
from smolvm import SmolVMError
from smolvm.types import CommandResult

from hagent.sandbox import SandboxKind
from hagent.sandbox.manifest import SandboxManifest
from hagent.sandbox.smolvm.audit import SandboxAuditor, SandboxEventStore
from hagent.sandbox.smolvm.health import SmolVMHealthChecker
from hagent.sandbox.smolvm.sandbox import HagentSmolVMSandbox
from hagent.server.leases import LeaseStore, SandboxState
from hagent.server.project_workspace import ProjectWorkspace
from hagent.server.runs import RunStatus, RunStore
from tests.sandbox.test_smolvm_sandbox_unit import FakeLifecycle, FakeVM, make_sandbox

# ---------------------------------------------------------------------------
# HagentSmolVMSandbox.health_check:直连 vm.run("true"),不产生审计噪音
# ---------------------------------------------------------------------------


def test_health_check_true_when_probe_ok():
    sandbox, vm = make_sandbox()
    vm.run_result = CommandResult(exit_code=0, stdout="", stderr="")
    assert sandbox.health_check() is True
    probe = vm.run_calls[0]
    assert probe["command"] == "true"
    assert probe["timeout"] == 5


def test_health_check_false_on_nonzero_exit():
    sandbox, vm = make_sandbox()
    vm.run_result = CommandResult(exit_code=1, stdout="", stderr="")
    assert sandbox.health_check() is False


def test_health_check_false_on_channel_error():
    sandbox, vm = make_sandbox()
    vm.run_error = SmolVMError("vsock gone")
    assert sandbox.health_check() is False


def test_health_check_false_after_close():
    sandbox, _vm = make_sandbox()
    sandbox.close()
    assert sandbox.health_check() is False


def test_health_check_writes_no_audit(tmp_path):
    from hagent.sandbox.smolvm.audit import CommandAuditLog

    vm = FakeVM()
    lifecycle = FakeLifecycle(vm)
    manifest = SandboxManifest(
        sandbox_id=lifecycle.vm_id,
        kind="smolvm",
        image_tag="t",
        runtime="firecracker",
        container_id=lifecycle.vm_id,
    )
    sandbox = HagentSmolVMSandbox(
        lifecycle=lifecycle,
        manifest=manifest,
        auditor=SandboxAuditor(command_log=CommandAuditLog(root=tmp_path)),
    )
    sandbox.bind_project("project-1")
    sandbox.health_check()
    assert not list(tmp_path.glob("*.jsonl")), "健康探针不得刷审计 JSONL"


# ---------------------------------------------------------------------------
# SmolVMHealthChecker
# ---------------------------------------------------------------------------


class RescuableSandbox:
    """execute(find)/download_files 可控的处置对象替身。"""

    def __init__(self):
        self.workspace_dir = "/workspace"
        self.manifest = SandboxManifest(
            sandbox_id="hagent-s-1",
            kind="smolvm",
            image_tag="t",
            runtime="firecracker",
            container_id="hagent-s-1",
        )
        self.guest_files: dict[str, bytes] = {}
        self.execute_error: Exception | None = None
        self.health = False

    def health_check(self) -> bool:
        return self.health

    def execute(self, command: str, *, timeout: int | None = None):
        class R:
            pass

        if self.execute_error is not None:
            raise self.execute_error
        r = R()
        if command.startswith("find "):
            r.output = "".join(f"{p}\n" for p in sorted(self.guest_files))
            r.exit_code = 0
        else:
            r.output = ""
            r.exit_code = 0
        return r

    def download_files(self, paths):
        class D:
            def __init__(self, path, content, error):
                self.path = path
                self.content = content
                self.error = error

        return [
            D(p, self.guest_files.get(p), None if p in self.guest_files else "file_not_found")
            for p in paths
        ]


def _make_checker(tmp_path, sandbox, *, project_workspace=None, run_store=None):
    store = LeaseStore(tmp_path / "sessions.db")
    project_id = "project-alpha"
    store.ensure(project_id, sandbox_kind="smolvm")
    store.update_state(project_id, state=SandboxState.RUNNING.value)
    events = SandboxEventStore(tmp_path / "sessions.db")
    dropped: list[str] = []

    def drop(candidate_project_id, _expected_sandbox, before_drop, after_drop):
        before_drop()
        dropped.append(candidate_project_id)
        after_drop()
        return True

    checker = SmolVMHealthChecker(
        targets_fn=lambda: [(project_id, sandbox)],
        drop_fn=drop,
        leases=store,
        workspace_root=tmp_path / "wsp",
        auditor=SandboxAuditor(event_store=events),
        project_workspace=project_workspace,
        run_store=run_store,
    )
    return checker, project_id, store, events, dropped


def test_checker_targets_and_check_delegate(tmp_path):
    sandbox = RescuableSandbox()
    checker, project_id, *_ = _make_checker(tmp_path, sandbox)
    assert checker.targets() == [(project_id, sandbox)]
    assert checker.check(sandbox) is False
    sandbox.health = True
    assert checker.check(sandbox) is True


def test_checker_treats_paused_sandbox_as_healthy(tmp_path):
    """缺陷修复:paused VM 是刻意冻结,非病态。

    SDK `vm.run()` 对非 RUNNING 状态必抛(facade 前置断言),探针必失败;
    若不豁免,GC 在 idle_pause 冻结的 VM 会被健康巡检在 ~45s 内误判杀重建,
    永远走不到 idle_evict 的快照持久化档。
    """
    sandbox = RescuableSandbox()
    sandbox.health = False  # 探针会失败(冻结 VM)
    sandbox.manifest.paused = True
    checker, *_ = _make_checker(tmp_path, sandbox)
    assert checker.check(sandbox) is True, "paused 沙箱必须视为健康,不得探针"


def test_checker_probes_again_after_resume(tmp_path):
    # 唤醒后 manifest.paused 复位 → 恢复正常探活(死 VM 仍会被抓)
    sandbox = RescuableSandbox()
    sandbox.manifest.paused = False
    sandbox.health = False
    checker, *_ = _make_checker(tmp_path, sandbox)
    assert checker.check(sandbox) is False


def test_checker_treats_missing_health_check_as_healthy(tmp_path):
    class NoProbe:
        pass

    sandbox = RescuableSandbox()
    checker, *_ = _make_checker(tmp_path, sandbox)
    assert checker.check(NoProbe()) is True


def test_checker_check_exception_is_unhealthy(tmp_path):
    class Exploding:
        def health_check(self):
            raise RuntimeError("boom")

    sandbox = RescuableSandbox()
    checker, *_ = _make_checker(tmp_path, sandbox)
    assert checker.check(Exploding()) is False


def test_on_unhealthy_rescues_drops_orphans_and_records(tmp_path):
    sandbox = RescuableSandbox()
    sandbox.guest_files = {
        "/workspace/out.md": b"# result",
        "/workspace/sub/data.json": b"{}",
    }
    checker, project_id, store, events, dropped = _make_checker(tmp_path, sandbox)
    checker.on_unhealthy(project_id, sandbox)
    # 1）把产物抢救到宿主侧的项目标准工作区。
    workspace = Path(tmp_path / "wsp" / "projects" / project_id / "workspace")
    assert (workspace / "out.md").read_bytes() == b"# result"
    assert (workspace / "sub/data.json").read_bytes() == b"{}"
    # 2) 清残留
    assert dropped == [project_id]
    # 3）把项目租约标记为 orphaned。
    assert store.get(project_id).sandbox_state == SandboxState.ORPHANED.value
    # 4) 事件 health_fail
    rows = events.list(project_id=project_id, event="health_fail")
    assert len(rows) == 1
    assert rows[0].vm_id == "hagent-s-1"


def test_on_unhealthy_commits_rescued_files_to_canonical_head(tmp_path):
    sandbox = RescuableSandbox()
    sandbox.guest_files = {"/workspace/deliverables/抢救稿.md": b"saved"}
    workspace = ProjectWorkspace(tmp_path / "wsp")
    workspace.initialize("project-alpha")
    checker, project_id, *_ = _make_checker(
        tmp_path,
        sandbox,
        project_workspace=workspace,
    )

    checker.on_unhealthy(project_id, sandbox)

    revision = workspace.history(project_id)[0]
    assert revision.kind == "lifecycle_rescue"
    assert revision.interrupted is True
    assert workspace.read_file(project_id, "deliverables/抢救稿.md") == b"saved"


def test_on_unhealthy_links_rescue_commit_to_active_chat_turn(tmp_path):
    sandbox = RescuableSandbox()
    sandbox.guest_files = {"/workspace/deliverables/抢救稿.md": b"saved"}
    workspace = ProjectWorkspace(tmp_path / "wsp")
    workspace.initialize("project-alpha")
    runs = RunStore(tmp_path / "sessions.db")
    run = runs.create_chat_turn(
        project_id="project-alpha",
        session_id="session-one",
        base_revision=workspace.head("project-alpha"),
        summary="chat_turn: 生成抢救稿",
    )
    runs.mark_running(run.id)
    checker, project_id, *_ = _make_checker(
        tmp_path,
        sandbox,
        project_workspace=workspace,
        run_store=runs,
    )

    checker.on_unhealthy(project_id, sandbox)

    revision = workspace.history(project_id)[0]
    saved = runs.get(run.id)
    assert revision.run_id == run.id
    assert revision.kind == "chat_turn"
    assert saved.status is RunStatus.INTERRUPTED
    assert saved.commit_sha == revision.sha


def test_on_unhealthy_rescue_failure_does_not_block(tmp_path):
    sandbox = RescuableSandbox()
    sandbox.execute_error = SmolVMError("vsock dead")
    checker, project_id, store, events, dropped = _make_checker(tmp_path, sandbox)
    checker.on_unhealthy(project_id, sandbox)
    assert dropped == [project_id], "抢救失败不得阻断清残留"
    assert store.get(project_id).sandbox_state == SandboxState.ORPHANED.value
    assert len(events.list(event="health_fail")) == 1


def test_rescue_skips_failed_downloads(tmp_path):
    sandbox = RescuableSandbox()
    sandbox.guest_files = {"/workspace/keep.txt": b"ok"}

    original = sandbox.execute

    def execute_with_ghost(command, *, timeout=None):
        r = original(command, timeout=timeout)
        if command.startswith("find "):
            r.output = "/workspace/keep.txt\n/workspace/ghost.txt\n"
        return r

    sandbox.execute = execute_with_ghost
    checker, project_id, *_ = _make_checker(tmp_path, sandbox)
    checker.on_unhealthy(project_id, sandbox)
    workspace = Path(tmp_path / "wsp" / "projects" / project_id / "workspace")
    assert (workspace / "keep.txt").exists()
    assert not (workspace / "ghost.txt").exists()


def test_stale_health_target_cannot_drop_replacement_sandbox(tmp_path):
    from hagent.sandbox.pool import SandboxLease
    from hagent.sandbox.supervisor import SandboxSupervisor
    from hagent.server.manager import SessionManager
    from hagent.server.sessions import SessionStore

    class Pool:
        node_id = "local"

        def __init__(self):
            self.evicted: list[str] = []

        def evict(self, project_id):
            self.evicted.append(project_id)
            return True

    class Reconciler:
        def plan(self):
            return []

        def apply(self, _action):
            return None

        def reap_errors(self):
            return None

    project_id = "project-alpha"
    old_sandbox = RescuableSandbox()
    replacement = RescuableSandbox()
    replacement.manifest.container_id = "hagent-replacement-1"
    check_started = Event()
    allow_check = Event()

    def blocking_health_check():
        check_started.set()
        assert allow_check.wait(timeout=2)
        return False

    old_sandbox.health_check = blocking_health_check
    pool = Pool()
    db_path = tmp_path / "health-race.db"
    leases = LeaseStore(db_path)
    manager = SessionManager(
        store=SessionStore(db_path),
        lease_store=leases,
        sandbox_pool=pool,
        workspace_root=tmp_path / "workspaces",
    )
    manager.create_session(project_id=project_id, sandbox_kind=SandboxKind.SMOLVM)
    leases.update_state(project_id, state=SandboxState.RUNNING.value)
    leases.update_metadata(project_id, sandbox_id=old_sandbox.manifest.container_id)
    manager._leases[project_id] = SandboxLease(old_sandbox, project_id)
    events = SandboxEventStore(db_path)
    checker = SmolVMHealthChecker(
        targets_fn=manager.live_sandboxes,
        drop_fn=manager.drop_sandbox,
        leases=leases,
        workspace_root=manager.workspace_root,
        auditor=SandboxAuditor(event_store=events),
    )
    supervisor = SandboxSupervisor(
        reconciler=Reconciler(),
        health_checker=checker,
    )
    supervisor._health_failures[project_id] = 2

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(supervisor._health_once)
        assert check_started.wait(timeout=2)
        with manager._lock_for(project_id):
            manager._leases[project_id] = SandboxLease(replacement, project_id)
            leases.update_metadata(
                project_id,
                sandbox_id=replacement.manifest.container_id,
            )
        allow_check.set()
        future.result(timeout=2)

    assert manager.get_project_sandbox(project_id) is replacement
    assert pool.evicted == []
    assert leases.get(project_id).sandbox_state == SandboxState.RUNNING.value
    assert events.list(project_id=project_id, event="health_fail") == []


@pytest.mark.parametrize(
    ("concurrent_action", "expected_state"),
    [
        ("ensure", SandboxState.RUNNING.value),
        ("release", SandboxState.CLOSED.value),
    ],
)
def test_health_finalize_holds_project_guard_until_audit_before_next_action(
    tmp_path,
    concurrent_action,
    expected_state,
):
    from hagent.sandbox.pool import SandboxPool
    from hagent.server.manager import SessionManager
    from hagent.server.sessions import SessionStore

    old_sandbox = RescuableSandbox()
    replacement = RescuableSandbox()
    replacement.manifest.container_id = "hagent-replacement-2"
    old_sandbox.close = MagicMock()
    replacement.close = MagicMock()
    sandboxes = iter((old_sandbox, replacement))
    pool = SandboxPool(
        sandbox_factory=lambda: next(sandboxes),
        min_size=0,
        max_size=1,
    )
    db_path = tmp_path / "health-finalize.db"
    leases = LeaseStore(db_path)
    manager = SessionManager(
        store=SessionStore(db_path),
        lease_store=leases,
        sandbox_pool=pool,
        workspace_root=tmp_path / "workspaces",
    )
    session = manager.create_session(
        project_id="project-alpha",
        sandbox_kind=SandboxKind.SMOLVM,
    )
    assert manager.ensure_sandbox(session.id) is old_sandbox
    audit_started = Event()
    allow_audit = Event()
    auditor = MagicMock()

    def blocking_audit(**_kwargs):
        audit_started.set()
        assert allow_audit.wait(timeout=2)

    auditor.record_event.side_effect = blocking_audit
    checker = SmolVMHealthChecker(
        targets_fn=manager.live_sandboxes,
        drop_fn=manager.drop_sandbox,
        leases=leases,
        workspace_root=manager.workspace_root,
        auditor=auditor,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        health_future = executor.submit(
            checker.on_unhealthy,
            "project-alpha",
            old_sandbox,
        )
        assert audit_started.wait(timeout=2)
        if concurrent_action == "ensure":
            action_future = executor.submit(manager.ensure_sandbox, session.id)
        else:
            action_future = executor.submit(manager.release_project, "project-alpha")
        time.sleep(0.05)
        assert action_future.done() is False
        allow_audit.set()
        health_future.result(timeout=2)
        result = action_future.result(timeout=2)

    if concurrent_action == "ensure":
        assert result is replacement
    assert leases.get("project-alpha").sandbox_state == expected_state
    auditor.record_event.assert_called_once()
    manager.shutdown()
