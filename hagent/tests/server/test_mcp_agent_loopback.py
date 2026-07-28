"""server 模式 MCP client 接入（票 04）：loopback Streamable HTTP 链路。

真 uvicorn（127.0.0.1 临时端口）跑完整 app（含 LoopbackOnlyASGI 与
AgentContextASGI），agent 侧经 langchain-mcp-adapters 连 /mcp：工具可见可调、
run 归属与项目绑定 header 进审计/护栏、session 装配线传对连接。
"""

from __future__ import annotations

import sqlite3
import threading
import time
from unittest.mock import MagicMock

import pytest
import uvicorn

from hagent.mcp_tools import load_prose_mcp_tools, prose_http_connection
from tests.prose_mcp import (
    EXPECTED_PROSE_TOOLS,
    content_json as _content_json,
    make_prose_workspace,
)

@pytest.fixture
def live_server(tmp_path, monkeypatch):
    """真端口起完整 app：MCP loopback 链路需要真 socket（进程内 ASGI 调用
    会跨事件循环触碰 stateless session manager 的 lifespan task group）。

    项目经 ProjectStore 真实建出——server 模式的 project 护栏认 ProjectStore
    （幽灵 project_id 一律 project_not_found），workspace 目录单独存在不算数。"""
    from hagent.server.projects import ProjectStore

    db_path = tmp_path / "hagent.sqlite"
    project = ProjectStore(db_path).create("loopback").id
    paths = make_prose_workspace(tmp_path, project)
    assert paths["db_path"] == db_path  # helper 与本 fixture 同一 DB 文件
    monkeypatch.setenv("HAGENT_SESSIONS_DB", str(db_path))
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(paths["workspace_root"]))

    from hagent.server.app import create_app

    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=0, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started:
        if time.time() > deadline or not thread.is_alive():
            raise RuntimeError("uvicorn 测试实例未能启动")
        time.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield {"url": f"http://127.0.0.1:{port}/mcp", "db_path": db_path, "project": project}
    server.should_exit = True
    thread.join(timeout=10)


def test_agent_tools_visible_and_callable_via_loopback(live_server):
    """session 内 agent 工具面：15 个 prose_* 可见（锁名字——SSE 工具事件与
    前端 08 票依赖），可调，run 归属 header 落审计。"""
    project = live_server["project"]
    tools = {
        t.name: t
        for t in load_prose_mcp_tools(
            prose_http_connection(
                url=live_server["url"], actor_ref="session:s-loop", project_id=project
            )
        )
    }
    assert set(tools) == EXPECTED_PROSE_TOOLS

    doc = _content_json(
        tools["prose_register_document"].invoke(
            {"project_id": project, "path": "docs/tender.md", "doc_type": "tender"}
        )
    )
    assert doc["created"] is True

    status = _content_json(
        tools["prose_get_matrix_status"].invoke({"project_id": project})
    )
    assert len(status["matrices"]) == 4

    rows = sqlite3.connect(live_server["db_path"]).execute(
        "SELECT actor_kind, actor_ref, action FROM asset_events"
    ).fetchall()
    assert rows == [("agent", "session:s-loop", "register_document")]


def test_sse_tool_call_events_carry_prose_tool_name():
    """SSE 工具事件按名透传（前端 08 票依赖 prose_* 事件名，AC1）。"""
    from hagent.server.sse import parse_lg_chunk

    class FakeToolCallStart:
        type = "AIMessageChunk"
        content = ""
        tool_call_chunks = [
            {
                "name": "prose_submit_matrix_records",
                "args": '{"matrix":"technical"',
                "id": "call-1",
                "index": 0,
            }
        ]

    class FakeToolResult:
        type = "tool"
        name = "prose_submit_matrix_records"
        tool_call_id = "call-1"
        content = '{"count": 2}'

    started = list(parse_lg_chunk(("messages", (FakeToolCallStart(), {}))))
    assert ("tool_call.started", {
        "call_id": "call-1",
        "tool_name": "prose_submit_matrix_records",
        "args_chunk": '{"matrix":"technical"',
        "parent_tool_use_id": None,
    }) in started

    completed = list(parse_lg_chunk(("messages", (FakeToolResult(), {}))))
    assert any(
        event == "tool_call.completed"
        and data["tool_name"] == "prose_submit_matrix_records"
        for event, data in completed
    )


def test_get_or_build_agent_wires_loopback_connection(tmp_path, monkeypatch):
    from hagent.server import agents

    captured: dict = {}

    def fake_create_hagent(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(agents, "_agents", {})
    monkeypatch.setattr(agents, "get_checkpointer", lambda: object())
    monkeypatch.setattr(agents, "create_hagent", fake_create_hagent)

    agents.get_or_build_agent("sid-mcp", str(tmp_path), project_id="p-real")
    conn = captured["mcp_connection"]
    assert conn["transport"] == "streamable_http"
    assert conn["url"].endswith("/mcp")
    # 项目绑定由 server 打进 header：agent 无从得知自己的 hagent project_id，
    # 不绑定它就只能猜（2026-07-13 事故根因）。
    assert conn["headers"] == {
        "X-Hagent-Actor-Ref": "session:sid-mcp",
        "X-Hagent-Project-Id": "p-real",
    }


def test_get_or_build_agent_respects_mcp_disabled(tmp_path, monkeypatch):
    from hagent.server import agents

    captured: dict = {}

    def fake_create_hagent(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(agents, "_agents", {})
    monkeypatch.setattr(agents, "get_checkpointer", lambda: object())
    monkeypatch.setattr(agents, "create_hagent", fake_create_hagent)
    monkeypatch.setenv("HAGENT_MCP_DISABLED", "1")

    agents.get_or_build_agent("sid-mcp-off", str(tmp_path))
    assert captured["mcp_connection"] is None
