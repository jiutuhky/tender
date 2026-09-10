"""Web 异步执行流：取消、心跳和单次模型尝试的临时输出归属。"""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import aclosing
from typing import Any

import anyio

from hagent.model_retry.policy import ModelCallFailed, ModelRunCancelled
from hagent.model_retry.runtime import register_run, release_run, run_control
from hagent.server.sse import SSEFormatter, drain_sandbox_events, parse_lg_chunk, render_sandbox_event
from hagent.server.transcript import append_transcript
from hagent.sandbox.errors import SandboxUnavailable
from hagent.server.workspace_checkpoint import CheckpointFailure

logger = logging.getLogger(__name__)
HEARTBEAT_SECONDS = 15
CANCEL_POLL_SECONDS = 0.1


async def _async_from_sync(iterator):
    """兼容确定性前置解析和同步测试替身；模型生产路径使用 astream。"""
    end = object()
    while True:
        value = await asyncio.to_thread(next, iterator, end)
        if value is end:
            return
        yield value


async def stream_agent_events(agent: Any, content: str, thread_id: str, *, project_id=None,
                              run_id=None, checkpoint=None, cancel_check=None):
    from hagent.server.routers.messages import _stream_ingest_progress, _task_store_todos

    fmt = SSEFormatter()
    control = register_run(run_id or thread_id)
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    failure: list[BaseException] = []
    cancelled = None
    lifecycle_cancel = False
    client_closed = False
    result = None
    checkpoint_error = None
    parts: dict[str, list[str]] = {}
    attempts: dict[str, int] = {}
    tool_states: dict[str, dict] = {}
    last_heartbeat = time.monotonic()

    async def produce():
        token = run_control.set(control)
        try:
            async for frame in _async_from_sync(_stream_ingest_progress(fmt, project_id)):
                control.check()
                await queue.put(frame)
            args = dict(config={"configurable": {"thread_id": thread_id}, "metadata": {"run_id": run_id}},
                        stream_mode=["updates", "messages", "custom"], subgraphs=True)
            stream = agent.astream({"messages": [{"role": "user", "content": content}]}, **args) if hasattr(agent, "astream") else _async_from_sync(agent.stream({"messages": [{"role": "user", "content": content}]}, **args))
            async with aclosing(stream):
                async for chunk in stream:
                    control.check()
                    await queue.put(chunk)
        except SandboxUnavailable:
            control.cancel("任务执行环境已停止，本轮无法继续。")
        except (asyncio.CancelledError, ModelRunCancelled):
            raise
        except Exception as exc:
            failure.append(exc)
        finally:
            run_control.reset(token)

    task = asyncio.create_task(produce(), name=f"run:{run_id}")
    try:
        yield fmt.format("run.started", {"run_id": run_id})
        while True:
            reason = cancel_check() if cancel_check else None
            if reason:
                lifecycle_cancel = True
                control.cancel(reason)
            if control.stopped.is_set():
                cancelled = control.reason
                break
            if task.done() and queue.empty():
                if task.cancelled():
                    cancelled = control.reason
                else:
                    try:
                        task.result()
                    except ModelRunCancelled as exc:
                        cancelled = str(exc) or control.reason
                break
            try:
                chunk = await asyncio.wait_for(queue.get(), CANCEL_POLL_SECONDS)
            except TimeoutError:
                chunk = None
            if time.monotonic() - last_heartbeat >= HEARTBEAT_SECONDS:
                yield b": heartbeat\n\n"
                last_heartbeat = time.monotonic()
            for sandbox_event in drain_sandbox_events(thread_id):
                yield render_sandbox_event(sandbox_event).encode("utf-8")
            if chunk is None:
                continue
            if isinstance(chunk, bytes):
                yield chunk
                continue
            if isinstance(chunk, tuple) and len(chunk) == 3:
                namespace, mode, payload = chunk
                inner = (mode, payload)
                state_key = repr(namespace)
            else:
                inner, state_key = chunk, ""
            if inner[0] == "custom" and isinstance(inner[1], dict):
                event_data = inner[1].get("data", {})
                call = event_data.get("model_call_id", "")
                if event_data.get("attempt", 0) < attempts.get(call, 0):
                    continue
                if inner[1].get("event") == "model.attempt.started":
                    attempts[call] = event_data["attempt"]
                if inner[1].get("event") == "model.retry":
                    attempts[call] = event_data["attempt"] + 1
                    parts.pop(call, None)
                    tool_states.pop(f"{call}:{event_data['attempt']}", None)
            # 并发子图可以共享 namespace，参数分片必须按逻辑调用与尝试隔离。
            parser_key = state_key
            if inner[0] == "messages":
                metadata = inner[1][1] or {}
                if metadata.get("model_call_id"):
                    parser_key = f"{metadata['model_call_id']}:{metadata.get('attempt')}"
                else:
                    parser_key += str(metadata.get("parent_tool_use_id", ""))
            for event, data in parse_lg_chunk(inner, tool_call_state=tool_states.setdefault(parser_key, {})):
                call = data.get("model_call_id", "")
                attempt = data.get("attempt", 0)
                if event in ("message.delta", "tool_call.started") and call and attempt < attempts.get(call, 0):
                    continue
                if event == "todo.refresh_requested":
                    todos = _task_store_todos(agent)
                    if todos is not None:
                        yield fmt.format("todo.updated", {"todos": todos})
                    continue
                if event == "message.delta" and not data.get("parent_tool_use_id"):
                    text = data.get("content_chunk")
                    if isinstance(text, list):
                        text = "".join(b.get("text", "") for b in text if isinstance(b, dict) and b.get("type") == "text")
                    if isinstance(text, str):
                        parts.setdefault(call or state_key, []).append(text)
                yield fmt.format(event, data)
    except (asyncio.CancelledError, GeneratorExit):
        client_closed = True
        control.cancel("客户端连接已断开，本轮已停止。")
        raise
    finally:
        if not task.done():
            task.cancel()
        # ASGI 断连的取消作用域不能打断资源回收和 best-effort checkpoint。
        with anyio.CancelScope(shield=True):
            control.cancel(control.reason)
            await asyncio.gather(task, return_exceptions=True)
            await control.close_resources()
            if checkpoint:
                error = cancelled or ("客户端连接已断开" if client_closed else None) or (str(failure[0]) if failure else None)
                try:
                    result = await asyncio.to_thread(checkpoint, interrupted=bool(client_closed or cancelled or failure), error=error)
                except CheckpointFailure as exc:
                    result, checkpoint_error = exc.result, "部分成果保存失败，请核对项目文件。"
                except Exception:
                    checkpoint_error = "成果保存未确认，请核对项目文件。"
                    logger.warning("run=%s checkpoint=failed", run_id)
        release_run(run_id or thread_id)

    saved = bool(result is not None and checkpoint_error is None and not lifecycle_cancel)
    if result is not None and result.commit_sha:
        yield fmt.format("workspace.checkpointed", {"run_id": result.run_id, "commit_sha": result.commit_sha,
                                                   "files_changed": list(result.files_changed), "checkpoint_saved": saved})
    if cancelled:
        yield fmt.format("run.cancelled", {"run_id": run_id, "message": cancelled, "checkpoint_saved": saved})
        return
    if failure:
        exc = failure[0]
        if isinstance(exc, ModelCallFailed):
            parts.pop(exc.context["model_call_id"], None)
            data = exc.payload()
        else:
            logger.error("run=%s exception_type=%s", run_id, type(exc).__name__)
            data = {"code": "agent_error", "message": "本轮执行出现异常，请核对已有成果后重试。", "exception_types": [type(exc).__name__]}
        yield fmt.format("error", {**data, "run_id": run_id, "checkpoint_saved": saved,
                                   "checkpoint_message": checkpoint_error})
        return
    try:
        await asyncio.to_thread(append_transcript, thread_id, "assistant", "".join("".join(value) for value in parts.values()))
    except Exception:
        logger.warning("run=%s transcript=failed", run_id)
    if checkpoint_error:
        yield fmt.format("error", {"code": "workspace_checkpoint_error", "message": checkpoint_error, "checkpoint_saved": False})
        return
    yield fmt.format("done", {"thread_id": thread_id, "checkpoint_saved": saved})
