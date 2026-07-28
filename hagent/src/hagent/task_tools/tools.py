from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from hagent.task_tools.models import (
    Task,
    TaskCreateInput,
    TaskGetInput,
    TaskListInput,
    TaskListItem,
    TaskUpdateInput,
)
from hagent.task_tools.store import TaskStore


class TaskStructuredTool(StructuredTool):
    @property
    def tool_call_schema(self) -> dict[str, Any]:
        if isinstance(self.args_schema, type) and issubclass(self.args_schema, BaseModel):
            schema = self.args_schema.model_json_schema()
            if self.description:
                return {**schema, "description": self.description}
            return schema
        return super().tool_call_schema


def create_task_tools(
    store: TaskStore, *, claimant: str | None = None
) -> list[StructuredTool]:
    def _task_create(
        subject: str,
        description: str,
        activeForm: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        task = store.create_task(
            subject=subject,
            description=description,
            activeForm=activeForm,
            metadata=metadata,
        )
        return f"Task #{task.id} created successfully: {task.subject}"

    def _task_get(taskId: str) -> str:
        task = store.get_task(taskId)
        if task is None:
            return "Task not found"
        return _format_task_get(task)

    def _task_update(
        taskId: str,
        subject: str | None = None,
        description: str | None = None,
        activeForm: str | None = None,
        status: str | None = None,
        addBlocks: list[str] | None = None,
        addBlockedBy: list[str] | None = None,
        owner: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if status == "deleted":
            if store.get_task(taskId) is None:
                return "Task not found"
            if store.delete_task(taskId):
                return f"Updated task #{taskId} deleted"
            return "Failed to delete task"

        task = store.get_task(taskId)
        if task is None:
            return "Task not found"

        updated_fields: list[str] = []
        dependency_fields: list[str] = []

        if addBlocks:
            new_blocks = [
                blocked_task_id
                for blocked_task_id in addBlocks
                if blocked_task_id not in task.blocks
            ]
            if new_blocks:
                dependency_fields.append("blocks")
            for blocked_task_id in new_blocks:
                store.block_task(taskId, blocked_task_id)

        if addBlockedBy:
            new_blockers = [
                blocker_task_id
                for blocker_task_id in addBlockedBy
                if blocker_task_id not in task.blockedBy
            ]
            if new_blockers:
                dependency_fields.append("blockedBy")
            for blocker_task_id in new_blockers:
                store.block_task(blocker_task_id, taskId)

        task = store.get_task(taskId)
        if task is None:
            return "Task not found"

        update_kwargs: dict[str, Any] = {}
        for field_name, value in {
            "subject": subject,
            "description": description,
            "activeForm": activeForm,
            "status": status,
            "owner": owner,
        }.items():
            if value is not None and getattr(task, field_name) != value:
                update_kwargs[field_name] = value
                updated_fields.append(field_name)

        if metadata is not None:
            merged_metadata = _merge_metadata(task.metadata, metadata)
            if task.metadata != merged_metadata:
                update_kwargs["metadata"] = metadata
                updated_fields.append("metadata")
        updated_fields.extend(dependency_fields)

        updated = store.update_task(
            taskId,
            subject=update_kwargs.get("subject"),
            description=update_kwargs.get("description"),
            activeForm=update_kwargs.get("activeForm"),
            status=update_kwargs.get("status"),
            owner=update_kwargs.get("owner"),
            metadata=update_kwargs.get("metadata"),
        )
        if updated is None:
            return "Task not found"

        return f"Updated task #{taskId} {', '.join(updated_fields)}"

    def _task_list() -> str:
        items = store.list_task_items()
        if not items:
            return "No tasks found"
        return "\n".join(_format_task_list_item(item) for item in items)

    return [
        TaskStructuredTool.from_function(
            func=_task_create,
            name="TaskCreate",
            description=(
                "Create a planning task with a subject, description, optional active form, "
                "and metadata. New tasks start pending and can later be linked as blockers."
            ),
            args_schema=TaskCreateInput,
        ),
        TaskStructuredTool.from_function(
            func=_task_get,
            name="TaskGet",
            description=(
                "Read the complete record for one task, including full dependency "
                "fields and blockers that may already be completed."
            ),
            args_schema=TaskGetInput,
        ),
        TaskStructuredTool.from_function(
            func=_task_update,
            name="TaskUpdate",
            description=(
                "Update a task's fields, status, owner, metadata, or dependency links. "
                "Use status deleted to remove a task, addBlocks for tasks this task blocks, "
                "and addBlockedBy for tasks that block this task."
            ),
            args_schema=TaskUpdateInput,
        ),
        TaskStructuredTool.from_function(
            func=_task_list,
            name="TaskList",
            description=(
                "List concise task items for planning, with completed blockers omitted "
                "from each item's blockedBy projection."
            ),
            args_schema=TaskListInput,
        ),
    ]


def _format_task_get(task: Task) -> str:
    lines = [
        f"Task #{task.id}: {task.subject}",
        f"Status: {task.status}",
        f"Description: {task.description}",
    ]
    if task.blockedBy:
        lines.append(f"Blocked by: {_format_task_ids(task.blockedBy)}")
    if task.blocks:
        lines.append(f"Blocks: {_format_task_ids(task.blocks)}")
    return "\n".join(lines)


def _format_task_list_item(item: TaskListItem) -> str:
    line = f"#{item.id} [{item.status}] {item.subject}"
    if item.owner:
        line += f" ({item.owner})"
    if item.blockedBy:
        line += f" [blocked by {_format_task_ids(item.blockedBy)}]"
    return line


def _format_task_ids(task_ids: list[str]) -> str:
    return ", ".join(f"#{task_id}" for task_id in task_ids)


def _merge_metadata(
    existing_metadata: dict[str, Any] | None, metadata_update: dict[str, Any]
) -> dict[str, Any] | None:
    merged = dict(existing_metadata or {})
    for key, value in metadata_update.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged or None
