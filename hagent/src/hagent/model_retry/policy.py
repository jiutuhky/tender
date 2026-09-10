"""模型故障分类与退避：只返回安全摘要，诊断不包含请求正文或认证信息。"""
from __future__ import annotations

import asyncio
import math
import random
import ssl
import time
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


class IncompleteResponseError(ConnectionError):
    """传输结束，但模型未提供完整结束标志。"""


class ModelTimeoutError(TimeoutError):
    """模型首响应或流内进展超时。"""


class ModelRunCancelled(BaseException):
    """运行控制信号，必须穿透工具的异常兜底。"""


@dataclass(frozen=True)
class ModelErrorInfo:
    category: str
    retryable: bool
    message: str
    action: str
    status_code: int | None = None
    request_id: str | None = None
    retry_after_ms: float | None = None
    exception_types: tuple[str, ...] = ()


class ModelCallFailed(Exception):
    """单次逻辑模型调用已终止，父智能体不得重新派发绕过预算。"""
    def __init__(self, info: ModelErrorInfo, attempts: int, context: dict[str, Any]):
        self.info, self.attempts, self.context = info, attempts, context
        super().__init__(info.message)

    def payload(self) -> dict[str, Any]:
        return {
            **asdict(self.info), **self.context, "code": "model_call_failed",
            "attempts": self.attempts, "attempt": self.attempts, "exhausted": self.info.retryable,
            "message": self.info.message + (
                f"已尝试 {self.attempts} 次，本轮已停止。" if self.info.retryable else "本轮已停止。"
            ),
        }


def exception_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    seen: set[int] = set()
    while id(exc) not in seen:
        chain.append(exc)
        seen.add(id(exc))
        nested = exc.__cause__ or exc.__context__
        if nested is None:
            break
        exc = nested
    return chain


def retry_after(headers: Any, now: float) -> float | None:
    """服务端要求的最小等待时间；允许长等待，不另设累计上限。"""
    for key in ("retry-after-ms", "retry-after"):
        value = headers.get(key)
        if value is None:
            continue
        try:
            seconds = float(value) / (1000 if key.endswith("-ms") else 1)
        except (ValueError, TypeError):
            try:
                seconds = max(0, parsedate_to_datetime(value).timestamp() - now)
            except (ValueError, TypeError, OverflowError):
                continue
        if math.isfinite(seconds) and seconds >= 0:
            return seconds * 1000
    return None


def classify_error(exc: BaseException, *, now: float | None = None) -> ModelErrorInfo:
    chain = exception_chain(exc)
    if any(isinstance(e, (asyncio.CancelledError, ModelRunCancelled)) for e in chain):
        raise ModelRunCancelled()
    headers: dict[str, str] = {}
    status = None
    request_id = None
    texts: list[str] = []
    for e in chain:
        response = getattr(e, "response", None)
        status = status or getattr(e, "status_code", None) or getattr(response, "status_code", None)
        headers.update({str(k).lower(): str(v) for k, v in (getattr(response, "headers", None) or {}).items()})
        request_id = request_id or getattr(e, "request_id", None)
        texts.extend((str(e), str(getattr(e, "body", ""))))
    description = " ".join(texts).lower()
    types = tuple(type(e).__name__ for e in chain)
    request_id = request_id or headers.get("request-id") or headers.get("x-request-id")
    # 请求 ID 只接受有界的标识符，不能把异常正文作为诊断字段输出。
    if request_id and (len(str(request_id)) > 160 or not all(c.isalnum() or c in "-_.:" for c in str(request_id))):
        request_id = None
    def info(category: str, retryable: bool, message: str, action: str) -> ModelErrorInfo:
        return ModelErrorInfo(category, retryable and headers.get("x-should-retry", "").lower() != "false",
                              message, action, status, request_id,
                              retry_after(headers, time.time() if now is None else now), types)
    def contains(*words: str) -> bool:
        return any(word in description for word in words)
    # 明确永久故障优先于网关 HTTP 500、x-should-retry:true。
    if any(isinstance(e, ssl.SSLCertVerificationError) for e in chain) or contains("certificate_verify_failed", "certificate verify failed"):
        return info("certificate", False, "模型服务的安全证书校验失败。", "请检查网关证书和本机信任配置。")
    if status == 401 or contains("authentication_error", "invalid api key", "invalid_api_key", "invalid x-api-key", "unauthorized"):
        return info("authentication", False, "模型服务密钥无效或已失效。", "请更新模型服务密钥后重新发送。")
    if contains("insufficient_quota", "insufficient balance", "credit balance", "billing", "余额不足", "quota exhausted") or status == 402:
        return info("billing", False, "模型服务余额或额度不足。", "请检查服务商账户额度后重新发送。")
    if status == 403 or contains("permission_error", "permission denied", "access denied"):
        return info("permission", False, "模型服务拒绝了访问权限。", "请检查密钥权限和模型授权。")
    if contains("convert_request_failed", "not implemented", "unsupported protocol", "unsupported endpoint"):
        return info("protocol", False, "模型网关不支持当前请求协议。", "请检查网关的 Anthropic 协议支持和地址配置。")
    if status == 404 or contains("model_not_found", "model not found", "model does not exist", "unknown model"):
        return info("model_not_found", False, "指定模型不存在或当前账户无法使用。", "请检查模型名称与服务商模型列表。")
    if status == 413 or contains("context_length", "context window", "prompt is too long", "maximum context", "too many tokens", "request too large"):
        return info("context_limit", False, "本次请求超出模型的上下文或大小限制。", "请缩小本次处理范围或开启新会话。")
    if status in (400, 422) or contains("invalid_request_error", "invalid request", "invalid_request"):
        return info("invalid_request", False, "模型服务无法接受本次请求参数。", "请检查模型参数与协议兼容性。")
    if any(type(e).__name__ == "SandboxUnavailable" for e in chain):
        raise ModelRunCancelled("任务执行环境已停止。")
    if status == 429 or contains("rate_limit_error", "rate limit exceeded"):
        return info("rate_limit", True, "模型服务暂时限流。", "可稍后恢复上次要求并重新发送。")
    if status == 529 or contains("overloaded_error", "overloaded", "server busy"):
        return info("overloaded", True, "模型服务暂时过载。", "可稍后恢复上次要求并重新发送。")
    if any(isinstance(e, IncompleteResponseError) for e in chain):
        return info("incomplete_response", True, "模型响应中途断开。", "可恢复上次要求并重新发送。")
    if any(isinstance(e, (TimeoutError, httpx.TimeoutException)) or "Timeout" in type(e).__name__ for e in chain):
        return info("timeout", True, "等待模型响应超时。", "请稍后重试，或检查模型服务连接。")
    if status in (408, 409) or isinstance(status, int) and status >= 500:
        return info("server", True, "模型服务暂时异常。", "可稍后恢复上次要求并重新发送。")
    if any(isinstance(e, (ConnectionError, httpx.NetworkError, httpx.RemoteProtocolError, ssl.SSLEOFError)) or type(e).__name__ == "APIConnectionError" for e in chain) or contains("econnreset", "epipe", "temporary failure in name resolution", "unexpected eof"):
        return info("connection", True, "暂时无法连接模型服务。", "请检查网络或稍后重新发送。")
    if headers.get("x-should-retry", "").lower() == "true" and status is not None:
        return info("server", True, "模型服务要求稍后重试。", "请稍后恢复上次要求并重新发送。")
    return info("internal", False, "模型调用出现程序异常。", "请联系维护人员并提供请求标识。")


@dataclass(frozen=True)
class ModelRetryPolicy:
    max_retries: int = 10
    base_ms: float = 500
    max_delay_ms: float = 32000
    connect_timeout: float = 10
    first_response_timeout: float = 600
    stream_idle_timeout: float = 90

    @classmethod
    def from_config(cls, config: Any) -> ModelRetryPolicy:
        return cls(config.model_max_retries, config.model_retry_base_ms, config.model_retry_max_delay_ms,
                   config.model_connect_timeout_seconds, config.model_first_response_timeout_seconds,
                   config.model_stream_idle_timeout_seconds)

    def delay_ms(self, retry: int, error: ModelErrorInfo, random_value: float | None = None) -> float:
        jitter = random.random() if random_value is None else random_value
        if error.retry_after_ms is not None:
            return error.retry_after_ms + jitter * 1000
        base = min(self.base_ms * 2 ** min(retry - 1, 63), self.max_delay_ms)
        return base * (1 + 0.25 * jitter)
