"""P1：子代理 hooks（frontmatter 释放 / Stop→SubagentStop / SubagentStart / PermissionDenied）。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace

from hagent.hooks.config import HookRegistration, LoadedHooks, load_hooks_dict
from hagent.hooks.context import HookContext
from hagent.hooks.events import HookEvent
from hagent.hooks.middleware import HagentHooksMiddleware
from hagent.hooks.runner import HookRunner
from hagent.hooks.schema import CommandHookConfig
from hagent.subagents.compiler import _subagent_hooks_middleware
from hagent.subagents.loader import load_markdown_agents


def _ctx(tmp_path: Path, **kw) -> HookContext:
    cwd = tmp_path / "ws"
    cwd.mkdir(exist_ok=True)
    return HookContext(
        session_id="s1",
        cwd=cwd,
        project_root=tmp_path,
        transcript_path=tmp_path / "t.jsonl",
        **kw,
    )


def _loaded(event: HookEvent, command: str) -> LoadedHooks:
    loaded = LoadedHooks()
    loaded.by_event[event] = [
        HookRegistration(
            event=event,
            matcher=None,
            hook=CommandHookConfig(command=command),
            source="project",
        )
    ]
    return loaded


# ------------------------------------------------------------------
# load_hooks_dict：frontmatter hooks + Stop→SubagentStop 转换
# ------------------------------------------------------------------


def test_load_hooks_dict_converts_stop_to_subagent_stop():
    loaded = load_hooks_dict(
        {"Stop": [{"hooks": [{"type": "command", "command": "verify.sh"}]}]},
        source="agent:reviewer",
    )
    assert not loaded.has(HookEvent.STOP)
    regs = loaded.for_event(HookEvent.SUBAGENT_STOP)
    assert [r.hook.command for r in regs] == ["verify.sh"]
    assert regs[0].source == "agent:reviewer"


def test_load_hooks_dict_merges_stop_into_existing_subagent_stop():
    loaded = load_hooks_dict(
        {
            "SubagentStop": [{"hooks": [{"type": "command", "command": "a.sh"}]}],
            "Stop": [{"hooks": [{"type": "command", "command": "b.sh"}]}],
        },
        source="agent:x",
    )
    assert [r.hook.command for r in loaded.for_event(HookEvent.SUBAGENT_STOP)] == [
        "a.sh",
        "b.sh",
    ]


def test_loader_keeps_hooks_frontmatter(tmp_path: Path):
    (tmp_path / "reviewer.md").write_text(
        "---\n"
        "name: reviewer\n"
        "description: 审查\n"
        "hooks:\n"
        "  Stop:\n"
        "    - hooks:\n"
        "        - type: command\n"
        "          command: verify.sh\n"
        "---\n"
        "正文",
        encoding="utf-8",
    )
    specs = load_markdown_agents([tmp_path])
    assert specs[0]["hooks"] == {
        "Stop": [{"hooks": [{"type": "command", "command": "verify.sh"}]}]
    }


# ------------------------------------------------------------------
# _subagent_hooks_middleware
# ------------------------------------------------------------------


def test_subagent_middleware_merges_global_and_frontmatter(tmp_path: Path):
    global_runner = HookRunner(
        _loaded(HookEvent.PRE_TOOL_USE, "global.sh"), _ctx(tmp_path)
    )
    spec = {
        "name": "reviewer",
        "description": "d",
        "system_prompt": "p",
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "fm.sh"}]}]},
    }
    mw = _subagent_hooks_middleware(spec, global_runner, None)
    assert isinstance(mw, HagentHooksMiddleware)
    assert mw.stop_event == HookEvent.SUBAGENT_STOP
    assert mw.runner.has_hooks(HookEvent.PRE_TOOL_USE)  # 全局继承
    assert mw.runner.has_hooks(HookEvent.SUBAGENT_STOP)  # frontmatter 转换
    assert mw.runner.ctx.agent_type == "reviewer"
    assert mw.runner.ctx.agent_id.startswith("reviewer-")


def test_subagent_middleware_none_when_no_hooks(tmp_path: Path):
    spec = {"name": "x", "description": "d", "system_prompt": "p"}
    assert _subagent_hooks_middleware(spec, None, None) is None
    empty_runner = HookRunner(LoadedHooks(), _ctx(tmp_path))
    assert _subagent_hooks_middleware(spec, empty_runner, None) is None


def test_subagent_middleware_frontmatter_only_with_context(tmp_path: Path):
    spec = {
        "name": "x",
        "description": "d",
        "system_prompt": "p",
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "v.sh"}]}]},
    }
    mw = _subagent_hooks_middleware(spec, None, _ctx(tmp_path))
    assert mw is not None
    assert mw.runner.has_hooks(HookEvent.SUBAGENT_STOP)


# ------------------------------------------------------------------
# SubagentStop payload 字段
# ------------------------------------------------------------------


async def test_subagent_stop_payload_fields(tmp_path: Path):
    capture = tmp_path / "payload.json"
    runner = HookRunner(
        _loaded(HookEvent.SUBAGENT_STOP, f"cat > {capture}"),
        _ctx(tmp_path, agent_id="reviewer-abc", agent_type="reviewer"),
    )
    mw = HagentHooksMiddleware(runner, stop_event=HookEvent.SUBAGENT_STOP)
    from langchain_core.messages import AIMessage, HumanMessage

    state = {"messages": [HumanMessage("hi"), AIMessage("子代理完成")]}
    await mw.aafter_model(state, None)
    payload = json.loads(capture.read_text())
    assert payload["hook_event_name"] == "SubagentStop"
    assert payload["agent_id"] == "reviewer-abc"
    assert payload["agent_type"] == "reviewer"
    assert payload["agent_transcript_path"].endswith("t.jsonl")
    assert payload["stop_hook_active"] is False
    assert payload["last_assistant_message"] == "子代理完成"


# ------------------------------------------------------------------
# PermissionDenied
# ------------------------------------------------------------------


async def test_permission_denied_fired_on_pre_tool_use_deny(tmp_path: Path):
    capture = tmp_path / "denied.json"
    loaded = _loaded(HookEvent.PRE_TOOL_USE, "echo 危险 >&2; exit 2")
    loaded.by_event[HookEvent.PERMISSION_DENIED] = [
        HookRegistration(
            event=HookEvent.PERMISSION_DENIED,
            matcher=None,
            hook=CommandHookConfig(command=f"cat > {capture}"),
            source="project",
        )
    ]
    mw = HagentHooksMiddleware(HookRunner(loaded, _ctx(tmp_path)))
    request = SimpleNamespace(
        tool_call={"name": "Bash", "args": {"command": "rm -rf /"}, "id": "t1"},
        tool=None,
        state={},
        runtime=None,
    )

    async def handler(req):
        raise AssertionError("不应执行")

    result = await mw.awrap_tool_call(request, handler)
    assert result.status == "error"
    payload = json.loads(capture.read_text())
    assert payload["hook_event_name"] == "PermissionDenied"
    assert payload["tool_name"] == "Bash"
    assert "危险" in payload["reason"]


# ------------------------------------------------------------------
# SubagentStart（agent_tool）
# ------------------------------------------------------------------


async def test_subagent_start_injects_context(tmp_path: Path):
    from langchain_core.messages import AIMessage

    from hagent.subagents.agent_tool import build_agent_tool

    class _Runnable:
        def __init__(self):
            self.states = []

        async def ainvoke(self, state, config):
            self.states.append(state)
            return {"messages": [AIMessage(content="done")]}

    runnable = _Runnable()
    payload = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStart",
                "additionalContext": "注意：先读 CLAUDE.md",
            }
        }
    )
    loaded = _loaded(HookEvent.SUBAGENT_START, f"echo '{payload}'")
    runner = HookRunner(loaded, _ctx(tmp_path))
    tool = build_agent_tool(
        {"general-purpose": runnable}, "desc", hook_runner=runner
    )
    runtime = SimpleNamespace(tool_call_id="call-9", state={}, config={})
    await tool.coroutine(
        description="做事",
        prompt="任务简报",
        subagent_type=None,
        runtime=runtime,
    )
    prompt_msg = runnable.states[0]["messages"][0]
    assert "任务简报" in prompt_msg.content
    assert "注意：先读 CLAUDE.md" in prompt_msg.content


async def test_subagent_start_matcher_filters_by_agent_type(tmp_path: Path):
    from langchain_core.messages import AIMessage

    from hagent.subagents.agent_tool import build_agent_tool

    class _Runnable:
        async def ainvoke(self, state, config):
            return {"messages": [AIMessage(content="done")]}

    marker = tmp_path / "fired"
    loaded = LoadedHooks()
    loaded.by_event[HookEvent.SUBAGENT_START] = [
        HookRegistration(
            event=HookEvent.SUBAGENT_START,
            matcher="Explore",  # 与 general-purpose 不匹配
            hook=CommandHookConfig(command=f"touch {marker}"),
            source="project",
        )
    ]
    runner = HookRunner(loaded, _ctx(tmp_path))
    tool = build_agent_tool(
        {"general-purpose": _Runnable()}, "desc", hook_runner=runner
    )
    runtime = SimpleNamespace(tool_call_id="call-1", state={}, config={})
    await tool.coroutine(
        description="做事", prompt="p", subagent_type=None, runtime=runtime
    )
    assert not marker.exists()
