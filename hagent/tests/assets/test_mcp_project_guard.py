"""MCP 面的 project 护栏：project_id 必须是真实的 hagent 项目，且不得跨会话越界。

背景（2026-07-13 实测事故）：agent 无从得知自己的 hagent project_id，于是从招标文件
正文里读到「项目编号：2025-JQ04-F1054」当成 project_id 传给全部 prose_* 工具。只读与
草稿类工具照单全收（对象库按 project_id 建命名空间、读时不存在即返空），坐实了错误判断；
唯独碰文件系统的 prose_register_document 报 file_not_found——agent 用 Bash 明明看得见
那个文件，却被工具告知不存在，陷入无法自解的矛盾，flail 了 60 余次工具调用直至沙箱被
健康巡检杀掉。

两道护栏（对齐 REST adapter 的 `_require_project` 404 语义）：
- project_not_found：project_id 不是已存在的 hagent 项目 → 第一次调用即 fail loud，
  错误 hint 点明「不是招标文件正文里的项目编号」，且对象库零污染。
- project_mismatch：调用方（会话）已绑定项目时，传入的 project_id 必须与之一致；
  错误 message 携带正确的 project_id，agent 据此自愈，无需人工介入。
"""

from __future__ import annotations

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from hagent.assets.mcp import build_mcp_server
from hagent.assets.mcp_actor import PROJECT_ID_ENV, current_project_id

PROJECT = "136e7c24669044f1"  # hagent 项目 id
GHOST = "2025-JQ04-F1054"  # 招标文件正文里的项目编号（事故里被误当 project_id）

SOURCE_LINES = [
    "# 招标文件",
    "",
    "投标人须具备有效的信息系统建设资质，并提供近三年同类项目业绩证明。",
]


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "projects" / PROJECT / "workspace"
    (ws / "sources").mkdir(parents=True)
    (ws / "sources" / "tender.md").write_text("\n".join(SOURCE_LINES), encoding="utf-8")
    return ws


@pytest.fixture
def mcp_server(service, workspace):
    """project_exists 由 server 侧注入（app.py 传 ProjectStore）；此处模拟只有 PROJECT 存在。"""
    return build_mcp_server(
        service,
        workspace_for=lambda project_id: workspace,
        project_exists=lambda project_id: project_id == PROJECT,
    )


@pytest.fixture(autouse=True)
def no_ambient_binding(monkeypatch):
    """默认无会话绑定（stdio/CLI 语义）；需要绑定的用例自行 setenv。"""
    monkeypatch.delenv(PROJECT_ID_ENV, raising=False)


def _error_payload(result) -> dict:
    assert result.isError
    text = result.content[0].text
    return json.loads(text[text.index("{") :])


async def _call(mcp_server, name: str, args: dict):
    async with create_connected_server_and_client_session(mcp_server) as session:
        return await session.call_tool(name, args)


class TestProjectNotFound:
    async def test_read_tool_rejects_unknown_project(self, mcp_server):
        """事故第一现场：prose_get_matrix_status 曾对幽灵 project_id 返回四矩阵全 empty。"""
        result = await _call(mcp_server, "prose_get_matrix_status", {"project_id": GHOST})

        payload = _error_payload(result)
        assert payload["code"] == "project_not_found"
        assert GHOST in payload["message"]
        assert "项目编号" in payload["hint"]  # 点明「不是招标文件里的编号」

    async def test_draft_tool_rejects_unknown_project_without_polluting_store(
        self, mcp_server, service
    ):
        """写入面：开草稿曾在幽灵命名空间里建出 matrices/asset_events 记录。"""
        result = await _call(
            mcp_server,
            "prose_start_matrix_draft",
            {"project_id": GHOST, "matrix_type": "basic_info"},
        )

        assert _error_payload(result)["code"] == "project_not_found"
        assert service.matrix_status(GHOST) == [] or all(
            entry.state.value == "empty" for entry in service.matrix_status(GHOST)
        )
        assert service.get_matrix_info(GHOST, "basic_info").state.value == "empty"

    async def test_known_project_passes(self, mcp_server):
        result = await _call(mcp_server, "prose_get_matrix_status", {"project_id": PROJECT})

        assert not result.isError


class TestProjectMismatch:
    async def test_bound_session_rejects_other_project(self, mcp_server, monkeypatch):
        """会话已绑定项目时越界写别的项目：拒绝，并把正确的 project_id 告诉 agent。"""
        monkeypatch.setenv(PROJECT_ID_ENV, PROJECT)

        result = await _call(mcp_server, "prose_get_matrix_status", {"project_id": GHOST})

        payload = _error_payload(result)
        assert payload["code"] == "project_mismatch"
        assert PROJECT in payload["hint"]  # 自愈线索：正确的 project_id 就在错误里

    async def test_bound_session_accepts_its_own_project(self, mcp_server, monkeypatch):
        monkeypatch.setenv(PROJECT_ID_ENV, PROJECT)

        result = await _call(mcp_server, "prose_get_matrix_status", {"project_id": PROJECT})

        assert not result.isError

    async def test_env_binding_readable(self, monkeypatch):
        monkeypatch.setenv(PROJECT_ID_ENV, PROJECT)
        assert current_project_id() == PROJECT


class TestGuardCoversWholeSurface:
    async def test_every_project_scoped_tool_guards(self, mcp_server):
        """护栏挂在 tool 装配处，不是逐个工具手写——新增工具自动继承。"""
        async with create_connected_server_and_client_session(mcp_server) as session:
            tools = (await session.list_tools()).tools
            scoped = [
                t for t in tools if "project_id" in t.inputSchema.get("properties", {})
            ]
            assert len(scoped) == 15  # spec §5 的 15 个工具全部按 project 命名空间

        minimal = {
            "prose_register_document": {"path": "sources/tender.md"},
            "prose_list_documents": {},
            "prose_start_matrix_draft": {"matrix_type": "basic_info"},
            "prose_submit_matrix_records": {
                "matrix": "basic_info",
                "section": "timeline",
                "records": [{"event": "bid_deadline"}],
            },
            "prose_update_matrix_item": {
                "matrix": "technical",
                "item_id": "TECH-001",
                "set": {"title": "x"},
            },
            "prose_drop_matrix_item": {"matrix": "technical", "item_id": "TECH-001"},
            "prose_move_matrix_item": {
                "from_matrix": "technical",
                "to_matrix": "business",
                "item_id": "TECH-001",
                "new_id": "BIZ-009",
            },
            "prose_set_matrix_meta": {"matrix": "basic_info", "set": {"project_name": "x"}},
            "prose_validate_matrix": {"matrix": "basic_info"},
            "prose_publish_matrix": {"matrix": "basic_info"},
            "prose_get_matrix": {"matrix": "basic_info"},
            "prose_query_matrix_items": {"matrix": "basic_info"},
            "prose_get_matrix_status": {},
            "prose_set_item_response_status": {
                "matrix": "technical",
                "item_id": "TECH-001",
                "status": "compliant",
            },
            "prose_confirm_matrix_item": {"matrix": "technical", "item_id": "TECH-001"},
        }
        assert set(minimal) == {t.name for t in scoped}

        for name, args in minimal.items():
            result = await _call(mcp_server, name, {"project_id": GHOST, **args})
            assert _error_payload(result)["code"] == "project_not_found", name
