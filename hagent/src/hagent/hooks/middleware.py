"""HagentHooksMiddleware —— hook 事件在 LangGraph 图内的接线。

- PreToolUse / PostToolUse / PostToolUseFailure：``wrap_tool_call`` /
  ``awrap_tool_call``。deny 短路 = 不调 handler 直接返回 error ToolMessage
  （等价 CC「exit 2 stderr 给模型」）；``updatedInput`` 经
  ``request.override(tool_call=...)`` 改写；additionalContext 以
  ``<system-reminder>`` 追加到 ToolMessage 尾部（LangGraph 无独立
  attachment 通道，模型可见性与 CC 等价）。
- Stop：``after_model`` / ``aafter_model``（两者都必须挂
  ``@hook_config(can_jump_to=["model"])``）。阻断时返回
  ``{"messages": [HumanMessage(...)], "jump_to": "model"}`` 让图回到 model
  节点继续对话（CC 语义：stderr 作为新用户消息）。防死循环双保险：
  payload 的 ``stop_hook_active``（CC 语义）+ ``hagent_stop_block_count``
  硬上限（hagent 附加保护，服务端无人工 Ctrl+C）。

所有钩子 sync + async 成对实现（LangGraph 的 sync .stream() 内部桥接
async，sync-only middleware 会在 SSE 路径静默失效 —— 见 core.py 的
SanitizeAnthropicThinkingBlocksMiddleware 注释）。
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, NotRequired

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import (
    AgentState,
    PrivateStateAttr,
    hook_config,
)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from hagent.hooks.events import HookEvent
from hagent.hooks.runner import HookAggregate, HookRunner

logger = logging.getLogger(__name__)

MAX_STOP_BLOCKS = 5

_TOOL_EVENTS = (
    HookEvent.PRE_TOOL_USE,
    HookEvent.POST_TOOL_USE,
    HookEvent.POST_TOOL_USE_FAILURE,
)


class HooksAgentState(AgentState):
    hagent_stop_hook_active: NotRequired[Annotated[bool, PrivateStateAttr]]
    hagent_stop_block_count: NotRequired[Annotated[int, PrivateStateAttr]]


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return str(content)


def _append_context(message: ToolMessage, notes: list[str]) -> ToolMessage:
    if not notes:
        return message
    reminder = "\n\n".join(f"<system-reminder>\n{n}\n</system-reminder>" for n in notes)
    content = message.content
    if isinstance(content, str):
        new_content: Any = f"{content}\n\n{reminder}" if content else reminder
    elif isinstance(content, list):
        new_content = [*content, {"type": "text", "text": f"\n\n{reminder}"}]
    else:
        new_content = f"{content}\n\n{reminder}"
    return message.model_copy(update={"content": new_content})


class HagentHooksMiddleware(AgentMiddleware):
    state_schema = HooksAgentState
    name = "HagentHooks"

    def __init__(
        self,
        runner: HookRunner,
        *,
        stop_event: HookEvent = HookEvent.STOP,
        max_stop_blocks: int = MAX_STOP_BLOCKS,
    ) -> None:
        """stop_event: 主图用 Stop；子代理图用 SubagentStop（CC 语义）。"""
        super().__init__()
        self.runner = runner
        self.stop_event = stop_event
        self.max_stop_blocks = max_stop_blocks

    # ------------------------------------------------------------------
    # PreToolUse / PostToolUse / PostToolUseFailure
    # ------------------------------------------------------------------

    def _pre_fields(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool_name": tool_call.get("name", ""),
            "tool_input": tool_call.get("args", {}),
            "tool_use_id": tool_call.get("id", ""),
        }

    def _pre_short_circuit(
        self, agg: HookAggregate, tool_call: dict[str, Any]
    ) -> tuple[ToolMessage | None, str | None]:
        """deny / ask（降级）/ 阻断 → (替代 ToolMessage, deny 原因)；否则 (None, None)。"""
        decision = agg.permission_decision
        if decision == "deny" or (decision is None and agg.blocked):
            reason = (
                agg.permission_reason
                or agg.block_reason
                or agg.stop_reason
                or "Blocked by PreToolUse hook"
            )
            return (
                ToolMessage(
                    content=f"PreToolUse hook denied this tool call: {reason}",
                    status="error",
                    tool_call_id=tool_call.get("id", ""),
                    name=tool_call.get("name"),
                ),
                reason,
            )
        if decision == "ask":
            reason = agg.permission_reason or "requires approval"
            return (
                ToolMessage(
                    content=(
                        "PreToolUse hook returned permissionDecision \"ask\": "
                        f"{reason}. 交互式审批尚未接通（P1 HITL），本次按 deny 处理。"
                    ),
                    status="error",
                    tool_call_id=tool_call.get("id", ""),
                    name=tool_call.get("name"),
                ),
                reason,
            )
        return None, None

    def _denied_fields(
        self, tool_call: dict[str, Any], reason: str
    ) -> dict[str, Any]:
        return {
            "tool_name": tool_call.get("name", ""),
            "tool_input": tool_call.get("args", {}),
            "tool_use_id": tool_call.get("id", ""),
            "reason": reason,
        }

    @staticmethod
    def _apply_updated_input(request: Any, agg: HookAggregate) -> Any:
        if agg.updated_input is None:
            return request
        tool_call = {**request.tool_call, "args": agg.updated_input}
        return request.override(tool_call=tool_call)

    def _post_fields(
        self, request: Any, result: Any
    ) -> dict[str, Any]:
        tool_call = request.tool_call
        return {
            "tool_name": tool_call.get("name", ""),
            "tool_input": tool_call.get("args", {}),
            "tool_response": getattr(result, "content", str(result)),
            "tool_use_id": tool_call.get("id", ""),
        }

    def _fail_fields(self, request: Any, error: str) -> dict[str, Any]:
        tool_call = request.tool_call
        return {
            "tool_name": tool_call.get("name", ""),
            "tool_input": tool_call.get("args", {}),
            "tool_use_id": tool_call.get("id", ""),
            "error": error,
        }

    @staticmethod
    def _post_notes(agg: HookAggregate) -> list[str]:
        notes = list(agg.contexts)
        if agg.block_reasons:
            # 工具已执行，exit 2 的 stderr 立即给模型（CC PostToolUse 语义）
            notes.append(f"PostToolUse hook feedback (blocking): {agg.block_reason}")
        return notes

    def wrap_tool_call(self, request: Any, handler: Any) -> Any:
        if not self.runner.has_hooks(*_TOOL_EVENTS):
            return handler(request)
        pre_notes: list[str] = []
        if self.runner.has_hooks(HookEvent.PRE_TOOL_USE):
            agg = self.runner.run(
                HookEvent.PRE_TOOL_USE, self._pre_fields(request.tool_call)
            )
            short, deny_reason = self._pre_short_circuit(agg, request.tool_call)
            if short is not None:
                if deny_reason and self.runner.has_hooks(HookEvent.PERMISSION_DENIED):
                    self.runner.run(
                        HookEvent.PERMISSION_DENIED,
                        self._denied_fields(request.tool_call, deny_reason),
                    )
                return short
            request = self._apply_updated_input(request, agg)
            pre_notes = list(agg.contexts)
        try:
            result = handler(request)
        except Exception as exc:
            if self.runner.has_hooks(HookEvent.POST_TOOL_USE_FAILURE):
                self.runner.run(
                    HookEvent.POST_TOOL_USE_FAILURE,
                    self._fail_fields(request, str(exc)),
                )
            raise
        return self._handle_result_sync(request, result, pre_notes)

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        if not self.runner.has_hooks(*_TOOL_EVENTS):
            return await handler(request)
        pre_notes: list[str] = []
        if self.runner.has_hooks(HookEvent.PRE_TOOL_USE):
            agg = await self.runner.arun(
                HookEvent.PRE_TOOL_USE, self._pre_fields(request.tool_call)
            )
            short, deny_reason = self._pre_short_circuit(agg, request.tool_call)
            if short is not None:
                if deny_reason and self.runner.has_hooks(HookEvent.PERMISSION_DENIED):
                    await self.runner.arun(
                        HookEvent.PERMISSION_DENIED,
                        self._denied_fields(request.tool_call, deny_reason),
                    )
                return short
            request = self._apply_updated_input(request, agg)
            pre_notes = list(agg.contexts)
        try:
            result = await handler(request)
        except Exception as exc:
            if self.runner.has_hooks(HookEvent.POST_TOOL_USE_FAILURE):
                await self.runner.arun(
                    HookEvent.POST_TOOL_USE_FAILURE,
                    self._fail_fields(request, str(exc)),
                )
            raise
        return await self._handle_result_async(request, result, pre_notes)

    def _handle_result_sync(
        self, request: Any, result: Any, pre_notes: list[str]
    ) -> Any:
        if not isinstance(result, ToolMessage):
            # Command 等非 ToolMessage 结果：只跑 hook，不改写
            if self.runner.has_hooks(HookEvent.POST_TOOL_USE):
                self.runner.run(
                    HookEvent.POST_TOOL_USE, self._post_fields(request, result)
                )
            return result
        if result.status == "error":
            if self.runner.has_hooks(HookEvent.POST_TOOL_USE_FAILURE):
                agg = self.runner.run(
                    HookEvent.POST_TOOL_USE_FAILURE,
                    self._fail_fields(request, _message_text(result)),
                )
                return _append_context(result, pre_notes + list(agg.contexts))
            return _append_context(result, pre_notes)
        if self.runner.has_hooks(HookEvent.POST_TOOL_USE):
            agg = self.runner.run(
                HookEvent.POST_TOOL_USE, self._post_fields(request, result)
            )
            return _append_context(result, pre_notes + self._post_notes(agg))
        return _append_context(result, pre_notes)

    async def _handle_result_async(
        self, request: Any, result: Any, pre_notes: list[str]
    ) -> Any:
        if not isinstance(result, ToolMessage):
            if self.runner.has_hooks(HookEvent.POST_TOOL_USE):
                await self.runner.arun(
                    HookEvent.POST_TOOL_USE, self._post_fields(request, result)
                )
            return result
        if result.status == "error":
            if self.runner.has_hooks(HookEvent.POST_TOOL_USE_FAILURE):
                agg = await self.runner.arun(
                    HookEvent.POST_TOOL_USE_FAILURE,
                    self._fail_fields(request, _message_text(result)),
                )
                return _append_context(result, pre_notes + list(agg.contexts))
            return _append_context(result, pre_notes)
        if self.runner.has_hooks(HookEvent.POST_TOOL_USE):
            agg = await self.runner.arun(
                HookEvent.POST_TOOL_USE, self._post_fields(request, result)
            )
            return _append_context(result, pre_notes + self._post_notes(agg))
        return _append_context(result, pre_notes)

    # ------------------------------------------------------------------
    # Stop
    # ------------------------------------------------------------------

    def _should_fire_stop(self, state: dict[str, Any]) -> AIMessage | None:
        """即将自然停止（最后一条是无 tool_calls 的 AIMessage）时返回该消息。"""
        messages = state.get("messages") or []
        last = messages[-1] if messages else None
        if not isinstance(last, AIMessage) or last.tool_calls:
            return None
        if not self.runner.has_hooks(self.stop_event):
            return None
        return last

    def _stop_fields(self, state: dict[str, Any], last: AIMessage) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "stop_hook_active": bool(state.get("hagent_stop_hook_active")),
        }
        if self.stop_event == HookEvent.SUBAGENT_STOP:
            ctx = self.runner.ctx
            fields["agent_id"] = ctx.agent_id or ""
            fields["agent_type"] = ctx.agent_type or ""
            fields["agent_transcript_path"] = str(ctx.transcript_path)
        text = _message_text(last)
        if text:
            fields["last_assistant_message"] = text
        return fields

    def _stop_updates(
        self, state: dict[str, Any], agg: HookAggregate
    ) -> dict[str, Any] | None:
        # 对齐 CC stopHooks：blockingError 优先（阻止停止、继续对话）；
        # 仅 continue:false 而无 blockingError 时按停机处理
        if not agg.block_reasons:
            if state.get("hagent_stop_hook_active") or state.get(
                "hagent_stop_block_count"
            ):
                return {
                    "hagent_stop_hook_active": False,
                    "hagent_stop_block_count": 0,
                }
            return None
        count = int(state.get("hagent_stop_block_count") or 0) + 1
        if count > self.max_stop_blocks:
            logger.warning(
                "Stop hook 连续阻断 %d 次，超过上限 %d，强制放行",
                count,
                self.max_stop_blocks,
            )
            return {"hagent_stop_hook_active": False, "hagent_stop_block_count": 0}
        reason = agg.block_reason or "Stop hook blocked stopping."
        return {
            "messages": [HumanMessage(content=f"Stop hook feedback:\n{reason}")],
            "jump_to": "model",
            "hagent_stop_hook_active": True,
            "hagent_stop_block_count": count,
        }

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        last = self._should_fire_stop(state)
        if last is None:
            return None
        agg = self.runner.run(self.stop_event, self._stop_fields(state, last))
        return self._stop_updates(state, agg)

    @hook_config(can_jump_to=["model"])
    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        last = self._should_fire_stop(state)
        if last is None:
            return None
        agg = await self.runner.arun(self.stop_event, self._stop_fields(state, last))
        return self._stop_updates(state, agg)
