from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TaskStatus = Literal["pending", "in_progress", "completed"]
TaskUpdateStatus = Literal["pending", "in_progress", "completed", "deleted"]


def _strip_null_default_from_schema(schema: dict[str, Any]) -> None:
    if schema.get("default") is None:
        schema.pop("default")


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    subject: str
    description: str
    activeForm: str | None = None
    owner: str | None = None
    status: TaskStatus
    blocks: list[str] = Field(default_factory=list)
    blockedBy: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None


class TaskCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(description="A brief title for the task")
    description: str = Field(description="What needs to be done")
    activeForm: str = Field(
        default=None,
        description='Present continuous form shown when in_progress, e.g. "Running tests"',
        json_schema_extra=_strip_null_default_from_schema,
    )
    metadata: dict[str, Any] = Field(
        default=None,
        description="Arbitrary metadata to attach to the task",
        json_schema_extra=_strip_null_default_from_schema,
    )

    @field_validator("activeForm", "metadata", mode="before")
    @classmethod
    def _reject_explicit_nulls(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("explicit null is not allowed")
        return value


class TaskGetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taskId: str = Field(description="The ID of the task to retrieve")


class TaskUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taskId: str = Field(description="The ID of the task to update")
    subject: str = Field(
        default=None,
        description="New subject for the task",
        json_schema_extra=_strip_null_default_from_schema,
    )
    description: str = Field(
        default=None,
        description="New description for the task",
        json_schema_extra=_strip_null_default_from_schema,
    )
    activeForm: str = Field(
        default=None,
        description="New in-progress display text",
        json_schema_extra=_strip_null_default_from_schema,
    )
    status: TaskUpdateStatus = Field(
        default=None,
        description="New status for the task",
        json_schema_extra=_strip_null_default_from_schema,
    )
    addBlocks: list[str] = Field(
        default=None,
        description="Task IDs that this task blocks",
        json_schema_extra=_strip_null_default_from_schema,
    )
    addBlockedBy: list[str] = Field(
        default=None,
        description="Task IDs that block this task",
        json_schema_extra=_strip_null_default_from_schema,
    )
    owner: str = Field(
        default=None,
        description="New owner for the task",
        json_schema_extra=_strip_null_default_from_schema,
    )
    metadata: dict[str, Any] = Field(
        default=None,
        description="Metadata keys to merge into the task. Set a key to null to delete it.",
        json_schema_extra=_strip_null_default_from_schema,
    )

    @field_validator(
        "subject",
        "description",
        "activeForm",
        "status",
        "addBlocks",
        "addBlockedBy",
        "owner",
        "metadata",
        mode="before",
    )
    @classmethod
    def _reject_explicit_nulls(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("explicit null is not allowed")
        return value


class TaskListInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    subject: str
    status: TaskStatus
    owner: str | None = None
    blockedBy: list[str] = Field(default_factory=list)


def task_to_todo(task: Task) -> dict[str, Any]:
    todo: dict[str, Any] = {
        "content": task.subject,
        "status": task.status,
        "id": task.id,
        "description": task.description,
        "blockedBy": list(task.blockedBy),
    }
    if task.activeForm:
        todo["activeForm"] = task.activeForm
    if task.owner:
        todo["owner"] = task.owner
    return todo
