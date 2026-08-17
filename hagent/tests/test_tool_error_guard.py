"""ToolErrorGuardMiddleware:工具异常 → error ToolMessage(不炸流);控制流异常放行。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import ToolMessage
from langgraph.errors import GraphInterrupt

from hagent.sandbox.errors import SandboxUnavailable, SandboxUnavailableReason
from hagent.tool_error_guard import ToolErrorGuardMiddleware


def _request() -> SimpleNamespace:
    return SimpleNamespace(
        tool_call={"name": "Read", "args": {"file_path": "a.md"}, "id": "t1"},
        tool=None,
        state={},
        runtime=None,
    )


def test_sandbox_unavailable_becomes_error_tool_message():
    mw = ToolErrorGuardMiddleware()

    def handler(request: Any) -> ToolMessage:
        raise SandboxUnavailable(SandboxUnavailableReason.GONE, detail="VM x deleted")

    result = mw.wrap_tool_call(_request(), handler)
    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert result.tool_call_id == "t1"
    assert result.name == "Read"
    assert result.content.startswith("[sandbox_unavailable:gone]")
    assert "VM x deleted" not in result.content, "detail 只进日志,不进模型"


def test_generic_exception_becomes_error_tool_message():
    mw = ToolErrorGuardMiddleware()

    def handler(request: Any) -> ToolMessage:
        raise OSError("sandbox write failed: upload_failed: disk full")

    result = mw.wrap_tool_call(_request(), handler)
    assert result.status == "error"
    assert "Read" in result.content and "OSError" in result.content


def test_graph_interrupt_is_not_swallowed():
    mw = ToolErrorGuardMiddleware()

    def handler(request: Any) -> ToolMessage:
        raise GraphInterrupt()

    with pytest.raises(GraphInterrupt):
        mw.wrap_tool_call(_request(), handler)


async def test_async_pair_has_same_semantics():
    mw = ToolErrorGuardMiddleware()

    async def failing(request: Any) -> ToolMessage:
        raise SandboxUnavailable(SandboxUnavailableReason.PAUSED)

    result = await mw.awrap_tool_call(_request(), failing)
    assert result.status == "error"
    assert result.content.startswith("[sandbox_unavailable:paused]")

    async def interrupting(request: Any) -> ToolMessage:
        raise GraphInterrupt()

    with pytest.raises(GraphInterrupt):
        await mw.awrap_tool_call(_request(), interrupting)


def test_success_passthrough():
    mw = ToolErrorGuardMiddleware()
    ok = ToolMessage(content="fine", tool_call_id="t1")
    assert mw.wrap_tool_call(_request(), lambda request: ok) is ok


async def test_hooks_see_guarded_error_as_post_tool_use_failure(tmp_path):
    """接线顺序契约:hooks 在外、guard 在内 → 工具异常触发 PostToolUseFailure。"""
    from hagent.hooks.config import HookRegistration, LoadedHooks
    from hagent.hooks.context import HookContext
    from hagent.hooks.events import HookEvent
    from hagent.hooks.middleware import HagentHooksMiddleware
    from hagent.hooks.runner import HookRunner
    from hagent.hooks.schema import CommandHookConfig

    marker = tmp_path / "failed.txt"
    loaded = LoadedHooks()
    loaded.by_event[HookEvent.POST_TOOL_USE_FAILURE] = [
        HookRegistration(
            event=HookEvent.POST_TOOL_USE_FAILURE,
            matcher=None,
            hook=CommandHookConfig(command=f"touch {marker}"),
            source="project",
        )
    ]
    cwd = tmp_path / "ws"
    cwd.mkdir()
    runner = HookRunner(
        loaded,
        HookContext(
            session_id="s1", cwd=cwd, project_root=tmp_path, transcript_path=tmp_path / "t.jsonl"
        ),
    )
    hooks_mw = HagentHooksMiddleware(runner)
    guard = ToolErrorGuardMiddleware()

    async def tool(request: Any) -> ToolMessage:
        raise SandboxUnavailable(SandboxUnavailableReason.CONNECT_FAILED)

    async def inner(request: Any) -> ToolMessage:
        return await guard.awrap_tool_call(request, tool)

    result = await hooks_mw.awrap_tool_call(_request(), inner)
    assert result.status == "error"
    assert marker.exists(), "PostToolUseFailure hook 应被触发"
