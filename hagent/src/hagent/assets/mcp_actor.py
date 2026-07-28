"""调用方上下文注入（票 04 run 归属 + project 绑定，spec §6）。

MCP 工具面是无状态的（工具显式收 project_id），但**调用方身份**必须由 transport
带进来，不能靠 agent 自报：

- ``actor_ref``（run 归属）：审计事件的 actor 落到哪个 run / session。
- ``project_id``（项目绑定）：调用方所属的 hagent 项目。agent 在 sandbox 里看到的
  workspace 是 ``/workspace``，**无从得知自己的 hagent project_id**；不绑定就只能猜
  （2026-07-13 事故：agent 拿招标文件正文里的「项目编号」当 project_id，写脏了一个
  幽灵命名空间并 flail 到沙箱被健康巡检杀掉）。绑定后工具侧据此拒绝越界调用，并把
  正确的 project_id 回给 agent（护栏见 assets/mcp.py 的 `_project_guard`）。

两条注入通道：

- HTTP（server loopback）：client 每次调用带 ``X-Hagent-Actor-Ref`` /
  ``X-Hagent-Project-Id`` header，``AgentContextASGI`` 在请求任务里写进 ContextVar；
  stateless FastMCP 的工具执行任务从请求任务派生（contextvars 随任务创建复制），
  工具侧经 ``current_actor_ref()`` / ``current_project_id()`` 读出。
- stdio（CLI host）：子进程 env ``HAGENT_MCP_ACTOR_REF`` / ``HAGENT_MCP_PROJECT_ID``
  是进程级等价物，作为 ContextVar 未命中时的回退。

与 mcp_guard 分文件：guard 管 transport 准入策略，本文件只管调用方身份传递。
"""

from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Any

ACTOR_REF_HEADER = "X-Hagent-Actor-Ref"
PROJECT_ID_HEADER = "X-Hagent-Project-Id"

ACTOR_REF_ENV = "HAGENT_MCP_ACTOR_REF"
PROJECT_ID_ENV = "HAGENT_MCP_PROJECT_ID"

_ACTOR_REF_HEADER_RAW = ACTOR_REF_HEADER.lower().encode("latin-1")
_PROJECT_ID_HEADER_RAW = PROJECT_ID_HEADER.lower().encode("latin-1")

_actor_ref: ContextVar[str | None] = ContextVar("hagent_mcp_actor_ref", default=None)
_project_id: ContextVar[str | None] = ContextVar("hagent_mcp_project_id", default=None)


def current_actor_ref() -> str | None:
    """工具执行期的 run 归属：HTTP header 注入优先，env 回退（stdio 模式）。"""
    return _actor_ref.get() or os.environ.get(ACTOR_REF_ENV) or None


def current_project_id() -> str | None:
    """工具执行期的项目绑定：HTTP header 注入优先，env 回退（stdio 模式）。

    None = 调用方未绑定项目（如裸 stdio 排障）：此时工具只做项目存在性校验，
    不做越界校验（无基准可比）。
    """
    return _project_id.get() or os.environ.get(PROJECT_ID_ENV) or None


class AgentContextASGI:
    """包裹 streamable_http_app：把调用方上下文 header 收进 ContextVar。

    只读取自定义 header，不做鉴权语义——loopback 内自家 agent 自报身份，
    对外开放（OAuth 2.1）时 run 归属与项目绑定须换由 auth 层给出，届时替换此层。
    """

    def __init__(self, app: Any):
        self._app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = scope.get("headers", [])
        tokens: list[tuple[ContextVar[str | None], Any]] = []
        for raw_name, var in (
            (_ACTOR_REF_HEADER_RAW, _actor_ref),
            (_PROJECT_ID_HEADER_RAW, _project_id),
        ):
            value = next((v for k, v in headers if k == raw_name), None)
            if value:
                tokens.append((var, var.set(value.decode("latin-1"))))
        try:
            await self._app(scope, receive, send)
        finally:
            for var, token in reversed(tokens):
                var.reset(token)
