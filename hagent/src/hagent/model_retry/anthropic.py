"""Anthropic 流适配：结束标志、首响应/无进展计时与响应资源释放。"""
from __future__ import annotations

import asyncio
import threading
import time
from functools import cached_property
from contextlib import closing, aclosing
from typing import Any

import anthropic
import httpx
from langchain_anthropic import ChatAnthropic
from langchain_anthropic.chat_models import _tools_in_params, _documents_in_params, _thinking_in_params, _compact_in_params
from langchain_core.outputs import ChatGenerationChunk

from .policy import IncompleteResponseError, ModelRetryPolicy, ModelTimeoutError
from .runtime import attempt_context, run_control, sync_bridge


def is_progress(event: Any) -> bool:
    if event.type == "content_block_start":
        block = event.content_block
        return bool(getattr(block, "text", None) or getattr(block, "thinking", None) or getattr(block, "input", None))
    if event.type == "content_block_delta":
        delta = event.delta
        return bool(getattr(delta, "text", None) or getattr(delta, "thinking", None) or getattr(delta, "partial_json", None))
    return False


class StreamWatchdog:
    def __init__(self, policy: ModelRetryPolicy):
        self.policy = policy
        self.last_progress = time.monotonic()
        self.started = False
        self.seen_message_start = False
        self.warned = False
        self.complete = False
        self.context = attempt_context.get()
        self.control = run_control.get()

    def observe(self, event: Any) -> None:
        if event.type == "message_start":
            self.seen_message_start = True
            self.started = True
            self.last_progress = time.monotonic()
        if is_progress(event):
            self.started = True
            self.last_progress = time.monotonic()
            self.warned = False
        if event.type == "message_stop":
            self.complete = True

    def check(self) -> None:
        if self.control:
            self.control.check()
        elapsed = time.monotonic() - self.last_progress
        limit = self.policy.stream_idle_timeout if self.started else self.policy.first_response_timeout
        if elapsed >= limit:
            raise ModelTimeoutError("模型流长时间没有有效进展")
        if elapsed >= min(45, limit / 2) and not self.warned:
            self.warned = True
            if self.context:
                self.context.emit("model.slow", {**self.context.data, "message": "模型响应较慢，正在等待服务恢复。"})

    def finish(self) -> None:
        if not self.complete or not self.seen_message_start:
            raise IncompleteResponseError("模型流缺少完整的 message_start/message_stop")


def guarded_stream(stream: Any, policy: ModelRetryPolicy):
    """同步 SDK 读取阻塞时由看门狗关闭该响应；不关闭共享连接池。"""
    watchdog = StreamWatchdog(policy)
    finished = threading.Event()
    failure: list[BaseException] = []
    def watch() -> None:
        while not finished.wait(0.05):
            try:
                watchdog.check()
            except BaseException as exc:
                failure.append(exc)
                stream.close()
                return
    thread = threading.Thread(target=watch, name="model-stream-watchdog", daemon=True)
    thread.start()
    try:
        try:
            for event in stream:
                if failure:
                    raise failure[0]
                watchdog.observe(event)
                yield event
                if watchdog.complete:
                    break
        except Exception:
            if failure:
                raise failure[0] from None
            raise
        if failure:
            raise failure[0]
        watchdog.finish()
    finally:
        finished.set()
        stream.close()
        thread.join(timeout=1)


async def guarded_astream(stream: Any, policy: ModelRetryPolicy, *, watchdog: StreamWatchdog | None = None):
    watchdog = watchdog or StreamWatchdog(policy)
    iterator = stream.__aiter__()
    pending: asyncio.Task | None = None
    try:
        while True:
            pending = asyncio.create_task(anext(iterator))
            while not pending.done():
                watchdog.check()
                await asyncio.wait({pending}, timeout=0.05)
            try:
                event = pending.result()
            except StopAsyncIteration:
                break
            watchdog.observe(event)
            yield event
            if watchdog.complete:
                break
        watchdog.finish()
    finally:
        if pending and not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        await stream.close()


class RecoverableChatAnthropic(ChatAnthropic):
    retry_policy: ModelRetryPolicy = ModelRetryPolicy()

    @cached_property
    def _client_params(self) -> dict[str, Any]:
        params = dict(super()._client_params)
        params["max_retries"] = 0
        # read 限制用于建连后的首响应；流内真实进展由独立看门狗控制。
        params["timeout"] = httpx.Timeout(self.retry_policy.first_response_timeout,
                                         connect=self.retry_policy.connect_timeout)
        return params

    def _stream(self, messages, stop=None, run_manager=None, *, stream_usage=None, **kwargs):
        payload = self._get_request_payload(messages, stop=stop, **{**kwargs, "stream": True})
        coerce = not any(check(payload) for check in (_tools_in_params, _documents_in_params, _thinking_in_params, _compact_in_params))
        block = None
        with closing(self._create(payload)) as stream:
            for event in stream:
                msg, block = self._make_message_chunk_from_anthropic_event(event,
                    stream_usage=self.stream_usage if stream_usage is None else stream_usage,
                    coerce_content_to_string=coerce, block_start_event=block)
                if msg is not None:
                    chunk = ChatGenerationChunk(message=msg)
                    if run_manager and isinstance(msg.content, str):
                        run_manager.on_llm_new_token(msg.content, chunk=chunk)
                    yield chunk

    async def _astream(self, messages, stop=None, run_manager=None, *, stream_usage=None, **kwargs):
        payload = self._get_request_payload(messages, stop=stop, **{**kwargs, "stream": True})
        coerce = not any(check(payload) for check in (_tools_in_params, _documents_in_params, _thinking_in_params, _compact_in_params))
        block = None
        async with aclosing(await self._acreate(payload)) as stream:
            async for event in stream:
                msg, block = self._make_message_chunk_from_anthropic_event(event,
                    stream_usage=self.stream_usage if stream_usage is None else stream_usage,
                    coerce_content_to_string=coerce, block_start_event=block)
                if msg is not None:
                    chunk = ChatGenerationChunk(message=msg)
                    if run_manager and isinstance(msg.content, str):
                        await run_manager.on_llm_new_token(msg.content, chunk=chunk)
                    yield chunk

    def _create(self, payload: dict) -> Any:
        # 同步 CLI 复用异步传输的请求取消、首响应超时和流看门狗。
        if not payload.get("stream"):
            raise ValueError("恢复层模型调用必须开启流式响应")
        async def response():
            stream = await self._acreate(payload)
            try:
                async for event in stream:
                    yield event
            finally:
                await stream.aclose()
        return sync_bridge(response)

    async def _acreate(self, payload: dict) -> Any:
        # 每次尝试独占客户端，取消和断流回收不会影响并发子任务的连接。
        client = new_async_client(self._client_params)
        watchdog = StreamWatchdog(self.retry_policy)
        create = client.beta.messages.create if "betas" in payload else client.messages.create
        pending = asyncio.create_task(create(**payload))
        control = run_control.get()
        if control:
            control.resources[client] = pending
        try:
            while not pending.done():
                watchdog.check()
                await asyncio.wait({pending}, timeout=0.05)
            stream = pending.result()
        except BaseException:
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
            await client.close()
            if control:
                control.resources.pop(client, None)
            raise
        async def response():
            try:
                async for event in guarded_astream(stream, self.retry_policy, watchdog=watchdog):
                    yield event
            finally:
                await client.close()
                if control:
                    control.resources.pop(client, None)
        return response()


def new_async_client(params: dict[str, Any]):
    return anthropic.AsyncAnthropic(**params)


def adapt_model(model: Any, policy: ModelRetryPolicy, metadata: dict[str, Any]) -> Any:
    if isinstance(model, ChatAnthropic):
        # 从已解析实例保留密钥、网关、模型和 provider 参数；客户端在新尝试中惰性建立。
        values = {key: getattr(model, key) for key in ChatAnthropic.model_fields}
        values.update(max_retries=0, streaming=True, metadata={**(model.metadata or {}), **metadata}, retry_policy=policy)
        return RecoverableChatAnthropic(**values)
    updates = {"metadata": {**(getattr(model, "metadata", None) or {}), **metadata}}
    if hasattr(model, "max_retries"):
        updates["max_retries"] = 0
    return model.model_copy(update=updates)
