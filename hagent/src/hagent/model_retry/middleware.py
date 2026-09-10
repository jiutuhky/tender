"""只重试当前模型轮；失败输出不会返回给图，因此工具节点不会执行半截调用。"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import asdict
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langgraph.config import get_config, get_stream_writer

from .anthropic import adapt_model
from .policy import ModelCallFailed, ModelRetryPolicy, IncompleteResponseError, classify_error
from .runtime import AttemptContext, RunControl, attempt_context, run_control

logger = logging.getLogger(__name__)


def call_context() -> tuple[dict[str, Any], Any]:
    try:
        metadata = get_config().get("metadata", {})
        writer = get_stream_writer()
    except RuntimeError:
        metadata, writer = {}, lambda _: None
    data = {"model_call_id": uuid.uuid4().hex, "run_id": metadata.get("run_id"),
            "parent_tool_use_id": metadata.get("parent_tool_use_id")}
    return data, lambda event, value: writer({"event": event, "data": value})


class ModelRetryMiddleware(AgentMiddleware):
    name = "HagentModelRetry"

    def __init__(self, policy: ModelRetryPolicy | None = None):
        if policy is None:
            from hagent.config import HagentConfig
            policy = ModelRetryPolicy.from_config(HagentConfig.from_env())
        self.policy = policy

    def _failed(self, exc: Exception, attempt: int, context: dict, emit: Any) -> float:
        if isinstance(exc, ModelCallFailed):
            raise exc
        info = classify_error(exc)
        exhausted = attempt > self.policy.max_retries
        delay = self.policy.delay_ms(attempt, info) if info.retryable and not exhausted else 0
        logger.warning("model_call=%s run=%s parent=%s attempt=%s category=%s types=%s status=%s wait_ms=%s outcome=%s",
                       context["model_call_id"], context["run_id"], context["parent_tool_use_id"], attempt,
                       info.category, info.exception_types, info.status_code, round(delay), "stopped" if not delay else "retry")
        if not info.retryable or exhausted:
            raise ModelCallFailed(info, attempt, context) from exc
        emit("model.retry", {**asdict(info), **context, "attempt": attempt, "retry": attempt,
                             "max_retries": self.policy.max_retries, "wait_ms": delay,
                             "next_attempt_at": time.time() * 1000 + delay})
        return delay / 1000

    @staticmethod
    def _validate(response: Any) -> None:
        for message in getattr(response, "result", []):
            if getattr(message, "type", "") == "ai" and not message.content and not message.tool_calls:
                raise IncompleteResponseError("模型返回了空回复")
            if getattr(message, "invalid_tool_calls", None):
                raise IncompleteResponseError("模型工具参数未完整生成")

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        context, emit = call_context()
        control = run_control.get() or RunControl()
        for attempt in range(1, self.policy.max_retries + 2):
            control.check()
            data = {**context, "attempt": attempt, "max_retries": self.policy.max_retries}
            emit("model.attempt.started", data)
            token = attempt_context.set(AttemptContext(data, emit))
            try:
                response = handler(request.override(model=adapt_model(request.model, self.policy, data)))
                control.check()
                self._validate(response)
            except Exception as exc:
                control.check()
                delay = self._failed(exc, attempt, context, emit)
            else:
                emit("model.call.completed", data)
                logger.info("model_call=%s attempt=%s outcome=recovered", context["model_call_id"], attempt)
                return response
            finally:
                attempt_context.reset(token)
            control.sleep(delay)
        raise AssertionError("模型重试预算状态异常")

    async def awrap_model_call(self, request: Any, handler: Any) -> Any:
        context, emit = call_context()
        control = run_control.get() or RunControl()
        for attempt in range(1, self.policy.max_retries + 2):
            control.check()
            data = {**context, "attempt": attempt, "max_retries": self.policy.max_retries}
            emit("model.attempt.started", data)
            token = attempt_context.set(AttemptContext(data, emit))
            try:
                response = await handler(request.override(model=adapt_model(request.model, self.policy, data)))
                control.check()
                self._validate(response)
            except Exception as exc:
                control.check()
                delay = self._failed(exc, attempt, context, emit)
            else:
                emit("model.call.completed", data)
                logger.info("model_call=%s attempt=%s outcome=recovered", context["model_call_id"], attempt)
                return response
            finally:
                attempt_context.reset(token)
            await control.asleep(delay)
        raise AssertionError("模型重试预算状态异常")
