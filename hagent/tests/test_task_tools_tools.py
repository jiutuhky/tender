from pathlib import Path

import pytest
from pydantic import ValidationError

from hagent.task_tools.models import TaskCreateInput, TaskGetInput, TaskUpdateInput
from hagent.task_tools.store import TaskStore
from hagent.task_tools.tools import create_task_tools


def _tools_by_name(store: TaskStore, claimant: str | None = None):
    return {tool.name: tool for tool in create_task_tools(store, claimant=claimant)}


def _schema_contains_top_level_null(schema: object) -> bool:
    if isinstance(schema, dict):
        if schema.get("type") == "null" or (
            "default" in schema and schema["default"] is None
        ):
            return True
        return any(_schema_contains_top_level_null(value) for value in schema.values())
    if isinstance(schema, list):
        return any(_schema_contains_top_level_null(item) for item in schema)
    return False


def test_create_task_tools_exposes_expected_names_and_schemas(tmp_path) -> None:
    tools = create_task_tools(TaskStore(tmp_path))

    assert [tool.name for tool in tools] == ["TaskCreate", "TaskGet", "TaskUpdate", "TaskList"]
    assert tools[0].args_schema is TaskCreateInput
    assert tools[1].args_schema is TaskGetInput
    assert tools[2].args_schema is TaskUpdateInput
    assert tools[3].args_schema.model_fields == {}
    assert tools[3].args_schema.model_config["extra"] == "forbid"

    with pytest.raises(ValidationError):
        tools[3].args_schema.model_validate({"unexpected": True})


def test_task_create_and_update_tool_args_do_not_advertise_top_level_nulls(tmp_path) -> None:
    tools = _tools_by_name(TaskStore(tmp_path))

    for field in ["activeForm", "metadata"]:
        assert not _schema_contains_top_level_null(tools["TaskCreate"].args[field])

    for field in [
        "subject",
        "description",
        "activeForm",
        "status",
        "addBlocks",
        "addBlockedBy",
        "owner",
        "metadata",
    ]:
        assert not _schema_contains_top_level_null(tools["TaskUpdate"].args[field])


def test_task_tools_create_get_list_and_update_happy_path(tmp_path) -> None:
    store = TaskStore(tmp_path)
    tools = _tools_by_name(store)

    created = tools["TaskCreate"].invoke(
        {"subject": "部署服务", "description": "Deploy the API.", "metadata": {"priority": "high"}}
    )
    assert created == "Task #1 created successfully: 部署服务"

    get_payload = tools["TaskGet"].invoke({"taskId": "1"})
    assert get_payload == "\n".join(
        [
            "Task #1: 部署服务",
            "Status: pending",
            "Description: Deploy the API.",
        ]
    )

    tools["TaskCreate"].invoke({"subject": "Write tests", "description": "Cover behavior."})
    tools["TaskCreate"].invoke({"subject": "Review", "description": "Review changes."})

    updated = tools["TaskUpdate"].invoke(
        {
            "taskId": "2",
            "subject": "Write focused tests",
            "description": "Cover task tools behavior.",
            "activeForm": "Writing tests",
            "status": "in_progress",
            "owner": "coder",
            "metadata": {"kind": "test"},
            "addBlocks": ["3"],
            "addBlockedBy": ["1"],
        }
    )

    assert (
        updated
        == "Updated task #2 subject, description, activeForm, status, owner, metadata, blocks, blockedBy"
    )
    assert store.get_task("2").model_dump(exclude_none=True) == {
        "id": "2",
        "subject": "Write focused tests",
        "description": "Cover task tools behavior.",
        "activeForm": "Writing tests",
        "owner": "coder",
        "status": "in_progress",
        "blocks": ["3"],
        "blockedBy": ["1"],
        "metadata": {"kind": "test"},
    }
    assert store.get_task("1").blocks == ["2"]
    assert store.get_task("3").blockedBy == ["2"]

    list_payload = tools["TaskList"].invoke({})
    assert list_payload == "\n".join(
        [
            "#1 [pending] 部署服务",
            "#2 [in_progress] Write focused tests (coder) [blocked by #1]",
            "#3 [pending] Review [blocked by #2]",
        ]
    )


def test_task_update_deleted_removes_task(tmp_path) -> None:
    store = TaskStore(tmp_path)
    tools = _tools_by_name(store)
    task = store.create_task(subject="Remove me", description="Delete this task.")

    assert tools["TaskUpdate"].invoke({"taskId": task.id, "status": "deleted"}) == "Updated task #1 deleted"
    assert store.get_task(task.id) is None
    assert tools["TaskUpdate"].invoke({"taskId": task.id, "status": "deleted"}) == "Task not found"


def test_task_list_filters_completed_blockers_but_task_get_preserves_full_blockers(tmp_path) -> None:
    store = TaskStore(tmp_path)
    tools = _tools_by_name(store)
    blocker = store.create_task(subject="Setup", description="Prepare.")
    blocked = store.create_task(subject="Build", description="Build feature.")
    store.block_task(blocker.id, blocked.id)
    store.update_task(blocker.id, status="completed")

    list_payload = tools["TaskList"].invoke({})
    get_payload = tools["TaskGet"].invoke({"taskId": blocked.id})

    assert list_payload == "\n".join(
        [
            "#1 [completed] Setup",
            "#2 [pending] Build",
        ]
    )
    assert get_payload == "\n".join(
        [
            "Task #2: Build",
            "Status: pending",
            "Description: Build feature.",
            "Blocked by: #1",
        ]
    )


@pytest.mark.parametrize(
    ("setup", "expected", "expected_owner"),
    [
        ("missing", "Task not found", None),
        ("already_claimed", "Updated task #1 status", "reviewer"),
        ("completed", "Updated task #1 status", None),
        ("blocked", "Updated task #2 status", None),
        ("busy", "Updated task #2 status", None),
    ],
)
def test_task_update_in_progress_ignores_claimant_rejections(tmp_path, setup, expected, expected_owner) -> None:
    store = TaskStore(tmp_path)
    tools = _tools_by_name(store, claimant="coder")

    if setup == "missing":
        payload = {"taskId": "404", "status": "in_progress"}
    elif setup == "already_claimed":
        task = store.create_task(subject="Claimed", description="Owned.")
        store.update_task(task.id, owner="reviewer")
        payload = {"taskId": task.id, "status": "in_progress"}
    elif setup == "completed":
        task = store.create_task(subject="Done", description="Already done.")
        store.update_task(task.id, status="completed")
        payload = {"taskId": task.id, "status": "in_progress"}
    elif setup == "blocked":
        blocker = store.create_task(subject="Blocker", description="Must finish.")
        blocked = store.create_task(subject="Blocked", description="Waits.")
        store.block_task(blocker.id, blocked.id)
        payload = {"taskId": blocked.id, "status": "in_progress"}
    else:
        store.create_task(subject="Active", description="Busy work.")
        task = store.create_task(subject="Next", description="Next work.")
        store.claim_task("1", "coder")
        payload = {"taskId": task.id, "status": "in_progress"}

    assert tools["TaskUpdate"].invoke(payload) == expected
    if setup != "missing":
        task_id = payload["taskId"]
        assert store.get_task(task_id).status == "in_progress"
        assert store.get_task(task_id).owner == expected_owner


def test_task_update_in_progress_same_claimant_retry_succeeds(tmp_path) -> None:
    store = TaskStore(tmp_path)
    tools = _tools_by_name(store, claimant="coder")
    task = store.create_task(subject="Retry", description="Same claimant can retry.")

    assert tools["TaskUpdate"].invoke({"taskId": task.id, "status": "in_progress"}) == "Updated task #1 status"
    assert tools["TaskUpdate"].invoke({"taskId": task.id, "status": "in_progress"}) == "Updated task #1 "
    assert store.get_task(task.id).owner is None


def test_task_update_missing_dependency_does_not_abort_field_or_status_updates(tmp_path) -> None:
    store = TaskStore(tmp_path)
    tools = _tools_by_name(store)
    task = store.create_task(subject="Original", description="Original description.")

    result = tools["TaskUpdate"].invoke(
        {
            "taskId": task.id,
            "subject": "Changed",
            "status": "completed",
            "addBlocks": ["404"],
        }
    )

    updated = store.get_task(task.id)
    assert result == "Updated task #1 subject, status, blocks"
    assert updated.subject == "Changed"
    assert updated.status == "completed"
    assert updated.blocks == []


def test_task_update_added_blocker_prevents_claim_and_status_change(tmp_path) -> None:
    store = TaskStore(tmp_path)
    tools = _tools_by_name(store, claimant="coder")
    blocker = store.create_task(subject="Blocker", description="Must finish first.")
    blocked = store.create_task(subject="Blocked", description="Waits for blocker.")

    result = tools["TaskUpdate"].invoke(
        {"taskId": blocked.id, "status": "in_progress", "addBlockedBy": [blocker.id]}
    )

    blocked_after = store.get_task(blocked.id)
    assert result == "Updated task #2 status, blockedBy"
    assert blocked_after.status == "in_progress"
    assert blocked_after.owner is None
    assert blocked_after.blockedBy == [blocker.id]


def test_task_update_claimant_in_progress_ignores_conflicting_owner(tmp_path) -> None:
    store = TaskStore(tmp_path)
    tools = _tools_by_name(store, claimant="coder")
    task = store.create_task(subject="Claim me", description="Claimed via update.")

    result = tools["TaskUpdate"].invoke(
        {"taskId": task.id, "status": "in_progress", "owner": "reviewer"}
    )

    updated = store.get_task(task.id)
    assert result == "Updated task #1 status, owner"
    assert updated.status == "in_progress"
    assert updated.owner == "reviewer"


def test_task_get_missing_and_task_list_empty_match_claude_visible_strings(tmp_path) -> None:
    tools = _tools_by_name(TaskStore(tmp_path))

    assert tools["TaskGet"].invoke({"taskId": "404"}) == "Task not found"
    assert tools["TaskList"].invoke({}) == "No tasks found"


def test_task_tools_do_not_use_signature_inspection_shim() -> None:
    tools_source = Path("src/hagent/task_tools/tools.py").read_text(encoding="utf-8")

    assert "inspect" not in tools_source
    assert "signature" not in tools_source
