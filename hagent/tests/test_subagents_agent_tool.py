"""Tests for hagent.subagents.agent_tool.build_agent_tool.

Note on test invocation pattern:
    `ToolRuntime` is injected by Pregel during graph execution. There is no
    public, supported way to inject it via `tool.invoke(...)`'s RunnableConfig
    in this langchain_core 1.4.0 / langgraph version. We therefore call the
    underlying function directly via `tool.func(...)` (and `tool.coroutine`
    for the async path). This is the same approach used by deepagents'
    internal tests and exercises the implementation contract precisely.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command

from hagent.subagents.agent_tool import AgentToolInput, build_agent_tool


class _RecordingRunnable:
    """Stand-in for a compiled subagent runnable. Records every invoke."""

    def __init__(self, name: str, response_text: str = "done", extra_state: dict | None = None):
        self.name = name
        self.response_text = response_text
        self.extra_state = extra_state or {}
        self.invocations: list[tuple[dict, dict]] = []
        self.ainvocations: list[tuple[dict, dict]] = []

    def invoke(self, state: dict, config: dict) -> dict:
        self.invocations.append((state, config))
        return {
            "messages": [AIMessage(content=self.response_text)],
            **self.extra_state,
        }

    async def ainvoke(self, state: dict, config: dict) -> dict:
        self.ainvocations.append((state, config))
        return {
            "messages": [AIMessage(content=self.response_text)],
            **self.extra_state,
        }


def _runtime(
    *,
    tool_call_id: str = "call-1",
    state: dict | None = None,
    config: dict | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        tool_call_id=tool_call_id,
        state=state if state is not None else {"messages": ["should_be_dropped"]},
        config=config if config is not None else {},
    )


def _runnables() -> dict[str, _RecordingRunnable]:
    return {
        "general-purpose": _RecordingRunnable("general-purpose", "general done"),
        "Explore": _RecordingRunnable("Explore", "explore done"),
        "Plan": _RecordingRunnable("Plan", "plan done"),
    }


# ---------------------------------------------------------------------------
# 1. name
# ---------------------------------------------------------------------------
def test_agent_tool_name_is_Agent():
    tool = build_agent_tool(_runnables(), description="any-description")
    assert isinstance(tool, StructuredTool)
    assert tool.name == "Agent"


# ---------------------------------------------------------------------------
# 2. description pass-through
# ---------------------------------------------------------------------------
def test_agent_tool_description_passed_through():
    desc = "Launch a specialized subagent. Available: general-purpose, Explore, Plan."
    tool = build_agent_tool(_runnables(), description=desc)
    assert tool.description == desc


# ---------------------------------------------------------------------------
# 3. schema: description+prompt required, subagent_type optional
# ---------------------------------------------------------------------------
def test_agent_tool_schema_has_required_and_optional_fields():
    tool = build_agent_tool(_runnables(), description="d")
    schema = tool.args_schema.model_json_schema()
    props = schema["properties"]
    required = set(schema.get("required", []))

    assert "description" in props
    assert "prompt" in props
    assert "subagent_type" in props

    assert required == {"description", "prompt"}
    # subagent_type is optional → not in required, has default of None
    assert "subagent_type" not in required
    assert props["subagent_type"].get("default", "MISSING") is None

    # And the pydantic class itself behaves accordingly.
    obj = AgentToolInput(description="d", prompt="p")
    assert obj.subagent_type is None


# ---------------------------------------------------------------------------
# 4. routing default → general-purpose; HumanMessage(prompt) is injected
# ---------------------------------------------------------------------------
def test_agent_tool_routes_to_default_general_purpose_when_subagent_type_omitted():
    runnables = _runnables()
    tool = build_agent_tool(runnables, description="d")
    runtime = _runtime()

    result = tool.func(
        description="short label",
        prompt="please do X",
        subagent_type=None,
        runtime=runtime,
    )

    # general-purpose runnable was called exactly once; others not at all.
    assert len(runnables["general-purpose"].invocations) == 1
    assert len(runnables["Explore"].invocations) == 0
    assert len(runnables["Plan"].invocations) == 0

    sent_state, _sent_config = runnables["general-purpose"].invocations[0]
    assert isinstance(sent_state["messages"], list)
    assert len(sent_state["messages"]) == 1
    assert isinstance(sent_state["messages"][0], HumanMessage)
    assert sent_state["messages"][0].content == "please do X"

    assert isinstance(result, Command)


# ---------------------------------------------------------------------------
# 5. routing by explicit subagent_type
# ---------------------------------------------------------------------------
def test_agent_tool_routes_by_subagent_type():
    runnables = _runnables()
    tool = build_agent_tool(runnables, description="d")
    runtime = _runtime()

    tool.func(
        description="label",
        prompt="explore this",
        subagent_type="Explore",
        runtime=runtime,
    )

    assert len(runnables["Explore"].invocations) == 1
    assert len(runnables["general-purpose"].invocations) == 0
    assert len(runnables["Plan"].invocations) == 0


# ---------------------------------------------------------------------------
# 6. unknown subagent_type returns error string
# ---------------------------------------------------------------------------
def test_agent_tool_unknown_subagent_type_returns_error_string():
    runnables = _runnables()
    tool = build_agent_tool(runnables, description="d")
    runtime = _runtime()

    result = tool.func(
        description="label",
        prompt="do thing",
        subagent_type="not-a-real-agent",
        runtime=runtime,
    )

    assert isinstance(result, str)
    assert "not-a-real-agent" in result
    # error string must mention the registered subagents
    for name in runnables:
        assert name in result


# ---------------------------------------------------------------------------
# 7. returns Command with ToolMessage; tool_call_id preserved; content rtrim
# ---------------------------------------------------------------------------
def test_agent_tool_returns_command_with_tool_message():
    runnables = {
        "general-purpose": _RecordingRunnable(
            "general-purpose", response_text="all done   \n\n  "
        )
    }
    tool = build_agent_tool(runnables, description="d")
    runtime = _runtime(tool_call_id="tc-42")

    result = tool.func(
        description="label",
        prompt="do thing",
        subagent_type=None,
        runtime=runtime,
    )

    assert isinstance(result, Command)
    update = result.update
    assert "messages" in update
    msgs = update["messages"]
    assert len(msgs) == 1
    msg = msgs[0]
    assert isinstance(msg, ToolMessage)
    assert msg.tool_call_id == "tc-42"
    # right-trimmed
    assert msg.content == "all done"


# ---------------------------------------------------------------------------
# 8. parent state excludes messages/todos/structured_response; preserves rest
# ---------------------------------------------------------------------------
def test_agent_tool_excludes_messages_todos_from_passed_state():
    runnables = _runnables()
    tool = build_agent_tool(runnables, description="d")
    parent_state = {
        "messages": [HumanMessage(content="parent msg")],
        "todos": [{"id": 1, "content": "x"}],
        "structured_response": {"foo": "bar"},
        "files": {"a.txt": "hello"},
        "session_workspace": "/tmp/ws",
    }
    runtime = _runtime(state=parent_state)

    tool.func(
        description="label",
        prompt="hi",
        subagent_type=None,
        runtime=runtime,
    )

    sent_state, _ = runnables["general-purpose"].invocations[0]
    # excluded keys must not contain parent values; messages was overwritten
    assert "todos" not in sent_state
    assert "structured_response" not in sent_state
    # messages key exists but contains only the new HumanMessage(prompt)
    assert len(sent_state["messages"]) == 1
    assert isinstance(sent_state["messages"][0], HumanMessage)
    assert sent_state["messages"][0].content == "hi"
    # other state keys are preserved
    assert sent_state["files"] == {"a.txt": "hello"}
    assert sent_state["session_workspace"] == "/tmp/ws"


# ---------------------------------------------------------------------------
# 9. raises when tool_call_id is missing
# ---------------------------------------------------------------------------
def test_agent_tool_raises_when_tool_call_id_missing():
    runnables = _runnables()
    tool = build_agent_tool(runnables, description="d")
    runtime = _runtime(tool_call_id="")

    with pytest.raises(ValueError):
        tool.func(
            description="label",
            prompt="hi",
            subagent_type=None,
            runtime=runtime,
        )


# ---------------------------------------------------------------------------
# 10. async path mirrors sync behavior
# ---------------------------------------------------------------------------
def test_agent_tool_async_path_routes_and_returns_command():
    runnables = _runnables()
    tool = build_agent_tool(runnables, description="d")
    runtime = _runtime(tool_call_id="tc-async")

    result = asyncio.run(
        tool.coroutine(
            description="label",
            prompt="do async",
            subagent_type="Plan",
            runtime=runtime,
        )
    )

    assert len(runnables["Plan"].ainvocations) == 1
    sent_state, _ = runnables["Plan"].ainvocations[0]
    assert sent_state["messages"][0].content == "do async"

    assert isinstance(result, Command)
    msg = result.update["messages"][0]
    assert isinstance(msg, ToolMessage)
    assert msg.tool_call_id == "tc-async"


# ---------------------------------------------------------------------------
# 11. config forwarding: callbacks/tags/configurable propagate; others don't
# ---------------------------------------------------------------------------
def test_agent_tool_forwards_only_callbacks_tags_configurable_from_parent_config():
    runnables = _runnables()
    tool = build_agent_tool(runnables, description="d")
    parent_config = {
        "callbacks": ["cb1"],
        "tags": ["t1"],
        "configurable": {"foo": "bar"},
        "recursion_limit": 99,
        "metadata": {"x": "y"},
    }
    runtime = _runtime(config=parent_config)

    tool.func(
        description="label",
        prompt="hi",
        subagent_type=None,
        runtime=runtime,
    )

    _state, sent_config = runnables["general-purpose"].invocations[0]
    assert sent_config.get("callbacks") == ["cb1"]
    assert sent_config.get("tags") == ["t1"]
    # parent configurable keys flow through; ls_agent_type is added by _forward_config
    assert sent_config.get("configurable", {}).get("foo") == "bar"
    assert "recursion_limit" not in sent_config
    # 父级 metadata 不泄漏到子代理（子代理 bound config 必须赢）……
    assert sent_config.get("metadata", {}).get("x") is None
    # ……但 _forward_config 会注入归属用的 parent_tool_use_id（= 本次 Agent 的 tool_call_id）。
    assert sent_config["metadata"]["parent_tool_use_id"] == "call-1"


# ---------------------------------------------------------------------------
# 11b. 子代理归属：注入 parent_tool_use_id（对齐 CC parentToolUseID）
# ---------------------------------------------------------------------------
def test_agent_tool_injects_tool_call_id_as_parent_tool_use_id():
    """Agent 工具把自己的 tool_call_id 注入子代理 config.metadata，
    使子代理流式 token 带精确归属，前端据此分组（不再靠 liveness 猜测，
    避免并行多 Agent 串台/无限嵌套）。"""
    runnables = _runnables()
    tool = build_agent_tool(runnables, "d")
    tool.func(
        description="x",
        prompt="y",
        subagent_type=None,
        runtime=_runtime(tool_call_id="agent-77"),
    )
    _state, sent_config = runnables["general-purpose"].invocations[0]
    assert sent_config["metadata"]["parent_tool_use_id"] == "agent-77"


def test_agent_tool_async_injects_tool_call_id_as_parent_tool_use_id():
    import asyncio

    runnables = _runnables()
    tool = build_agent_tool(runnables, "d")
    asyncio.run(
        tool.coroutine(
            description="x",
            prompt="y",
            subagent_type=None,
            runtime=_runtime(tool_call_id="agent-async-9"),
        )
    )
    _state, sent_config = runnables["general-purpose"].ainvocations[0]
    assert sent_config["metadata"]["parent_tool_use_id"] == "agent-async-9"


# ---------------------------------------------------------------------------
# 12. configurable tagged with ls_agent_type="subagent" for LangSmith
# ---------------------------------------------------------------------------
def test_agent_tool_tags_subagent_configurable_with_ls_agent_type():
    """LangSmith tracing distinguishes subagent runs from parent via configurable."""
    runnables = _runnables()
    tool = build_agent_tool(runnables, "d")
    tool.func(
        description="x",
        prompt="y",
        subagent_type=None,
        runtime=_runtime(config={"configurable": {"thread_id": "t1"}}),
    )
    _state, forwarded_config = runnables["general-purpose"].invocations[0]
    assert forwarded_config["configurable"]["ls_agent_type"] == "subagent"
    # original parent configurable keys still flow through
    assert forwarded_config["configurable"]["thread_id"] == "t1"
