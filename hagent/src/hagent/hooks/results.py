"""hook 执行结果的分类与 JSON 输出处理。

对齐 CC hooks.ts：
- parseHookOutput（:399）：stdout 以 ``{`` 开头才按 JSON 解析，否则纯文本。
- executeHooks 的 exit code 分支（:2500-2697）：**JSON 输出优先于 exit code**
  （stdout 是合法 JSON 时按 JSON 语义处理，exit 2 的阻断路径只对非 JSON 生效）；
  0=success、2=blocking、其他=non-blocking error；JSON 校验失败按
  non-blocking error（exitCode 1）。
- processHookJSONOutput（:489）：continue/decision/systemMessage/
  hookSpecificOutput 的字段提取与事件名校验。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import ValidationError

from hagent.hooks.events import HookEvent
from hagent.hooks.schema import HookJSONOutput

logger = logging.getLogger(__name__)

Outcome = Literal["success", "blocking", "non_blocking_error", "cancelled"]


@dataclass
class HookExecutionResult:
    """单个 hook 执行后的规范化结果（原始输出 + 已处理的控制字段）。"""

    outcome: Outcome
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    json_output: HookJSONOutput | None = None
    # exit 0 且非 JSON 时的 stdout.trim()（按事件决定是否注入为上下文）
    plain_text: str | None = None
    # —— processHookJSONOutput 提取的控制字段 ——
    blocking_error: str | None = None
    prevent_continuation: bool = False
    stop_reason: str | None = None
    permission_behavior: Literal["allow", "deny", "ask"] | None = None
    permission_reason: str | None = None
    updated_input: dict[str, Any] | None = None
    additional_context: str | None = None
    initial_user_message: str | None = None
    updated_mcp_tool_output: Any | None = None
    system_message: str | None = None
    suppress_output: bool = False
    # non-blocking error 时给用户看的消息
    error_message: str | None = None
    backgrounded: bool = False

    extras: dict[str, Any] = field(default_factory=dict)


def process_json_output(
    result: HookExecutionResult,
    output: HookJSONOutput,
    expected_event: HookEvent,
) -> None:
    """把 JSON 高级控制字段落到 result 上；事件名不符时抛 ValueError（CC 同款 throw）。"""
    result.json_output = output
    if output.continue_ is False:
        result.prevent_continuation = True
        if output.stop_reason:
            result.stop_reason = output.stop_reason
    if output.decision == "approve":
        result.permission_behavior = "allow"
    elif output.decision == "block":
        result.permission_behavior = "deny"
        result.blocking_error = output.reason or "Blocked by hook"
    if output.system_message:
        result.system_message = output.system_message
    if output.suppress_output:
        result.suppress_output = True
    # 对齐 CC :573-575：有权限决策且 json.reason 存在时记录 reason
    if result.permission_behavior is not None and output.reason is not None:
        result.permission_reason = output.reason

    hso = output.hook_specific_output
    if hso is None:
        return
    if hso.hook_event_name != expected_event.value:
        raise ValueError(
            f"Hook returned incorrect event name: expected "
            f"'{expected_event.value}' but got '{hso.hook_event_name}'"
        )
    if expected_event == HookEvent.PRE_TOOL_USE:
        if hso.permission_decision == "allow":
            result.permission_behavior = "allow"
        elif hso.permission_decision == "deny":
            result.permission_behavior = "deny"
            result.blocking_error = (
                hso.permission_decision_reason
                or output.reason
                or "Blocked by hook"
            )
        elif hso.permission_decision == "ask":
            result.permission_behavior = "ask"
        # 对齐 CC :628：permissionDecisionReason 无条件覆盖
        result.permission_reason = hso.permission_decision_reason or result.permission_reason
        if hso.updated_input is not None:
            result.updated_input = hso.updated_input
        result.additional_context = hso.additional_context
    elif expected_event == HookEvent.SESSION_START:
        result.additional_context = hso.additional_context
        result.initial_user_message = hso.initial_user_message
    elif expected_event == HookEvent.POST_TOOL_USE:
        result.additional_context = hso.additional_context
        if hso.updated_mcp_tool_output is not None:
            result.updated_mcp_tool_output = hso.updated_mcp_tool_output
    elif expected_event in (
        HookEvent.USER_PROMPT_SUBMIT,
        HookEvent.SETUP,
        HookEvent.SUBAGENT_START,
        HookEvent.POST_TOOL_USE_FAILURE,
        HookEvent.NOTIFICATION,
    ):
        result.additional_context = hso.additional_context
    elif expected_event == HookEvent.PERMISSION_DENIED:
        result.extras["retry"] = hso.retry


def classify_command_output(
    *,
    command_desc: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    event: HookEvent,
) -> HookExecutionResult:
    """按 CC executeHooks 语义把子进程输出归类为 HookExecutionResult。"""
    result = HookExecutionResult(
        outcome="success", exit_code=exit_code, stdout=stdout, stderr=stderr
    )
    trimmed = stdout.strip()
    if trimmed.startswith("{"):
        parsed: HookJSONOutput | None = None
        try:
            raw = json.loads(trimmed)
            parsed = HookJSONOutput.model_validate(raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            result.outcome = "non_blocking_error"
            result.exit_code = 1
            result.error_message = f"JSON validation failed: {exc}"
            return result
        if parsed.async_ is True:
            # async 响应：按 CC 语义视为已后台化，本次结果即 success
            result.backgrounded = True
            return result
        try:
            process_json_output(result, parsed, event)
        except ValueError as exc:
            result.outcome = "non_blocking_error"
            result.error_message = str(exc)
            result.json_output = None
            return result
        # JSON 语义优先：outcome 保持 success，阻断由 blocking_error /
        # prevent_continuation 表达（对齐 CC :2604-2612）
        return result

    if exit_code == 0:
        result.plain_text = stdout.strip()
        return result
    if exit_code == 2:
        result.outcome = "blocking"
        result.blocking_error = f"[{command_desc}]: {stderr or 'No stderr output'}"
        return result
    result.outcome = "non_blocking_error"
    result.error_message = (
        f"Failed with non-blocking status code: {stderr.strip() or 'No stderr output'}"
    )
    return result
