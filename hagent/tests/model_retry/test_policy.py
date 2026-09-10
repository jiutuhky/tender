"""可控随机数与传输故障，不连接真实模型。"""
import ssl
from email.utils import formatdate

import anthropic
import httpx
import pytest

from hagent.config import HagentConfig
from hagent.model_retry.policy import ModelRetryPolicy, classify_error, retry_after, IncompleteResponseError


def api_error(status, body=None, headers=None):
    response = httpx.Response(status, headers=headers or {}, request=httpx.Request("POST", "https://model.test/v1/messages"))
    return anthropic.APIStatusError(str(body or status), response=response, body=body)


@pytest.mark.parametrize("error,category,retryable", [
    (ConnectionResetError(), "connection", True),
    (ssl.SSLEOFError("TLS EOF"), "connection", True),
    (httpx.ConnectError("temporary DNS failure"), "connection", True),
    (httpx.ReadTimeout("timed out"), "timeout", True),
    (IncompleteResponseError(), "incomplete_response", True),
    (api_error(408), "server", True), (api_error(409), "server", True),
    (api_error(429), "rate_limit", True), (api_error(529), "overloaded", True),
    (api_error(502), "server", True), (api_error(500), "server", True),
    (api_error(200, {"error": {"type": "overloaded_error"}}), "overloaded", True),
    (api_error(500, {"code": "convert_request_failed", "message": "not implemented"}, {"x-should-retry": "true"}), "protocol", False),
    (api_error(500, {"error": {"type": "authentication_error"}}), "authentication", False),
    (api_error(429, {"error": "insufficient_quota"}), "billing", False),
    (api_error(401), "authentication", False), (api_error(403), "permission", False),
    (api_error(404), "model_not_found", False), (api_error(413), "context_limit", False),
    (api_error(400), "invalid_request", False),
    (ssl.SSLCertVerificationError("certificate verify failed"), "certificate", False),
    (ValueError("bad local value"), "internal", False),
    (api_error(503, headers={"x-should-retry": "false"}), "server", False),
])
def test_classification(error, category, retryable):
    info = classify_error(error)
    assert (info.category, info.retryable) == (category, retryable)


def test_exception_chain_and_safe_diagnostics():
    inner = ssl.SSLCertVerificationError("secret-body sk-private")
    error = anthropic.APIConnectionError(request=httpx.Request("POST", "https://model.test"))
    error.__cause__ = inner
    result = classify_error(error)
    assert result.category == "certificate"
    assert "sk-private" not in str(result)
    assert result.exception_types == ("APIConnectionError", "SSLCertVerificationError")


@pytest.mark.parametrize("retry,base", [(1, 500), (2, 1000), (6, 16000), (7, 32000), (10, 32000)])
def test_backoff(retry, base):
    policy = ModelRetryPolicy()
    info = classify_error(ConnectionError())
    assert policy.delay_ms(retry, info, 0) == base
    assert policy.delay_ms(retry, info, 1) == base * 1.25


def test_retry_after():
    now = 1700000000
    assert retry_after({"retry-after-ms": "1234", "retry-after": "8"}, now) == 1234
    assert retry_after({"retry-after": "1.5"}, now) == 1500
    assert retry_after({"retry-after": formatdate(now + 7200, usegmt=True)}, now) == 7200000
    assert retry_after({"retry-after-ms": "bad", "retry-after": "2"}, now) == 2000
    for invalid in ["-3", "nan", "inf", "bad"]:
        assert retry_after({"retry-after": invalid}, now) is None
    info = classify_error(api_error(429, headers={"retry-after": "3600"}))
    assert ModelRetryPolicy().delay_ms(1, info, 0) == 3600000
    assert ModelRetryPolicy().delay_ms(1, info, 1) == 3601000


def test_config_defaults_and_overrides(monkeypatch):
    cfg = HagentConfig(model="anthropic:test", langsmith_tracing=False)
    assert ModelRetryPolicy.from_config(cfg) == ModelRetryPolicy()
    monkeypatch.setenv("HAGENT_MODEL_MAX_RETRIES", "0")
    monkeypatch.setenv("HAGENT_MODEL_STREAM_IDLE_TIMEOUT_SECONDS", "12")
    assert HagentConfig.from_env().model_max_retries == 0
    assert HagentConfig.from_env().model_stream_idle_timeout_seconds == 12
    monkeypatch.setenv("HAGENT_MODEL_RETRY_BASE_MS", "nan")
    with pytest.raises(ValueError):
        HagentConfig.from_env()
