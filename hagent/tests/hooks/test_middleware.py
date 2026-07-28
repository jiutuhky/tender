"""HagentHooksMiddleware 直调层测试（手工构造 request/state + fake handler）。"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from hagent.hooks.config import HookRegistration, LoadedHooks
from hagent.hooks.context import HookContext
from hagent.hooks.events import HookEvent
from hagent.hooks.middleware import HagentHooksMiddleware
from hagent.hooks.runner import HookRunner
from hagent.hooks.schema import CommandHookConfig


class _FakeRequest(SimpleNamespace):
    """模拟 ToolCallRequest 的最小面（tool_call + override）。"""

    def override(self, **overrides: Any) -> "_FakeRequest":
        merged = dict(self.__dict__)
        merged.update(overrides)
        return _FakeRequest(**merged)


def _ctx(tmp_path: Path) -> HookContext:
    cwd = tmp_path / "ws"
    cwd.mkdir(exist_ok=True)
    return HookContext(
        session_id="s1",
        cwd=cwd,
        project_root=tmp_path,
        transcript_path=tmp_path / "t.jsonl",
    )


def _runner(tmp_path: Path, event: HookEvent, command: str) -> HookRunner:
    loaded = LoadedHooks()
    loaded.by_event[event] = [
        HookRegistration(
            event=event,
            matcher=None,
            hook=CommandHookConfig(command=command),
            source="project",
        )
    ]
    return HookRunner(loaded, _ctx(tmp_path))


def _request(args: dict | None = None) -> _FakeRequest:
    return _FakeRequest(
        tool_call={"name": "Bash", "args": args or {"command": "ls"}, "id": "t1"},
        tool=None,
        state={},
        runtime=None,
    )


def _ok_handler(request: Any) -> ToolMessage:
    return ToolMessage(content="tool output", tool_call_id=request.tool_call["id"])


async def test_deny_short_circuits_handler(tmp_path: Path):
    mw = HagentHooksMiddleware(
        _runner(tmp_path, HookEvent.PRE_TOOL_USE, "echo 不许 >&2; exit 2")
    )
    called = []

    async def handler(request):
        called.append(request)
        return _ok_handler(request)

    result = await mw.awrap_tool_call(_request(), handler)
    assert called == []  # handler 未被调用
    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert "不许" in result.content


async def test_ask_downgraded_to_deny(tmp_path: Path):
    payload = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": "需要确认",
            }
        }
    )
    mw = HagentHooksMiddleware(
        _runner(tmp_path, HookEvent.PRE_TOOL_USE, f"echo '{payload}'")
    )
    result = await mw.awrap_tool_call(_request(), _async(_ok_handler))
    assert result.status == "error"
    assert "ask" in result.content
    assert "需要确认" in result.content


def _async(fn):
    async def wrapper(request):
        return fn(request)

    return wrapper


async def test_updated_input_rewrites_args(tmp_path: Path):
    payload = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": {"command": "ls -la"},
            }
        }
    )
    mw = HagentHooksMiddleware(
        _runner(tmp_path, HookEvent.PRE_TOOL_USE, f"echo '{payload}'")
    )
    seen = {}

    async def handler(request):
        seen["args"] = request.tool_call["args"]
        return _ok_handler(request)

    await mw.awrap_tool_call(_request({"command": "ls"}), handler)
    assert seen["args"] == {"command": "ls -la"}


async def test_post_tool_use_appends_context(tmp_path: Path):
    payload = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": "记得检查 lint",
            }
        }
    )
    mw = HagentHooksMiddleware(
        _runner(tmp_path, HookEvent.POST_TOOL_USE, f"echo '{payload}'")
    )
    result = await mw.awrap_tool_call(_request(), _async(_ok_handler))
    assert "tool output" in result.content
    assert "<system-reminder>" in result.content
    assert "记得检查 lint" in result.content


async def test_post_tool_use_blocking_feedback_appended(tmp_path: Path):
    mw = HagentHooksMiddleware(
        _runner(tmp_path, HookEvent.POST_TOOL_USE, "echo 有问题 >&2; exit 2")
    )
    result = await mw.awrap_tool_call(_request(), _async(_ok_handler))
    assert "PostToolUse hook feedback (blocking)" in result.content
    assert "有问题" in result.content


async def test_post_tool_use_failure_on_error_result(tmp_path: Path):
    marker = tmp_path / "fail.json"
    mw = HagentHooksMiddleware(
        _runner(tmp_path, HookEvent.POST_TOOL_USE_FAILURE, f"cat > {marker}")
    )

    async def failing_handler(request):
        return ToolMessage(
            content="boom", status="error", tool_call_id=request.tool_call["id"]
        )

    await mw.awrap_tool_call(_request(), failing_handler)
    payload = json.loads(marker.read_text())
    assert payload["hook_event_name"] == "PostToolUseFailure"
    assert payload["error"] == "boom"


async def test_post_tool_use_failure_on_exception(tmp_path: Path):
    marker = tmp_path / "exc.json"
    mw = HagentHooksMiddleware(
        _runner(tmp_path, HookEvent.POST_TOOL_USE_FAILURE, f"cat > {marker}")
    )

    async def raising_handler(request):
        raise RuntimeError("爆炸")

    with pytest.raises(RuntimeError):
        await mw.awrap_tool_call(_request(), raising_handler)
    payload = json.loads(marker.read_text())
    assert payload["error"] == "爆炸"


def test_wrap_tool_call_sync_path(tmp_path: Path):
    mw = HagentHooksMiddleware(
        _runner(tmp_path, HookEvent.PRE_TOOL_USE, "echo no >&2; exit 2")
    )
    result = mw.wrap_tool_call(_request(), _ok_handler)
    assert result.status == "error"


# ------------------------------------------------------------------
# Stop（after_model）
# ------------------------------------------------------------------


def _stop_state(**extra) -> dict:
    return {"messages": [HumanMessage("hi"), AIMessage("全部完成")], **extra}


async def test_stop_block_jumps_to_model(tmp_path: Path):
    mw = HagentHooksMiddleware(
        _runner(tmp_path, HookEvent.STOP, "echo 继续干活 >&2; exit 2")
    )
    updates = await mw.aafter_model(_stop_state(), None)
    assert updates is not None
    assert updates["jump_to"] == "model"
    assert updates["hagent_stop_hook_active"] is True
    assert updates["hagent_stop_block_count"] == 1
    msg = updates["messages"][0]
    assert isinstance(msg, HumanMessage)
    assert msg.content.startswith("Stop hook feedback:")
    assert "继续干活" in msg.content


async def test_stop_pass_returns_none(tmp_path: Path):
    mw = HagentHooksMiddleware(_runner(tmp_path, HookEvent.STOP, "exit 0"))
    assert await mw.aafter_model(_stop_state(), None) is None


async def test_stop_not_fired_when_tool_calls_pending(tmp_path: Path):
    marker = tmp_path / "fired"
    mw = HagentHooksMiddleware(
        _runner(tmp_path, HookEvent.STOP, f"touch {marker}")
    )
    state = {
        "messages": [
            AIMessage(
                "",
                tool_calls=[{"name": "Bash", "args": {}, "id": "t1"}],
            )
        ]
    }
    assert await mw.aafter_model(state, None) is None
    assert not marker.exists()


async def test_stop_hook_active_passed_in_payload(tmp_path: Path):
    capture = tmp_path / "payload.json"
    mw = HagentHooksMiddleware(
        _runner(tmp_path, HookEvent.STOP, f"cat > {capture}; exit 0")
    )
    await mw.aafter_model(_stop_state(hagent_stop_hook_active=True), None)
    payload = json.loads(capture.read_text())
    assert payload["stop_hook_active"] is True
    assert payload["last_assistant_message"] == "全部完成"


async def test_stop_block_count_hard_limit(tmp_path: Path):
    mw = HagentHooksMiddleware(
        _runner(tmp_path, HookEvent.STOP, "echo again >&2; exit 2"),
        max_stop_blocks=2,
    )
    state = _stop_state(hagent_stop_hook_active=True, hagent_stop_block_count=2)
    updates = await mw.aafter_model(state, None)
    assert updates == {
        "hagent_stop_hook_active": False,
        "hagent_stop_block_count": 0,
    }  # 超限强制放行，无 jump_to


async def test_stop_continue_false_without_block_stops(tmp_path: Path):
    payload = json.dumps({"continue": False, "stopReason": "到此为止"})
    mw = HagentHooksMiddleware(
        _runner(tmp_path, HookEvent.STOP, f"echo '{payload}'")
    )
    updates = await mw.aafter_model(_stop_state(), None)
    assert updates is None or "jump_to" not in updates


def test_sync_async_hooks_implemented_in_pairs():
    """反射守护：凡覆写 sync 钩子必须成对覆写 async 版（SSE 路径依赖）。"""
    from langchain.agents.middleware import AgentMiddleware

    pairs = [
        ("wrap_tool_call", "awrap_tool_call"),
        ("after_model", "aafter_model"),
        ("before_model", "abefore_model"),
        ("before_agent", "abefore_agent"),
        ("after_agent", "aafter_agent"),
        ("wrap_model_call", "awrap_model_call"),
    ]
    for sync_name, async_name in pairs:
        sync_overridden = getattr(HagentHooksMiddleware, sync_name, None) is not getattr(
            AgentMiddleware, sync_name, None
        )
        async_overridden = getattr(
            HagentHooksMiddleware, async_name, None
        ) is not getattr(AgentMiddleware, async_name, None)
        assert sync_overridden == async_overridden, (
            f"{sync_name}/{async_name} 必须成对覆写"
        )


def test_after_model_jump_config_on_both_variants():
    assert getattr(HagentHooksMiddleware.after_model, "__can_jump_to__", None) == [
        "model"
    ]
    assert getattr(HagentHooksMiddleware.aafter_model, "__can_jump_to__", None) == [
        "model"
    ]
