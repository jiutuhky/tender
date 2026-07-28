"""人工状态动作：应答状态与确认（仅 business / technical 的 items 区段有效）。"""

import pytest

from hagent.assets.errors import AssetError
from hagent.assets.model import Actor

from .conftest import make_item


@pytest.fixture
def published_business(service, agent_actor):
    service.start_draft("proj-1", "business", actor=agent_actor)
    service.submit_records(
        "proj-1", "business", section="items",
        records=[make_item(1, prefix="BIZ")], actor=agent_actor,
    )
    service.publish("proj-1", "business", actor=agent_actor)
    return service


def test_set_response_status_on_published_item(published_business, user_actor):
    item = published_business.set_item_response_status(
        "proj-1", "business", "BIZ-001",
        status="negative_deviation", note="交付周期偏离：要求 30 天，我方 45 天",
        reason="项目组评审结论", actor=user_actor,
    )
    assert item.response_status == "negative_deviation"
    assert item.response_note == "交付周期偏离：要求 30 天，我方 45 天"
    assert item.version == 2

    # 偏离表投影 = 一组过滤参数
    deviations, total = published_business.query_items(
        "proj-1", "business", response_status="negative_deviation"
    )
    assert total == 1 and deviations[0].item_id == "BIZ-001"

    ev = published_business.list_events("proj-1", action="set_item_response_status")[-1]
    assert ev.before == {"response_status": None, "response_note": None}
    assert ev.after["response_status"] == "negative_deviation"


def test_agent_records_on_behalf_actor(published_business):
    on_behalf = Actor(kind="agent_on_behalf", ref="run-007")
    published_business.set_item_response_status(
        "proj-1", "business", "BIZ-001", status="compliant", actor=on_behalf
    )
    ev = published_business.list_events("proj-1", action="set_item_response_status")[-1]
    assert (ev.actor_kind, ev.actor_ref) == ("agent_on_behalf", "run-007")


def test_response_status_value_is_validated(published_business, user_actor):
    with pytest.raises(AssetError) as exc:
        published_business.set_item_response_status(
            "proj-1", "business", "BIZ-001", status="ok", actor=user_actor
        )
    assert exc.value.code == "invalid_argument"


def test_response_status_rejected_for_non_response_matrices(service, agent_actor, user_actor):
    service.start_draft("proj-1", "scoring", actor=agent_actor)
    service.submit_records(
        "proj-1", "scoring", section="items", records=[make_item(1, prefix="SCORE")], actor=agent_actor
    )
    with pytest.raises(AssetError) as exc:
        service.set_item_response_status(
            "proj-1", "scoring", "SCORE-001", status="compliant", actor=user_actor
        )
    assert exc.value.code == "invalid_argument"


def test_response_status_rejected_outside_items_section(service, agent_actor, user_actor):
    service.start_draft("proj-1", "technical", actor=agent_actor)
    result = service.submit_records(
        "proj-1", "technical", section="deliverables", records=[{"name": "部署包"}], actor=agent_actor
    )
    with pytest.raises(AssetError) as exc:
        service.set_item_response_status(
            "proj-1", "technical", result.item_ids[0], status="compliant", actor=user_actor
        )
    assert exc.value.code == "invalid_argument"


def test_confirm_item(published_business, user_actor):
    item = published_business.confirm_item("proj-1", "business", "BIZ-001", actor=user_actor)
    assert item.confirmed is True
    assert item.version == 2
    confirmed, total = published_business.query_items("proj-1", "business", confirmed=True)
    assert total == 1
    ev = published_business.list_events("proj-1", action="confirm_matrix_item")[-1]
    assert ev.before == {"confirmed": False} and ev.after == {"confirmed": True}
