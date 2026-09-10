"""CC-aligned `Agent` tool.

Builds a `StructuredTool` named ``Agent`` whose schema mirrors the Claude
Code `Agent` tool:

- ``description`` (required): short 3-5 word label shown to the user.
- ``prompt`` (required): full task brief the subagent will see.
- ``subagent_type`` (optional): name of a pre-registered subagent.
  Omit to route to ``general-purpose``.

The tool routes to pre-compiled subagent runnables (built by Task 5's
compiler). State pass-through excludes ``messages`` / ``todos`` /
``structured_response`` and injects ``[HumanMessage(prompt)]`` before
invoking the subagent. Returns a ``Command`` updating the parent's
``messages`` with a ``ToolMessage`` carrying the subagent's final
right-trimmed message text and the original ``tool_call_id``.
"""

from typing import Any

# IMPORTANT: do NOT add `from __future__ import annotations` to this file.
# LangChain's StructuredTool detects ToolRuntime injection by reading the live
# annotation object on the function signature (issubclass check against
# _DirectlyInjectedToolArg). Under PEP 563 / `__future__.annotations`, those
# annotations become strings and the injector silently no-ops, so the live
# agent fails with `missing 1 required positional argument: 'runtime'`.
# deepagents' equivalent task() tool in middleware/subagents.py keeps eager
# annotations for the same reason.
from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command
from pydantic import BaseModel, Field

from hagent.hooks.events import HookEvent

# State keys that are excluded when passing state to subagents.
# Deepagents 0.5.9 also excludes skills_metadata/skills_load_errors/memory_contents
# (see deepagents/middleware/subagents.py:186-193). Hagent doesn't wire SkillsMiddleware
# or MemoryMiddleware, so the narrower set is correct today. Extend this set if those
# middleware ever land in Hagent.
_EXCLUDED_STATE_KEYS: frozenset[str] = frozenset(
    {"messages", "todos", "structured_response"}
)
_DEFAULT_SUBAGENT = "general-purpose"


class AgentToolInput(BaseModel):
    """CC-aligned Agent tool input schema."""

    description: str = Field(
        description=(
            "A short (3-5 word) description of the task. Shown to the user as a label."
        )
    )
    prompt: str = Field(
        description=(
            "The full task brief for the subagent. The subagent does not see the "
            "parent conversation; include all the context it needs."
        )
    )
    subagent_type: str | None = Field(
        default=None,
        description=(
            "The type of specialized subagent to use. Omit to use the "
            "general-purpose agent. Must match one of the available agent types "
            "listed in the tool description."
        ),
    )


def _prepare_state(runtime: ToolRuntime, prompt: str) -> dict[str, Any]:
    """Build the subagent's input state from the parent runtime's state.

    Excludes ``messages`` / ``todos`` / ``structured_response`` so the
    subagent starts clean, then injects the user-supplied prompt as the
    sole ``HumanMessage``.
    """
    parent_state = runtime.state or {}
    state: dict[str, Any] = {
        k: v for k, v in parent_state.items() if k not in _EXCLUDED_STATE_KEYS
    }
    state["messages"] = [HumanMessage(content=prompt)]
    return state


def _forward_config(runtime: ToolRuntime) -> dict[str, Any]:
    """Forward only the safe-to-propagate keys from the parent's config.

    Mirrors deepagents' behavior: ``callbacks`` / ``tags`` / ``configurable``
    pass through; ``recursion_limit`` / parent ``metadata`` do not (the
    subagent's bound config must win).

    We DO set a fresh ``metadata`` carrying ``parent_tool_use_id`` = this
    Agent call's ``tool_call_id``. ``callbacks`` propagation makes the
    subagent's run stream under the parent (``subgraphs=True``), and this
    metadata then rides along on every streamed token's metadata, so the SSE
    adapter (``server/sse.py``) can attribute each subagent event to the
    spawning Agent call — the CC ``parentToolUseID`` model. This is the only
    reliable signal: the LangGraph subgraph namespace task-id is NOT the
    tool_call_id, and parallel subagents spawned in one turn even share a
    namespace prefix, so namespace-based attribution would collide.
    """
    parent = runtime.config or {}
    out: dict[str, Any] = {}
    for key in ("callbacks", "tags", "configurable"):
        if key in parent:
            out[key] = parent[key]
    # Tag subagent runs so LangSmith / downstream middleware can distinguish
    # them from the parent agent. Mirrors deepagents subagents.py:485-491.
    out["configurable"] = {**out.get("configurable", {}), "ls_agent_type": "subagent"}
    out["metadata"] = {"parent_tool_use_id": runtime.tool_call_id}
    run_id = (parent.get("metadata") or {}).get("run_id")
    if run_id is not None:
        out["metadata"]["run_id"] = run_id
    return out


def _finalize(result: Any, tool_call_id: str) -> Command:
    """Turn the subagent's terminal state into a Command for the parent."""
    content = ""
    msgs = result.get("messages") if isinstance(result, dict) else None
    if msgs:
        last = msgs[-1]
        text = getattr(last, "text", None)
        if text is None:
            text = getattr(last, "content", "")
            if isinstance(text, list):
                text = "".join(
                    block.get("text", "")
                    for block in text
                    if isinstance(block, dict)
                )
        content = (text or "").rstrip()
    state_update: dict[str, Any] = {
        k: v
        for k, v in (result or {}).items()
        if k not in _EXCLUDED_STATE_KEYS
    }
    return Command(
        update={
            **state_update,
            "messages": [ToolMessage(content, tool_call_id=tool_call_id)],
        }
    )


def _unknown_subagent_error(target: str, runnables: dict[str, Any]) -> str:
    available = ", ".join(f"`{k}`" for k in runnables)
    return (
        f"Cannot invoke subagent '{target}' — not registered. "
        f"Available subagents: {available}."
    )


def build_agent_tool(
    runnables: dict[str, Any],
    description: str,
    hook_runner: Any | None = None,
) -> StructuredTool:
    """Build the CC-aligned `Agent` tool.

    Args:
        runnables: Mapping of subagent name → compiled runnable (the kind
            built by ``hagent.subagents.compiler.compile_subagent_runnable``).
            Must contain a ``general-purpose`` entry — that's where
            ``subagent_type=None`` routes.
        description: The string to use as the tool's description. Callers
            are expected to render the available-subagents list into it
            (see Task 7).

    Returns:
        A ``StructuredTool`` named ``"Agent"`` with ``args_schema =
        AgentToolInput``.
    """

    def _subagent_start_fields(target: str, runtime: ToolRuntime) -> dict:
        return {"agent_id": runtime.tool_call_id or "", "agent_type": target}

    def _apply_start_contexts(prompt: str, agg: Any) -> str:
        # SubagentStart：blocking 忽略（CC 语义）；additionalContext/stdout 注入
        contexts = getattr(agg, "contexts", None) or []
        if contexts:
            return prompt + "\n\n" + "\n".join(contexts)
        return prompt

    def agent(
        description: str,
        prompt: str,
        subagent_type: str | None,
        runtime: ToolRuntime,
    ) -> Any:
        if not runtime.tool_call_id:
            raise ValueError(
                "Agent tool invocation requires runtime.tool_call_id"
            )
        target = subagent_type or _DEFAULT_SUBAGENT
        if target not in runnables:
            return _unknown_subagent_error(target, runnables)
        runnable = runnables[target]
        if hook_runner is not None and hook_runner.has_hooks(HookEvent.SUBAGENT_START):
            agg = hook_runner.run(
                HookEvent.SUBAGENT_START, _subagent_start_fields(target, runtime)
            )
            prompt = _apply_start_contexts(prompt, agg)
        state = _prepare_state(runtime, prompt)
        config = _forward_config(runtime)
        result = runnable.invoke(state, config)
        return _finalize(result, runtime.tool_call_id)

    async def aagent(
        description: str,
        prompt: str,
        subagent_type: str | None,
        runtime: ToolRuntime,
    ) -> Any:
        if not runtime.tool_call_id:
            raise ValueError(
                "Agent tool invocation requires runtime.tool_call_id"
            )
        target = subagent_type or _DEFAULT_SUBAGENT
        if target not in runnables:
            return _unknown_subagent_error(target, runnables)
        runnable = runnables[target]
        if hook_runner is not None and hook_runner.has_hooks(HookEvent.SUBAGENT_START):
            agg = await hook_runner.arun(
                HookEvent.SUBAGENT_START, _subagent_start_fields(target, runtime)
            )
            prompt = _apply_start_contexts(prompt, agg)
        state = _prepare_state(runtime, prompt)
        config = _forward_config(runtime)
        result = await runnable.ainvoke(state, config)
        return _finalize(result, runtime.tool_call_id)

    return StructuredTool.from_function(
        name="Agent",
        func=agent,
        coroutine=aagent,
        description=description,
        infer_schema=False,
        args_schema=AgentToolInput,
    )


__all__ = ["AgentToolInput", "build_agent_tool"]
