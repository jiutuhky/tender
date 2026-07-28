from __future__ import annotations

import json
import threading
from collections import deque
from dataclasses import dataclass
from typing import Any, Iterator, Literal

TASK_TOOL_NAMES = {"TaskCreate", "TaskGet", "TaskUpdate", "TaskList"}


class SSEFormatter:
    def __init__(self) -> None:
        self._next_id = 0

    def format(self, event: str, data: dict[str, Any]) -> bytes:
        eid = self._next_id
        self._next_id += 1
        payload = json.dumps(data, ensure_ascii=False)
        return (
            f"id: {eid}\n"
            f"event: {event}\n"
            f"data: {payload}\n\n"
        ).encode("utf-8")


ToolCallState = dict[int, dict[str, str]]


def parse_lg_chunk(
    chunk: Any,
    *,
    tool_call_state: ToolCallState | None = None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """把一个 LangGraph stream 元素翻译成 (event, data) 序列。

    输入约定（来自 agent.stream(..., stream_mode=["updates","messages"], subgraphs=True, version="v2")）：
        chunk = (stream_mode, payload)
    其中：
        - stream_mode == "messages": payload = (token, metadata) 元组
        - stream_mode == "updates": payload = {node_name: node_state} 字典

    注意：调用方负责把 subgraphs=True 时的 3-tuple (namespace, mode, payload) 在喂入前去掉 namespace。
    """
    if not isinstance(chunk, tuple) or len(chunk) != 2:
        return

    mode, payload = chunk

    if mode == "messages":
        token, meta = payload
        # 子代理归属：Agent 工具把自己的 tool_call_id 注入子代理 config metadata，
        # 故子代理流式 token 的 metadata 带 parent_tool_use_id；主 agent 的 token 没有，
        # 记为 None。前端据此把事件挂到对应子代理（对齐 CC 的 parentToolUseID 分组），
        # 不再靠「最后一个 running 子代理」猜测——后者在并行多 Agent 下会串台并无限嵌套。
        parent_tool_use_id = (meta or {}).get("parent_tool_use_id")
        token_type = getattr(token, "type", "")
        # AIMessageChunk
        if token_type in ("AIMessageChunk", "ai"):
            tool_chunks = getattr(token, "tool_call_chunks", None) or []
            for tc in tool_chunks:
                name = tc.get("name")
                call_id = tc.get("id")
                index = tc.get("index")
                args_chunk = tc.get("args", "")
                saved: dict[str, str] = {}
                if tool_call_state is not None and isinstance(index, int):
                    saved = tool_call_state.setdefault(index, {})
                    if call_id:
                        saved["call_id"] = call_id
                    if name:
                        saved["tool_name"] = name
                    call_id = call_id or saved.get("call_id")
                    name = name or saved.get("tool_name")
                if name or args_chunk:
                    yield ("tool_call.started", {
                        "call_id": call_id,
                        "tool_name": name or "",
                        "args_chunk": args_chunk,
                        "parent_tool_use_id": parent_tool_use_id,
                    })
            content = getattr(token, "content", "")
            # content 可能是 str，也可能是 list[content-block]（Anthropic extended-thinking
            # 模型常见：[{type: "thinking", thinking: ...}, {type: "text", text: ...}, ...]）。
            # 原样透传，前端按 block.type 分别渲染 thinking / text / redacted_thinking。
            if content:
                yield ("message.delta", {
                    "role": "assistant",
                    "content_chunk": content,
                    "parent_tool_use_id": parent_tool_use_id,
                })
        # ToolMessage
        elif token_type == "tool":
            tool_name = getattr(token, "name", "")
            call_id = getattr(token, "tool_call_id", None)
            result = getattr(token, "content", "")
            yield ("tool_call.completed", {
                "call_id": call_id,
                "tool_name": tool_name,
                "result_summary": str(result),
                "parent_tool_use_id": parent_tool_use_id,
            })
            if tool_name in TASK_TOOL_NAMES:
                yield ("todo.refresh_requested", {"tool_name": tool_name})

    elif mode == "updates":
        # 节点级状态更新；遇到 interrupt 节点抛 interrupt.requested
        if isinstance(payload, dict):
            for node, state in payload.items():
                if node == "__interrupt__":
                    yield ("interrupt.requested", {"payload": str(state)})


# --- Sandbox lifecycle events (M6) ---


@dataclass
class SandboxEvent:
    """Lifecycle event emitted to the SSE stream for sandbox state transitions."""

    kind: Literal[
        "created",
        "adopted",
        "paused",
        "resumed",
        "evicted",
        "orphaned",
        "health_fail",
        "snapshotted",
        "restored",
        "error",
    ]
    session_id: str
    sandbox_id: str | None = None
    reason: str | None = None


def render_sandbox_event(event: SandboxEvent) -> str:
    """Render a SandboxEvent as a single SSE message frame."""
    payload = {
        "event": f"sandbox.{event.kind}",
        "session_id": event.session_id,
        "sandbox_id": event.sandbox_id,
        "reason": event.reason,
    }
    return f"event: sandbox.{event.kind}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


# —— 会话级事件队列(Task B7)——————————————————————————————————————
# sandbox 生命周期事件发生在后台线程(supervisor/GC/reconciler),SSE 流
# 却按消息请求存在——事件先积压在此,消息流开始时冲刷给前端。
# 上限防无人认领的会话无界增长;溢出丢最旧(前端可从事件表补全历史)。

_PENDING_MAX_PER_SESSION = 50
_PENDING_SANDBOX_EVENTS: dict[str, deque[SandboxEvent]] = {}
_PENDING_LOCK = threading.Lock()


def push_sandbox_event(event: SandboxEvent) -> None:
    with _PENDING_LOCK:
        queue = _PENDING_SANDBOX_EVENTS.setdefault(
            event.session_id, deque(maxlen=_PENDING_MAX_PER_SESSION)
        )
        queue.append(event)


def drain_sandbox_events(session_id: str) -> list[SandboxEvent]:
    with _PENDING_LOCK:
        queue = _PENDING_SANDBOX_EVENTS.pop(session_id, None)
    return list(queue) if queue else []
