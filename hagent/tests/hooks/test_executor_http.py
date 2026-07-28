"""http 执行器测试 —— httpx MockTransport。"""

from __future__ import annotations

import httpx

from hagent.hooks.events import HookEvent
from hagent.hooks.executor_http import build_headers, execute_http_hook
from hagent.hooks.schema import HttpHookConfig


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_posts_payload_and_parses_json_response():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content.decode("utf-8")
        seen["content_type"] = request.headers["content-type"]
        return httpx.Response(200, json={"decision": "block", "reason": "拒绝"})

    res = await execute_http_hook(
        HttpHookConfig(url="http://hooks.test/h"),
        '{"hook_event_name": "PreToolUse"}',
        HookEvent.PRE_TOOL_USE,
        env={},
        client=_client(handler),
    )
    assert seen["body"] == '{"hook_event_name": "PreToolUse"}'
    assert seen["content_type"] == "application/json"
    assert res.outcome == "success"
    assert res.permission_behavior == "deny"
    assert res.blocking_error == "拒绝"


async def test_empty_body_is_ok():
    res = await execute_http_hook(
        HttpHookConfig(url="http://hooks.test/h"),
        "{}",
        HookEvent.STOP,
        env={},
        client=_client(lambda r: httpx.Response(204)),
    )
    assert res.outcome == "success"
    assert res.blocking_error is None


async def test_non_2xx_is_non_blocking_error():
    res = await execute_http_hook(
        HttpHookConfig(url="http://hooks.test/h"),
        "{}",
        HookEvent.STOP,
        env={},
        client=_client(lambda r: httpx.Response(500, text="boom")),
    )
    assert res.outcome == "non_blocking_error"
    assert "500" in (res.error_message or "")


async def test_invalid_json_body_is_non_blocking_error():
    res = await execute_http_hook(
        HttpHookConfig(url="http://hooks.test/h"),
        "{}",
        HookEvent.STOP,
        env={},
        client=_client(lambda r: httpx.Response(200, text="not json")),
    )
    assert res.outcome == "non_blocking_error"


async def test_connection_error_is_non_blocking():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    res = await execute_http_hook(
        HttpHookConfig(url="http://hooks.test/h"),
        "{}",
        HookEvent.STOP,
        env={},
        client=_client(handler),
    )
    assert res.outcome == "non_blocking_error"


def test_header_env_interpolation_allowlist():
    hook = HttpHookConfig.model_validate(
        {
            "type": "http",
            "url": "http://hooks.test/h",
            "headers": {
                "Authorization": "Bearer $MY_TOKEN",
                "X-Other": "${NOT_ALLOWED}",
                "X-Evil": "$MY_TOKEN\r\nX-Injected: 1",
            },
            "allowedEnvVars": ["MY_TOKEN"],
        }
    )
    headers = build_headers(hook, {"MY_TOKEN": "sek", "NOT_ALLOWED": "leak"})
    assert headers["Authorization"] == "Bearer sek"
    assert headers["X-Other"] == ""  # 白名单外置空
    assert "\r" not in headers["X-Evil"] and "\n" not in headers["X-Evil"]
    assert headers["Content-Type"] == "application/json"
