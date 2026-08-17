"""ToolErrorGuardMiddleware:工具异常兜底 → error ToolMessage,不炸整条 agent 流。

LangGraph ``ToolNode`` 默认只把入参校验错误(``ToolInvocationError``)转成
ToolMessage,其它异常一路上抛穿过 agent graph,最终在 SSE 层以 ``error{agent_error}``
终止本轮——模型永远看不到出错、无法自我修复(如 ``SandboxUnavailable``、
文件传输 ``OSError``)。``create_deep_agent`` / ``create_agent`` 均不暴露
``handle_tool_errors``,故用 ``wrap_tool_call`` 中间件兜底(与 hooks 中间件同一
挂点;sync + async 成对,SSE 走 async)。

放置位置:hooks 中间件**之后**(内层),使 hooks 能以 ``status="error"`` 的
ToolMessage 触发 PostToolUseFailure。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.errors import GraphBubbleUp

from hagent.sandbox.errors import SandboxUnavailable

logger = logging.getLogger(__name__)


def _error_message(request: Any, exc: BaseException) -> ToolMessage:
    tool_call = getattr(request, "tool_call", None) or {}
    name = tool_call.get("name") if isinstance(tool_call, dict) else None
    call_id = tool_call.get("id", "") if isinstance(tool_call, dict) else ""
    if isinstance(exc, SandboxUnavailable):
        content = str(exc)
    else:
        content = f"Error: tool '{name or 'unknown'}' failed: {type(exc).__name__}: {exc}"
        logger.exception("tool %s 抛出未处理异常,已转为 error ToolMessage", name)
    return ToolMessage(content=content, status="error", tool_call_id=call_id, name=name)


class ToolErrorGuardMiddleware(AgentMiddleware):
    """把工具执行期的非控制流异常转成 ``ToolMessage(status="error")``。"""

    name = "HagentToolErrorGuard"

    def wrap_tool_call(self, request: Any, handler: Any) -> Any:
        try:
            return handler(request)
        except GraphBubbleUp:
            # GraphInterrupt 等控制流异常必须放行(HITL / 子图中断)
            raise
        except Exception as exc:  # noqa: BLE001
            return _error_message(request, exc)

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        try:
            return await handler(request)
        except GraphBubbleUp:
            raise
        except Exception as exc:  # noqa: BLE001
            return _error_message(request, exc)
