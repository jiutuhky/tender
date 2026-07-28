from __future__ import annotations

import json

from hagent.server.sse import SandboxEvent, render_sandbox_event


def test_render_created_event():
    ev = SandboxEvent(kind="created", session_id="s1", sandbox_id="docker-abc", reason=None)
    text = render_sandbox_event(ev)
    # SSE 框架格式：第一行 event：; 后面 data：JSON
    lines = text.strip().split("\n")
    assert lines[0] == "event: sandbox.created"
    payload = json.loads(lines[1].removeprefix("data: "))
    assert payload["event"] == "sandbox.created"
    assert payload["session_id"] == "s1"
    assert payload["sandbox_id"] == "docker-abc"


def test_render_error_event_includes_reason():
    ev = SandboxEvent(kind="error", session_id="s1", sandbox_id=None, reason="image_pull_failed")
    text = render_sandbox_event(ev)
    payload = json.loads(text.strip().split("\n")[1].removeprefix("data: "))
    assert payload["event"] == "sandbox.error"
    assert payload["reason"] == "image_pull_failed"


def test_all_event_kinds_render():
    for kind in ("created", "paused", "resumed", "evicted", "error"):
        ev = SandboxEvent(kind=kind, session_id="s1", sandbox_id=None, reason=None)
        text = render_sandbox_event(ev)
        assert f"event: sandbox.{kind}" in text


# ---------------------------------------------------------------------------
# Task B7:新事件种类 + 会话级事件队列(push/drain)+ 各路径发射
# ---------------------------------------------------------------------------

import pytest

from hagent.server.sse import (
    drain_sandbox_events,
    push_sandbox_event,
)


@pytest.fixture(autouse=True)
def _clean_event_queue():
    yield
    # 模块级队列,测试间互不串味
    from hagent.server import sse as sse_mod

    with sse_mod._PENDING_LOCK:
        sse_mod._PENDING_SANDBOX_EVENTS.clear()


def test_new_event_kinds_render():
    for kind in ("adopted", "orphaned", "health_fail"):
        ev = SandboxEvent(kind=kind, session_id="s1", sandbox_id=None, reason=None)
        assert f"event: sandbox.{kind}" in render_sandbox_event(ev)


def test_push_drain_per_session_fifo():
    push_sandbox_event(SandboxEvent(kind="created", session_id="s1", sandbox_id="a"))
    push_sandbox_event(SandboxEvent(kind="evicted", session_id="s1", sandbox_id="a"))
    push_sandbox_event(SandboxEvent(kind="created", session_id="s2", sandbox_id="b"))
    drained = drain_sandbox_events("s1")
    assert [e.kind for e in drained] == ["created", "evicted"]
    assert drain_sandbox_events("s1") == [], "drain 后队列清空"
    assert [e.kind for e in drain_sandbox_events("s2")] == ["created"]


def test_push_caps_queue_keeps_latest():
    for i in range(60):
        push_sandbox_event(SandboxEvent(kind="paused", session_id="s1", reason=str(i)))
    drained = drain_sandbox_events("s1")
    assert len(drained) == 50
    assert drained[-1].reason == "59", "溢出时丢最旧,保最新"


def _manager_with_project(tmp_path):
    from tests.server.test_manager_rebuild import FakePool
    from hagent.sandbox import SandboxKind
    from hagent.server.leases import LeaseStore
    from hagent.server.manager import SessionManager
    from hagent.server.sessions import SessionStore

    db = tmp_path / "s.db"
    store = SessionStore(db)
    manager = SessionManager(
        store=store,
        lease_store=LeaseStore(db),
        sandbox_pool=FakePool(),
        workspace_root=tmp_path / "w",
    )
    first = manager.create_session(
        project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM
    )
    second = manager.create_session(
        project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM
    )
    return manager, first, second


def test_first_project_run_emits_created_to_all_project_sessions(tmp_path):
    manager, first, second = _manager_with_project(tmp_path)

    manager.ensure_sandbox(first.id)

    assert [event.kind for event in drain_sandbox_events(first.id)] == ["created"]
    assert [event.kind for event in drain_sandbox_events(second.id)] == ["created"]


def test_project_lifecycle_event_fans_out_with_reason(tmp_path):
    manager, first, second = _manager_with_project(tmp_path)

    manager.emit_project_event(
        "health_fail", "project-alpha", reason="连续探活失败,杀重建"
    )

    for session_id in (first.id, second.id):
        (event,) = drain_sandbox_events(session_id)
        assert event.kind == "health_fail"
        assert event.reason == "连续探活失败,杀重建"


def test_message_stream_flushes_pending_sandbox_events():
    from hagent.server.routers.messages import _stream_agent_events

    push_sandbox_event(
        SandboxEvent(kind="health_fail", session_id="t1", sandbox_id="smolvm-x", reason="连败")
    )
    push_sandbox_event(SandboxEvent(kind="orphaned", session_id="t1", sandbox_id=None))

    class FakeAgent:
        def stream(self, *args, **kwargs):
            return iter([])

    frames = b"".join(_stream_agent_events(FakeAgent(), "hi", thread_id="t1")).decode()
    health_pos = frames.find("event: sandbox.health_fail")
    orphan_pos = frames.find("event: sandbox.orphaned")
    done_pos = frames.find("event: done")
    assert health_pos != -1 and orphan_pos != -1
    assert health_pos < orphan_pos < done_pos, "积压事件序在 agent 流之前冲刷"
    assert drain_sandbox_events("t1") == []
