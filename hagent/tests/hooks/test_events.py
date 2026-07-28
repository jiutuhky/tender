"""payload 拼写快照测试 —— 与 CC coreSchemas.ts 逐字段对齐的守护线。"""

from __future__ import annotations

from pathlib import Path

import pytest

from hagent.hooks.context import HookContext
from hagent.hooks.events import (
    AGENT_HOOK_TIMEOUT_S,
    HTTP_HOOK_TIMEOUT_S,
    PROMPT_HOOK_TIMEOUT_S,
    SESSION_END_TIMEOUT_S,
    TOOL_HOOK_TIMEOUT_S,
    HookEvent,
    build_payload,
    default_timeout_s,
    is_hook_event,
    match_query_for,
)


def _ctx(**kwargs) -> HookContext:
    defaults = dict(
        session_id="sid123",
        cwd=Path("/tmp/ws"),
        project_root=Path("/repo"),
        transcript_path=Path("/tmp/hagent/transcripts/sid123.jsonl"),
    )
    defaults.update(kwargs)
    return HookContext(**defaults)


def test_hook_events_complete_28():
    # 与 CC coreSchemas.ts HOOK_EVENTS 完全一致（顺序与拼写）
    expected = [
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
        "Notification",
        "UserPromptSubmit",
        "SessionStart",
        "SessionEnd",
        "Stop",
        "StopFailure",
        "SubagentStart",
        "SubagentStop",
        "PreCompact",
        "PostCompact",
        "PermissionRequest",
        "PermissionDenied",
        "Setup",
        "TeammateIdle",
        "TaskCreated",
        "TaskCompleted",
        "Elicitation",
        "ElicitationResult",
        "ConfigChange",
        "WorktreeCreate",
        "WorktreeRemove",
        "InstructionsLoaded",
        "CwdChanged",
        "FileChanged",
    ]
    assert [e.value for e in HookEvent] == expected
    assert len(expected) == 27  # CC 常量数组实际 27 项（含全部事件名）
    assert is_hook_event("PreToolUse")
    assert not is_hook_event("NotAnEvent")


def test_base_payload_spelling():
    payload = _ctx().base_payload()
    assert payload == {
        "session_id": "sid123",
        "transcript_path": "/tmp/hagent/transcripts/sid123.jsonl",
        "cwd": "/tmp/ws",
    }
    full = _ctx(
        permission_mode="default", agent_id="a1", agent_type="general-purpose"
    ).base_payload()
    assert full["permission_mode"] == "default"
    assert full["agent_id"] == "a1"
    assert full["agent_type"] == "general-purpose"


def test_pre_tool_use_payload_snapshot():
    payload = build_payload(
        HookEvent.PRE_TOOL_USE,
        _ctx(),
        {"tool_name": "Bash", "tool_input": {"command": "ls"}, "tool_use_id": "tu1"},
    )
    assert set(payload) == {
        "session_id",
        "transcript_path",
        "cwd",
        "hook_event_name",
        "tool_name",
        "tool_input",
        "tool_use_id",
    }
    assert payload["hook_event_name"] == "PreToolUse"


def test_post_tool_use_payload_snapshot():
    payload = build_payload(
        HookEvent.POST_TOOL_USE,
        _ctx(),
        {
            "tool_name": "Read",
            "tool_input": {"file_path": "/a"},
            "tool_response": "content",
            "tool_use_id": "tu2",
        },
    )
    assert payload["hook_event_name"] == "PostToolUse"
    assert payload["tool_response"] == "content"


def test_stop_payload_snapshot():
    payload = build_payload(
        HookEvent.STOP,
        _ctx(),
        {"stop_hook_active": False, "last_assistant_message": "done"},
    )
    assert payload["hook_event_name"] == "Stop"
    assert payload["stop_hook_active"] is False
    assert payload["last_assistant_message"] == "done"


def test_session_start_end_payload_snapshot():
    start = build_payload(HookEvent.SESSION_START, _ctx(), {"source": "startup"})
    assert start["hook_event_name"] == "SessionStart"
    assert start["source"] == "startup"
    end = build_payload(HookEvent.SESSION_END, _ctx(), {"reason": "other"})
    assert end["hook_event_name"] == "SessionEnd"
    assert end["reason"] == "other"


def test_user_prompt_submit_payload_snapshot():
    payload = build_payload(HookEvent.USER_PROMPT_SUBMIT, _ctx(), {"prompt": "你好"})
    assert payload["hook_event_name"] == "UserPromptSubmit"
    assert payload["prompt"] == "你好"


def test_build_payload_rejects_missing_and_unknown_fields():
    with pytest.raises(ValueError, match="缺少必填字段"):
        build_payload(HookEvent.PRE_TOOL_USE, _ctx(), {"tool_name": "Bash"})
    with pytest.raises(ValueError, match="未知字段"):
        build_payload(
            HookEvent.USER_PROMPT_SUBMIT, _ctx(), {"prompt": "x", "promptText": "x"}
        )


def test_match_query_mapping():
    assert (
        match_query_for(HookEvent.PRE_TOOL_USE, {"tool_name": "Bash"}) == "Bash"
    )
    assert (
        match_query_for(HookEvent.SESSION_START, {"source": "startup"}) == "startup"
    )
    assert match_query_for(HookEvent.SESSION_END, {"reason": "other"}) == "other"
    assert (
        match_query_for(HookEvent.SUBAGENT_STOP, {"agent_type": "Explore"})
        == "Explore"
    )
    assert (
        match_query_for(HookEvent.NOTIFICATION, {"notification_type": "idle"})
        == "idle"
    )
    assert (
        match_query_for(HookEvent.FILE_CHANGED, {"file_path": "/a/b/c.txt"})
        == "c.txt"
    )
    # Stop / UserPromptSubmit 无 matchQuery（matcher 被整体忽略）
    assert match_query_for(HookEvent.STOP, {"stop_hook_active": False}) is None
    assert match_query_for(HookEvent.USER_PROMPT_SUBMIT, {"prompt": "x"}) is None


def test_default_timeouts():
    assert default_timeout_s(HookEvent.PRE_TOOL_USE, "command", env={}) == 600.0
    assert TOOL_HOOK_TIMEOUT_S == 600.0
    assert default_timeout_s(HookEvent.SESSION_END, "command", env={}) == 1.5
    assert SESSION_END_TIMEOUT_S == 1.5
    assert default_timeout_s(HookEvent.STOP, "prompt", env={}) == 30.0
    assert PROMPT_HOOK_TIMEOUT_S == 30.0
    assert default_timeout_s(HookEvent.STOP, "agent", env={}) == 60.0
    assert AGENT_HOOK_TIMEOUT_S == 60.0
    assert default_timeout_s(HookEvent.PRE_TOOL_USE, "http", env={}) == 600.0
    assert HTTP_HOOK_TIMEOUT_S == 600.0
    # SessionEnd 支持 CC 的毫秒 env 覆盖
    assert (
        default_timeout_s(
            HookEvent.SESSION_END,
            "command",
            env={"CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS": "3000"},
        )
        == 3.0
    )
