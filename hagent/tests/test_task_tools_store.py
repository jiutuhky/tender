from hagent.task_tools.store import TaskStore, sanitize_path_component


def test_sanitize_path_component_replaces_unsafe_characters() -> None:
    assert sanitize_path_component("../team one") == "---team-one"
    assert sanitize_path_component("abc_DEF-123") == "abc_DEF-123"


def test_create_task_assigns_monotonic_ids_and_persists(tmp_path) -> None:
    store = TaskStore(tmp_path, task_list_id="session/a")

    first = store.create_task(subject="First", description="One")
    second = store.create_task(subject="Second", description="Two", activeForm="Doing second")

    assert first.id == "1"
    assert second.id == "2"
    assert second.activeForm == "Doing second"
    assert store.get_task("1") == first
    assert store.get_task("2") == second
    assert (tmp_path / ".hagent" / "tasks" / "session-a" / "1.json").exists()


def test_delete_task_removes_references_and_does_not_reuse_id(tmp_path) -> None:
    store = TaskStore(tmp_path, task_list_id="tasks")
    one = store.create_task(subject="One", description="Blocks two")
    two = store.create_task(subject="Two", description="Blocked by one")
    assert store.block_task(one.id, two.id) is True

    assert store.delete_task(one.id) is True
    next_task = store.create_task(subject="Three", description="New work")

    assert next_task.id == "3"
    assert store.get_task(one.id) is None
    assert store.get_task(two.id).blockedBy == []


def test_update_task_merges_metadata_and_removes_null_keys(tmp_path) -> None:
    store = TaskStore(tmp_path, task_list_id="tasks")
    task = store.create_task(
        subject="Original",
        description="Original description",
        metadata={"keep": "old", "remove": "yes"},
    )

    updated = store.update_task(
        task.id,
        subject="Changed",
        metadata={"keep": "new", "remove": None, "added": 3},
    )

    assert updated is not None
    assert updated.subject == "Changed"
    assert updated.metadata == {"keep": "new", "added": 3}


def test_list_tasks_filters_internal_tasks_and_completed_blockers_for_summary(tmp_path) -> None:
    store = TaskStore(tmp_path, task_list_id="tasks")
    blocker = store.create_task(subject="Setup", description="Prepare")
    blocked = store.create_task(subject="Build", description="Build feature")
    internal = store.create_task(
        subject="Hidden",
        description="Internal task",
        metadata={"_internal": True},
    )
    store.block_task(blocker.id, blocked.id)

    summary_before = store.list_task_items()
    assert [item.id for item in summary_before] == [blocker.id, blocked.id]
    assert summary_before[1].blockedBy == [blocker.id]

    store.update_task(blocker.id, status="completed")
    summary_after = store.list_task_items()

    assert [item.id for item in summary_after] == [blocker.id, blocked.id]
    assert summary_after[1].blockedBy == []
    assert internal.id not in [item.id for item in summary_after]


def test_claim_task_rejects_claimed_completed_and_blocked_tasks(tmp_path) -> None:
    store = TaskStore(tmp_path, task_list_id="tasks")
    blocker = store.create_task(subject="Blocker", description="Must finish first")
    blocked = store.create_task(subject="Blocked", description="Waits for blocker")
    store.block_task(blocker.id, blocked.id)

    blocked_result = store.claim_task(blocked.id, claimant="coder")
    assert blocked_result == {"success": False, "reason": "blocked", "blockedByTasks": [blocker.id]}

    claimed_result = store.claim_task(blocker.id, claimant="coder")
    assert claimed_result["success"] is True
    assert store.get_task(blocker.id).owner == "coder"

    already_claimed = store.claim_task(blocker.id, claimant="researcher")
    assert already_claimed["success"] is False
    assert already_claimed["reason"] == "already_claimed"

    store.update_task(blocker.id, status="completed")
    completed_result = store.claim_task(blocker.id, claimant="coder")
    assert completed_result["success"] is False
    assert completed_result["reason"] == "already_resolved"


def test_claim_task_allows_same_claimant_retry(tmp_path) -> None:
    store = TaskStore(tmp_path, task_list_id="tasks")
    task = store.create_task(subject="Retryable", description="Claim can be retried")

    first_claim = store.claim_task(task.id, claimant="coder")
    retry_claim = store.claim_task(task.id, claimant="coder")

    assert first_claim["success"] is True
    assert retry_claim["success"] is True
    assert retry_claim["task"]["id"] == task.id
    assert retry_claim["task"]["owner"] == "coder"


def test_reset_task_list_clears_tasks_and_keeps_high_water_mark(tmp_path) -> None:
    store = TaskStore(tmp_path, task_list_id="tasks")
    store.create_task(subject="One", description="First")
    store.create_task(subject="Two", description="Second")

    store.reset()
    task = store.create_task(subject="Three", description="After reset")

    assert store.list_tasks() == [task]
    assert task.id == "3"
