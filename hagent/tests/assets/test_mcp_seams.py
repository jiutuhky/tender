"""MCP 工具面的服务层接缝（票 03）：查询过滤 / 总览统计 / 四矩阵状态 /
workspace 注册 / 无条件门禁发布 / 校验摘要事件 / 跨进程 WAL。"""

from __future__ import annotations

import hashlib
import sqlite3

import pytest

from hagent.assets.errors import AssetError
from hagent.assets.validators import ValidationFailedError

PROJECT = "p-mcp-seams"

SOURCE_LINES = [
    "# 招标文件",
    "",
    "投标人须具备有效的信息系统建设资质，并提供近三年同类项目业绩证明。",
    "系统须支持每秒一千次并发查询，响应时间不超过两百毫秒。",
    "所有数据须在境内存储，并通过等级保护三级测评。",
]


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "workspace"
    (ws / "docs").mkdir(parents=True)
    (ws / "docs" / "tender.md").write_text("\n".join(SOURCE_LINES), encoding="utf-8")
    return ws


@pytest.fixture
def doc(service, workspace, agent_actor):
    content = (workspace / "docs" / "tender.md").read_bytes()
    return service.register_document(
        PROJECT,
        path="docs/tender.md",
        sha256=hashlib.sha256(content).hexdigest(),
        doc_type="tender",
        actor=agent_actor,
    )


def _item(i: int, *, category: str, mandatory: bool, line: int, doc_id: str) -> dict:
    return {
        "id": f"TECH-{i:03d}",
        "category": category,
        "title": f"条目 {i}",
        "requirement_text": SOURCE_LINES[line - 1],
        "mandatory": mandatory,
        "response_required": True,
        "source_refs": [{"document_id": doc_id, "line_span": [line, line]}],
        "confidence": "high",
    }


@pytest.fixture
def seeded(service, doc, agent_actor):
    """technical 草稿：3 条 items（类别/强制性/关键词各异）+ 1 条非 items 行。"""
    service.start_draft(PROJECT, "technical", actor=agent_actor)
    service.submit_records(
        PROJECT,
        "technical",
        section="items",
        records=[
            _item(1, category="function", mandatory=True, line=4, doc_id=doc.id),
            _item(2, category="performance", mandatory=False, line=5, doc_id=doc.id),
            _item(3, category="function", mandatory=False, line=3, doc_id=doc.id),
        ],
        actor=agent_actor,
    )
    service.submit_records(
        PROJECT,
        "technical",
        section="deliverables",
        records=[{"name": "系统部署手册", "source_refs": []}],
        actor=agent_actor,
    )
    return doc


class TestQueryFilters:
    def test_filter_by_category(self, service, seeded):
        items, total = service.query_items(PROJECT, "technical", category="function")
        assert total == 2
        assert {i.item_id for i in items} == {"TECH-001", "TECH-003"}

    def test_filter_by_mandatory(self, service, seeded):
        items, total = service.query_items(PROJECT, "technical", mandatory=True)
        assert total == 1
        assert items[0].item_id == "TECH-001"

    def test_filter_by_keyword(self, service, seeded):
        items, total = service.query_items(PROJECT, "technical", keyword="并发查询")
        assert total == 1
        assert items[0].item_id == "TECH-001"

    def test_filters_compose_with_pagination(self, service, seeded):
        items, total = service.query_items(
            PROJECT, "technical", category="function", limit=1, offset=1
        )
        assert total == 2
        assert len(items) == 1


class TestMatrixOverview:
    def test_overview_has_envelope_and_stats(self, service, seeded, agent_actor):
        service.set_item_response_status(
            PROJECT, "technical", "TECH-001",
            status="negative_deviation", note="资质等级不足", actor=agent_actor,
        )
        service.confirm_item(PROJECT, "technical", "TECH-002", actor=agent_actor)

        overview = service.get_matrix_overview(PROJECT, "technical")
        assert overview.info.matrix_type == "technical"
        assert overview.stats.stage == "draft"
        assert overview.stats.total == 4
        assert overview.stats.by_section == {"items": 3, "deliverables": 1}
        assert overview.stats.by_response_status == {"unset": 2, "negative_deviation": 1}
        assert overview.stats.confirmed_count == 1
        assert overview.stats.mandatory_count == 1
        assert overview.stats.by_category == {"function": 2, "performance": 1}

    def test_overview_of_empty_matrix(self, service):
        overview = service.get_matrix_overview(PROJECT, "scoring")
        assert overview.info.state.value == "empty"
        assert overview.stats.total == 0
        assert overview.stats.by_section == {}


class TestMatrixStatus:
    def test_status_covers_four_matrices(self, service, seeded):
        statuses = service.matrix_status(PROJECT)
        by_type = {s.matrix_type: s for s in statuses}
        assert set(by_type) == {"basic_info", "business", "technical", "scoring"}
        assert by_type["technical"].state.value == "drafting"
        assert by_type["technical"].draft_count == 4
        assert by_type["technical"].current_count == 0
        assert by_type["basic_info"].state.value == "empty"
        assert by_type["basic_info"].last_validation is None

    def test_validate_with_actor_records_summary(self, service, seeded, workspace, agent_actor):
        report = service.validate_matrix(
            PROJECT, "technical", workspace_root=workspace, actor=agent_actor
        )
        statuses = {s.matrix_type: s for s in service.matrix_status(PROJECT)}
        last = statuses["technical"].last_validation
        assert last is not None
        assert last["status"] == report.status
        assert last["error_count"] == len(report.errors)
        assert last["checked_items"] == report.checked_items
        assert "ts" in last

    def test_validate_without_actor_stays_pure(self, service, seeded, workspace):
        service.validate_matrix(PROJECT, "technical", workspace_root=workspace)
        statuses = {s.matrix_type: s for s in service.matrix_status(PROJECT)}
        assert statuses["technical"].last_validation is None


class TestRegisterWorkspaceDocument:
    def test_computes_sha_and_registers(self, service, workspace, agent_actor):
        record = service.register_workspace_document(
            PROJECT, path="docs/tender.md", doc_type="tender",
            workspace_root=workspace, actor=agent_actor,
        )
        expected = hashlib.sha256(
            (workspace / "docs" / "tender.md").read_bytes()
        ).hexdigest()
        assert record.sha256 == expected
        assert record.path == "docs/tender.md"
        assert record.created is True

    def test_idempotent_on_same_content(self, service, workspace, agent_actor):
        first = service.register_workspace_document(
            PROJECT, path="docs/tender.md", doc_type="tender",
            workspace_root=workspace, actor=agent_actor,
        )
        second = service.register_workspace_document(
            PROJECT, path="docs/tender.md", doc_type="tender",
            workspace_root=workspace, actor=agent_actor,
        )
        assert second.id == first.id
        assert second.created is False

    def test_missing_file_is_actionable(self, service, workspace, agent_actor):
        with pytest.raises(AssetError) as exc:
            service.register_workspace_document(
                PROJECT, path="docs/nope.md", doc_type=None,
                workspace_root=workspace, actor=agent_actor,
            )
        assert exc.value.code == "file_not_found"
        assert exc.value.hint

    def test_rejects_path_escape(self, service, workspace, agent_actor):
        (workspace.parent / "secret.md").write_text("outside", encoding="utf-8")
        with pytest.raises(AssetError) as exc:
            service.register_workspace_document(
                PROJECT, path="../secret.md", doc_type=None,
                workspace_root=workspace, actor=agent_actor,
            )
        assert exc.value.code == "invalid_path"


class TestPublishGated:
    def test_valid_draft_publishes(self, service, seeded, workspace, agent_actor):
        service.set_meta(
            PROJECT,
            "technical",
            set={
                "project_id": "ZB-2026-001",
                "project_name": "示例信息化项目",
                "extraction_summary": {"status": "complete", "confidence": "high", "warnings": []},
            },
            actor=agent_actor,
        )
        result = service.publish_gated(
            PROJECT, "technical", workspace_root=workspace, actor=agent_actor
        )
        assert result.rev == 1
        assert service.get_matrix_info(PROJECT, "technical").state.value == "published"
        # 门禁产出的报告落校验摘要：发布后「最近校验摘要」不陈旧
        statuses = {s.matrix_type: s for s in service.matrix_status(PROJECT)}
        assert statuses["technical"].last_validation["status"] == "pass"

    def test_invalid_draft_is_rejected(self, service, seeded, workspace, agent_actor):
        # 缺 envelope 必填字段 → 结构校验 error → 门禁拒绝，状态保持草稿
        with pytest.raises(ValidationFailedError):
            service.publish_gated(
                PROJECT, "technical", workspace_root=workspace, actor=agent_actor
            )
        assert service.get_matrix_info(PROJECT, "technical").state.value == "drafting"
        # 被拒的门禁校验同样留摘要（含错误计数）
        statuses = {s.matrix_type: s for s in service.matrix_status(PROJECT)}
        assert statuses["technical"].last_validation["status"] == "fail"
        assert statuses["technical"].last_validation["error_count"] >= 1


class TestCrossProcessSharing:
    def test_store_uses_wal(self, store, tmp_path):
        conn = sqlite3.connect(tmp_path / "hagent.sqlite")
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            conn.close()
        assert mode.lower() == "wal"
