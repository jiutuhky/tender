"""行级动作靶点规则：有草稿写草稿，无草稿写当前版（=增量维护）。"""

import pytest

from hagent.assets.errors import AssetError
from hagent.assets.model import MatrixLifecycle

from .conftest import make_item


@pytest.fixture
def published(service, agent_actor):
    """一个已发布的 technical 矩阵（TECH-001 / TECH-002），无草稿。"""
    service.start_draft("proj-1", "technical", actor=agent_actor)
    service.set_meta(
        "proj-1", "technical",
        set={"project_name": "某市数据平台采购", "extraction_summary": {"status": "complete"}},
        actor=agent_actor,
    )
    service.submit_records(
        "proj-1", "technical", section="items",
        records=[make_item(1), make_item(2)], actor=agent_actor,
    )
    service.publish("proj-1", "technical", actor=agent_actor)
    return service


def test_update_targets_draft_when_drafting(service, agent_actor):
    service.start_draft("proj-1", "technical", actor=agent_actor)
    service.submit_records(
        "proj-1", "technical", section="items", records=[make_item(1)], actor=agent_actor
    )
    item = service.update_item(
        "proj-1", "technical", "TECH-001",
        set={"mandatory": True}, reason="招标文件标注星号", actor=agent_actor,
    )
    assert item.stage == "draft"
    assert item.payload["mandatory"] is True
    assert item.payload["title"] == "需求条目 1"  # 浅合并保留未触及字段
    assert item.version == 2


def test_update_targets_current_when_published(published, agent_actor):
    item = published.update_item(
        "proj-1", "technical", "TECH-001",
        set={"requirement_text": "澄清后的口径"}, reason="澄清文件第3条", actor=agent_actor,
    )
    assert item.stage == "current"
    assert item.version == 2
    # 已发布态的行级变更即增量维护，状态保持 published
    assert published.get_matrix_info("proj-1", "technical").state is MatrixLifecycle.PUBLISHED


def test_row_ops_without_any_version_are_rejected(service, agent_actor):
    for call in (
        lambda: service.update_item("proj-1", "technical", "TECH-001", set={"a": 1}, actor=agent_actor),
        lambda: service.drop_item("proj-1", "technical", "TECH-001", actor=agent_actor),
        lambda: service.set_meta("proj-1", "technical", set={"a": 1}, actor=agent_actor),
    ):
        with pytest.raises(AssetError) as exc:
            call()
        assert exc.value.code == "matrix_empty"


def test_update_unknown_item_is_actionable(published, agent_actor):
    with pytest.raises(AssetError) as exc:
        published.update_item("proj-1", "technical", "TECH-999", set={"a": 1}, actor=agent_actor)
    assert exc.value.code == "item_not_found"
    assert exc.value.hint is not None


def test_update_set_rejects_id_and_manual_state_fields(published, agent_actor):
    with pytest.raises(AssetError) as exc:
        published.update_item("proj-1", "technical", "TECH-001", set={"id": "TECH-088"}, actor=agent_actor)
    assert exc.value.code == "invalid_argument"
    with pytest.raises(AssetError) as exc:
        published.update_item(
            "proj-1", "technical", "TECH-001", set={"response_status": "compliant"}, actor=agent_actor
        )
    assert "set_item_response_status" in (exc.value.hint or "")


def test_drop_item_removes_row_and_audits_before(published, agent_actor):
    published.drop_item("proj-1", "technical", "TECH-002", reason="与 TECH-001 重复", actor=agent_actor)
    _, total = published.query_items("proj-1", "technical")
    assert total == 1
    ev = published.list_events("proj-1", action="drop_matrix_item")[-1]
    assert ev.target == "technical/TECH-002"
    assert ev.before["payload"]["id"] == "TECH-002"
    assert ev.reason == "与 TECH-001 重复"


def test_move_item_across_matrices(service, agent_actor):
    service.start_draft("proj-1", "technical", actor=agent_actor)
    service.start_draft("proj-1", "business", actor=agent_actor)
    service.submit_records(
        "proj-1", "technical", section="items", records=[make_item(1)], actor=agent_actor
    )
    moved = service.move_item(
        "proj-1", from_matrix="technical", to_matrix="business",
        item_id="TECH-001", new_id="BIZ-031",
        set={"category": "service"}, reason="属商务服务承诺", actor=agent_actor,
    )
    assert moved.matrix_type == "business"
    assert moved.item_id == "BIZ-031"
    assert moved.payload["id"] == "BIZ-031"
    assert moved.payload["category"] == "service"
    assert moved.version == 1
    _, tech_total = service.query_items("proj-1", "technical")
    assert tech_total == 0
    _, biz_total = service.query_items("proj-1", "business")
    assert biz_total == 1


def test_move_rejects_target_id_collision_and_empty_target(service, agent_actor):
    service.start_draft("proj-1", "technical", actor=agent_actor)
    service.submit_records(
        "proj-1", "technical", section="items", records=[make_item(1), make_item(2)], actor=agent_actor
    )
    # 目标矩阵无任何版本
    with pytest.raises(AssetError) as exc:
        service.move_item(
            "proj-1", from_matrix="technical", to_matrix="business",
            item_id="TECH-001", new_id="BIZ-001", actor=agent_actor,
        )
    assert exc.value.code == "matrix_empty"
    # 目标 id 已占用
    service.start_draft("proj-1", "business", actor=agent_actor)
    service.submit_records(
        "proj-1", "business", section="items", records=[make_item(1, prefix="BIZ")], actor=agent_actor
    )
    with pytest.raises(AssetError) as exc:
        service.move_item(
            "proj-1", from_matrix="technical", to_matrix="business",
            item_id="TECH-002", new_id="BIZ-001", actor=agent_actor,
        )
    assert exc.value.code == "item_exists"


def test_move_only_applies_to_items_section(service, agent_actor):
    service.start_draft("proj-1", "technical", actor=agent_actor)
    service.start_draft("proj-1", "business", actor=agent_actor)
    result = service.submit_records(
        "proj-1", "technical", section="deliverables", records=[{"name": "部署包"}], actor=agent_actor
    )
    with pytest.raises(AssetError) as exc:
        service.move_item(
            "proj-1", from_matrix="technical", to_matrix="business",
            item_id=result.item_ids[0], new_id="BIZ-001", actor=agent_actor,
        )
    assert exc.value.code == "invalid_argument"


def test_set_meta_targets_current_when_published(published, agent_actor):
    merged = published.set_meta(
        "proj-1", "technical", set={"extraction_summary": {"confidence": "high"}}, actor=agent_actor
    )
    assert merged["extraction_summary"]["confidence"] == "high"
    info = published.get_matrix_info("proj-1", "technical")
    # 深合并：既有 envelope 字段保留
    assert info.meta["project_name"] == "某市数据平台采购"
    assert info.meta["extraction_summary"] == {"status": "complete", "confidence": "high"}
    assert info.draft_meta is None
