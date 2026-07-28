"""MCP 工具面（票 03）：清单/schema/annotations 对齐 spec §5；错误结构化可行动。

跨 transport 行为与 stdio/HTTP 全链见 test_mcp_transports.py。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from hagent.assets.mcp import build_mcp_server

PROJECT = "p-mcp-surface"

SPEC_TOOLS = {
    "prose_register_document",
    "prose_list_documents",
    "prose_start_matrix_draft",
    "prose_submit_matrix_records",
    "prose_update_matrix_item",
    "prose_drop_matrix_item",
    "prose_move_matrix_item",
    "prose_set_matrix_meta",
    "prose_validate_matrix",
    "prose_publish_matrix",
    "prose_get_matrix",
    "prose_query_matrix_items",
    "prose_get_matrix_status",
    "prose_set_item_response_status",
    "prose_confirm_matrix_item",
}

READ_ONLY_TOOLS = {
    "prose_list_documents",
    "prose_validate_matrix",
    "prose_get_matrix",
    "prose_query_matrix_items",
    "prose_get_matrix_status",
}

DESTRUCTIVE_TOOLS = {"prose_start_matrix_draft", "prose_drop_matrix_item"}

SOURCE_LINES = [
    "# 招标文件",
    "",
    "投标人须具备有效的信息系统建设资质，并提供近三年同类项目业绩证明。",
    "系统须支持每秒一千次并发查询，响应时间不超过两百毫秒。",
]


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "ws"
    (ws / "docs").mkdir(parents=True)
    (ws / "docs" / "tender.md").write_text("\n".join(SOURCE_LINES), encoding="utf-8")
    return ws


@pytest.fixture
def mcp_server(service, workspace):
    return build_mcp_server(service, workspace_for=lambda project_id: workspace)


def _error_payload(result) -> dict:
    """FastMCP 会给 ToolError 文本加 'Error executing tool …: ' 前缀，
    结构化 payload 是其后的 JSON。"""
    assert result.isError
    text = result.content[0].text
    return json.loads(text[text.index("{"):])


async def test_tool_list_matches_spec(mcp_server):
    async with create_connected_server_and_client_session(mcp_server) as session:
        tools = (await session.list_tools()).tools
        assert {t.name for t in tools} == SPEC_TOOLS
        by_name = {t.name: t for t in tools}
        for name, tool in by_name.items():
            assert tool.annotations is not None, name
            assert tool.annotations.readOnlyHint is (name in READ_ONLY_TOOLS), name
            assert tool.annotations.destructiveHint is (name in DESTRUCTIVE_TOOLS), name
            assert tool.annotations.openWorldHint is False, name
            assert tool.outputSchema is not None, name
        assert by_name["prose_register_document"].annotations.idempotentHint is True


async def test_submit_schema_forces_batch_limit(mcp_server):
    async with create_connected_server_and_client_session(mcp_server) as session:
        tools = (await session.list_tools()).tools
        submit = next(t for t in tools if t.name == "prose_submit_matrix_records")
        records = submit.inputSchema["properties"]["records"]
        assert records["maxItems"] == 10
        assert records["minItems"] == 1


async def test_query_schema_forces_pagination(mcp_server):
    async with create_connected_server_and_client_session(mcp_server) as session:
        tools = (await session.list_tools()).tools
        query = next(t for t in tools if t.name == "prose_query_matrix_items")
        limit = query.inputSchema["properties"]["limit"]
        assert limit["default"] == 20
        assert limit["maximum"] == 100
        for key in ("has_more", "next_offset", "total_count"):
            assert key in query.outputSchema["properties"]


async def test_resources_mirror_skill_files(mcp_server, monkeypatch):
    repo_hagent = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(repo_hagent)  # skill 发现走进程 CWD 的 .hagent/skills
    async with create_connected_server_and_client_session(mcp_server) as session:
        resources = (await session.list_resources()).resources
        assert {str(r.uri) for r in resources} == {
            "prose://contracts/matrix-schema",
            "prose://guides/extraction",
        }
        schema_doc = await session.read_resource("prose://contracts/matrix-schema")
        expected = (
            repo_hagent
            / ".hagent/skills/bid-response-matrix/references/response-matrix-schema.md"
        ).read_text(encoding="utf-8")
        assert schema_doc.contents[0].text == expected


async def test_errors_are_structured_and_actionable(mcp_server):
    async with create_connected_server_and_client_session(mcp_server) as session:
        result = await session.call_tool(
            "prose_submit_matrix_records",
            {
                "project_id": PROJECT,
                "matrix": "technical",
                "section": "items",
                "records": [{"id": "TECH-001"}],
            },
        )
        payload = _error_payload(result)
        assert payload["code"] == "no_draft"
        assert "start_matrix_draft" in payload["hint"]


async def test_conflict_error_carries_current_version(mcp_server, service, agent_actor, workspace):
    content = (workspace / "docs" / "tender.md").read_bytes()
    doc = service.register_document(
        PROJECT, path="docs/tender.md", sha256=hashlib.sha256(content).hexdigest(),
        doc_type="tender", actor=agent_actor,
    )
    service.start_draft(PROJECT, "technical", actor=agent_actor)
    service.submit_records(
        PROJECT, "technical", section="items",
        records=[{
            "id": "TECH-001", "category": "function", "title": "并发",
            "requirement_text": SOURCE_LINES[3], "mandatory": True,
            "source_refs": [{"document_id": doc.id, "line_span": [4, 4]}],
        }],
        actor=agent_actor,
    )
    async with create_connected_server_and_client_session(mcp_server) as session:
        result = await session.call_tool(
            "prose_update_matrix_item",
            {
                "project_id": PROJECT,
                "matrix": "technical",
                "item_id": "TECH-001",
                "set": {"title": "并发性能"},
                "expected_version": 99,
            },
        )
        payload = _error_payload(result)
        assert payload["code"] == "version_conflict"
        assert payload["current_version"] == 1
        assert payload["hint"]


async def test_internal_errors_do_not_leak(mcp_server, service, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("/secret/path/traceback details")

    monkeypatch.setattr(service, "matrix_status", boom)
    async with create_connected_server_and_client_session(mcp_server) as session:
        result = await session.call_tool("prose_get_matrix_status", {"project_id": PROJECT})
        payload = _error_payload(result)
        assert payload["code"] == "internal_error"
        assert "/secret/path" not in result.content[0].text
        assert "RuntimeError" in payload["message"]


async def test_publish_rejection_embeds_full_report(mcp_server, service, agent_actor):
    service.start_draft(PROJECT, "technical", actor=agent_actor)
    service.submit_records(
        PROJECT, "technical", section="items",
        records=[{
            "id": "TECH-001", "category": "function", "title": "无源文条目",
            "requirement_text": "凭空要求", "mandatory": False,
            "source_refs": [{"document_id": "doc-missing", "line_span": [1, 1]}],
        }],
        actor=agent_actor,
    )
    async with create_connected_server_and_client_session(mcp_server) as session:
        result = await session.call_tool(
            "prose_publish_matrix", {"project_id": PROJECT, "matrix": "technical"}
        )
        payload = _error_payload(result)
        assert payload["code"] == "validation_failed"
        assert payload["report"]["error_count"] >= 1
        assert all(
            {"target", "code", "message"} <= issue.keys()
            for issue in payload["report"]["issues"]
        )


async def test_get_matrix_has_stats_but_no_items(mcp_server, service, agent_actor):
    service.start_draft(PROJECT, "technical", actor=agent_actor)
    service.submit_records(
        PROJECT, "technical", section="items",
        records=[{
            "id": "TECH-001", "category": "function", "title": "并发",
            "requirement_text": "x", "mandatory": True,
            "source_refs": [{"document_id": "doc-x", "line_span": [1, 1]}],
        }],
        actor=agent_actor,
    )
    async with create_connected_server_and_client_session(mcp_server) as session:
        result = await session.call_tool(
            "prose_get_matrix", {"project_id": PROJECT, "matrix": "technical"}
        )
        assert not result.isError
        data = result.structuredContent
        assert data["stats"]["total"] == 1
        assert data["stats"]["by_category"] == {"function": 1}
        assert "items" not in data


async def test_query_pagination_behavior(mcp_server, service, agent_actor):
    service.start_draft(PROJECT, "business", actor=agent_actor)
    service.submit_records(
        PROJECT, "business", section="items",
        records=[
            {
                "id": f"BIZ-{i:03d}", "category": "qualification", "title": f"资质 {i}",
                "requirement_text": f"要求 {i}", "mandatory": False,
                "source_refs": [{"document_id": "doc-x", "line_span": [1, 1]}],
            }
            for i in range(1, 8)
        ],
        actor=agent_actor,
    )
    async with create_connected_server_and_client_session(mcp_server) as session:
        result = await session.call_tool(
            "prose_query_matrix_items",
            {"project_id": PROJECT, "matrix": "business", "limit": 3, "offset": 6},
        )
        data = result.structuredContent
        assert data["total_count"] == 7
        assert len(data["items"]) == 1
        assert data["has_more"] is False
        assert data["next_offset"] is None
