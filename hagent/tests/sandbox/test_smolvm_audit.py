"""Task B1 — 审计:命令 JSONL + sandbox_events 事件表 + 埋点(spec §4.5 / D11)。

审计永远 best-effort:任何审计失败只告警,不影响 execute/upload/download 主链路。
"""

from __future__ import annotations

import json

import pytest
from smolvm import OperationTimeoutError
from smolvm.types import CommandResult

from hagent.sandbox.manifest import SandboxManifest
from hagent.sandbox.smolvm.audit import (
    CommandAuditLog,
    SandboxAuditor,
    SandboxEventStore,
)
from hagent.sandbox.smolvm.sandbox import HagentSmolVMSandbox
from tests.sandbox.test_smolvm_sandbox_unit import FakeLifecycle, FakeVM

VM_ID = "hagent-abcd1234-a1b2c3"


def _read_jsonl(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


# ---------------------------------------------------------------------------
# CommandAuditLog:JSONL 逐字段快照 + append-only + 按 pid 分文件
# ---------------------------------------------------------------------------


def test_jsonl_exec_record_fields_snapshot(tmp_path):
    log = CommandAuditLog(root=tmp_path)
    log.record(
        project_id="sid1234",
        vm_id=VM_ID,
        action="exec",
        command="echo hi",
        exit_code=0,
        duration_ms=12,
        bytes_out=3,
    )
    records = _read_jsonl(tmp_path / "audit-sid1234.jsonl")
    assert len(records) == 1
    record = records[0]
    assert set(record) == {
        "ts",
        "project_id",
        "vm_id",
        "action",
        "command",
        "exit_code",
        "duration_ms",
        "bytes_out",
    }
    assert record["project_id"] == "sid1234"
    assert record["vm_id"] == VM_ID
    assert record["action"] == "exec"
    assert record["command"] == "echo hi"
    assert record["exit_code"] == 0
    assert record["duration_ms"] == 12
    assert record["bytes_out"] == 3
    assert isinstance(record["ts"], float)


def test_jsonl_file_record_uses_path_and_error(tmp_path):
    log = CommandAuditLog(root=tmp_path)
    log.record(
        project_id="sid1234",
        vm_id=VM_ID,
        action="upload",
        path="/workspace/a.txt",
        duration_ms=5,
        bytes_out=128,
        error="upload_failed: boom",
    )
    (record,) = _read_jsonl(tmp_path / "audit-sid1234.jsonl")
    assert record["action"] == "upload"
    assert record["path"] == "/workspace/a.txt"
    assert record["error"] == "upload_failed: boom"
    assert "command" not in record
    assert "exit_code" not in record


def test_jsonl_append_only_and_split_by_sid(tmp_path):
    log = CommandAuditLog(root=tmp_path)
    for _ in range(2):
        log.record(project_id="s1", vm_id=VM_ID, action="exec", command="a", exit_code=0)
    log.record(project_id="s2", vm_id=VM_ID, action="exec", command="b", exit_code=1)
    assert len(_read_jsonl(tmp_path / "audit-s1.jsonl")) == 2
    assert len(_read_jsonl(tmp_path / "audit-s2.jsonl")) == 1


def test_jsonl_falls_back_to_vm_id_when_session_unbound(tmp_path):
    log = CommandAuditLog(root=tmp_path)
    log.record(project_id=None, vm_id=VM_ID, action="exec", command="a", exit_code=0)
    (record,) = _read_jsonl(tmp_path / f"audit-{VM_ID}.jsonl")
    assert record["project_id"] is None


def test_audit_dir_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_SANDBOX_AUDIT_DIR", str(tmp_path / "custom"))
    log = CommandAuditLog()
    log.record(project_id="s1", vm_id=VM_ID, action="exec", command="a", exit_code=0)
    assert (tmp_path / "custom" / "audit-s1.jsonl").exists()


# ---------------------------------------------------------------------------
# SandboxEventStore:事件表写入 + migration 幂等
# ---------------------------------------------------------------------------


def test_event_store_record_and_list(tmp_path):
    store = SandboxEventStore(tmp_path / "events.db")
    store.record(event="created", project_id="s1", vm_id=VM_ID, detail={"attempt": 1})
    store.record(event="evicted", project_id="s1", vm_id=VM_ID)
    rows = store.list(project_id="s1")
    assert [r.event for r in rows] == ["created", "evicted"]
    assert rows[0].vm_id == VM_ID
    assert rows[0].detail == {"attempt": 1}
    assert rows[1].detail is None
    assert rows[0].ts > 0


def test_event_store_filter_by_event(tmp_path):
    store = SandboxEventStore(tmp_path / "events.db")
    store.record(event="created", project_id="s1", vm_id=VM_ID)
    store.record(event="created", project_id="s2", vm_id="hagent-x-y")
    store.record(event="orphaned", project_id="s1")
    assert len(store.list(event="created")) == 2
    assert len(store.list(project_id="s1", event="orphaned")) == 1


def test_event_store_limit_returns_recent_desc(tmp_path):
    # ops 事件尾:limit 模式取最近 N 条、倒序(最新在前);不传 limit 维持正序全量
    store = SandboxEventStore(tmp_path / "events.db")
    for ev in ("created", "paused", "resumed", "evicted"):
        store.record(event=ev, project_id="s1", vm_id=VM_ID)
    recent = store.list(limit=2)
    assert [r.event for r in recent] == ["evicted", "resumed"]
    assert [r.event for r in store.list()] == ["created", "paused", "resumed", "evicted"]


def test_event_store_rejects_unknown_event(tmp_path):
    store = SandboxEventStore(tmp_path / "events.db")
    with pytest.raises(ValueError):
        store.record(event="not-a-real-event", project_id="s1")


def test_event_store_migration_idempotent(tmp_path):
    db = tmp_path / "events.db"
    SandboxEventStore(db).record(event="created", project_id="s1")
    # 二次构造(重启场景)不得破坏既有数据
    store = SandboxEventStore(db)
    assert len(store.list()) == 1


def test_event_store_shares_sessions_db(tmp_path):
    """事件表落 hagent SQLite(与 sessions 同库分表,spec §4.5)。"""
    from hagent.server.sessions import SessionStore

    db = tmp_path / "sessions.db"
    SessionStore(db)
    store = SandboxEventStore(db)
    store.record(event="created", project_id="s1")
    assert len(store.list()) == 1


# ---------------------------------------------------------------------------
# SandboxAuditor:best-effort — 审计失败不影响主链路
# ---------------------------------------------------------------------------


def test_auditor_swallows_command_log_failure(tmp_path):
    blocker = tmp_path / "occupied"
    blocker.write_text("not a dir")
    auditor = SandboxAuditor(command_log=CommandAuditLog(root=blocker))
    # root 是文件不是目录 → 底层写入必然失败;auditor 不得上抛
    auditor.record_command(project_id="s1", vm_id=VM_ID, action="exec", command="a")


def test_auditor_swallows_event_store_failure(tmp_path):
    store = SandboxEventStore(tmp_path / "events.db")
    auditor = SandboxAuditor(event_store=store)
    auditor.record_event(event="not-a-real-event", project_id="s1")  # ValueError 被吞


def test_auditor_noop_without_sinks():
    auditor = SandboxAuditor()
    auditor.record_command(project_id="s1", vm_id=VM_ID, action="exec", command="a")
    auditor.record_event(event="created", project_id="s1")


# ---------------------------------------------------------------------------
# HagentSmolVMSandbox 埋点:execute / upload / download / close
# ---------------------------------------------------------------------------


def make_audited_sandbox(tmp_path, vm: FakeVM | None = None):
    vm = vm or FakeVM()
    lifecycle = FakeLifecycle(vm)
    manifest = SandboxManifest(
        sandbox_id=lifecycle.vm_id,
        kind="smolvm",
        image_tag="hagent-sandbox",
        runtime="firecracker",
        container_id=lifecycle.vm_id,
    )
    store = SandboxEventStore(tmp_path / "events.db")
    auditor = SandboxAuditor(command_log=CommandAuditLog(root=tmp_path), event_store=store)
    sandbox = HagentSmolVMSandbox(lifecycle=lifecycle, manifest=manifest, auditor=auditor)
    sandbox.bind_project("sid1234")
    return sandbox, vm, store


def test_execute_writes_exec_audit_record(tmp_path):
    sandbox, vm, _ = make_audited_sandbox(tmp_path)
    vm.run_result = CommandResult(exit_code=0, stdout="hi\n", stderr="")
    sandbox.execute("echo hi")
    (record,) = _read_jsonl(tmp_path / "audit-sid1234.jsonl")
    assert record["action"] == "exec"
    assert record["command"] == "echo hi"  # 原始命令,非 bash -c 包装
    assert record["exit_code"] == 0
    assert record["duration_ms"] >= 0
    assert record["bytes_out"] == len("hi\n".encode())
    assert record["project_id"] == "sid1234"
    assert record["vm_id"] == VM_ID


def test_execute_timeout_audited_as_124(tmp_path):
    sandbox, vm, _ = make_audited_sandbox(tmp_path)
    vm.run_error = OperationTimeoutError("run", 120.0)
    sandbox.execute("sleep 999")
    (record,) = _read_jsonl(tmp_path / "audit-sid1234.jsonl")
    assert record["exit_code"] == 124


def test_upload_download_audited_per_file(tmp_path):
    sandbox, vm, _ = make_audited_sandbox(tmp_path)
    vm.files["/workspace/out.txt"] = b"result"
    sandbox.upload_files([("/workspace/a.txt", b"12345")])
    sandbox.download_files(["/workspace/out.txt", "/workspace/missing.txt"])
    records = _read_jsonl(tmp_path / "audit-sid1234.jsonl")
    upload, ok_download, missing_download = records
    assert upload["action"] == "upload"
    assert upload["path"] == "/workspace/a.txt"
    assert upload["bytes_out"] == 5
    assert "error" not in upload
    assert ok_download["action"] == "download"
    assert ok_download["bytes_out"] == len(b"result")
    assert missing_download["error"] == "file_not_found"


def test_audit_failure_does_not_break_execute(tmp_path):
    vm = FakeVM()
    lifecycle = FakeLifecycle(vm)
    manifest = SandboxManifest(
        sandbox_id=lifecycle.vm_id,
        kind="smolvm",
        image_tag="hagent-sandbox",
        runtime="firecracker",
        container_id=lifecycle.vm_id,
    )
    blocker = tmp_path / "occupied"
    blocker.write_text("not a dir")
    auditor = SandboxAuditor(command_log=CommandAuditLog(root=blocker))
    sandbox = HagentSmolVMSandbox(lifecycle=lifecycle, manifest=manifest, auditor=auditor)
    vm.run_result = CommandResult(exit_code=0, stdout="ok\n", stderr="")
    resp = sandbox.execute("echo ok")
    assert resp.exit_code == 0
    assert resp.output == "ok\n"


def test_close_records_evicted_event(tmp_path):
    sandbox, _vm, store = make_audited_sandbox(tmp_path)
    sandbox.close()
    sandbox.close()  # 幂等:只记一次
    events = store.list(event="evicted")
    assert len(events) == 1
    assert events[0].project_id == "sid1234"
    assert events[0].vm_id == VM_ID


def test_pause_resume_record_events(tmp_path):
    sandbox, _vm, store = make_audited_sandbox(tmp_path)
    sandbox.pause()
    sandbox.resume()
    assert [r.event for r in store.list(project_id="sid1234")] == ["paused", "resumed"]


# ---------------------------------------------------------------------------
# lifecycle 埋点:start() 的 created / create_failed
# ---------------------------------------------------------------------------


class FakeStartLifecycle:
    def __init__(self, *, fail: bool = False):
        self.vm_id = VM_ID
        self._fail = fail

    def start(self):
        if self._fail:
            raise RuntimeError("boot exploded")
        return SandboxManifest(
            sandbox_id=self.vm_id,
            kind="smolvm",
            image_tag="hagent-sandbox",
            runtime="firecracker",
            container_id=self.vm_id,
        )


def test_start_records_created_event(tmp_path, monkeypatch):
    store = SandboxEventStore(tmp_path / "events.db")
    auditor = SandboxAuditor(event_store=store)
    monkeypatch.setattr(
        "hagent.sandbox.smolvm.sandbox.SmolVMLifecycle",
        lambda **kwargs: FakeStartLifecycle(),
    )
    sandbox = HagentSmolVMSandbox.start(project_id="sid1234", auditor=auditor)
    events = store.list(event="created")
    assert len(events) == 1
    assert events[0].vm_id == VM_ID
    assert events[0].project_id == "sid1234"
    assert sandbox._auditor is auditor


def test_start_failure_records_create_failed(tmp_path, monkeypatch):
    store = SandboxEventStore(tmp_path / "events.db")
    auditor = SandboxAuditor(event_store=store)
    monkeypatch.setattr(
        "hagent.sandbox.smolvm.sandbox.SmolVMLifecycle",
        lambda **kwargs: FakeStartLifecycle(fail=True),
    )
    with pytest.raises(RuntimeError, match="boot exploded"):
        HagentSmolVMSandbox.start(project_id="sid1234", auditor=auditor)
    events = store.list(event="create_failed")
    assert len(events) == 1
    assert "boot exploded" in (events[0].detail or {}).get("error", "")
