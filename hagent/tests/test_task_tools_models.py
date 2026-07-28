import pytest
from pydantic import ValidationError

from hagent.task_tools.models import (
    Task,
    TaskCreateInput,
    TaskListItem,
    TaskStatus,
    TaskUpdateInput,
    task_to_todo,
)


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


def test_task_model_accepts_claude_code_fields() -> None:
    task = Task(
        id="7",
        subject="Run tests",
        description="Run pytest and inspect failures.",
        activeForm="Running tests",
        owner="coder",
        status="in_progress",
        blocks=["9"],
        blockedBy=["3"],
        metadata={"source": "user"},
    )

    assert task.id == "7"
    assert task.subject == "Run tests"
    assert task.description == "Run pytest and inspect failures."
    assert task.activeForm == "Running tests"
    assert task.owner == "coder"
    assert task.status == "in_progress"
    assert task.blocks == ["9"]
    assert task.blockedBy == ["3"]
    assert task.metadata == {"source": "user"}


def test_task_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        Task(
            id="1",
            subject="Bad status",
            description="Invalid status must fail validation.",
            status="open",
            blocks=[],
            blockedBy=[],
        )


def test_task_create_input_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        TaskCreateInput(
            subject="Do work",
            description="Complete the work.",
            unexpected=True,
        )


def test_task_create_input_optional_field_schema_is_not_nullable() -> None:
    properties = TaskCreateInput.model_json_schema()["properties"]

    for field in ["activeForm", "metadata"]:
        assert not _schema_contains_top_level_null(properties[field])


def test_task_create_input_allows_omitted_optional_fields() -> None:
    payload = TaskCreateInput.model_validate(
        {"subject": "Do work", "description": "Complete the work."}
    )

    assert payload.activeForm is None
    assert payload.metadata is None


@pytest.mark.parametrize(
    "payload",
    [
        {"subject": "Do work", "description": "Complete the work.", "activeForm": None},
        {"subject": "Do work", "description": "Complete the work.", "metadata": None},
    ],
)
def test_task_create_input_rejects_explicit_null_optional_fields(payload) -> None:
    with pytest.raises(ValidationError):
        TaskCreateInput.model_validate(payload)


def test_task_update_accepts_deleted_action_and_metadata_nulls() -> None:
    update = TaskUpdateInput(
        taskId="4",
        status="deleted",
        metadata={"keep": "value", "remove": None},
        addBlocks=["8"],
        addBlockedBy=["2"],
    )

    assert update.taskId == "4"
    assert update.status == "deleted"
    assert update.metadata == {"keep": "value", "remove": None}
    assert update.addBlocks == ["8"]
    assert update.addBlockedBy == ["2"]


def test_task_update_input_optional_field_schema_is_not_nullable() -> None:
    properties = TaskUpdateInput.model_json_schema()["properties"]

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
        assert not _schema_contains_top_level_null(properties[field])


def test_task_update_input_allows_omitted_optional_fields() -> None:
    payload = TaskUpdateInput.model_validate({"taskId": "4"})

    assert payload.subject is None
    assert payload.description is None
    assert payload.activeForm is None
    assert payload.status is None
    assert payload.addBlocks is None
    assert payload.addBlockedBy is None
    assert payload.owner is None
    assert payload.metadata is None


@pytest.mark.parametrize(
    "field",
    [
        "subject",
        "description",
        "activeForm",
        "status",
        "addBlocks",
        "addBlockedBy",
        "owner",
        "metadata",
    ],
)
def test_task_update_input_rejects_explicit_null_optional_fields(field) -> None:
    with pytest.raises(ValidationError):
        TaskUpdateInput.model_validate({"taskId": "4", field: None})


def test_task_list_item_filters_completed_blockers_before_rendering() -> None:
    item = TaskListItem(
        id="5",
        subject="Implement API",
        status="pending",
        owner="coder",
        blockedBy=["1"],
    )

    assert item.model_dump(exclude_none=True) == {
        "id": "5",
        "subject": "Implement API",
        "status": "pending",
        "owner": "coder",
        "blockedBy": ["1"],
    }


def test_task_to_todo_matches_existing_server_shape() -> None:
    task = Task(
        id="2",
        subject="Write tests",
        description="Cover task store behavior.",
        status="pending",
        blocks=[],
        blockedBy=["1"],
    )

    assert task_to_todo(task) == {
        "content": "Write tests",
        "status": "pending",
        "id": "2",
        "description": "Cover task store behavior.",
        "blockedBy": ["1"],
    }
