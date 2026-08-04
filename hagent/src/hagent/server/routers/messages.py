from __future__ import annotations

import logging
from typing import Any, Iterator, Protocol

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from hagent.hooks.events import HookEvent
from hagent.ingest.tasks import get_ingest_registry
from hagent.server.agents import get_or_build_agent
from hagent.server.auth import require_api_key
from hagent.server.hooks_registry import (
    get_hook_runner,
    pop_pending_session_context,
)
from hagent.server.routers.sessions import get_session_manager, get_store
from hagent.server.sse import (
    SSEFormatter,
    drain_sandbox_events,
    parse_lg_chunk,
    render_sandbox_event,
)
from hagent.server.transcript import append_transcript
from hagent.server.workspace_checkpoint import (
    CheckpointFailure,
    CheckpointResult,
)
from hagent.task_tools.models import task_to_todo


logger = logging.getLogger(__name__)


class CheckpointCallback(Protocol):
    def __call__(
        self,
        *,
        interrupted: bool,
        error: str | None = None,
    ) -> CheckpointResult: ...


def _session_sandbox(sid: str, *, rebuild: bool = False) -> Any | None:
    """Return the live sandbox held by SessionManager for this sid (or None).

    rebuild=True(仅 POST 消息路径)时经 ensure_sandbox 走 orphaned 重建
    (spec §4.3:首条新消息触发新 VM + files 重灌);GET 路径只读不重建。
    Returning None for host-mode sessions or for early-import test scenarios
    where the manager has not been wired keeps the caller branchless."""
    try:
        mgr = get_session_manager()
    except RuntimeError:
        return None
    if not rebuild:
        return mgr.get_sandbox(sid)
    sandbox = mgr.ensure_sandbox(sid)
    if sandbox is not None:
        # 活跃度只认消息级 API 交互:touch 进 idle GC 的判定基准
        # (manifest.last_used_at);GET/SSE 路径不 touch,心跳不续期
        manifest = getattr(sandbox, "manifest", None)
        touch = getattr(manifest, "touch", None)
        if callable(touch):
            touch()
    return sandbox

router = APIRouter(dependencies=[Depends(require_api_key)])


class MessageBody(BaseModel):
    content: str


def _build_skill_message(skill: str, args: str | None) -> str:
    normalized = skill.strip().lstrip("/")
    if args:
        return f'Use the `Skill` tool with skill: "{normalized}" and args: "{args}".'
    return f'Use the `Skill` tool with skill: "{normalized}".'


def _expand_skill_message(content: str) -> str:
    stripped = content.strip()
    if not stripped.startswith("/skill:"):
        return content
    rest = stripped[len("/skill:") :].strip()
    if not rest:
        return content
    if " " in rest:
        skill, args = rest.split(" ", 1)
        return _build_skill_message(skill, args.strip() or None)
    return _build_skill_message(rest, None)


def _task_store_todos(agent: Any) -> list[dict[str, Any]] | None:
    store = getattr(agent, "_hagent_task_store", None)
    list_tasks = getattr(store, "list_tasks", None)
    if store is None or not callable(list_tasks):
        return None
    try:
        tasks = list_tasks()
        todos = [task_to_todo(task) for task in tasks]
        list_task_items = getattr(store, "list_task_items", None)
        if callable(list_task_items):
            items_by_id = {item.id: item for item in list_task_items()}
            for todo in todos:
                item = items_by_id.get(todo.get("id"))
                if item is not None:
                    todo["blockedBy"] = list(item.blockedBy)
                    if item.owner:
                        todo["owner"] = item.owner
                    else:
                        todo.pop("owner", None)
        return todos
    except Exception:  # noqa: BLE001
        return None


#: 等待入库任务时的进度轮询间隔（秒）——OCR 实测约 1 s/页，无需更密
INGEST_POLL_SECONDS = 0.5


def _stream_ingest_progress(fmt: SSEFormatter, project_id: str | None) -> Iterator[bytes]:
    """把该 project 在跑的原文解析等完，其间沿本流上报「原文解析 N/M 页」。

    解析失败不拦消息：失败页在 md 里已留占位，整份文档不作废——把失败如实报出来，
    agent 照常起跑。
    """
    if not project_id:
        return
    job = get_ingest_registry().claim(project_id)
    if job is None:
        return

    reported: tuple[int, int] | None = None
    while True:
        progress = job.progress
        current = (progress.done, progress.total)
        if current != reported:
            reported = current
            yield fmt.format(
                event="ingest.progress",
                data={
                    "project_id": project_id,
                    "path": job.pdf_path,
                    "done": progress.done,
                    "total": progress.total,
                    "label": f"原文解析 {progress.done}/{progress.total} 页",
                },
            )
        if job.wait(INGEST_POLL_SECONDS):
            break

    if job.error is not None:
        yield fmt.format(
            event="ingest.failed",
            data={"project_id": project_id, "message": str(job.error)},
        )
        return

    result = job.result
    yield fmt.format(
        event="ingest.completed",
        data={
            "project_id": project_id,
            "document_id": result.document_id if result else None,
            "markdown_path": result.markdown_path if result else None,
            "sidecar_path": result.sidecar_path if result else None,
            "failed_pages": list(result.failed_pages) if result else [],
        },
    )
    # md 与 sidecar 刚落 canonical workspace，租约活跃时补一次注入，
    # 让 agent 在 VM 里看得到（失败留待下一轮 ensure 追平）
    try:
        get_session_manager().sync_project_workspace(project_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("project %s 解析后注入 VM 失败(留待追平): %s", project_id, exc)


def _stream_agent_events(
    agent: Any,
    content: str,
    thread_id: str,
    *,
    project_id: str | None = None,
    run_id: str | None = None,
    checkpoint: CheckpointCallback | None = None,
) -> Iterator[bytes]:
    fmt = SSEFormatter()
    tool_call_states: dict[str, dict[int, dict[str, str]]] = {"": {}}
    # 简版 transcript：累积主图（非子代理 namespace）的 assistant 增量
    assistant_parts: list[str] = []
    # OCR 是上传后的确定性前置任务：md 与 sidecar 就绪后才起 agent。进度沿本条
    # 既有通道上报，不另开通道。
    yield from _stream_ingest_progress(fmt, project_id)
    # 后台线程积压的 sandbox 生命周期事件先冲刷(Task B7):前端在 agent
    # 输出前得知 orphaned/health_fail/evicted 等状态变化
    for sandbox_event in drain_sandbox_events(thread_id):
        yield render_sandbox_event(sandbox_event).encode("utf-8")
    if run_id is not None:
        yield fmt.format(event="run.started", data={"run_id": run_id})

    def finish_checkpoint(
        *, interrupted: bool, error: str | None = None
    ) -> CheckpointResult | None:
        if checkpoint is None:
            return None
        return checkpoint(interrupted=interrupted, error=error)

    def checkpoint_frame(result: CheckpointResult | None) -> bytes | None:
        if result is None:
            return None
        if result.commit_sha is not None:
            return fmt.format(
                event="workspace.checkpointed",
                data={
                    "run_id": result.run_id,
                    "commit_sha": result.commit_sha,
                    "files_changed": list(result.files_changed),
                },
            )
        return None

    try:
        for chunk in agent.stream(
            {"messages": [{"role": "user", "content": content}]},
            config={"configurable": {"thread_id": thread_id}},
            stream_mode=["updates", "messages"],
            subgraphs=True,
        ):
            # subgraphs=True 时 chunk = (namespace, mode, payload); 否则 (mode, payload)
            if isinstance(chunk, tuple) and len(chunk) == 3:
                _ns, mode, payload = chunk
                inner = (mode, payload)
                state_key = repr(_ns)
            else:
                inner = chunk
                state_key = ""
            tool_call_state = tool_call_states.setdefault(state_key, {})
            for event, data in parse_lg_chunk(inner, tool_call_state=tool_call_state):
                if event == "todo.refresh_requested":
                    todos = _task_store_todos(agent)
                    if todos is not None:
                        yield fmt.format(event="todo.updated", data={"todos": todos})
                    continue
                if event == "message.delta" and state_key in ("", "()"):
                    part = data.get("content_chunk")
                    if isinstance(part, str):
                        assistant_parts.append(part)
                yield fmt.format(event=event, data=data)
    except GeneratorExit:
        try:
            finish_checkpoint(interrupted=True, error="客户端断连或用户打断")
        except Exception as exc:  # noqa: BLE001
            logger.warning("run %s 断连 checkpoint 失败: %s", run_id, exc)
        raise
    except Exception as agent_error:  # noqa: BLE001
        result = None
        try:
            result = finish_checkpoint(interrupted=True, error=str(agent_error))
        except CheckpointFailure as checkpoint_error:
            result = checkpoint_error.result
            logger.warning(
                "run %s 异常后的 checkpoint 未完整收尾: %s",
                run_id,
                checkpoint_error,
            )
        except Exception as checkpoint_error:  # noqa: BLE001
            logger.warning(
                "run %s 异常后的 checkpoint 失败: %s", run_id, checkpoint_error
            )
        frame = checkpoint_frame(result)
        if frame is not None:
            yield frame
        yield fmt.format(
            event="error",
            data={"code": "agent_error", "message": str(agent_error)},
        )
        return

    try:
        append_transcript(thread_id, "assistant", "".join(assistant_parts))
    except Exception as exc:  # noqa: BLE001
        logger.warning("session %s assistant transcript 写入失败: %s", thread_id, exc)

    try:
        result = finish_checkpoint(interrupted=False)
    except CheckpointFailure as checkpoint_error:
        frame = checkpoint_frame(checkpoint_error.result)
        if frame is not None:
            yield frame
        yield fmt.format(
            event="error",
            data={
                "code": "workspace_checkpoint_error",
                "message": str(checkpoint_error),
            },
        )
        return
    except Exception as checkpoint_error:  # noqa: BLE001
        yield fmt.format(
            event="error",
            data={
                "code": "workspace_checkpoint_error",
                "message": str(checkpoint_error),
            },
        )
        return
    frame = checkpoint_frame(result)
    if frame is not None:
        yield frame
    yield fmt.format(event="done", data={"thread_id": thread_id})


def _hook_blocked_stream(sid: str, reason: str) -> Iterator[bytes]:
    """UserPromptSubmit 阻断：prompt 不进图（CC 的「擦除」），SSE 明示原因。"""
    fmt = SSEFormatter()
    yield fmt.format(event="hook.blocked", data={"reason": reason, "thread_id": sid})
    yield fmt.format(event="done", data={"thread_id": sid})


@router.post("/sessions/{sid}/messages")
def post_message(sid: str, body: MessageBody) -> StreamingResponse:
    store = get_store()
    s = store.get(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    store.touch(sid)
    manager = get_session_manager()
    content = _expand_skill_message(body.content)
    runner = get_hook_runner(sid)
    if runner is not None and runner.has_hooks(HookEvent.USER_PROMPT_SUBMIT):
        agg = runner.run(HookEvent.USER_PROMPT_SUBMIT, {"prompt": content})
        if agg.blocked:
            reason = agg.block_reason or agg.stop_reason or "Blocked by hook"
            return StreamingResponse(
                _hook_blocked_stream(sid, reason),
                media_type="text/event-stream",
            )
        if agg.contexts:
            # exit0 stdout / additionalContext 注入给模型（CC 语义）
            content = content + "\n\n" + "\n".join(agg.contexts)
    pending = pop_pending_session_context(sid)
    if pending:
        content = (
            f"<session-start-hook>\n{pending}\n</session-start-hook>\n\n{content}"
        )
    summary_text = " ".join(body.content.split())[:80] or "空消息"
    run = manager.create_chat_turn(sid, summary=f"chat_turn: {summary_text}")

    # sandbox idle 治理只认消息级交互(spec §5:SSE 心跳/轮询不续期)
    manager.touch_activity(sid)
    try:
        sandbox = _session_sandbox(sid, rebuild=True)
    except Exception as exc:
        from hagent.sandbox.ledger import CapacityExceeded
        from hagent.sandbox.pool import PoolExhausted

        if isinstance(exc, (CapacityExceeded, PoolExhausted)):
            manager.reject_run(run.id, str(exc))
            raise HTTPException(
                status_code=503,
                detail=str(exc),
                headers={"Retry-After": "30"},
            ) from exc
        manager.interrupt_run_best_effort(
            run.id,
            sandbox=manager.get_sandbox(sid),
            error=str(exc),
        )
        raise
    try:
        agent = get_or_build_agent(
            sid, manager.workspace_dir(sid), project_id=s.project_id, sandbox=sandbox
        )
    except Exception as exc:
        manager.interrupt_run_best_effort(
            run.id,
            sandbox=sandbox,
            error=str(exc),
        )
        raise
    try:
        append_transcript(sid, "user", content)
    except Exception as exc:
        manager.interrupt_run_best_effort(
            run.id,
            sandbox=sandbox,
            error=str(exc),
        )
        raise
    manager.mark_run_running(run.id)
    return StreamingResponse(
        _stream_agent_events(
            agent,
            content,
            thread_id=sid,
            project_id=s.project_id,
            run_id=run.id,
            checkpoint=lambda **kwargs: manager.checkpoint_run(
                run.id,
                sandbox=sandbox,
                **kwargs,
            ),
        ),
        media_type="text/event-stream",
    )


def _normalize_message(m: Any) -> dict:
    """Convert a LangGraph message (BaseMessage subclass or plain dict) to {role, content}.

    Content 保留原结构：str 或 list[content-block]。前端按 block.type 渲染
    （extended-thinking 模型会给 [{type:"thinking",...}, {type:"text",...}]）。
    """
    if isinstance(m, dict):
        return {"role": m.get("role", "unknown"), "content": m.get("content", "")}
    role = getattr(m, "type", "unknown")  # BaseMessage 子类有 .type 属性 (ai/human/tool/system)
    content = getattr(m, "content", "")
    return {"role": role, "content": content}


@router.get("/sessions/{sid}/messages")
def get_messages(sid: str) -> list[dict]:
    store = get_store()
    s = store.get(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    agent = get_or_build_agent(
        sid,
        get_session_manager().workspace_dir(sid),
        project_id=s.project_id,
        sandbox=_session_sandbox(sid),
    )
    state = agent.get_state({"configurable": {"thread_id": sid}})
    msgs = state.values.get("messages", []) if state else []
    return [_normalize_message(m) for m in msgs]


@router.get("/sessions/{sid}/todos")
def get_todos(sid: str) -> list[dict]:
    store = get_store()
    s = store.get(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    agent = get_or_build_agent(
        sid,
        get_session_manager().workspace_dir(sid),
        project_id=s.project_id,
        sandbox=_session_sandbox(sid),
    )
    todos = _task_store_todos(agent)
    if todos is not None:
        return todos
    state = agent.get_state({"configurable": {"thread_id": sid}})
    return list(state.values.get("todos", [])) if state else []


class InterruptBody(BaseModel):
    interrupt_id: str
    decision: str
    reason: str | None = None


@router.post("/sessions/{sid}/interrupt")
def post_interrupt(sid: str, body: InterruptBody) -> dict:
    store = get_store()
    s = store.get(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    # MVP B 方案：interrupt 端点保留，不主动触发；future hookup via Command(resume=...)
    return {"ok": True, "session_id": sid, "decision": body.decision}
