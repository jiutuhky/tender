"""prompt / agent 型 hook 执行器（LLM 求值）。

对齐 CC exec{Prompt,Agent}Hook：
- ``$ARGUMENTS`` 占位替换为 hook 输入 JSON（无占位则追加，对齐
  substituteArguments 的 appendIfNoPlaceholder）。
- 模型返回 ``{"ok": true}`` 或 ``{"ok": false, "reason": ...}``；
  ok=false → blocking + preventContinuation + stopReason。
- prompt 默认 30s / agent 默认 60s；默认模型 small-fast（Haiku），
  ``HAGENT_HOOKS_SMALL_MODEL`` 可覆盖。
- 不走 agent 主循环（避免递归触发 UserPromptSubmit hook）。
- 与 CC 差异：agent 型用最终回复文本承载 JSON 结论（hagent 无
  StructuredOutput 强制工具）；最大轮次用 recursion_limit 约束。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Callable, Sequence

from hagent.hooks.events import HookEvent, default_timeout_s
from hagent.hooks.results import HookExecutionResult
from hagent.hooks.schema import AgentHookConfig, PromptHookConfig

logger = logging.getLogger(__name__)

DEFAULT_SMALL_MODEL = "claude-haiku-4-5"

# CC execPromptHook 的 system prompt（去 Claude Code 品牌词）
PROMPT_HOOK_SYSTEM = """You are evaluating a hook in an agent harness.

Your response must be a JSON object matching one of the following schemas:
1. If the condition is met, return: {"ok": true}
2. If the condition is not met, return: {"ok": false, "reason": "Reason for why it is not met"}"""

# CC execAgentHook 的 system prompt 适配版（最终结论走末条回复文本）
AGENT_HOOK_SYSTEM = """You are verifying a hook condition in an agent harness.

Use the available tools to inspect the workspace and verify the condition.
Use as few steps as possible - be efficient and direct.

When done, your final reply must be ONLY a JSON object:
- {"ok": true} if the condition is met
- {"ok": false, "reason": "why it is not met"} if the condition is not met"""

ModelFactory = Callable[[str | None], Any]

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def substitute_arguments(prompt: str, json_input: str) -> str:
    if "$ARGUMENTS" in prompt:
        return prompt.replace("$ARGUMENTS", json_input)
    return f"{prompt}\n\n{json_input}"


def _default_model_factory(model: str | None) -> Any:
    from langchain.chat_models import init_chat_model

    name = model or os.environ.get("HAGENT_HOOKS_SMALL_MODEL") or DEFAULT_SMALL_MODEL
    return init_chat_model(name)


def _message_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        return "".join(parts)
    return str(content)


def _verdict_to_result(text: str, hook_kind: str) -> HookExecutionResult:
    """把模型的 {"ok": ...} 结论翻成 HookExecutionResult（对齐 execPromptHook）。"""
    trimmed = text.strip()
    raw: Any = None
    try:
        raw = json.loads(trimmed)
    except json.JSONDecodeError:
        # 容错：从回复中抠出首个 JSON 对象（无结构化输出强制时的兜底）
        match = _JSON_OBJECT_RE.search(trimmed)
        if match:
            try:
                raw = json.loads(match.group(0))
            except json.JSONDecodeError:
                raw = None
    if not isinstance(raw, dict) or not isinstance(raw.get("ok"), bool):
        return HookExecutionResult(
            outcome="non_blocking_error",
            stdout=trimmed,
            exit_code=1,
            error_message="JSON validation failed",
        )
    if raw["ok"]:
        return HookExecutionResult(outcome="success", stdout=trimmed)
    reason = raw.get("reason")
    reason_str = str(reason) if reason is not None else "condition not met"
    return HookExecutionResult(
        outcome="blocking",
        stdout=trimmed,
        blocking_error=f"{hook_kind} hook condition was not met: {reason_str}",
        prevent_continuation=True,
        stop_reason=reason_str,
    )


async def execute_prompt_hook(
    hook: PromptHookConfig,
    payload_json: str,
    event: HookEvent,
    *,
    model_factory: ModelFactory | None = None,
) -> HookExecutionResult:
    timeout = (
        hook.timeout
        if hook.timeout is not None
        else default_timeout_s(event, "prompt")
    )
    prompt = substitute_arguments(hook.prompt, payload_json)
    try:
        model = (model_factory or _default_model_factory)(hook.model)
        response = await asyncio.wait_for(
            model.ainvoke(
                [
                    {"role": "system", "content": PROMPT_HOOK_SYSTEM},
                    {"role": "user", "content": prompt},
                ]
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return HookExecutionResult(
            outcome="cancelled",
            stderr=f"Prompt hook cancelled: timed out after {timeout}s",
        )
    except Exception as exc:  # noqa: BLE001 — 对齐 CC：模型错误不阻断
        return HookExecutionResult(
            outcome="non_blocking_error",
            error_message=f"Error executing prompt hook: {exc}",
        )
    return _verdict_to_result(_message_text(response), "Prompt")


async def execute_agent_hook(
    hook: AgentHookConfig,
    payload_json: str,
    event: HookEvent,
    *,
    tools: Sequence[Any] | None = None,
    model_factory: ModelFactory | None = None,
) -> HookExecutionResult:
    timeout = (
        hook.timeout if hook.timeout is not None else default_timeout_s(event, "agent")
    )
    prompt = substitute_arguments(hook.prompt, payload_json)
    try:
        from langchain.agents import create_agent

        model = (model_factory or _default_model_factory)(hook.model)
        agent = create_agent(
            model=model,
            tools=list(tools or []),
            system_prompt=AGENT_HOOK_SYSTEM,
        )
        state = await asyncio.wait_for(
            agent.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config={"recursion_limit": 50},  # 对齐 CC MAX_AGENT_TURNS 量级
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return HookExecutionResult(
            outcome="cancelled",
            stderr=f"Agent hook cancelled: timed out after {timeout}s",
        )
    except Exception as exc:  # noqa: BLE001
        return HookExecutionResult(
            outcome="non_blocking_error",
            error_message=f"Error executing agent hook: {exc}",
        )
    messages = state.get("messages", []) if isinstance(state, dict) else []
    final_text = _message_text(messages[-1]) if messages else ""
    return _verdict_to_result(final_text, "Agent")
