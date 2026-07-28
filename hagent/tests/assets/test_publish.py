"""publish 原子切换：快照 → 晋升 → 清草稿；中途失败不产生半切换状态。"""

import pytest

from hagent.assets.errors import AssetError
from hagent.assets.model import MatrixLifecycle
from hagent.assets.store import AssetStore

from .conftest import make_item


def _draft_with_records(service, actor, n=2):
    service.start_draft("proj-1", "technical", actor=actor)
    service.set_meta(
        "proj-1", "technical",
        set={"project_name": "某市数据平台采购", "extraction_summary": {"status": "complete"}},
        actor=actor,
    )
    service.submit_records(
        "proj-1", "technical", section="items",
        records=[make_item(i + 1) for i in range(n)], actor=actor,
    )


def test_publish_promotes_draft_and_clears_it(service, agent_actor):
    _draft_with_records(service, agent_actor)
    result = service.publish("proj-1", "technical", actor=agent_actor)
    assert result.rev == 1
    assert result.record_count == 2
    assert result.state is MatrixLifecycle.PUBLISHED

    info = service.get_matrix_info("proj-1", "technical")
    assert info.state is MatrixLifecycle.PUBLISHED
    assert info.current_rev == 1
    assert info.meta["project_name"] == "某市数据平台采购"
    assert info.draft_meta is None

    current, total = service.query_items("proj-1", "technical")
    assert total == 2 and all(i.stage == "current" for i in current)
    _, draft_total = service.query_items("proj-1", "technical", stage="draft")
    assert draft_total == 0


def test_publish_snapshot_is_complete(service, agent_actor):
    _draft_with_records(service, agent_actor)
    service.publish("proj-1", "technical", actor=agent_actor)
    snapshot = service.get_revision("proj-1", "technical", rev=1)
    assert snapshot is not None
    assert snapshot["matrix_type"] == "technical"
    assert snapshot["rev"] == 1
    assert snapshot["meta"]["project_name"] == "某市数据平台采购"
    records = snapshot["records"]
    assert {r["item_id"] for r in records} == {"TECH-001", "TECH-002"}
    sample = records[0]
    # 快照带全人工状态字段，可作恢复锚点
    assert {"section", "payload", "response_status", "response_note", "confirmed", "version"} <= set(sample)


def test_publish_rejected_outside_draft_states(service, agent_actor):
    with pytest.raises(AssetError) as exc:
        service.publish("proj-1", "technical", actor=agent_actor)
    assert exc.value.code == "invalid_state"

    _draft_with_records(service, agent_actor)
    service.publish("proj-1", "technical", actor=agent_actor)
    with pytest.raises(AssetError) as exc:
        service.publish("proj-1", "technical", actor=agent_actor)
    assert exc.value.code == "invalid_state"


def test_republish_via_escape_hatch_increments_rev(service, agent_actor):
    _draft_with_records(service, agent_actor)
    service.publish("proj-1", "technical", actor=agent_actor)

    service.start_draft("proj-1", "technical", discard_manual_states=True, actor=agent_actor)
    info = service.get_matrix_info("proj-1", "technical")
    assert info.state is MatrixLifecycle.PUBLISHED_DRAFTING
    # 重抽期间草稿与当前版并立
    _, current_total = service.query_items("proj-1", "technical", stage="current")
    assert current_total == 2

    service.submit_records(
        "proj-1", "technical", section="items", records=[make_item(9)], actor=agent_actor
    )
    result = service.publish("proj-1", "technical", actor=agent_actor)
    assert result.rev == 2

    current, total = service.query_items("proj-1", "technical")
    assert total == 1 and current[0].item_id == "TECH-009"
    assert service.get_revision("proj-1", "technical", rev=2) is not None


def test_publish_gate_rejects_on_validation_error(service, agent_actor):
    _draft_with_records(service, agent_actor)

    def gate(meta, items):
        raise AssetError("validation_failed", "存在未通过校验的条目", hint="先修复再 publish")

    with pytest.raises(AssetError) as exc:
        service.publish("proj-1", "technical", actor=agent_actor, validate=gate)
    assert exc.value.code == "validation_failed"
    info = service.get_matrix_info("proj-1", "technical")
    assert info.state is MatrixLifecycle.DRAFTING
    assert info.current_rev == 0


def test_publish_failure_mid_transaction_leaves_no_half_switch(service, agent_actor, monkeypatch):
    _draft_with_records(service, agent_actor)

    # 审计写入是 publish 事务内最后一步；在此注入故障验证整体回滚
    def boom(self, conn, **kwargs):
        raise RuntimeError("模拟中途故障")

    monkeypatch.setattr(AssetStore, "append_event", boom)
    with pytest.raises(RuntimeError):
        service.publish("proj-1", "technical", actor=agent_actor)
    monkeypatch.undo()

    info = service.get_matrix_info("proj-1", "technical")
    assert info.state is MatrixLifecycle.DRAFTING
    assert info.current_rev == 0
    assert info.draft_meta is not None
    _, draft_total = service.query_items("proj-1", "technical", stage="draft")
    assert draft_total == 2
    _, current_total = service.query_items("proj-1", "technical", stage="current")
    assert current_total == 0
    assert service.get_revision("proj-1", "technical", rev=1) is None
    # 故障的 publish 不留下任何事件（事务整体回滚）
    assert [e.action for e in service.list_events("proj-1") if e.action == "publish_matrix"] == []
