"""Process-local background task registry for Bash executions."""

from __future__ import annotations

import os
import signal
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal


TaskStatus = Literal["running", "backgrounded", "completed", "failed", "killed"]


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    command: str
    description: str | None
    pid: int
    process_group_id: int
    status: TaskStatus
    started_at: float
    completed_at: float | None
    output_path: Path
    exit_code: int | None
    interrupted: bool


class TaskRegistry:
    """Tracks shell task lifecycle records and can terminate active groups."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tasks: dict[str, TaskRecord] = {}

    def start(
        self,
        *,
        task_id: str,
        command: str,
        description: str | None,
        pid: int,
        process_group_id: int,
        output_path: Path,
        status: TaskStatus = "running",
    ) -> TaskRecord:
        record = TaskRecord(
            task_id=task_id,
            command=command,
            description=description,
            pid=pid,
            process_group_id=process_group_id,
            status=status,
            started_at=time.time(),
            completed_at=None,
            output_path=output_path,
            exit_code=None,
            interrupted=False,
        )
        with self._lock:
            self._tasks[task_id] = record
        return record

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list(self) -> list[TaskRecord]:
        with self._lock:
            return list(self._tasks.values())

    def mark_completed(self, task_id: str, *, exit_code: int, interrupted: bool) -> None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return
            final_interrupted = interrupted or record.interrupted
            if final_interrupted or record.status == "killed":
                status: TaskStatus = "killed"
            elif exit_code == 0:
                status = "completed"
            else:
                status = "failed"
            self._tasks[task_id] = replace(
                record,
                status=status,
                completed_at=time.time(),
                exit_code=exit_code,
                interrupted=final_interrupted,
            )

    def mark_killed(self, task_id: str) -> None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                return
            self._tasks[task_id] = replace(
                record,
                status="killed",
                completed_at=time.time(),
                interrupted=True,
            )

    def kill(self, task_id: str, *, sig: int = signal.SIGKILL) -> bool:
        record = self.get(task_id)
        if record is None:
            return False
        if record.status not in {"running", "backgrounded"}:
            return False
        killed = True
        try:
            os.killpg(record.process_group_id, sig)
        except ProcessLookupError:
            return False
        self.mark_killed(task_id)
        return killed

    def cleanup(self) -> None:
        for record in self.list():
            if record.status in {"running", "backgrounded"}:
                self.kill(record.task_id)
