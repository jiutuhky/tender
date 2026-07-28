"""模型响应修复：为 invalid_tool_calls 合成 error ToolMessage，堵住协议 400。

模型（尤见 DeepSeek 的 Anthropic 兼容端点）偶发生成参数 JSON 非法的
tool call——如把招标原文里的英文双引号原样抄进字符串值。LangChain 会把
这类调用归入 ``AIMessage.invalid_tool_calls``，而工具节点只执行合法的
``tool_calls``：invalid 调用永远等不到 ToolMessage 回包，但 content 里的
``tool_use`` 块原样保留，下一次模型调用即被 Anthropic 协议校验拒绝
（tool_use 无配对 tool_result → 400，2026-07-15 解析中断事故）。

deepagents 自带的 ``PatchToolCallsMiddleware`` 只在 ``before_agent`` 修
跨 run 的历史遗留悬空调用，救不了同一 run 循环内的这种情况；路由又只认
``tool_calls``（全部 invalid 时连 tools 节点都不进、回合静默结束）。

本 middleware 在 ``after_model`` 兜底：

- 每个 invalid_tool_call 追加一条 ``status="error"`` 的 ToolMessage，
  提示模型参数非法、修正后重发——协议配对与自愈重试一并解决；
- 全部调用皆 invalid 时 ``jump_to`` 回 model 让模型立刻重试（有限次，
  防坏 JSON 死循环；耗尽后让回合正常结束，此时协议配对仍完整）。

与 sanitize.py 同理独立成模块，供主图（core.py）与子代理图
（subagents/compiler.py）共用。
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
from langchain_core.messages import AIMessage, ToolMessage

logger = logging.getLogger(__name__)

# 连续「全 invalid」响应的模型重试上限，超过即放弃并让回合正常结束。
MAX_ALL_INVALID_RETRIES = 3


class ToolCallRepairState(AgentState):
    hagent_all_invalid_retries: NotRequired[Annotated[int, PrivateStateAttr]]


def _repair_messages(message: AIMessage) -> list[ToolMessage]:
    valid_ids = {tc.get("id") for tc in message.tool_calls}
    repairs: list[ToolMessage] = []
    for call in message.invalid_tool_calls:
        call_id = call.get("id")
        # 无 id 的 invalid 调用不会以 tool_use 块出现在回传 content 里，
        # 不构成协议悬空；与合法调用同 id 的（理论不可能）也跳过。
        if not call_id or call_id in valid_ids:
            continue
        name = call.get("name") or "unknown"
        error = call.get("error")
        detail = f"（解析错误：{error}）" if error else ""
        repairs.append(
            ToolMessage(
                content=(
                    f"工具调用 {name}（id={call_id}）未执行：参数不是合法 JSON{detail}。"
                    "常见原因是字符串值里的英文双引号未转义。"
                    "请修正参数后重新发起该调用，不要放弃这次操作。"
                ),
                name=name,
                tool_call_id=call_id,
                status="error",
            )
        )
    return repairs


class RepairInvalidToolCallsMiddleware(AgentMiddleware):
    state_schema = ToolCallRepairState
    name = "RepairInvalidToolCalls"

    def _after_model(self, state: Any) -> dict[str, Any] | None:
        messages = state.get("messages") or []
        last = messages[-1] if messages else None
        if not isinstance(last, AIMessage):
            return None
        retries = state.get("hagent_all_invalid_retries", 0)
        if not last.invalid_tool_calls:
            # 干净响应重置重试预算；只有脏过（>0）才写，省 checkpoint 记录。
            return {"hagent_all_invalid_retries": 0} if retries else None
        repairs = _repair_messages(last)
        if not repairs:
            return None
        logger.warning(
            "模型产出 %d 个 invalid tool call，已合成 error ToolMessage 兜底：%s",
            len(repairs),
            [m.tool_call_id for m in repairs],
        )
        update: dict[str, Any] = {"messages": repairs}
        if not last.tool_calls:
            # 全部 invalid：路由不会进 tools 节点，回合会静默结束——
            # 跳回 model 让它带着 error ToolMessage 立刻重试。
            if retries < MAX_ALL_INVALID_RETRIES:
                update["jump_to"] = "model"
                update["hagent_all_invalid_retries"] = retries + 1
            else:
                logger.error(
                    "连续 %d 次全 invalid tool call，停止重试，让回合结束", retries
                )
        return update

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:  # noqa: ARG002
        return self._after_model(state)

    @hook_config(can_jump_to=["model"])
    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:  # noqa: ARG002
        return self._after_model(state)


repair_invalid_tool_calls_middleware = RepairInvalidToolCallsMiddleware()
