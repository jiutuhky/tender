"""prose MCP 工具面测试共享件（票 04）：名字契约与调用结果解析。

15 个工具名是跨层契约（SSE 工具事件 → 前端 08 票），host 侧与 server 侧
测试都要锁同一份清单——改名必须两条链路同时红。
"""

from __future__ import annotations

import json
from pathlib import Path

EXPECTED_PROSE_TOOLS = {
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


def content_json(result) -> dict:
    """content_and_artifact 工具的 content 是 content-block 列表，取 JSON 文本。"""
    assert isinstance(result, list) and result, result
    return json.loads(result[0]["text"])


def make_prose_workspace(tmp_path: Path, project: str) -> dict[str, Path]:
    """按 ProjectWorkspace 路径约定铺一个含样例源文件的 project workspace。"""
    db_path = tmp_path / "hagent.sqlite"
    workspace_root = tmp_path / "workspaces"
    ws = workspace_root / "projects" / project / "workspace"
    (ws / "docs").mkdir(parents=True)
    (ws / "docs" / "tender.md").write_text("# 招标\n\n要求一。\n", encoding="utf-8")
    return {"db_path": db_path, "workspace_root": workspace_root}


def register_project(db_path: Path, project_id: str, name: str = "test") -> None:
    """按给定 id 落一个真实项目：server 模式的 MCP project 护栏认 ProjectStore，
    光有 workspace 目录不算数（幽灵 project_id 一律 project_not_found）。

    ProjectStore.create 自生成 id，这里改写成固定 id 以便测试用常量——只碰 id 列，
    projects 表 schema 演进无感。"""
    import sqlite3

    from hagent.server.projects import ProjectStore

    created = ProjectStore(db_path).create(name)
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE projects SET id = ? WHERE id = ?", (project_id, created.id))
