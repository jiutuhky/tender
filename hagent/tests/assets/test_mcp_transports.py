"""双 transport（票 03）：stdio 全链 e2e、HTTP loopback/Origin 门、跨 client 一致性。

草稿态等一切状态只在 DB（WAL 跨进程共享）：stdio 子进程与 server 进程内的
HTTP client 交替操作同一草稿，行为必须一致。
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tests.prose_mcp import register_project

PROJECT = "p-transport"

SOURCE_LINES = [
    "# 招标文件",
    "",
    "投标人须具备有效的信息系统建设资质，并提供近三年同类项目业绩证明。",
    "系统须支持每秒一千次并发查询，响应时间不超过两百毫秒。",
    "所有数据须在境内存储，并通过等级保护三级测评。",
]

ENVELOPE = {
    "project_id": "ZB-2026-001",
    "project_name": "示例信息化项目",
    "extraction_summary": {"status": "complete", "confidence": "high", "warnings": []},
}

HTTP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
    "MCP-Protocol-Version": "2025-06-18",
}


def _record(i: int, line: int, *, text: str | None = None, doc_id: str) -> dict:
    return {
        "id": f"TECH-{i:03d}",
        "category": "function",
        "title": f"条目 {i}",
        "requirement_text": SOURCE_LINES[line - 1] if text is None else text,
        "mandatory": False,
        "response_required": True,
        "source_refs": [{"document_id": doc_id, "line_span": [line, line]}],
        "confidence": "high",
    }


@pytest.fixture
def shared_env(tmp_path, monkeypatch):
    """server（进程内 app）与 stdio 子进程共享的 DB / workspace 约定。"""
    db_path = tmp_path / "hagent.sqlite"
    workspace_root = tmp_path / "workspaces"
    ws = workspace_root / "projects" / PROJECT / "workspace"
    (ws / "docs").mkdir(parents=True)
    (ws / "docs" / "tender.md").write_text("\n".join(SOURCE_LINES), encoding="utf-8")
    monkeypatch.setenv("HAGENT_SESSIONS_DB", str(db_path))
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(workspace_root))
    monkeypatch.setenv("HAGENT_SANDBOX_KIND", "none")
    # HTTP 侧（进程内 app）的 project 护栏认 ProjectStore；stdio 侧无 server 装配，
    # 回落 workspace 目录存在性判定——两条链路都要能过。
    register_project(db_path, PROJECT, name="transport")
    return {"db_path": db_path, "workspace_root": workspace_root}


def _stdio_params(shared_env) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "hagent.assets.mcp"],
        env={
            "PATH": os.environ.get("PATH", ""),
            "HAGENT_SESSIONS_DB": str(shared_env["db_path"]),
            "HAGENT_WORKSPACE_ROOT": str(shared_env["workspace_root"]),
        },
    )


async def _call(session: ClientSession, name: str, arguments: dict) -> dict | None:
    result = await session.call_tool(name, arguments)
    assert not result.isError, result.content[0].text
    return result.structuredContent


async def test_stdio_full_chain(shared_env):
    """验收链：注册 → 开草稿 → 提交 → 修复 → validate → publish。"""
    async with stdio_client(_stdio_params(shared_env)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            doc = await _call(
                session,
                "prose_register_document",
                {"project_id": PROJECT, "path": "docs/tender.md", "doc_type": "tender"},
            )
            assert doc["created"] is True

            info = await _call(
                session,
                "prose_start_matrix_draft",
                {"project_id": PROJECT, "matrix_type": "technical"},
            )
            assert info["state"] == "drafting"

            await _call(
                session,
                "prose_set_matrix_meta",
                {"project_id": PROJECT, "matrix": "technical", "set": ENVELOPE},
            )
            # 第 2 条 requirement_text 故意改写（源文保真过不了），留给修复步骤
            submitted = await _call(
                session,
                "prose_submit_matrix_records",
                {
                    "project_id": PROJECT,
                    "matrix": "technical",
                    "section": "items",
                    "records": [
                        _record(1, 4, doc_id=doc["id"]),
                        _record(
                            2, 5,
                            text="这是一段完全改写过的要求描述，与源文没有任何字面重叠",
                            doc_id=doc["id"],
                        ),
                    ],
                },
            )
            assert submitted["count"] == 2

            first = await _call(
                session,
                "prose_validate_matrix",
                {"project_id": PROJECT, "matrix": "technical"},
            )
            assert first["all_pass"] is False
            failing = first["reports"][0]
            assert any(i["target"] == "technical/TECH-002" for i in failing["issues"])

            # 行级修复：改回与 line_span 对齐的原文
            fixed = await _call(
                session,
                "prose_update_matrix_item",
                {
                    "project_id": PROJECT,
                    "matrix": "technical",
                    "item_id": "TECH-002",
                    "set": {"requirement_text": SOURCE_LINES[4]},
                    "reason": "源文保真修复",
                    "expected_version": 1,
                },
            )
            assert fixed["version"] == 2

            second = await _call(
                session,
                "prose_validate_matrix",
                {"project_id": PROJECT, "matrix": "technical"},
            )
            assert second["all_pass"] is True

            published = await _call(
                session,
                "prose_publish_matrix",
                {"project_id": PROJECT, "matrix": "technical"},
            )
            assert published["rev"] == 1
            assert published["state"] == "published"

            status = await _call(
                session, "prose_get_matrix_status", {"project_id": PROJECT}
            )
            technical = next(
                m for m in status["matrices"] if m["matrix_type"] == "technical"
            )
            assert technical["state"] == "published"
            assert technical["current_count"] == 2
            assert technical["draft_count"] == 0
            assert technical["last_validation"]["status"] == "pass"


@asynccontextmanager
async def _running_app():
    """在测试自身的 task 里进出 lifespan（anyio cancel scope 不允许跨 task）。"""
    from hagent.server.app import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        yield app


def _http_client(app, *, peer: str = "127.0.0.1") -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app, client=(peer, 40000)),
        base_url="http://127.0.0.1:8000",
    )


async def _http_call(client: httpx.AsyncClient, name: str, arguments: dict) -> dict:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    resp = await client.post("/mcp", json=body, headers=HTTP_HEADERS)
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert not result.get("isError"), json.dumps(result, ensure_ascii=False)
    return result["structuredContent"]


async def test_http_rejects_non_loopback(shared_env):
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    async with _running_app() as app:
        async with _http_client(app) as client:
            # 非 loopback Origin（DNS rebinding 特征）→ 403
            resp = await client.post(
                "/mcp", json=body, headers={**HTTP_HEADERS, "Origin": "http://evil.example.com"}
            )
            assert resp.status_code == 403
            assert resp.json()["error"]["code"] == "loopback_only"
            # loopback Origin 放行
            ok = await client.post(
                "/mcp", json=body, headers={**HTTP_HEADERS, "Origin": "http://localhost:3000"}
            )
            assert ok.status_code == 200
            # 其余路由不受 MCP loopback 门影响
            assert (await client.get("/healthz")).status_code == 200
        async with _http_client(app, peer="10.1.2.3") as remote:
            resp = await remote.post("/mcp", json=body, headers=HTTP_HEADERS)
            assert resp.status_code == 403


async def test_draft_flow_consistent_across_stdio_and_http(shared_env):
    """同一草稿流程跨 stdio 与 HTTP 两个 client 交替操作：状态只在 DB。"""
    params = _stdio_params(shared_env)
    async with _running_app() as http_app:
        await _cross_client_flow(params, http_app)


async def _cross_client_flow(params: StdioServerParameters, http_app) -> None:
    # ① stdio：注册 + 开草稿 + envelope + 第 1 条
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            doc = await _call(
                session,
                "prose_register_document",
                {"project_id": PROJECT, "path": "docs/tender.md", "doc_type": "tender"},
            )
            await _call(
                session,
                "prose_start_matrix_draft",
                {"project_id": PROJECT, "matrix_type": "technical"},
            )
            await _call(
                session,
                "prose_set_matrix_meta",
                {"project_id": PROJECT, "matrix": "technical", "set": ENVELOPE},
            )
            await _call(
                session,
                "prose_submit_matrix_records",
                {
                    "project_id": PROJECT,
                    "matrix": "technical",
                    "section": "items",
                    "records": [_record(1, 4, doc_id=doc["id"])],
                },
            )
            doc_id = doc["id"]

    # ② HTTP：同一草稿续传第 2 条，读到两条
    async with _http_client(http_app) as client:
        await _http_call(
            client,
            "prose_submit_matrix_records",
            {
                "project_id": PROJECT,
                "matrix": "technical",
                "section": "items",
                "records": [_record(2, 5, doc_id=doc_id)],
            },
        )
        overview = await _http_call(
            client, "prose_get_matrix", {"project_id": PROJECT, "matrix": "technical"}
        )
        assert overview["state"] == "drafting"
        assert overview["stats"]["total"] == 2

    # ③ stdio（新子进程 = 新 MCP session）：草稿仍在，校验并发布
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            query = await _call(
                session,
                "prose_query_matrix_items",
                {"project_id": PROJECT, "matrix": "technical"},
            )
            assert query["total_count"] == 2
            report = await _call(
                session,
                "prose_validate_matrix",
                {"project_id": PROJECT, "matrix": "technical"},
            )
            assert report["all_pass"] is True
            published = await _call(
                session,
                "prose_publish_matrix",
                {"project_id": PROJECT, "matrix": "technical"},
            )
            assert published["rev"] == 1

    # ④ HTTP：发布结果对 HTTP client 同样可见
    async with _http_client(http_app) as client:
        status = await _http_call(
            client, "prose_get_matrix_status", {"project_id": PROJECT}
        )
        technical = next(m for m in status["matrices"] if m["matrix_type"] == "technical")
        assert technical["state"] == "published"
        assert technical["current_count"] == 2
