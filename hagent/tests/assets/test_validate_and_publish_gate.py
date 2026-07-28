"""服务层校验接入：validate_matrix 纯读 + publish 门禁全套拦截（票 02）。"""

from __future__ import annotations

import hashlib

import pytest

from hagent.assets.errors import AssetError
from hagent.assets.validators import ValidationFailedError

SOURCE_LINES = [
    "# 招标文件",
    "",
    "投标人须具备有效的信息系统建设资质，并提供近三年同类项目业绩证明。",
    "系统须支持每秒一千次并发查询，响应时间不超过两百毫秒。",
    "所有数据须在境内存储，并通过等级保护三级测评。",
]

PROJECT = "p-gate"


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "tender.md").write_text("\n".join(SOURCE_LINES), encoding="utf-8")
    return tmp_path


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


def seed_draft(service, doc, actor, *, requirement_text: str) -> None:
    service.start_draft(PROJECT, "technical", actor=actor)
    service.set_meta(
        PROJECT,
        "technical",
        set={
            "project_id": "ZB-2026-001",
            "project_name": "示例信息化项目",
            "extraction_summary": {"status": "complete", "confidence": "high", "warnings": []},
        },
        actor=actor,
    )
    service.submit_records(
        PROJECT,
        "technical",
        section="items",
        records=[
            {
                "id": "TECH-001",
                "category": "function",
                "title": "并发性能",
                "requirement_text": requirement_text,
                "mandatory": False,
                "response_required": True,
                "source_refs": [{"document_id": doc.id, "line_span": [4, 4]}],
                "confidence": "high",
            }
        ],
        actor=actor,
    )


class TestValidateIsPureRead:
    def test_no_events_no_writes(self, service, doc, workspace, agent_actor):
        seed_draft(service, doc, agent_actor, requirement_text=SOURCE_LINES[3])
        events_before = service.list_events(PROJECT)
        items_before, _ = service.query_items(PROJECT, "technical")

        report = service.validate_matrix(PROJECT, "technical", workspace_root=workspace)

        assert report.status == "pass"
        assert service.list_events(PROJECT) == events_before
        items_after, _ = service.query_items(PROJECT, "technical")
        assert items_after == items_before
        info = service.get_matrix_info(PROJECT, "technical")
        assert info.current_rev == 0

    def test_failing_validation_is_also_pure(self, service, doc, workspace, agent_actor):
        seed_draft(service, doc, agent_actor, requirement_text="凭空捏造的一条与源文完全无关的要求描述。")
        events_before = service.list_events(PROJECT)

        report = service.validate_matrix(PROJECT, "technical", workspace_root=workspace)

        assert report.status == "fail"
        assert {i.code for i in report.errors} == {"low_source_overlap"}
        assert service.list_events(PROJECT) == events_before

    def test_validates_current_stage_when_published(self, service, doc, workspace, agent_actor):
        seed_draft(service, doc, agent_actor, requirement_text=SOURCE_LINES[3])
        service.publish(
            PROJECT,
            "technical",
            actor=agent_actor,
            validate=service.publish_gate(PROJECT, "technical", workspace_root=workspace),
        )
        report = service.validate_matrix(PROJECT, "technical", workspace_root=workspace)
        assert report.status == "pass"
        assert report.checked_items == 1


class TestPublishGate:
    def test_gate_rejects_and_rolls_back(self, service, doc, workspace, agent_actor):
        seed_draft(service, doc, agent_actor, requirement_text="凭空捏造的一条与源文完全无关的要求描述。")
        gate = service.publish_gate(PROJECT, "technical", workspace_root=workspace)

        with pytest.raises(ValidationFailedError) as excinfo:
            service.publish(PROJECT, "technical", actor=agent_actor, validate=gate)

        assert isinstance(excinfo.value, AssetError)
        assert excinfo.value.code == "validation_failed"
        report = excinfo.value.report
        assert report.status == "fail"
        assert all(i.hint for i in report.errors)

        # 整体回滚：仍在草稿态，无 revision，无 current 条目
        info = service.get_matrix_info(PROJECT, "technical")
        assert info.state.value == "drafting"
        assert info.current_rev == 0
        assert service.get_revision(PROJECT, "technical", rev=1) is None
        current, total = service.query_items(PROJECT, "technical", stage="current")
        assert total == 0

    def test_fix_then_publish_passes_gate(self, service, doc, workspace, agent_actor):
        seed_draft(service, doc, agent_actor, requirement_text="凭空捏造的一条与源文完全无关的要求描述。")
        gate = service.publish_gate(PROJECT, "technical", workspace_root=workspace)
        with pytest.raises(ValidationFailedError):
            service.publish(PROJECT, "technical", actor=agent_actor, validate=gate)

        # 按报告修复：把 requirement_text 还原为源文措辞
        service.update_item(
            PROJECT,
            "technical",
            "TECH-001",
            set={"requirement_text": SOURCE_LINES[3]},
            reason="按保真报告还原源文措辞",
            actor=agent_actor,
        )
        result = service.publish(
            PROJECT,
            "technical",
            actor=agent_actor,
            validate=service.publish_gate(PROJECT, "technical", workspace_root=workspace),
        )
        assert result.rev == 1
        assert result.record_count == 1

    def test_gate_blocks_structure_errors(self, service, doc, workspace, agent_actor):
        service.start_draft(PROJECT, "technical", actor=agent_actor)
        # 不 set_meta、条目缺字段 → 结构错误也拦发布
        service.submit_records(
            PROJECT,
            "technical",
            section="items",
            records=[{"id": "TECH-001", "title": "缺一堆字段"}],
            actor=agent_actor,
        )
        gate = service.publish_gate(PROJECT, "technical", workspace_root=workspace)
        with pytest.raises(ValidationFailedError) as excinfo:
            service.publish(PROJECT, "technical", actor=agent_actor, validate=gate)
        codes = {i.code for i in excinfo.value.report.errors}
        assert "missing_meta_field" in codes
        assert "missing_item_field" in codes
