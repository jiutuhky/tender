"""项目 Run 的持久化状态与查询。"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    session_id TEXT,
    node_id TEXT,
    status TEXT NOT NULL,
    base_revision TEXT,
    commit_sha TEXT,
    owned_paths TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    metadata_json TEXT
)
"""


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    CHECKPOINTING = "checkpointing"
    COMMITTED = "committed"
    INTERRUPTED = "interrupted"
    REJECTED = "rejected"


_ACTIVE_STATUSES = (
    RunStatus.PENDING.value,
    RunStatus.RUNNING.value,
    RunStatus.CHECKPOINTING.value,
)


@dataclass(frozen=True)
class RunState:
    id: str
    project_id: str
    kind: str
    session_id: str | None
    node_id: str | None
    status: RunStatus
    base_revision: str | None
    commit_sha: str | None
    owned_paths: tuple[str, ...]
    error: str | None
    created_at: str
    finished_at: str | None
    metadata: dict[str, Any]

    @property
    def summary(self) -> str:
        value = self.metadata.get("summary")
        return value if isinstance(value, str) else self.kind


def _now() -> str:
    return datetime.now(UTC).isoformat()


class RunStore:
    def __init__(self, db_path: Path | str):
        self._db_path = str(db_path)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(_SCHEMA)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_project ON runs(project_id, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_runs_active ON runs(project_id, status)"
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_chat_turn(
        self,
        *,
        project_id: str,
        session_id: str,
        base_revision: str | None,
        summary: str,
    ) -> RunState:
        run_id = uuid.uuid4().hex[:16]
        created_at = _now()
        metadata_json = json.dumps({"summary": summary}, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO runs "
                "(id, project_id, kind, session_id, status, base_revision, "
                "created_at, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    project_id,
                    "chat_turn",
                    session_id,
                    RunStatus.PENDING.value,
                    base_revision,
                    created_at,
                    metadata_json,
                ),
            )
        run = self.get(run_id)
        assert run is not None
        return run

    def get(self, run_id: str) -> RunState | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._row_to_state(row) if row is not None else None

    def mark_running(self, run_id: str) -> RunState:
        return self._set_status(run_id, RunStatus.RUNNING)

    def mark_checkpointing(self, run_id: str) -> RunState:
        return self._set_status(run_id, RunStatus.CHECKPOINTING)

    def finish(
        self,
        run_id: str,
        *,
        status: RunStatus,
        commit_sha: str | None = None,
        error: str | None = None,
    ) -> RunState:
        if status not in {
            RunStatus.COMMITTED,
            RunStatus.INTERRUPTED,
            RunStatus.REJECTED,
        }:
            raise ValueError(f"run 终态无效: {status.value}")
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE runs SET status = ?, commit_sha = ?, error = ?, "
                "finished_at = ? WHERE id = ?",
                (status.value, commit_sha, error, _now(), run_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(run_id)
        run = self.get(run_id)
        assert run is not None
        return run

    def active_for_project(self, project_id: str) -> list[RunState]:
        placeholders = ", ".join("?" for _ in _ACTIVE_STATUSES)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM runs WHERE project_id = ? AND status IN ({placeholders}) "
                "ORDER BY created_at",
                (project_id, *_ACTIVE_STATUSES),
            ).fetchall()
        return [self._row_to_state(row) for row in rows]

    def interrupt_active(self, *, error: str) -> list[RunState]:
        placeholders = ", ".join("?" for _ in _ACTIVE_STATUSES)
        finished_at = _now()
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT id FROM runs WHERE status IN ({placeholders}) "
                "ORDER BY created_at",
                _ACTIVE_STATUSES,
            ).fetchall()
            conn.execute(
                f"UPDATE runs SET status = ?, error = ?, finished_at = ? "
                f"WHERE status IN ({placeholders})",
                (
                    RunStatus.INTERRUPTED.value,
                    error,
                    finished_at,
                    *_ACTIVE_STATUSES,
                ),
            )
        recovered: list[RunState] = []
        for row in rows:
            run = self.get(row["id"])
            assert run is not None
            recovered.append(run)
        return recovered

    def _set_status(self, run_id: str, status: RunStatus) -> RunState:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE runs SET status = ? WHERE id = ?",
                (status.value, run_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(run_id)
        run = self.get(run_id)
        assert run is not None
        return run

    @staticmethod
    def _row_to_state(row: sqlite3.Row) -> RunState:
        owned_paths = json.loads(row["owned_paths"]) if row["owned_paths"] else []
        metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
        return RunState(
            id=row["id"],
            project_id=row["project_id"],
            kind=row["kind"],
            session_id=row["session_id"],
            node_id=row["node_id"],
            status=RunStatus(row["status"]),
            base_revision=row["base_revision"],
            commit_sha=row["commit_sha"],
            owned_paths=tuple(owned_paths),
            error=row["error"],
            created_at=row["created_at"],
            finished_at=row["finished_at"],
            metadata=metadata,
        )
