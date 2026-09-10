"""单轮取消与模型调用上下文；子图通过 ContextVar 继承同一取消信号。"""
from __future__ import annotations

import asyncio
import threading
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable

from .policy import ModelRunCancelled


class RunControl:
    def __init__(self) -> None:
        self.stopped = threading.Event()
        self.reason = "本轮已停止。"
        self.resources: dict[Any, asyncio.Task] = {}

    def cancel(self, reason: str = "本轮已停止。") -> None:
        self.reason = reason
        self.stopped.set()

    async def close_resources(self) -> None:
        """图结束时等待所有并发请求回收，再允许工作区 checkpoint。"""
        resources = list(self.resources.items())
        for _, pending in resources:
            if not pending.done():
                pending.cancel()
        await asyncio.gather(*(pending for _, pending in resources), return_exceptions=True)
        await asyncio.gather(*(client.close() for client, _ in resources), return_exceptions=True)
        self.resources.clear()

    def check(self) -> None:
        if self.stopped.is_set():
            raise ModelRunCancelled(self.reason)

    def sleep(self, seconds: float) -> None:
        if self.stopped.wait(seconds):
            self.check()

    async def asleep(self, seconds: float) -> None:
        # 不占用线程池；主 SSE 控制器还会直接取消整个图任务。
        end = asyncio.get_running_loop().time() + seconds
        while True:
            self.check()
            remaining = end - asyncio.get_running_loop().time()
            if remaining <= 0:
                return
            await asyncio.sleep(min(remaining, 0.1))


run_control: ContextVar[RunControl | None] = ContextVar("model_run_control", default=None)


@dataclass
class AttemptContext:
    data: dict[str, Any]
    emit: Callable[[str, dict[str, Any]], None]


attempt_context: ContextVar[AttemptContext | None] = ContextVar("model_attempt_context", default=None)
_controls: dict[str, RunControl] = {}
_lock = threading.Lock()


def register_run(run_id: str) -> RunControl:
    with _lock:
        return _controls.setdefault(run_id, RunControl())


def release_run(run_id: str) -> None:
    with _lock:
        _controls.pop(run_id, None)


def cancel_run(run_id: str, reason: str = "本轮已停止。") -> bool:
    with _lock:
        control = _controls.get(run_id)
        if control:
            control.cancel(reason)
        return control is not None


def sync_bridge(factory):
    """同步入口共用可取消的异步传输；退出时取消读取并回收线程与事件循环。"""
    import contextvars
    import queue

    mailbox = queue.Queue(maxsize=8)
    stopped = threading.Event()
    control = run_control.get()
    state: dict[str, Any] = {}
    end = object()
    context = contextvars.copy_context()

    async def send(value):
        while not stopped.is_set():
            try:
                mailbox.put_nowait(value)
                return
            except queue.Full:
                await asyncio.sleep(0.01)

    async def consume():
        state["loop"], state["task"] = asyncio.get_running_loop(), asyncio.current_task()
        stream = factory()
        try:
            async for item in stream:
                await send((True, item))
        except BaseException as exc:
            await send((False, exc))
        finally:
            await stream.aclose()
            await send((True, end))

    thread = threading.Thread(target=lambda: context.run(asyncio.run, consume()), name="model-sync-transport", daemon=True)
    thread.start()
    try:
        while True:
            if control:
                control.check()
            try:
                ok, value = mailbox.get(timeout=0.05)
            except queue.Empty:
                if not thread.is_alive():
                    raise RuntimeError("模型传输线程提前退出")
                continue
            if not ok:
                raise value
            if value is end:
                return
            yield value
    finally:
        stopped.set()
        loop, task = state.get("loop"), state.get("task")
        if loop is not None and not loop.is_closed() and task and not task.done():
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass
        thread.join(timeout=2)
