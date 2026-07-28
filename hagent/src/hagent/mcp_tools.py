"""prose_* MCP 工具面的 agent 侧接入（票 04，spec §6 / S8）。

真 MCP client（langchain-mcp-adapters）双链路连同一 FastMCP 对象：

- server 模式：loopback Streamable HTTP 连 hagent server 自挂的 ``/mcp``；
  server/agents.py 按 session 构造连接（actor_ref 走 header）。
- CLI host 模式：stdio 拉起 ``python -m hagent.assets.mcp`` 子进程，
  与宿主共享同一 SQLite（WAL）；actor_ref 走子进程 env。

工具调用无持久 MCP session（adapter 每次调用新建 session）——草稿态等一切
状态只在对象库，与 MCP session 无关（spec §5），stateless server 天然匹配。

sync 桥：deepagents graph 在 server（threadpool 里 ``agent.stream``）与 CLI
（``agent.invoke``）都是同步执行，而 adapter 产出的工具只有 coroutine。模块
持有一条后台事件循环线程，给每个工具补上阻塞式 ``func``；连接始终从宿主
进程发起，不随 sandbox 切线（MCP 工具永远宿主执行，对齐 hooks 的宿主纪律）。
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading
from collections.abc import Coroutine
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from hagent.assets.mcp_actor import (
    ACTOR_REF_ENV,
    ACTOR_REF_HEADER,
    PROJECT_ID_ENV,
    PROJECT_ID_HEADER,
)
from hagent.config import resolve_sessions_db_path

PROSE_MCP_SERVER_NAME = "prose"
DEFAULT_MCP_URL = "http://127.0.0.1:8000/mcp"

# 工具面加载（initialize + list_tools）与单次工具调用的阻塞上限。
LOAD_TIMEOUT_S = 60.0
CALL_TIMEOUT_S = 300.0

# stdio 子进程按需透传的宿主 env（不整体继承：收窄泄漏面，对齐
# HagentLocalShellBackend 的 inherit_env=False 纪律）。
_STDIO_PASSTHROUGH_ENV = ("HOME", "HAGENT_WORKSPACE_ROOT", "HAGENT_SKILLS_PATHS")

_bridge_lock = threading.Lock()
_bridge_loop: asyncio.AbstractEventLoop | None = None


def prose_mcp_disabled() -> bool:
    """全局关断（HAGENT_MCP_DISABLED）：测试与排障用，两个装配点都认它。"""
    return os.environ.get("HAGENT_MCP_DISABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def prose_stdio_connection(
    *, actor_ref: str | None = None, project_id: str | None = None
) -> dict[str, Any]:
    """CLI host 模式连接：stdio 拉起同一 FastMCP 对象（python -m hagent.assets.mcp）。

    子进程 cwd 继承宿主（项目层 skill 资源镜像依赖 server 进程 CWD 约定）；
    DB 路径显式传解析结果，保证与宿主进程解析到同一文件。actor_ref（run 归属）与
    project_id（项目绑定）经子进程 env 注入，工具侧由 assets/mcp_actor.py 收。
    """
    env: dict[str, str] = {
        "PATH": os.environ.get("PATH", ""),
        "HAGENT_SESSIONS_DB": resolve_sessions_db_path(),
    }
    for name in _STDIO_PASSTHROUGH_ENV:
        value = os.environ.get(name)
        if value:
            env[name] = value
    if actor_ref:
        env[ACTOR_REF_ENV] = actor_ref
    if project_id:
        env[PROJECT_ID_ENV] = project_id
    return {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-m", "hagent.assets.mcp"],
        "env": env,
    }


def prose_http_connection(
    url: str | None = None, *, actor_ref: str | None = None, project_id: str | None = None
) -> dict[str, Any]:
    """server 模式连接：loopback Streamable HTTP 连自家 ``/mcp``。

    url 解析链：显式参数 → ``HAGENT_MCP_URL`` → 默认 8000 端口（README 的
    uvicorn 规范端口）；server 起在其他端口时必须设 env。actor_ref（run 归属）与
    project_id（项目绑定）经 header 注入（assets/mcp_actor.py 收）——**project_id
    必须由 server 绑定，不能靠 agent 自报**：sandbox 里的 agent 只看得见 /workspace，
    无从得知自己的 hagent project_id，不绑定就只能猜。
    """
    resolved = url or os.environ.get("HAGENT_MCP_URL") or DEFAULT_MCP_URL
    connection: dict[str, Any] = {"transport": "streamable_http", "url": resolved}
    headers = {}
    if actor_ref:
        headers[ACTOR_REF_HEADER] = actor_ref
    if project_id:
        headers[PROJECT_ID_HEADER] = project_id
    if headers:
        connection["headers"] = headers
    return connection


def _ensure_bridge_loop() -> asyncio.AbstractEventLoop:
    """惰性起模块级后台事件循环（daemon 线程），全进程共享一条。"""
    global _bridge_loop
    with _bridge_lock:
        if _bridge_loop is None or _bridge_loop.is_closed():
            loop = asyncio.new_event_loop()
            threading.Thread(
                target=loop.run_forever, name="hagent-mcp-bridge", daemon=True
            ).start()
            _bridge_loop = loop
        return _bridge_loop


def _run_on_bridge(coro: Coroutine[Any, Any, Any], timeout: float) -> Any:
    return asyncio.run_coroutine_threadsafe(coro, _ensure_bridge_loop()).result(timeout)


def _attach_sync_bridge(tool: BaseTool) -> BaseTool:
    """给 adapter 产出的 async-only 工具补 sync 入口（graph 同步执行路径用）。

    async 路径（coroutine）原样保留，调用方在自己的事件循环里直接跑。
    """
    if not isinstance(tool, StructuredTool) or tool.coroutine is None:
        return tool
    coroutine = tool.coroutine

    def _sync_call(**kwargs: Any) -> Any:
        return _run_on_bridge(coroutine(**kwargs), timeout=CALL_TIMEOUT_S)

    tool.func = _sync_call
    return tool


def load_prose_mcp_tools(connection: dict[str, Any]) -> list[BaseTool]:
    """经真 MCP client 加载 prose_* 工具面，返回可注入组装线的 langchain tools。

    同步接口（create_hagent 是同步组装线）：list_tools 在桥线程事件循环上跑，
    server 模式下调用方线程阻塞期间主事件循环仍可服务 /mcp，无自锁。
    加载失败直接抛错（fail loud）：工具面唯一性下，静默降级只会让 skill
    编排在更深处以更难解释的方式失败。
    """
    client = MultiServerMCPClient({PROSE_MCP_SERVER_NAME: connection})
    try:
        tools = _run_on_bridge(client.get_tools(), timeout=LOAD_TIMEOUT_S)
    except Exception as exc:
        raise RuntimeError(
            f"prose MCP 工具面加载失败（transport={connection.get('transport')}，"
            f"target={connection.get('url') or connection.get('command')}）：{exc}"
        ) from exc
    return [_attach_sync_bridge(tool) for tool in tools]
