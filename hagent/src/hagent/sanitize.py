"""模型消息清洗:剔除 Anthropic 协议无法接受的坏 thinking 块。

独立成模块是为了让主图(core.py)与子代理图(subagents/compiler.py)共用,
后者不能反向 import core(会与 core → subagents 的导入成环)。
"""

from __future__ import annotations

from typing import Any

from langchain.agents.middleware import AgentMiddleware


def sanitize_anthropic_thinking_blocks(messages: list[Any]) -> list[Any]:
    cleaned_messages: list[Any] = []
    for message in messages:
        content = getattr(message, "content", None)
        if not isinstance(content, list):
            cleaned_messages.append(message)
            continue
        cleaned_content = [
            block
            for block in content
            if not (
                isinstance(block, dict)
                and block.get("type") == "thinking"
                and not block.get("thinking")
            )
        ]
        if len(cleaned_content) == len(content):
            cleaned_messages.append(message)
        else:
            cleaned_messages.append(message.model_copy(update={"content": cleaned_content}))
    return cleaned_messages


class SanitizeAnthropicThinkingBlocksMiddleware(AgentMiddleware):
    # @wrap_model_call only attaches wrap_model_call (sync); the async path falls
    # through to AgentMiddleware.awrap_model_call which raises NotImplementedError,
    # which langchain's chain composer treats as "skip this middleware." LangGraph's
    # sync .stream() bridges to async internally, so a sync-only middleware silently
    # no-ops on the live SSE path. Both implementations are required to actually
    # scrub bad thinking blocks (e.g. DeepSeek-via-Anthropic returns signed thinking
    # blocks with no `thinking` field, which Anthropic's API later rejects with
    # `messages[N].content: missing field 'thinking'`).
    name = "SanitizeAnthropicThinkingBlocks"

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        return handler(
            request.override(messages=sanitize_anthropic_thinking_blocks(request.messages))
        )

    async def awrap_model_call(self, request: Any, handler: Any) -> Any:
        return await handler(
            request.override(messages=sanitize_anthropic_thinking_blocks(request.messages))
        )


sanitize_anthropic_thinking_blocks_middleware = SanitizeAnthropicThinkingBlocksMiddleware()
