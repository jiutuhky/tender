from __future__ import annotations

import json
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import fcntl

from hagent.task_tools.models import Task, TaskListItem, TaskStatus

HIGH_WATER_MARK_FILE = ".highwatermark"


def sanitize_path_component(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", value)


class TaskStore:
    def __init__(self, workspace_root: str | Path, task_list_id: str = "tasklist") -> None:
        self.workspace_root = Path(workspace_root)
        self.task_list_id = task_list_id
        self.tasks_dir = (
            self.workspace_root
            / ".hagent"
            / "tasks"
            / sanitize_path_component(task_list_id)
        )
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.tasks_dir / ".lock"
        with lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _task_path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{sanitize_path_component(task_id)}.json"

    def _highwater_path(self) -> Path:
        return self.tasks_dir / HIGH_WATER_MARK_FILE

    def _read_highwater(self) -> int:
        try:
            return int(self._highwater_path().read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return 0

    def _write_highwater(self, value: int) -> None:
        self._highwater_path().write_text(str(value), encoding="utf-8")

    def _highest_file_id(self) -> int:
        highest = 0
        for path in self.tasks_dir.glob("*.json"):
            try:
                highest = max(highest, int(path.stem))
            except ValueError:
                continue
        return highest

    def _next_id(self) -> str:
        return str(max(self._highest_file_id(), self._read_highwater()) + 1)

    def _read_task_no_lock(self, task_id: str) -> Task | None:
        path = self._task_path(task_id)
        if not path.exists():
            return None
        try:
            return Task.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _write_task_no_lock(self, task: Task) -> None:
        self._task_path(task.id).write_text(
            json.dumps(task.model_dump(exclude_none=True), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _list_tasks_no_lock(self, *, include_internal: bool = False) -> list[Task]:
        tasks: list[Task] = []
        paths = sorted(
            self.tasks_dir.glob("*.json"),
            key=lambda path: (0, int(path.stem)) if path.stem.isdigit() else (1, path.stem),
        )
        for path in paths:
            task = self._read_task_no_lock(path.stem)
            if task is None:
                continue
            if not include_internal and task.metadata and task.metadata.get("_internal") is True:
                continue
            tasks.append(task)
        return tasks

    def create_task(
        self,
        *,
        subject: str,
        description: str,
        activeForm: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        with self._locked():
            task_id = self._next_id()
            task = Task(
                id=task_id,
                subject=subject,
                description=description,
                activeForm=activeForm,
                owner=None,
                status="pending",
                blocks=[],
                blockedBy=[],
                metadata=metadata,
            )
            self._write_task_no_lock(task)
            self._write_highwater(int(task_id))
            return task

    def get_task(self, task_id: str) -> Task | None:
        with self._locked():
            return self._read_task_no_lock(task_id)

    def list_tasks(self, *, include_internal: bool = False) -> list[Task]:
        with self._locked():
            return self._list_tasks_no_lock(include_internal=include_internal)

    def list_task_items(self) -> list[TaskListItem]:
        with self._locked():
            tasks = self._list_tasks_no_lock()
            all_tasks = self._list_tasks_no_lock(include_internal=True)
            completed_ids = {task.id for task in all_tasks if task.status == "completed"}
            return [
                TaskListItem(
                    id=task.id,
                    subject=task.subject,
                    status=task.status,
                    owner=task.owner,
                    blockedBy=[
                        task_id for task_id in task.blockedBy if task_id not in completed_ids
                    ],
                )
                for task in tasks
            ]

    def update_task(
        self,
        task_id: str,
        *,
        subject: str | None = None,
        description: str | None = None,
        activeForm: str | None = None,
        status: TaskStatus | None = None,
        owner: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task | None:
        with self._locked():
            existing = self._read_task_no_lock(task_id)
            if existing is None:
                return None

            data = existing.model_dump()
            for key, value in {
                "subject": subject,
                "description": description,
                "activeForm": activeForm,
                "status": status,
                "owner": owner,
            }.items():
                if value is not None:
                    data[key] = value

            if metadata is not None:
                merged = dict(existing.metadata or {})
                for key, value in metadata.items():
                    if value is None:
                        merged.pop(key, None)
                    else:
                        merged[key] = value
                data["metadata"] = merged or None

            updated = Task.model_validate(data)
            self._write_task_no_lock(updated)
            return updated

    def delete_task(self, task_id: str) -> bool:
        with self._locked():
            task_path = self._task_path(task_id)
            if not task_path.exists():
                return False

            try:
                numeric_id = int(task_id)
            except ValueError:
                numeric_id = 0
            if numeric_id > self._read_highwater():
                self._write_highwater(numeric_id)

            task_path.unlink()
            for task in self._list_tasks_no_lock(include_internal=True):
                blocks = [item for item in task.blocks if item != task_id]
                blocked_by = [item for item in task.blockedBy if item != task_id]
                if blocks != task.blocks or blocked_by != task.blockedBy:
                    self._write_task_no_lock(
                        task.model_copy(update={"blocks": blocks, "blockedBy": blocked_by})
                    )
            return True

    def block_task(self, from_task_id: str, to_task_id: str) -> bool:
        with self._locked():
            from_task = self._read_task_no_lock(from_task_id)
            to_task = self._read_task_no_lock(to_task_id)
            if from_task is None or to_task is None:
                return False

            if to_task_id not in from_task.blocks:
                from_task = from_task.model_copy(
                    update={"blocks": [*from_task.blocks, to_task_id]}
                )
                self._write_task_no_lock(from_task)
            if from_task_id not in to_task.blockedBy:
                to_task = to_task.model_copy(update={"blockedBy": [*to_task.blockedBy, from_task_id]})
                self._write_task_no_lock(to_task)
            return True

    def claim_task(
        self, task_id: str, claimant: str, *, reject_if_agent_busy: bool = False
    ) -> dict[str, Any]:
        with self._locked():
            task = self._read_task_no_lock(task_id)
            if task is None:
                return {"success": False, "reason": "task_not_found"}
            if task.status == "completed":
                return {"success": False, "reason": "already_resolved"}
            if task.owner and task.owner != claimant:
                return {"success": False, "reason": "already_claimed"}

            all_tasks = self._list_tasks_no_lock(include_internal=True)
            unresolved_ids = {item.id for item in all_tasks if item.status != "completed"}
            blocked_by = [item for item in task.blockedBy if item in unresolved_ids]
            if blocked_by:
                return {"success": False, "reason": "blocked", "blockedByTasks": blocked_by}

            if reject_if_agent_busy:
                busy_tasks = [
                    item.id
                    for item in all_tasks
                    if item.id != task_id and item.owner == claimant and item.status != "completed"
                ]
                if busy_tasks:
                    return {
                        "success": False,
                        "reason": "agent_busy",
                        "busyWithTasks": busy_tasks,
                    }

            updated = task.model_copy(update={"owner": claimant})
            self._write_task_no_lock(updated)
            return {"success": True, "task": updated.model_dump(exclude_none=True)}

    def reset(self) -> None:
        with self._locked():
            highest = self._highest_file_id()
            if highest > self._read_highwater():
                self._write_highwater(highest)
            for path in self.tasks_dir.glob("*.json"):
                path.unlink()
