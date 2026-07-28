"""http 型 hook 执行器：POST payload JSON 到配置 URL。

对齐 CC execHttpHook：默认超时 600s；响应 body 必须是 JSON（空 body 当
``{}``）并按 HookJSONOutput 处理；header 值支持 ``$VAR``/``${VAR}`` 环境变量
插值（仅 ``allowedEnvVars`` 白名单内的变量），并剥离 CR/LF/NUL 防 header
注入。SessionStart/Setup 不支持 http hook（runner 层过滤）。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Mapping

import httpx
from pydantic import ValidationError

from hagent.hooks.events import HookEvent, default_timeout_s
from hagent.hooks.results import HookExecutionResult, process_json_output
from hagent.hooks.schema import HookJSONOutput, HttpHookConfig

logger = logging.getLogger(__name__)

_ENV_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}|\$([A-Z_][A-Z0-9_]*)")
_HEADER_UNSAFE_RE = re.compile(r"[\r\n\x00]")


def _interpolate_env(
    value: str, allowed: frozenset[str], env: Mapping[str, str]
) -> str:
    def _sub(m: re.Match[str]) -> str:
        name = m.group(1) or m.group(2)
        if name not in allowed:
            logger.warning("http hook header 引用了白名单外的环境变量 $%s，置空", name)
            return ""
        return env.get(name, "")

    return _HEADER_UNSAFE_RE.sub("", _ENV_VAR_RE.sub(_sub, value))


def build_headers(
    hook: HttpHookConfig, env: Mapping[str, str]
) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if hook.headers:
        allowed = frozenset(hook.allowed_env_vars or [])
        for name, value in hook.headers.items():
            headers[name] = _interpolate_env(value, allowed, env)
    return headers


async def execute_http_hook(
    hook: HttpHookConfig,
    payload_json: str,
    event: HookEvent,
    *,
    env: Mapping[str, str],
    client: httpx.AsyncClient | None = None,
) -> HookExecutionResult:
    timeout = (
        hook.timeout if hook.timeout is not None else default_timeout_s(event, "http")
    )
    headers = build_headers(hook, env)
    own_client = client is None
    client = client or httpx.AsyncClient(follow_redirects=False)
    try:
        response = await client.post(
            hook.url,
            content=payload_json,
            headers=headers,
            timeout=timeout,
        )
    except httpx.TimeoutException:
        return HookExecutionResult(
            outcome="cancelled",
            stderr=f"HTTP hook cancelled: timed out after {timeout}s",
        )
    except httpx.HTTPError as exc:
        return HookExecutionResult(
            outcome="non_blocking_error",
            error_message=f"HTTP hook error: {exc}",
        )
    finally:
        if own_client:
            await client.aclose()

    body = response.text or ""
    if not (200 <= response.status_code < 300):
        return HookExecutionResult(
            outcome="non_blocking_error",
            stdout=body,
            error_message=(
                f"HTTP hook failed with status {response.status_code}: "
                f"{body[:500] or 'empty body'}"
            ),
        )

    result = HookExecutionResult(outcome="success", exit_code=0, stdout=body)
    trimmed = body.strip()
    if not trimmed:
        return result  # 空 body 当 {}（无控制字段）
    try:
        parsed = HookJSONOutput.model_validate(json.loads(trimmed))
    except (json.JSONDecodeError, ValidationError) as exc:
        return HookExecutionResult(
            outcome="non_blocking_error",
            stdout=body,
            error_message=f"HTTP hook response is not valid hook JSON: {exc}",
        )
    try:
        process_json_output(result, parsed, event)
    except ValueError as exc:
        return HookExecutionResult(
            outcome="non_blocking_error", stdout=body, error_message=str(exc)
        )
    return result
