"""MCP HTTP transport 安全（spec §6）：首发只服务 loopback，防 DNS rebinding。

与工具面（mcp.py）分离：本文件只管 transport 准入策略，对外开放（OAuth 2.1）
是独立后续任务，届时替换/扩展此层，不动工具契约。
"""

from __future__ import annotations

import ipaddress
import json
from typing import Any
from urllib.parse import urlsplit

# HTTP 端点路径。子 app 自带该路径并整体挂在 FastAPI 根（SDK 推荐挂法）：
# Mount("/mcp") 会把不带尾斜杠的 POST /mcp 307 到 /mcp/，部分 client 不跟随
MCP_HTTP_PATH = "/mcp"


class LoopbackOnlyASGI:
    """包裹 streamable_http_app：命中 MCP 路径且（对端为非 loopback IP，或携带
    非 loopback Origin）的请求一律 403。"""

    def __init__(self, app: Any, *, guard_path: str = MCP_HTTP_PATH):
        self._app = app
        self._guard_path = guard_path

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "http" and scope.get("path", "").startswith(self._guard_path):
            reason = self._reject_reason(scope)
            if reason is not None:
                await self._forbid(send, reason)
                return
        await self._app(scope, receive, send)

    @staticmethod
    def _is_loopback_host(host: str) -> bool:
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def _reject_reason(self, scope: dict) -> str | None:
        client = scope.get("client")
        if client is not None:
            peer = client[0]
            try:
                peer_ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None = (
                    ipaddress.ip_address(peer)
                )
            except ValueError:
                # 非 IP 对端（unix socket / 进程内测试客户端）：无网络暴露面，
                # 交给 Origin 校验兜底
                peer_ip = None
            if peer_ip is not None and not peer_ip.is_loopback:
                return f"MCP 面只服务 loopback，对端 {peer} 被拒"
        origin = next(
            (value for name, value in scope.get("headers", []) if name == b"origin"), None
        )
        if origin is not None:
            hostname = urlsplit(origin.decode("latin-1")).hostname
            if hostname is None or not self._is_loopback_host(hostname):
                return f"非 loopback Origin 被拒：{origin.decode('latin-1')}"
        return None

    @staticmethod
    async def _forbid(send: Any, reason: str) -> None:
        body = json.dumps(
            {"error": {"code": "loopback_only", "message": reason}}, ensure_ascii=False
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [(b"content-type", b"application/json; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": body})
