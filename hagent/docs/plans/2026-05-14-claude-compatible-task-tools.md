# Claude-Compatible Task Tools Implementation Plan

> **存档说明**：本 plan 产出自已退役的 superpowers 工作流，仅作历史参考；新工作一律走仓根 tickets.md（Matt 契约）。

**Goal:** Replace Hagent's V1 `write_todos` planning tool with Claude Code-compatible V2 `TaskCreate`, `TaskGet`, `TaskUpdate`, and `TaskList` tools, backed by persistent task state and dependency tracking.

**Architecture:** Add a focused `hagent.task_tools` package that owns task schemas, workspace-scoped JSON persistence, file locking, Claude-style result formatting, and LangChain `StructuredTool` factories. Wire the tools into `create_hagent()` next to the existing `Bash` and file tools, exclude DeepAgents' legacy `write_todos`, attach the task store to the created agent, and update the FastAPI/SSE layer so `/sessions/{sid}/todos` and `todo.updated` are driven by the V2 task store.

**Tech Stack:** Python 3.11+, Pydantic v2, LangChain `StructuredTool`, stdlib `fcntl` file locks on POSIX, pytest, FastAPI test client.

---

## Required Context

- Claude Code recovered source registers `TaskCreateTool`, `TaskGetTool`, `TaskUpdateTool`, and `TaskListTool` only when Todo V2 is enabled.
- Claude Code stores each task as JSON with fields `id`, `subject`, `description`, `activeForm`, `owner`, `status`, `blocks`, `blockedBy`, and `metadata`.
- Claude Code statuses are `pending`, `in_progress`, and `completed`; `TaskUpdate` additionally accepts `deleted` as an action that removes the task.
- Claude Code uses `blocks` and `blockedBy` as mirrored dependency arrays. A completed blocker no longer appears in `TaskList` output, but remains in the full task record returned by `TaskGet`.
- Claude Code uses a high-water mark to avoid ID reuse after deletion/reset.
- Hagent currently registers custom `Bash`, `Read`, `Write`, and `Edit` tools in `src/hagent/core.py`.
- Hagent currently exposes `/sessions/{sid}/todos` by reading `state.values["todos"]`, and emits `todo.updated` only for the legacy `write_todos` tool in `src/hagent/server/sse.py`.
- This plan treats `TaskCreate`/`TaskGet`/`TaskUpdate`/`TaskList` as Todo V2 and disables model access to `write_todos` so the agent cannot mix two planning systems.
- This plan intentionally does not build a new frontend task panel. It provides compatible backend data and SSE events so the current UI can keep using the `todo.updated` event and `/todos` endpoint while the model uses only Task tools.

## File Structure

Create:

- `src/hagent/task_tools/__init__.py` — public factory exports for task tools and task store.
- `src/hagent/task_tools/models.py` — Pydantic task models, input models, output projection helpers, and todo compatibility conversion.
- `src/hagent/task_tools/store.py` — workspace-scoped JSON task store, path sanitization, high-water mark handling, file locking, dependency mutation, reset, and task claiming.
- `src/hagent/task_tools/tools.py` — `TaskCreate`, `TaskGet`, `TaskUpdate`, and `TaskList` `StructuredTool` factories and Claude-style result strings.

Modify:

- `src/hagent/core.py` — exclude legacy `write_todos`, create task store, register task tools, attach `_hagent_task_store` to the agent.
- `src/hagent/server/agents.py` — pass `task_list_id=session_id` when building a session agent.
- `src/hagent/server/routers/messages.py` — emit `todo.updated` after task tool completions and prefer task-store state for `/todos`, with state fallback only for older agents that have no task store.
- `src/hagent/server/sse.py` — recognize Task tool completions as refresh-worthy and stop emitting live updates for `write_todos`.
- `prompts/hagent_base.zh.md` — replace `write_todos` workflow instructions with Task tool workflow instructions.
- `prompts/decisions.md` — record the prompt wording change required by repository policy.

Test:

- `tests/test_task_tools_models.py`
- `tests/test_task_tools_store.py`
- `tests/test_task_tools_tools.py`
- `tests/test_task_tools_registration.py`
- `tests/server/test_sse_adapter.py`
- `tests/server/test_messages_api.py`
- `tests/test_core.py`

---

### Task 1: Task Models and Todo Compatibility Projection

**Files:**
- Create: `src/hagent/task_tools/__init__.py`
- Create: `src/hagent/task_tools/models.py`
- Test: `tests/test_task_tools_models.py`

- [ ] **Step 1: Write the failing model tests**

Create `tests/test_task_tools_models.py`:

```python
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
```

- [ ] **Step 2: Run the model tests and verify they fail**

Run:

```bash
pytest tests/test_task_tools_models.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hagent.task_tools'`.

- [ ] **Step 3: Create the task tool package exports**

Create `src/hagent/task_tools/__init__.py`:

```python
from hagent.task_tools.models import Task
from hagent.task_tools.store import TaskStore
from hagent.task_tools.tools import create_task_tools

__all__ = ["Task", "TaskStore", "create_task_tools"]
```

- [ ] **Step 4: Implement the task models**

Create `src/hagent/task_tools/models.py`:

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TaskStatus = Literal["pending", "in_progress", "completed"]
TaskUpdateStatus = Literal["pending", "in_progress", "completed", "deleted"]


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
    activeForm: str | None = Field(
        default=None,
        description='Present continuous form shown when in_progress, e.g. "Running tests"',
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Arbitrary metadata to attach to the task",
    )


class TaskGetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taskId: str = Field(description="The ID of the task to retrieve")


class TaskUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taskId: str = Field(description="The ID of the task to update")
    subject: str | None = Field(default=None, description="New subject for the task")
    description: str | None = Field(default=None, description="New description for the task")
    activeForm: str | None = Field(default=None, description="New in-progress display text")
    status: TaskUpdateStatus | None = Field(default=None, description="New status for the task")
    addBlocks: list[str] | None = Field(default=None, description="Task IDs that this task blocks")
    addBlockedBy: list[str] | None = Field(default=None, description="Task IDs that block this task")
    owner: str | None = Field(default=None, description="New owner for the task")
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Metadata keys to merge into the task. Set a key to null to delete it.",
    )


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
    if task.owner:
        todo["owner"] = task.owner
    return todo
```

- [ ] **Step 5: Run the model tests and verify they pass**

Run:

```bash
pytest tests/test_task_tools_models.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/hagent/task_tools/__init__.py src/hagent/task_tools/models.py tests/test_task_tools_models.py
git commit -m "feat(task-tools): add task models"
```

Expected: commit succeeds.

---

### Task 2: Persistent Task Store with IDs, Updates, Deletion, Dependencies, and Claims

**Files:**
- Create: `src/hagent/task_tools/store.py`
- Test: `tests/test_task_tools_store.py`

- [ ] **Step 1: Write the failing store tests**

Create `tests/test_task_tools_store.py`:

```python
from hagent.task_tools.models import Task
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


def test_reset_task_list_clears_tasks_and_keeps_high_water_mark(tmp_path) -> None:
    store = TaskStore(tmp_path, task_list_id="tasks")
    store.create_task(subject="One", description="First")
    store.create_task(subject="Two", description="Second")

    store.reset()
    task = store.create_task(subject="Three", description="After reset")

    assert store.list_tasks() == [task]
    assert task.id == "3"
```

- [ ] **Step 2: Run the store tests and verify they fail**

Run:

```bash
pytest tests/test_task_tools_store.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hagent.task_tools.store'`.

- [ ] **Step 3: Implement the persistent store**

Create `src/hagent/task_tools/store.py`:

```python
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
        except Exception:
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
                status="pending",
                owner=None,
                blocks=[],
                blockedBy=[],
                metadata=metadata,
            )
            self._write_task(task)
            return task

    def _write_task(self, task: Task) -> None:
        self._task_path(task.id).write_text(
            json.dumps(task.model_dump(exclude_none=True), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_task(self, task_id: str) -> Task | None:
        path = self._task_path(task_id)
        if not path.exists():
            return None
        try:
            return Task.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def list_tasks(self, *, include_internal: bool = False) -> list[Task]:
        tasks: list[Task] = []
        for path in sorted(self.tasks_dir.glob("*.json"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0):
            task = self.get_task(path.stem)
            if task is None:
                continue
            if not include_internal and task.metadata and task.metadata.get("_internal"):
                continue
            tasks.append(task)
        return tasks

    def list_task_items(self) -> list[TaskListItem]:
        tasks = self.list_tasks()
        completed_ids = {task.id for task in tasks if task.status == "completed"}
        return [
            TaskListItem(
                id=task.id,
                subject=task.subject,
                status=task.status,
                owner=task.owner,
                blockedBy=[task_id for task_id in task.blockedBy if task_id not in completed_ids],
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
            existing = self.get_task(task_id)
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
            self._write_task(updated)
            return updated

    def delete_task(self, task_id: str) -> bool:
        with self._locked():
            path = self._task_path(task_id)
            if not path.exists():
                return False
            try:
                numeric_id = int(task_id)
            except ValueError:
                numeric_id = 0
            if numeric_id > self._read_highwater():
                self._write_highwater(numeric_id)
            path.unlink()
            for task in self.list_tasks(include_internal=True):
                new_blocks = [item for item in task.blocks if item != task_id]
                new_blocked_by = [item for item in task.blockedBy if item != task_id]
                if new_blocks != task.blocks or new_blocked_by != task.blockedBy:
                    self._write_task(task.model_copy(update={"blocks": new_blocks, "blockedBy": new_blocked_by}))
            return True

    def block_task(self, from_task_id: str, to_task_id: str) -> bool:
        with self._locked():
            from_task = self.get_task(from_task_id)
            to_task = self.get_task(to_task_id)
            if from_task is None or to_task is None:
                return False
            if to_task_id not in from_task.blocks:
                from_task = from_task.model_copy(update={"blocks": [*from_task.blocks, to_task_id]})
                self._write_task(from_task)
            if from_task_id not in to_task.blockedBy:
                to_task = to_task.model_copy(update={"blockedBy": [*to_task.blockedBy, from_task_id]})
                self._write_task(to_task)
            return True

    def claim_task(self, task_id: str, claimant: str, *, check_agent_busy: bool = False) -> dict[str, Any]:
        with self._locked():
            task = self.get_task(task_id)
            if task is None:
                return {"success": False, "reason": "task_not_found"}
            if task.owner and task.owner != claimant:
                return {"success": False, "reason": "already_claimed"}
            if task.status == "completed":
                return {"success": False, "reason": "already_resolved"}
            all_tasks = self.list_tasks(include_internal=True)
            unresolved_ids = {item.id for item in all_tasks if item.status != "completed"}
            blocked_by = [item for item in task.blockedBy if item in unresolved_ids]
            if blocked_by:
                return {"success": False, "reason": "blocked", "blockedByTasks": blocked_by}
            if check_agent_busy:
                busy = [
                    item.id
                    for item in all_tasks
                    if item.id != task_id and item.owner == claimant and item.status != "completed"
                ]
                if busy:
                    return {"success": False, "reason": "agent_busy", "busyWithTasks": busy}
            updated = task.model_copy(update={"owner": claimant})
            self._write_task(updated)
            return {"success": True, "task": updated.model_dump(exclude_none=True)}

    def reset(self) -> None:
        with self._locked():
            highest = self._highest_file_id()
            if highest > self._read_highwater():
                self._write_highwater(highest)
            for path in self.tasks_dir.glob("*.json"):
                path.unlink()
```

- [ ] **Step 4: Run the store tests and verify they pass**

Run:

```bash
pytest tests/test_task_tools_store.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/hagent/task_tools/store.py tests/test_task_tools_store.py
git commit -m "feat(task-tools): add persistent task store"
```

Expected: commit succeeds.

---

### Task 3: StructuredTool Implementations and Claude-Style Results

**Files:**
- Create: `src/hagent/task_tools/tools.py`
- Test: `tests/test_task_tools_tools.py`

- [ ] **Step 1: Write the failing tool tests**

Create `tests/test_task_tools_tools.py`:

```python
import json

from hagent.task_tools.store import TaskStore
from hagent.task_tools.tools import create_task_tools


def tools_by_name(store: TaskStore):
    return {tool.name: tool for tool in create_task_tools(store)}


def test_create_tool_creates_pending_task_and_returns_claude_message(tmp_path) -> None:
    store = TaskStore(tmp_path, task_list_id="tools")
    tools = tools_by_name(store)

    result = tools["TaskCreate"].invoke(
        {"subject": "Write tests", "description": "Cover task behavior.", "activeForm": "Writing tests"}
    )

    assert result == "Task #1 created successfully: Write tests"
    task = store.get_task("1")
    assert task.status == "pending"
    assert task.activeForm == "Writing tests"
    assert task.blocks == []
    assert task.blockedBy == []


def test_get_tool_returns_full_details_or_not_found(tmp_path) -> None:
    store = TaskStore(tmp_path, task_list_id="tools")
    task = store.create_task(subject="Inspect code", description="Read relevant files.")
    tools = tools_by_name(store)

    found = tools["TaskGet"].invoke({"taskId": task.id})
    missing = tools["TaskGet"].invoke({"taskId": "99"})

    assert "Task #1: Inspect code" in found
    assert "Status: pending" in found
    assert "Description: Read relevant files." in found
    assert missing == "Task not found"


def test_update_tool_updates_status_owner_dependencies_and_metadata(tmp_path) -> None:
    store = TaskStore(tmp_path, task_list_id="tools")
    one = store.create_task(subject="Setup", description="Prepare")
    two = store.create_task(subject="Build", description="Build")
    tools = tools_by_name(store)

    result = tools["TaskUpdate"].invoke(
        {
            "taskId": two.id,
            "status": "in_progress",
            "owner": "coder",
            "addBlockedBy": [one.id],
            "metadata": {"phase": "implementation"},
        }
    )

    assert result == "Updated task #2 status, owner, metadata, blockedBy"
    updated = store.get_task(two.id)
    assert updated.status == "in_progress"
    assert updated.owner == "coder"
    assert updated.blockedBy == [one.id]
    assert updated.metadata == {"phase": "implementation"}
    assert store.get_task(one.id).blocks == [two.id]


def test_update_tool_delete_action_removes_task(tmp_path) -> None:
    store = TaskStore(tmp_path, task_list_id="tools")
    task = store.create_task(subject="Remove me", description="Created by mistake")
    tools = tools_by_name(store)

    result = tools["TaskUpdate"].invoke({"taskId": task.id, "status": "deleted"})

    assert result == "Updated task #1 deleted"
    assert store.get_task(task.id) is None


def test_update_tool_missing_task_returns_non_error_result(tmp_path) -> None:
    store = TaskStore(tmp_path, task_list_id="tools")
    tools = tools_by_name(store)

    result = tools["TaskUpdate"].invoke({"taskId": "404", "status": "completed"})

    assert result == "Task not found"


def test_list_tool_formats_summary_and_hides_completed_blocker(tmp_path) -> None:
    store = TaskStore(tmp_path, task_list_id="tools")
    one = store.create_task(subject="Setup", description="Prepare")
    two = store.create_task(subject="Build", description="Build")
    store.block_task(one.id, two.id)
    tools = tools_by_name(store)

    before = tools["TaskList"].invoke({})
    assert before.splitlines() == [
        "#1 [pending] Setup",
        "#2 [pending] Build [blocked by #1]",
    ]

    store.update_task(one.id, status="completed")
    after = tools["TaskList"].invoke({})
    assert after.splitlines() == [
        "#1 [completed] Setup",
        "#2 [pending] Build",
    ]


def test_all_task_tools_expose_store_metadata(tmp_path) -> None:
    store = TaskStore(tmp_path, task_list_id="tools")

    for tool in create_task_tools(store):
        assert tool.metadata["hagent_task_store"] is store
```

- [ ] **Step 2: Run the tool tests and verify they fail**

Run:

```bash
pytest tests/test_task_tools_tools.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hagent.task_tools.tools'`.

- [ ] **Step 3: Implement the tool factories**

Create `src/hagent/task_tools/tools.py`:

```python
from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from hagent.task_tools.models import (
    TaskCreateInput,
    TaskGetInput,
    TaskListInput,
    TaskUpdateInput,
)
from hagent.task_tools.store import TaskStore

TASK_TOOL_NAMES = {"TaskCreate", "TaskGet", "TaskUpdate", "TaskList"}

TASK_CREATE_DESCRIPTION = """Create a new task in the task list.

Use this tool for complex multi-step work. New tasks are created with status pending and no owner.
"""

TASK_GET_DESCRIPTION = """Get a task by ID from the task list.

Use this before updating a task when you need the latest description, status, and dependencies.
"""

TASK_UPDATE_DESCRIPTION = """Update a task in the task list.

Status progresses pending -> in_progress -> completed. Set status to deleted to remove a task.
Only mark a task completed when the described work is fully done.
"""

TASK_LIST_DESCRIPTION = """List all tasks in the task list.

Use this to check available work, blocked work, ownership, and overall progress.
"""


def create_task_tools(store: TaskStore) -> list[StructuredTool]:
    def task_create(
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

    def task_get(taskId: str) -> str:
        task = store.get_task(taskId)
        if task is None:
            return "Task not found"
        lines = [
            f"Task #{task.id}: {task.subject}",
            f"Status: {task.status}",
            f"Description: {task.description}",
        ]
        if task.blockedBy:
            lines.append(f"Blocked by: {', '.join(f'#{item}' for item in task.blockedBy)}")
        if task.blocks:
            lines.append(f"Blocks: {', '.join(f'#{item}' for item in task.blocks)}")
        return "\n".join(lines)

    def task_update(
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
        existing = store.get_task(taskId)
        if existing is None:
            return "Task not found"

        updated_fields: list[str] = []
        if status == "deleted":
            deleted = store.delete_task(taskId)
            return f"Updated task #{taskId} deleted" if deleted else "Task not found"

        update_kwargs: dict[str, Any] = {}
        for field_name, value in {
            "subject": subject,
            "description": description,
            "activeForm": activeForm,
            "status": status,
            "owner": owner,
            "metadata": metadata,
        }.items():
            if value is not None:
                update_kwargs[field_name] = value
                updated_fields.append(field_name)
        if update_kwargs:
            store.update_task(taskId, **update_kwargs)

        if addBlocks:
            new_blocks = [item for item in addBlocks if item not in existing.blocks]
            for blocked_id in new_blocks:
                store.block_task(taskId, blocked_id)
            if new_blocks:
                updated_fields.append("blocks")
        if addBlockedBy:
            new_blocked_by = [item for item in addBlockedBy if item not in existing.blockedBy]
            for blocker_id in new_blocked_by:
                store.block_task(blocker_id, taskId)
            if new_blocked_by:
                updated_fields.append("blockedBy")

        suffix = ", ".join(updated_fields)
        return f"Updated task #{taskId} {suffix}".rstrip()

    def task_list() -> str:
        items = store.list_task_items()
        if not items:
            return "No tasks found"
        lines: list[str] = []
        for item in items:
            owner = f" ({item.owner})" if item.owner else ""
            blocked = (
                f" [blocked by {', '.join(f'#{task_id}' for task_id in item.blockedBy)}]"
                if item.blockedBy
                else ""
            )
            lines.append(f"#{item.id} [{item.status}] {item.subject}{owner}{blocked}")
        return "\n".join(lines)

    return [
        StructuredTool.from_function(
            func=task_create,
            name="TaskCreate",
            description=TASK_CREATE_DESCRIPTION,
            args_schema=TaskCreateInput,
            metadata={"hagent_task_store": store},
        ),
        StructuredTool.from_function(
            func=task_get,
            name="TaskGet",
            description=TASK_GET_DESCRIPTION,
            args_schema=TaskGetInput,
            metadata={"hagent_task_store": store},
        ),
        StructuredTool.from_function(
            func=task_update,
            name="TaskUpdate",
            description=TASK_UPDATE_DESCRIPTION,
            args_schema=TaskUpdateInput,
            metadata={"hagent_task_store": store},
        ),
        StructuredTool.from_function(
            func=task_list,
            name="TaskList",
            description=TASK_LIST_DESCRIPTION,
            args_schema=TaskListInput,
            metadata={"hagent_task_store": store},
        ),
    ]
```

- [ ] **Step 4: Run the tool tests and verify they pass**

Run:

```bash
pytest tests/test_task_tools_tools.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/hagent/task_tools/tools.py tests/test_task_tools_tools.py
git commit -m "feat(task-tools): add claude task tools"
```

Expected: commit succeeds.

---

### Task 4: Register Task Tools in Hagent Core and Disable V1 Todos

**Files:**
- Modify: `src/hagent/core.py`
- Modify: `src/hagent/server/agents.py`
- Test: `tests/test_task_tools_registration.py`
- Modify test: `tests/test_core.py`

- [ ] **Step 1: Write failing registration tests**

Create `tests/test_task_tools_registration.py`:

```python
from deepagents.backends import FilesystemBackend

from hagent.config import HagentConfig
from hagent.core import create_hagent


def test_create_hagent_registers_task_tools_and_attaches_store(tmp_path, monkeypatch) -> None:
    captured: dict = {}
    registered: dict = {}
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    backend = FilesystemBackend(root_dir=workspace, virtual_mode=False)

    class FakeAgent:
        pass

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return FakeAgent()

    def fake_register_harness_profile(key, profile):
        registered["profile"] = profile

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    monkeypatch.setattr("hagent.core.register_harness_profile", fake_register_harness_profile)

    agent = create_hagent(
        config=HagentConfig(model="test:model", langsmith_tracing=False),
        backend=backend,
        task_list_id="session-123",
    )

    tool_names = {tool.name for tool in captured["tools"]}
    assert {"TaskCreate", "TaskGet", "TaskUpdate", "TaskList"}.issubset(tool_names)
    assert "write_todos" not in tool_names
    assert "write_todos" in registered["profile"].excluded_tools
    assert getattr(agent, "_hagent_task_store").task_list_id == "session-123"
    assert getattr(agent, "_hagent_task_store").workspace_root == workspace


def test_task_tools_share_one_store(tmp_path, monkeypatch) -> None:
    captured: dict = {}
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    backend = FilesystemBackend(root_dir=workspace, virtual_mode=False)

    monkeypatch.setattr("hagent.core._create_deep_agent", lambda **kwargs: captured.update(kwargs) or object())

    create_hagent(
        config=HagentConfig(model="test:model", langsmith_tracing=False),
        backend=backend,
        task_list_id="tasks",
    )

    task_tools = [tool for tool in captured["tools"] if tool.name.startswith("Task")]
    stores = [tool.metadata["hagent_task_store"] for tool in task_tools]
    assert len(task_tools) == 4
    assert len({id(store) for store in stores}) == 1


def test_task_create_tool_runs_from_registered_agent_tools(tmp_path, monkeypatch) -> None:
    captured: dict = {}
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    backend = FilesystemBackend(root_dir=workspace, virtual_mode=False)

    monkeypatch.setattr("hagent.core._create_deep_agent", lambda **kwargs: captured.update(kwargs) or object())

    create_hagent(
        config=HagentConfig(model="test:model", langsmith_tracing=False),
        backend=backend,
        task_list_id="tasks",
    )
    task_create = next(tool for tool in captured["tools"] if tool.name == "TaskCreate")

    result = task_create.invoke({"subject": "Plan work", "description": "Break down the request."})

    assert result == "Task #1 created successfully: Plan work"
```

- [ ] **Step 2: Add a failing core signature test**

Append to `tests/test_core.py`:

```python
def test_create_hagent_accepts_task_list_id(monkeypatch):
    captured: dict = {}

    class FakeAgent:
        pass

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return FakeAgent()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    agent = create_hagent(task_list_id="explicit-list")

    assert getattr(agent, "_hagent_task_store").task_list_id == "explicit-list"
```

- [ ] **Step 3: Run registration tests and verify they fail**

Run:

```bash
pytest tests/test_task_tools_registration.py tests/test_core.py::test_create_hagent_accepts_task_list_id -v
```

Expected: FAIL with `TypeError: create_hagent() got an unexpected keyword argument 'task_list_id'` or because `write_todos` is not excluded.

- [ ] **Step 4: Exclude legacy `write_todos` and wire task tools into `create_hagent`**

Modify `src/hagent/core.py`:

```python
from hagent.task_tools import TaskStore, create_task_tools
```

Change the excluded tool constant to:

```python
DISABLED_DEEPAGENTS_TOOLS = frozenset(
    {"execute", "read_file", "write_file", "edit_file", "write_todos"}
)
```

Change the `create_hagent` signature to:

```python
def create_hagent(
    config: HagentConfig | None = None,
    backend: Any | None = None,
    extra_subagents: list[dict] | None = None,
    extra_tools: list[Any] | None = None,
    checkpointer: Any | None = None,
    task_list_id: str | None = None,
) -> Any:
```

Insert after `file_tools = create_claude_file_tools(...)`:

```python
    task_store = TaskStore(
        working_directory,
        task_list_id=task_list_id or os.environ.get("HAGENT_TASK_LIST_ID", "tasklist"),
    )
    task_tools = create_task_tools(task_store)
```

Change the tools list to:

```python
        tools=[bash_tool, *file_tools, *task_tools, *list(extra_tools or [])],
```

Insert before `return agent`:

```python
    try:
        setattr(agent, "_hagent_task_store", task_store)
    except Exception:
        pass
```

- [ ] **Step 5: Pass session ID as task list ID in the server agent cache**

Modify `src/hagent/server/agents.py`:

```python
        _agents[session_id] = create_hagent(
            backend=backend,
            checkpointer=get_checkpointer(),
            task_list_id=session_id,
        )
```

- [ ] **Step 6: Run registration tests and verify they pass**

Run:

```bash
pytest tests/test_task_tools_registration.py tests/test_core.py::test_create_hagent_accepts_task_list_id -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add src/hagent/core.py src/hagent/server/agents.py tests/test_task_tools_registration.py tests/test_core.py
git commit -m "feat(task-tools): register task tools in hagent"
```

Expected: commit succeeds.

---

### Task 5: Server Todo and SSE Compatibility for Task Tools

**Files:**
- Modify: `src/hagent/server/sse.py`
- Modify: `src/hagent/server/routers/messages.py`
- Modify test: `tests/server/test_sse_adapter.py`
- Modify test: `tests/server/test_messages_api.py`

- [ ] **Step 1: Write failing SSE parser tests**

Append to `tests/server/test_sse_adapter.py`:

```python
def test_parse_task_tool_completion_emits_todo_refresh_marker():
    class FakeToolMessage:
        type = "tool"
        content = "Updated task #1 status"
        tool_call_id = "abc"
        name = "TaskUpdate"

    out = list(parse_lg_chunk(("messages", (FakeToolMessage(), {}))))

    assert (
        "todo.refresh_requested",
        {"tool_name": "TaskUpdate"},
    ) in out


def test_parse_write_todos_completion_does_not_emit_todo_updated_after_v2_replacement():
    class FakeToolMessage:
        type = "tool"
        content = '[{"content": "legacy", "status": "pending"}]'
        tool_call_id = "abc"
        name = "write_todos"

    out = list(parse_lg_chunk(("messages", (FakeToolMessage(), {}))))

    assert not [event for event, _data in out if event == "todo.updated"]
    assert not [event for event, _data in out if event == "todo.refresh_requested"]


def test_parse_non_task_tool_completion_does_not_emit_todo_refresh_marker():
    class FakeToolMessage:
        type = "tool"
        content = "result"
        tool_call_id = "abc"
        name = "Read"

    out = list(parse_lg_chunk(("messages", (FakeToolMessage(), {}))))

    assert not [event for event, _data in out if event == "todo.refresh_requested"]
```

- [ ] **Step 2: Write failing `/todos` and streaming tests**

Append to `tests/server/test_messages_api.py`:

```python
def test_get_todos_prefers_hagent_task_store(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    from hagent.task_tools.store import TaskStore

    store = TaskStore(tmp_path / "workspace", task_list_id="session")
    store.create_task(subject="Use TaskCreate", description="Server should expose task store.")

    class FakeState:
        values = {"todos": [{"content": "legacy", "status": "pending"}]}

    class FakeAgent:
        _hagent_task_store = store

        def stream(self, *_a, **_kw):
            yield from ()

        def get_state(self, _cfg):
            return FakeState()

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd: FakeAgent(),
    )

    app = create_app()
    client = TestClient(app)
    sid = client.post("/sessions", json={"workspace_dir": str(tmp_path / "workspace")}).json()["session_id"]

    response = client.get(f"/sessions/{sid}/todos")

    assert response.status_code == 200
    assert response.json() == [
        {
            "content": "Use TaskCreate",
            "status": "pending",
            "id": "1",
            "description": "Server should expose task store.",
            "blockedBy": [],
        }
    ]


def test_post_message_streams_todo_updated_after_task_tool_completion(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    from hagent.task_tools.store import TaskStore

    workspace = tmp_path / "workspace"
    store = TaskStore(workspace, task_list_id="session")
    store.create_task(subject="Stream task", description="Emit todo update.")

    class FakeToolMessage:
        type = "tool"
        content = "Task #1 created successfully: Stream task"
        tool_call_id = "abc"
        name = "TaskCreate"

    class FakeAgent:
        _hagent_task_store = store

        def stream(self, *_args, **_kwargs):
            yield ((), "messages", (FakeToolMessage(), {}))

        def get_state(self, _cfg):
            return type("FakeState", (), {"values": {}})()

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd: FakeAgent(),
    )

    app = create_app()
    client = TestClient(app)
    sid = client.post("/sessions", json={"workspace_dir": str(workspace)}).json()["session_id"]

    with client.stream("POST", f"/sessions/{sid}/messages", json={"content": "hi"}) as response:
        body = b"".join(response.iter_bytes())

    assert b"event: todo.updated" in body
    assert b'"content": "Stream task"' in body
```

- [ ] **Step 3: Run server tests and verify they fail**

Run:

```bash
pytest tests/server/test_sse_adapter.py::test_parse_task_tool_completion_emits_todo_refresh_marker tests/server/test_sse_adapter.py::test_parse_non_task_tool_completion_does_not_emit_todo_refresh_marker tests/server/test_messages_api.py::test_get_todos_prefers_hagent_task_store tests/server/test_messages_api.py::test_post_message_streams_todo_updated_after_task_tool_completion -v
```

Expected: FAIL because Task tool completions are not recognized, `/todos` reads only agent state, and `write_todos` still emits live todo updates.

- [ ] **Step 4: Add Task tool refresh markers and remove `write_todos` live updates from the SSE adapter**

Modify `src/hagent/server/sse.py`:

```python
TASK_TOOL_NAMES = {"TaskCreate", "TaskGet", "TaskUpdate", "TaskList"}
```

Inside the `token_type == "tool"` branch, delete this legacy block:

```python
            if tool_name == "write_todos":
                # spec §5 要求 payload 是 {"todos": [...]}
                yield ("todo.updated", {"todos": _safe_parse_todos(str(result))})
```

Then add:

```python
            if tool_name in TASK_TOOL_NAMES:
                yield ("todo.refresh_requested", {"tool_name": tool_name})
```

- [ ] **Step 5: Add task-store todo projection helpers to messages router**

Modify `src/hagent/server/routers/messages.py` imports:

```python
from hagent.task_tools.models import task_to_todo
```

Add this helper above `_stream_agent_events`:

```python
def _task_store_todos(agent: Any) -> list[dict] | None:
    store = getattr(agent, "_hagent_task_store", None)
    if store is None:
        return None
    list_tasks = getattr(store, "list_tasks", None)
    if not callable(list_tasks):
        return None
    return [task_to_todo(task) for task in list_tasks()]
```

In `_stream_agent_events`, replace the parse loop body with:

```python
            for event, data in parse_lg_chunk(inner, tool_call_state=tool_call_state):
                if event == "todo.refresh_requested":
                    todos = _task_store_todos(agent)
                    if todos is not None:
                        yield fmt.format(event="todo.updated", data={"todos": todos})
                    continue
                yield fmt.format(event=event, data=data)
```

In `get_todos`, replace the final two lines with:

```python
    todos = _task_store_todos(agent)
    if todos is not None:
        return todos
    state = agent.get_state({"configurable": {"thread_id": sid}})
    return list(state.values.get("todos", [])) if state else []
```

The fallback to `state.values["todos"]` is only for old checkpointer/session data and fake agents in tests. New Hagent agents always have `_hagent_task_store` and no model-visible `write_todos`.

- [ ] **Step 6: Run server tests and verify they pass**

Run:

```bash
pytest tests/server/test_sse_adapter.py tests/server/test_messages_api.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add src/hagent/server/sse.py src/hagent/server/routers/messages.py tests/server/test_sse_adapter.py tests/server/test_messages_api.py
git commit -m "feat(server): stream task tool todo updates"
```

Expected: commit succeeds.

---

### Task 6: Prompt Instructions for Task Tools

**Files:**
- Modify: `prompts/hagent_base.zh.md`
- Modify: `prompts/decisions.md`
- Modify test: `tests/test_core.py`

- [ ] **Step 1: Write failing prompt tests**

Append to `tests/test_core.py`:

```python
def test_create_hagent_base_prompt_mentions_task_tools(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    create_hagent()

    system_prompt = captured["system_prompt"]
    assert "TaskCreate" in system_prompt
    assert "TaskUpdate" in system_prompt
    assert "TaskList" in system_prompt
    assert "TaskGet" in system_prompt
```

- [ ] **Step 2: Run the prompt test and verify it fails**

Run:

```bash
pytest tests/test_core.py::test_create_hagent_base_prompt_mentions_task_tools -v
```

Expected: FAIL because the base prompt currently mentions `write_todos` but not all Task tools.

- [ ] **Step 3: Update the base prompt**

Modify `prompts/hagent_base.zh.md`. Replace this existing instruction:

```markdown
 - 使用 write_todos 规划并追踪工作。每个任务完成后立即标记为 completed；不要批量标记。
```

with:

```markdown
 - 使用 `TaskCreate`、`TaskUpdate`、`TaskList`、`TaskGet` 规划并追踪复杂工作。3 个及以上步骤、用户明确要求 todo/task list、或需要并行/依赖管理时，先用 `TaskCreate` 建立任务。开始某项任务前用 `TaskUpdate` 标记为 `in_progress`；完成后立即用 `TaskUpdate` 标记为 `completed`；需要完整上下文时用 `TaskGet`；需要总览和选择下一项工作时用 `TaskList`。不要把未完成、测试失败、被阻塞或只做了一部分的任务标记为 `completed`。
```

- [ ] **Step 4: Record the prompt decision**

Append to `prompts/decisions.md`:

```markdown
## 2026-05-14 Task tool workflow

- Replaced the legacy `write_todos` instruction with Claude Code-compatible `TaskCreate`, `TaskGet`, `TaskUpdate`, and `TaskList` instructions.
- The prompt tells the model to create tasks for complex multi-step work, mark a task `in_progress` before starting, mark it `completed` only when fully done, use `TaskGet` for full task context, and use `TaskList` for progress and next-work selection.
```

- [ ] **Step 5: Run prompt checks**

Run:

```bash
pytest tests/test_core.py::test_create_hagent_base_prompt_mentions_task_tools -v
./scripts/check_base_prompt.sh
```

Expected: pytest PASS and `check_base_prompt.sh` exits 0.

- [ ] **Step 6: Commit**

Run:

```bash
git add prompts/hagent_base.zh.md prompts/decisions.md tests/test_core.py
git commit -m "docs(prompt): instruct agent to use task tools"
```

Expected: commit succeeds.

---

### Task 7: Focused Regression Run and Behavior Smoke

**Files:**
- No source files expected.
- Validate: `src/hagent/task_tools/*`, `src/hagent/core.py`, `src/hagent/server/*`, `prompts/hagent_base.zh.md`

- [ ] **Step 1: Run focused task tool tests**

Run:

```bash
pytest tests/test_task_tools_models.py tests/test_task_tools_store.py tests/test_task_tools_tools.py tests/test_task_tools_registration.py -v
```

Expected: PASS.

- [ ] **Step 2: Run server compatibility tests**

Run:

```bash
pytest tests/server/test_sse_adapter.py tests/server/test_messages_api.py -v
```

Expected: PASS.

- [ ] **Step 3: Run core registration tests**

Run:

```bash
pytest tests/test_core.py tests/test_claude_file_tools_registration.py -v
```

Expected: PASS.

- [ ] **Step 4: Run full Python suite**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 5: Manually smoke the registered tools without model calls**

Run:

```bash
python - <<'PY'
from pathlib import Path
from deepagents.backends import FilesystemBackend
from hagent.config import HagentConfig
from hagent.core import create_hagent

captured = {}

def fake_create_deep_agent(**kwargs):
    captured.update(kwargs)
    class FakeAgent:
        pass
    return FakeAgent()

import hagent.core
hagent.core._create_deep_agent = fake_create_deep_agent

workspace = Path("/tmp/hagent-task-tools-smoke")
workspace.mkdir(parents=True, exist_ok=True)
agent = create_hagent(
    config=HagentConfig(model="test:model", langsmith_tracing=False),
    backend=FilesystemBackend(root_dir=workspace, virtual_mode=False),
    task_list_id="smoke",
)
tools = {tool.name: tool for tool in captured["tools"]}
print(tools["TaskCreate"].invoke({"subject": "Smoke task", "description": "Check tool wiring."}))
print(tools["TaskUpdate"].invoke({"taskId": "1", "status": "in_progress"}))
print(tools["TaskList"].invoke({}))
print(getattr(agent, "_hagent_task_store").list_tasks()[0].subject)
PY
```

Expected output contains:

```text
Task #1 created successfully: Smoke task
Updated task #1 status
#1 [in_progress] Smoke task
Smoke task
```

- [ ] **Step 6: Commit verification-only changes if any**

Run:

```bash
git status --short
```

Expected: no unexpected source changes. If previous tasks already committed all changes, do not create an empty commit.

---

## Self-Review Notes

- Spec coverage: The plan covers the four Task tools, disables legacy `write_todos`, Claude-style task fields/statuses, dependency mirroring, deletion, high-water mark ID behavior, non-error missing-task update results, tool registration, server todo compatibility, and prompt guidance.
- Scope boundary: TaskCompleted/TaskCreated hook plugins, teammate mailbox, verification-agent nudges, and frontend task panel UI are not included because Hagent does not currently have those subsystems. The store and tool metadata leave clear attachment points for later work.
- Placeholder scan: The plan contains concrete paths, test code, implementation code, commands, and expected outcomes.
- Type consistency: The plan consistently uses `taskId`, `activeForm`, `blockedBy`, `addBlocks`, `addBlockedBy`, and `metadata`, matching the recovered Claude Code tool schemas.
