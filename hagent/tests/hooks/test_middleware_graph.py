"""真图集成测试：langchain.agents.create_agent + 脚本化假模型 + 真 hook 脚本。

验证 jump_to / add_messages 的真实图语义（直调层测不出来）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator, Sequence

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from hagent.hooks.config import HookRegistration, LoadedHooks
from hagent.hooks.context import HookContext
from hagent.hooks.events import HookEvent
from hagent.hooks.middleware import HagentHooksMiddleware
from hagent.hooks.runner import HookRunner
from hagent.hooks.schema import CommandHookConfig


class ScriptedModel(BaseChatModel):
    """按脚本依次吐出 AIMessage 的假模型（支持 bind_tools）。"""

    script: list[AIMessage]
    calls: list[list[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedModel":
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.calls.append(list(messages))
        index = min(len(self.calls) - 1, len(self.script) - 1)
        return ChatResult(
            generations=[ChatGeneration(message=self.script[index])]
        )


@tool
def toy_tool(text: str) -> str:
    """回显输入文本。"""
    return f"echoed: {text}"


def _runner(tmp_path: Path, loaded: LoadedHooks) -> HookRunner:
    cwd = tmp_path / "ws"
    cwd.mkdir(exist_ok=True)
    return HookRunner(
        loaded,
        HookContext(
            session_id="s1",
            cwd=cwd,
            project_root=tmp_path,
            transcript_path=tmp_path / "t.jsonl",
        ),
    )


def _loaded(event: HookEvent, command: str, matcher: str | None = None) -> LoadedHooks:
    loaded = LoadedHooks()
    loaded.by_event[event] = [
        HookRegistration(
            event=event,
            matcher=matcher,
            hook=CommandHookConfig(command=command),
            source="project",
        )
    ]
    return loaded


def _build_agent(model: ScriptedModel, runner: HookRunner):
    from langchain.agents import create_agent

    return create_agent(
        model=model,
        tools=[toy_tool],
        middleware=[HagentHooksMiddleware(runner)],
    )


def test_pre_tool_use_deny_reaches_model_as_error(tmp_path: Path):
    model = ScriptedModel(
        script=[
            AIMessage(
                "",
                tool_calls=[{"name": "toy_tool", "args": {"text": "hi"}, "id": "t1"}],
            ),
            AIMessage("好的，我不执行了"),
        ],
        calls=[],
    )
    runner = _runner(
        tmp_path, _loaded(HookEvent.PRE_TOOL_USE, "echo 禁止使用该工具 >&2; exit 2")
    )
    agent = _build_agent(model, runner)
    state = agent.invoke({"messages": [HumanMessage("run the tool")]})
    tool_messages = [m for m in state["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].status == "error"
    assert "禁止使用该工具" in tool_messages[0].content
    assert "echoed" not in tool_messages[0].content  # 工具没真跑


def test_stop_hook_blocks_then_allows(tmp_path: Path):
    """Stop exit 2 一次 → 图回 model；第二次 payload stop_hook_active=true。"""
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()
    # hook：dump stdin 到递增文件；首次 exit 2 阻断，其后放行
    hook_script = tmp_path / "stop_hook.sh"
    hook_script.write_text(
        f"""#!/usr/bin/env bash
n=$(ls {capture_dir} | wc -l)
cat > {capture_dir}/payload-$n.json
if [ "$n" -eq 0 ]; then
  echo "还有收尾工作没做" >&2
  exit 2
fi
exit 0
"""
    )
    hook_script.chmod(0o755)

    model = ScriptedModel(
        script=[AIMessage("我做完了"), AIMessage("补充完成，现在真的结束")],
        calls=[],
    )
    runner = _runner(tmp_path, _loaded(HookEvent.STOP, f"bash {hook_script}"))
    agent = _build_agent(model, runner)
    state = agent.invoke({"messages": [HumanMessage("do work")]})

    # 模型被调用了两轮（第一次 Stop 被阻断后 jump 回 model）
    assert len(model.calls) == 2
    # 阻断反馈以 HumanMessage 进入对话
    feedback = [
        m
        for m in state["messages"]
        if isinstance(m, HumanMessage) and str(m.content).startswith("Stop hook feedback:")
    ]
    assert len(feedback) == 1
    assert "还有收尾工作没做" in feedback[0].content
    # hook 被触发两次；第二次 stop_hook_active=true
    payloads = sorted(capture_dir.glob("payload-*.json"))
    assert len(payloads) == 2
    first = json.loads(payloads[0].read_text())
    second = json.loads(payloads[1].read_text())
    assert first["stop_hook_active"] is False
    assert second["stop_hook_active"] is True
    assert first["hook_event_name"] == "Stop"
    assert first["last_assistant_message"] == "我做完了"
    # 最终消息是第二轮的正常收尾
    final_ai = [m for m in state["messages"] if isinstance(m, AIMessage)][-1]
    assert final_ai.content == "补充完成，现在真的结束"


def test_updated_input_rewrites_tool_args_in_graph(tmp_path: Path):
    payload = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": {"text": "REWRITTEN"},
            }
        }
    )
    model = ScriptedModel(
        script=[
            AIMessage(
                "",
                tool_calls=[
                    {"name": "toy_tool", "args": {"text": "original"}, "id": "t1"}
                ],
            ),
            AIMessage("done"),
        ],
        calls=[],
    )
    runner = _runner(tmp_path, _loaded(HookEvent.PRE_TOOL_USE, f"echo '{payload}'"))
    agent = _build_agent(model, runner)
    state = agent.invoke({"messages": [HumanMessage("go")]})
    tool_messages = [m for m in state["messages"] if isinstance(m, ToolMessage)]
    assert "echoed: REWRITTEN" in tool_messages[0].content


async def test_stop_hook_works_on_async_path(tmp_path: Path):
    """SSE 走 async 路径 —— aafter_model 的 jump 语义同样成立。"""
    model = ScriptedModel(
        script=[AIMessage("done round 1"), AIMessage("done round 2")],
        calls=[],
    )
    fired = tmp_path / "fired"
    hook = (
        f"n=$(cat {fired} 2>/dev/null || echo 0); echo $((n+1)) > {fired}; "
        f'if [ "$n" = "0" ]; then echo again >&2; exit 2; fi'
    )
    runner = _runner(tmp_path, _loaded(HookEvent.STOP, hook))
    agent = _build_agent(model, runner)
    state = await agent.ainvoke({"messages": [HumanMessage("go")]})
    assert len(model.calls) == 2
    assert fired.read_text().strip() == "2"
    final_ai = [m for m in state["messages"] if isinstance(m, AIMessage)][-1]
    assert final_ai.content == "done round 2"
