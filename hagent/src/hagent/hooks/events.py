"""Hook 事件全集、payload 构造与 matchQuery 提取。

对齐 CC：
- 事件名与顺序：coreSchemas.ts 的 HOOK_EVENTS（28 个）。
- 每事件 payload 字段：coreSchemas.ts:388-765。
- matchQuery 取值：hooks.ts getMatchingHooks 的 switch（:1616-1670）。
- 默认超时：hooks.ts TOOL_HOOK_EXECUTION_TIMEOUT_MS=600s、
  SESSION_END_HOOK_TIMEOUT_MS_DEFAULT=1.5s（可用
  CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS 覆盖，沿用 CC 的 env 名）。
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import PurePath
from typing import Any, Mapping

from hagent.hooks.context import HookContext


class HookEvent(str, Enum):
    """CC 全部 28 个 hook 事件名（精确拼写）。"""

    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    POST_TOOL_USE_FAILURE = "PostToolUseFailure"
    NOTIFICATION = "Notification"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    SESSION_START = "SessionStart"
    SESSION_END = "SessionEnd"
    STOP = "Stop"
    STOP_FAILURE = "StopFailure"
    SUBAGENT_START = "SubagentStart"
    SUBAGENT_STOP = "SubagentStop"
    PRE_COMPACT = "PreCompact"
    POST_COMPACT = "PostCompact"
    PERMISSION_REQUEST = "PermissionRequest"
    PERMISSION_DENIED = "PermissionDenied"
    SETUP = "Setup"
    TEAMMATE_IDLE = "TeammateIdle"
    TASK_CREATED = "TaskCreated"
    TASK_COMPLETED = "TaskCompleted"
    ELICITATION = "Elicitation"
    ELICITATION_RESULT = "ElicitationResult"
    CONFIG_CHANGE = "ConfigChange"
    WORKTREE_CREATE = "WorktreeCreate"
    WORKTREE_REMOVE = "WorktreeRemove"
    INSTRUCTIONS_LOADED = "InstructionsLoaded"
    CWD_CHANGED = "CwdChanged"
    FILE_CHANGED = "FileChanged"


# hagent 已实现触发点的事件（P0 + P1 接线后逐步扩充）
SUPPORTED_EVENTS: frozenset[HookEvent] = frozenset(
    {
        HookEvent.PRE_TOOL_USE,
        HookEvent.POST_TOOL_USE,
        HookEvent.POST_TOOL_USE_FAILURE,
        HookEvent.USER_PROMPT_SUBMIT,
        HookEvent.SESSION_START,
        HookEvent.SESSION_END,
        HookEvent.STOP,
        HookEvent.SUBAGENT_START,
        HookEvent.SUBAGENT_STOP,
        HookEvent.PERMISSION_DENIED,
    }
)

_EVENT_VALUES: frozenset[str] = frozenset(e.value for e in HookEvent)


def is_hook_event(value: str) -> bool:
    return value in _EVENT_VALUES


# 每事件的 payload 字段契约（required, optional）。仅覆盖 hagent 会触发的
# 事件；build_payload 据此校验拼写，防止调用方传错字段名。
_EVENT_FIELDS: dict[HookEvent, tuple[frozenset[str], frozenset[str]]] = {
    HookEvent.PRE_TOOL_USE: (
        frozenset({"tool_name", "tool_input", "tool_use_id"}),
        frozenset(),
    ),
    HookEvent.POST_TOOL_USE: (
        frozenset({"tool_name", "tool_input", "tool_response", "tool_use_id"}),
        frozenset(),
    ),
    HookEvent.POST_TOOL_USE_FAILURE: (
        frozenset({"tool_name", "tool_input", "tool_use_id", "error"}),
        frozenset({"is_interrupt"}),
    ),
    HookEvent.PERMISSION_DENIED: (
        frozenset({"tool_name", "tool_input", "tool_use_id", "reason"}),
        frozenset(),
    ),
    HookEvent.PERMISSION_REQUEST: (
        frozenset({"tool_name", "tool_input"}),
        frozenset({"permission_suggestions"}),
    ),
    HookEvent.NOTIFICATION: (
        frozenset({"message", "notification_type"}),
        frozenset({"title"}),
    ),
    HookEvent.USER_PROMPT_SUBMIT: (frozenset({"prompt"}), frozenset()),
    HookEvent.SESSION_START: (
        frozenset({"source"}),
        frozenset({"agent_type", "model"}),
    ),
    HookEvent.SESSION_END: (frozenset({"reason"}), frozenset()),
    HookEvent.STOP: (
        frozenset({"stop_hook_active"}),
        frozenset({"last_assistant_message"}),
    ),
    HookEvent.SUBAGENT_START: (
        frozenset({"agent_id", "agent_type"}),
        frozenset(),
    ),
    HookEvent.SUBAGENT_STOP: (
        frozenset(
            {"stop_hook_active", "agent_id", "agent_transcript_path", "agent_type"}
        ),
        frozenset({"last_assistant_message"}),
    ),
}


def build_payload(
    event: HookEvent, ctx: HookContext, fields: Mapping[str, Any]
) -> dict[str, Any]:
    """构造写入 hook stdin 的 JSON payload（base + hook_event_name + 事件字段）。"""
    spec = _EVENT_FIELDS.get(event)
    if spec is not None:
        required, optional = spec
        keys = set(fields)
        missing = required - keys
        if missing:
            raise ValueError(f"{event.value} payload 缺少必填字段: {sorted(missing)}")
        unknown = keys - required - optional
        if unknown:
            raise ValueError(f"{event.value} payload 含未知字段: {sorted(unknown)}")
    payload = ctx.base_payload()
    payload["hook_event_name"] = event.value
    payload.update(fields)
    return payload


def match_query_for(event: HookEvent, payload: Mapping[str, Any]) -> str | None:
    """返回该事件用于 matcher 匹配的查询串；None 表示不做 matcher 过滤。

    对齐 hooks.ts getMatchingHooks：matchQuery 为空时 matcher 被整体忽略
    （即使配置了不匹配的 matcher 也会执行）。
    """
    if event in (
        HookEvent.PRE_TOOL_USE,
        HookEvent.POST_TOOL_USE,
        HookEvent.POST_TOOL_USE_FAILURE,
        HookEvent.PERMISSION_REQUEST,
        HookEvent.PERMISSION_DENIED,
    ):
        return payload.get("tool_name")
    if event == HookEvent.SESSION_START:
        return payload.get("source")
    if event in (HookEvent.SETUP, HookEvent.PRE_COMPACT, HookEvent.POST_COMPACT):
        return payload.get("trigger")
    if event == HookEvent.NOTIFICATION:
        return payload.get("notification_type")
    if event == HookEvent.SESSION_END:
        return payload.get("reason")
    if event == HookEvent.STOP_FAILURE:
        return payload.get("error")
    if event in (HookEvent.SUBAGENT_START, HookEvent.SUBAGENT_STOP):
        return payload.get("agent_type")
    if event in (HookEvent.ELICITATION, HookEvent.ELICITATION_RESULT):
        return payload.get("mcp_server_name")
    if event == HookEvent.CONFIG_CHANGE:
        return payload.get("source")
    if event == HookEvent.INSTRUCTIONS_LOADED:
        return payload.get("load_reason")
    if event == HookEvent.FILE_CHANGED:
        file_path = payload.get("file_path")
        return PurePath(file_path).name if file_path else None
    return None


# 默认超时（秒），对齐 CC 常量
TOOL_HOOK_TIMEOUT_S = 600.0  # TOOL_HOOK_EXECUTION_TIMEOUT_MS
SESSION_END_TIMEOUT_S = 1.5  # SESSION_END_HOOK_TIMEOUT_MS_DEFAULT
PROMPT_HOOK_TIMEOUT_S = 30.0  # execPromptHook 默认
AGENT_HOOK_TIMEOUT_S = 60.0  # execAgentHook 默认
HTTP_HOOK_TIMEOUT_S = 600.0  # DEFAULT_HTTP_HOOK_TIMEOUT_MS


def default_timeout_s(
    event: HookEvent,
    hook_type: str,
    env: Mapping[str, str] | None = None,
) -> float:
    """无 per-hook timeout 时的默认超时。

    SessionEnd 的事件级默认（1.5s）优先于类型级默认；沿用 CC 的
    CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS 覆盖变量（毫秒）。
    """
    env = env if env is not None else os.environ
    if event == HookEvent.SESSION_END:
        raw = env.get("CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS", "")
        if raw:
            try:
                return float(raw) / 1000.0
            except ValueError:
                pass
        return SESSION_END_TIMEOUT_S
    if hook_type == "prompt":
        return PROMPT_HOOK_TIMEOUT_S
    if hook_type == "agent":
        return AGENT_HOOK_TIMEOUT_S
    if hook_type == "http":
        return HTTP_HOOK_TIMEOUT_S
    return TOOL_HOOK_TIMEOUT_S
