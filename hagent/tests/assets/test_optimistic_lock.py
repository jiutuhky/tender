"""条目乐观锁：后写者收到可行动冲突错误（含当前 version 与重读指引），审计记录双方。"""

import pytest

from hagent.assets.errors import ConflictError

from .conftest import make_item


@pytest.fixture
def drafted(service, agent_actor):
    service.start_draft("proj-1", "technical", actor=agent_actor)
    service.submit_records(
        "proj-1", "technical", section="items", records=[make_item(1)], actor=agent_actor
    )
    return service


def test_stale_writer_gets_actionable_conflict(drafted, agent_actor, user_actor):
    # 双方都基于 version=1 读取；agent 先写成功
    updated = drafted.update_item(
        "proj-1", "technical", "TECH-001",
        set={"mandatory": True}, expected_version=1, actor=agent_actor,
    )
    assert updated.version == 2

    # 用户基于过期版本后写，收到冲突
    with pytest.raises(ConflictError) as exc:
        drafted.update_item(
            "proj-1", "technical", "TECH-001",
            set={"mandatory": False}, expected_version=1, actor=user_actor,
        )
    err = exc.value
    assert err.code == "version_conflict"
    assert err.current_version == 2
    assert "version=2" in (err.hint or "")  # 重读指引带当前 version

    # 冲突未落库
    items, _ = drafted.query_items("proj-1", "technical")
    assert items[0].payload["mandatory"] is True
    assert items[0].version == 2


def test_conflict_is_audited_for_both_parties(drafted, agent_actor, user_actor):
    drafted.update_item(
        "proj-1", "technical", "TECH-001",
        set={"mandatory": True}, expected_version=1, actor=agent_actor,
    )
    with pytest.raises(ConflictError):
        drafted.update_item(
            "proj-1", "technical", "TECH-001",
            set={"mandatory": False}, expected_version=1, actor=user_actor,
        )
    events = drafted.list_events("proj-1", action="update_matrix_item")
    assert len(events) == 2
    winner, loser = events
    assert winner.actor_kind == "agent" and winner.after is not None
    assert loser.actor_kind == "user" and loser.after is None
    assert "乐观锁冲突" in (loser.reason or "")


def test_retry_with_fresh_version_succeeds(drafted, agent_actor, user_actor):
    drafted.update_item(
        "proj-1", "technical", "TECH-001",
        set={"mandatory": True}, expected_version=1, actor=agent_actor,
    )
    with pytest.raises(ConflictError) as exc:
        drafted.update_item(
            "proj-1", "technical", "TECH-001",
            set={"notes": "以现场答疑为准"}, expected_version=1, actor=user_actor,
        )
    retried = drafted.update_item(
        "proj-1", "technical", "TECH-001",
        set={"notes": "以现场答疑为准"},
        expected_version=exc.value.current_version,
        actor=user_actor,
    )
    assert retried.version == 3
    assert retried.payload["mandatory"] is True  # 双方修改都在
    assert retried.payload["notes"] == "以现场答疑为准"


def test_update_without_expected_version_is_last_write_wins(drafted, agent_actor):
    item = drafted.update_item(
        "proj-1", "technical", "TECH-001", set={"mandatory": True}, actor=agent_actor
    )
    assert item.version == 2


# —— 人工动作乐观锁（票 07）：用户确认/标注与 agent 写并发时同样受 version 守卫 ——


def test_stale_confirm_gets_conflict_and_writes_nothing(drafted, agent_actor, user_actor):
    drafted.update_item(
        "proj-1", "technical", "TECH-001",
        set={"mandatory": True}, expected_version=1, actor=agent_actor,
    )
    with pytest.raises(ConflictError) as exc:
        drafted.confirm_item(
            "proj-1", "technical", "TECH-001", expected_version=1, actor=user_actor
        )
    assert exc.value.code == "version_conflict"
    assert exc.value.current_version == 2
    items, _ = drafted.query_items("proj-1", "technical")
    assert items[0].confirmed is False
    assert items[0].version == 2  # 冲突未推进版本


def test_stale_response_status_gets_conflict_and_writes_nothing(
    drafted, agent_actor, user_actor
):
    drafted.update_item(
        "proj-1", "technical", "TECH-001",
        set={"mandatory": True}, expected_version=1, actor=agent_actor,
    )
    with pytest.raises(ConflictError) as exc:
        drafted.set_item_response_status(
            "proj-1", "technical", "TECH-001",
            status="compliant", expected_version=1, actor=user_actor,
        )
    assert exc.value.current_version == 2
    items, _ = drafted.query_items("proj-1", "technical")
    assert items[0].response_status is None


def test_manual_action_conflict_is_audited(drafted, agent_actor, user_actor):
    drafted.update_item(
        "proj-1", "technical", "TECH-001",
        set={"mandatory": True}, expected_version=1, actor=agent_actor,
    )
    with pytest.raises(ConflictError):
        drafted.confirm_item(
            "proj-1", "technical", "TECH-001", expected_version=1, actor=user_actor
        )
    events = drafted.list_events("proj-1", action="confirm_matrix_item")
    assert len(events) == 1
    rejected = events[0]
    assert rejected.actor_kind == "user"
    assert rejected.after is None
    assert "乐观锁冲突" in (rejected.reason or "")


def test_manual_action_with_fresh_version_succeeds(drafted, agent_actor, user_actor):
    drafted.update_item(
        "proj-1", "technical", "TECH-001",
        set={"mandatory": True}, expected_version=1, actor=agent_actor,
    )
    confirmed = drafted.confirm_item(
        "proj-1", "technical", "TECH-001", expected_version=2, actor=user_actor
    )
    assert confirmed.confirmed is True
    marked = drafted.set_item_response_status(
        "proj-1", "technical", "TECH-001",
        status="compliant", expected_version=confirmed.version, actor=user_actor,
    )
    assert marked.response_status == "compliant"
