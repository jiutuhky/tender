"""草稿生命周期：start_draft 状态机 + submit_records 仅草稿态可用。"""

import pytest

from hagent.assets.errors import AssetError
from hagent.assets.model import MatrixLifecycle

from .conftest import make_item


def test_start_draft_from_empty(service, agent_actor):
    info = service.start_draft("proj-1", "technical", actor=agent_actor)
    assert info.state is MatrixLifecycle.DRAFTING
    assert info.draft_meta == {}
    assert info.current_rev == 0


def test_start_draft_rejects_unknown_matrix_type(service, agent_actor):
    with pytest.raises(AssetError) as exc:
        service.start_draft("proj-1", "outline", actor=agent_actor)
    assert exc.value.code == "invalid_matrix_type"


def test_start_draft_twice_is_rejected_with_hint(service, agent_actor):
    service.start_draft("proj-1", "technical", actor=agent_actor)
    with pytest.raises(AssetError) as exc:
        service.start_draft("proj-1", "technical", actor=agent_actor)
    assert exc.value.code == "draft_exists"
    assert exc.value.hint is not None


def test_start_draft_on_published_requires_explicit_discard(service, agent_actor):
    service.start_draft("proj-1", "technical", actor=agent_actor)
    service.submit_records(
        "proj-1", "technical", section="items", records=[make_item(1)], actor=agent_actor
    )
    service.publish("proj-1", "technical", actor=agent_actor)
    with pytest.raises(AssetError) as exc:
        service.start_draft("proj-1", "technical", actor=agent_actor)
    assert exc.value.code == "discard_required"
    assert "discard_manual_states" in (exc.value.hint or "")
    # 拒绝不改变矩阵状态
    assert service.get_matrix_info("proj-1", "technical").state is MatrixLifecycle.PUBLISHED


def test_submit_records_lands_in_draft_stage(service, agent_actor):
    service.start_draft("proj-1", "technical", actor=agent_actor)
    result = service.submit_records(
        "proj-1", "technical", section="items",
        records=[make_item(1), make_item(2)], actor=agent_actor,
    )
    assert result.stage == "draft"
    assert result.item_ids == ["TECH-001", "TECH-002"]
    items, total = service.query_items("proj-1", "technical", section="items")
    assert total == 2
    assert all(i.stage == "draft" and i.version == 1 for i in items)


def test_submit_non_items_section_generates_row_ids(service, agent_actor):
    service.start_draft("proj-1", "technical", actor=agent_actor)
    result = service.submit_records(
        "proj-1", "technical", section="deliverables",
        records=[{"name": "系统部署包"}, {"name": "验收报告"}], actor=agent_actor,
    )
    assert result.count == 2
    assert all(rid.startswith("deliverables:") for rid in result.item_ids)
    assert len(set(result.item_ids)) == 2


def test_submit_without_draft_is_rejected_with_next_step(service, agent_actor):
    with pytest.raises(AssetError) as exc:
        service.submit_records(
            "proj-1", "technical", section="items", records=[make_item(1)], actor=agent_actor
        )
    assert exc.value.code == "no_draft"
    assert "start_matrix_draft" in (exc.value.hint or "")


def test_submit_rejects_section_not_allowed_for_matrix(service, agent_actor):
    service.start_draft("proj-1", "basic_info", actor=agent_actor)
    with pytest.raises(AssetError) as exc:
        service.submit_records(
            "proj-1", "basic_info", section="items", records=[make_item(1)], actor=agent_actor
        )
    assert exc.value.code == "invalid_section"


def test_submit_items_require_string_id(service, agent_actor):
    service.start_draft("proj-1", "technical", actor=agent_actor)
    with pytest.raises(AssetError) as exc:
        service.submit_records(
            "proj-1", "technical", section="items", records=[{"title": "缺 id"}], actor=agent_actor
        )
    assert exc.value.code == "invalid_records"


def test_submit_duplicate_item_id_is_atomic_rejection(service, agent_actor):
    service.start_draft("proj-1", "technical", actor=agent_actor)
    service.submit_records(
        "proj-1", "technical", section="items", records=[make_item(1)], actor=agent_actor
    )
    with pytest.raises(AssetError) as exc:
        service.submit_records(
            "proj-1", "technical", section="items",
            records=[make_item(2), make_item(1)], actor=agent_actor,
        )
    assert exc.value.code == "item_exists"
    assert "TECH-001" in exc.value.message
    # 整批原子拒绝：TECH-002 不应部分写入
    _, total = service.query_items("proj-1", "technical", section="items")
    assert total == 1


def test_draft_lifecycle_writes_audit_events(service, agent_actor):
    service.start_draft("proj-1", "technical", actor=agent_actor)
    service.submit_records(
        "proj-1", "technical", section="items", records=[make_item(1)], actor=agent_actor
    )
    actions = [e.action for e in service.list_events("proj-1")]
    assert actions == ["start_matrix_draft", "submit_matrix_records"]
