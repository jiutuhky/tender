"""RepairInvalidToolCallsMiddleware:invalid tool call 的协议兜底与自愈重试。

事故背景(2026-07-15 解析中断):DeepSeek 生成参数 JSON 非法的 tool call,
LangChain 归入 invalid_tool_calls 后无人回 ToolMessage,下一次模型调用被
Anthropic 协议校验拒绝(tool_use 无配对 tool_result → 400)。
"""

from __future__ import annotations

from typing import Any, Iterator, Sequence

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from hagent.tool_call_repair import (
    MAX_ALL_INVALID_RETRIES,
    RepairInvalidToolCallsMiddleware,
    repair_invalid_tool_calls_middleware,
)


def _invalid_call(call_id: str | None, *, name: str = "toy_tool", error: str | None = None):
    return {
        "type": "invalid_tool_call",
        "id": call_id,
        "name": name,
        "args": '{"text": "带"未转义"引号"}',
        "error": error,
    }


def _valid_call(call_id: str, *, name: str = "toy_tool"):
    return {"type": "tool_call", "id": call_id, "name": name, "args": {"text": "ok"}}


def _state(*messages: Any, **extra: Any) -> dict[str, Any]:
    return {"messages": list(messages), **extra}


mw = RepairInvalidToolCallsMiddleware()


# ---------------------------------------------------------------------------
# 直调单测
# ---------------------------------------------------------------------------


def test_mixed_valid_invalid_appends_error_tool_message_without_jump():
    ai = AIMessage(
        content="",
        tool_calls=[_valid_call("call_01_ok")],
        invalid_tool_calls=[_invalid_call("call_00_bad", error="Expecting ',' delimiter")],
    )
    updates = mw.after_model(_state(ai), None)
    assert updates is not None
    (repair,) = updates["messages"]
    assert isinstance(repair, ToolMessage)
    assert repair.tool_call_id == "call_00_bad"
    assert repair.status == "error"
    assert "JSON" in repair.content
    assert "Expecting ',' delimiter" in repair.content
    # 还有合法调用会正常进 tools 节点,不跳转
    assert "jump_to" not in updates


def test_all_invalid_jumps_back_to_model_and_counts():
    ai = AIMessage(content="", invalid_tool_calls=[_invalid_call("call_00_bad")])
    updates = mw.after_model(_state(ai), None)
    assert updates is not None
    assert updates["jump_to"] == "model"
    assert updates["hagent_all_invalid_retries"] == 1
    assert updates["messages"][0].tool_call_id == "call_00_bad"


def test_all_invalid_retry_budget_exhausted_stops_jumping():
    ai = AIMessage(content="", invalid_tool_calls=[_invalid_call("call_00_bad")])
    state = _state(ai, hagent_all_invalid_retries=MAX_ALL_INVALID_RETRIES)
    updates = mw.after_model(state, None)
    assert updates is not None
    # 协议配对仍要补齐,但不再跳转重试
    assert updates["messages"][0].tool_call_id == "call_00_bad"
    assert "jump_to" not in updates
    assert "hagent_all_invalid_retries" not in updates


def test_clean_response_resets_retry_counter():
    ai = AIMessage(content="done")
    updates = mw.after_model(_state(ai, hagent_all_invalid_retries=2), None)
    assert updates == {"hagent_all_invalid_retries": 0}
    # 一直干净则不写状态
    assert mw.after_model(_state(ai), None) is None


def test_invalid_call_without_id_is_skipped():
    ai = AIMessage(content="", invalid_tool_calls=[_invalid_call(None)])
    assert mw.after_model(_state(ai), None) is None


def test_last_message_not_ai_is_noop():
    assert mw.after_model(_state(HumanMessage(content="hi")), None) is None
    assert mw.after_model(_state(), None) is None


@pytest.mark.asyncio
async def test_async_path_parity():
    """SSE 走 async 路径,aafter_model 必须与同步实现一致。"""
    ai = AIMessage(content="", invalid_tool_calls=[_invalid_call("call_00_bad")])
    updates = await mw.aafter_model(_state(ai), None)
    assert updates is not None
    assert updates["jump_to"] == "model"
    assert updates["messages"][0].tool_call_id == "call_00_bad"


# ---------------------------------------------------------------------------
# 真图集成:langchain.agents.create_agent + 脚本化假模型
# ---------------------------------------------------------------------------


class ScriptedModel(BaseChatModel):
    """按脚本依次吐出 AIMessage 的假模型(支持 bind_tools)。"""

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
        return ChatResult(generations=[ChatGeneration(message=self.script[index])])


@tool
def toy_tool(text: str) -> str:
    """回显输入文本。"""
    return f"echoed: {text}"


def _build_agent(model: ScriptedModel):
    from langchain.agents import create_agent

    return create_agent(
        model=model,
        tools=[toy_tool],
        middleware=[repair_invalid_tool_calls_middleware],
    )


def test_graph_all_invalid_repairs_and_retries_to_success():
    """全 invalid → 补 error ToolMessage → jump 回 model → 修正后正常收尾。"""
    model = ScriptedModel(
        script=[
            AIMessage(content="", invalid_tool_calls=[_invalid_call("call_00_bad")]),
            AIMessage(content="", tool_calls=[_valid_call("call_01_ok")]),
            AIMessage(content="完成"),
        ]
    )
    agent = _build_agent(model)
    result = agent.invoke({"messages": [HumanMessage(content="试试")]})
    messages = result["messages"]

    assert len(model.calls) == 3  # bad → (jump) retry → tool → final
    tool_msgs = {m.tool_call_id: m for m in messages if isinstance(m, ToolMessage)}
    assert tool_msgs["call_00_bad"].status == "error"
    assert "echoed" in tool_msgs["call_01_ok"].content
    # 每个 AIMessage 的 invalid/tool call 都有配对回包 → 不会再触发协议 400
    answered = set(tool_msgs)
    for m in messages:
        if isinstance(m, AIMessage):
            for call in (*m.tool_calls, *m.invalid_tool_calls):
                assert call["id"] in answered
    assert messages[-1].content == "完成"


def test_graph_persistent_invalid_gives_up_after_budget():
    """连续全 invalid:1 次原始 + MAX 次重试后放弃,回合正常结束且配对完整。"""
    model = ScriptedModel(
        script=[
            AIMessage(content="", invalid_tool_calls=[_invalid_call(f"call_00_bad{i}")])
            for i in range(MAX_ALL_INVALID_RETRIES + 2)
        ]
    )
    agent = _build_agent(model)
    result = agent.invoke({"messages": [HumanMessage(content="试试")]})
    messages = result["messages"]

    assert len(model.calls) == MAX_ALL_INVALID_RETRIES + 1
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    for m in messages:
        if isinstance(m, AIMessage):
            for call in m.invalid_tool_calls:
                assert call["id"] in answered
