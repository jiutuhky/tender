"""项目级沙箱租约持久化。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path


class SandboxState(str, Enum):
    CREATING = "creating"
    RUNNING = "running"
    PAUSED = "paused"
    SNAPSHOTTED = "snapshotted"
    ORPHANED = "orphaned"
    EVICTED = "evicted"
    ERROR = "error"
    CLOSED = "closed"


@dataclass(frozen=True)
class ProjectLeaseState:
    project_id: str
    sandbox_id: str | None = None
    sandbox_kind: str | None = None
    sandbox_state: str | None = None
    sandbox_desired_state: str | None = None
    snapshot_id: str | None = None
    materialized_revision: str | None = None
    node: str | None = None
    last_activity_at: str | None = None
    metadata_json: str | None = None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sandbox_leases (
    project_id TEXT PRIMARY KEY,
    sandbox_id TEXT,
    sandbox_kind TEXT,
    sandbox_state TEXT,
    sandbox_desired_state TEXT,
    snapshot_id TEXT,
    materialized_revision TEXT,
    node TEXT,
    last_activity_at TEXT,
    metadata_json TEXT
)
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class LeaseStore:
    def __init__(self, db_path: Path | str):
        self._db_path = str(db_path)
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure(
        self,
        project_id: str,
        *,
        sandbox_kind: str,
        node: str | None = None,
    ) -> ProjectLeaseState:
        if not project_id:
            raise ValueError("project_id is required")
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sandbox_leases "
                "(project_id, sandbox_kind, node, last_activity_at) VALUES (?, ?, ?, ?)",
                (project_id, sandbox_kind, node, _now()),
            )
        lease = self.get(project_id)
        assert lease is not None
        return lease

    def get(self, project_id: str) -> ProjectLeaseState | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sandbox_leases WHERE project_id = ?", (project_id,)
            ).fetchone()
        return self._row_to_state(row) if row is not None else None

    def list(self) -> list[ProjectLeaseState]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sandbox_leases ORDER BY last_activity_at DESC"
            ).fetchall()
        return [self._row_to_state(row) for row in rows]

    def update_state(
        self,
        project_id: str,
        *,
        state: str | None = None,
        desired_state: str | None = None,
    ) -> None:
        sets: list[str] = []
        params: list[object] = []
        if state is not None:
            sets.append("sandbox_state = ?")
            params.append(state)
        if desired_state is not None:
            sets.append("sandbox_desired_state = ?")
            params.append(desired_state)
        if not sets:
            return
        params.append(project_id)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE sandbox_leases SET {', '.join(sets)} WHERE project_id = ?",
                params,
            )

    def update_metadata(
        self,
        project_id: str,
        *,
        sandbox_id: str | None = None,
        sandbox_kind: str | None = None,
        materialized_revision: str | None = None,
        node: str | None = None,
        metadata_json: str | None = None,
    ) -> ProjectLeaseState:
        values = {
            "sandbox_id": sandbox_id,
            "sandbox_kind": sandbox_kind,
            "materialized_revision": materialized_revision,
            "node": node,
            "metadata_json": metadata_json,
        }
        sets = [f"{name} = ?" for name, value in values.items() if value is not None]
        params: list[object] = [value for value in values.values() if value is not None]
        if sets:
            params.append(project_id)
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE sandbox_leases SET {', '.join(sets)} WHERE project_id = ?",
                    params,
                )
        lease = self.get(project_id)
        if lease is None:
            raise KeyError(project_id)
        return lease

    def clear_sandbox(self, project_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sandbox_leases SET sandbox_id = NULL WHERE project_id = ?",
                (project_id,),
            )

    def update_snapshot(self, project_id: str, snapshot_id: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sandbox_leases SET snapshot_id = ? WHERE project_id = ?",
                (snapshot_id, project_id),
            )

    def touch_activity(self, project_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sandbox_leases SET last_activity_at = ? WHERE project_id = ?",
                (_now(), project_id),
            )

    def last_activity_timestamp(self, project_id: str) -> float | None:
        lease = self.get(project_id)
        if lease is None or lease.last_activity_at is None:
            return None
        try:
            return datetime.fromisoformat(lease.last_activity_at).timestamp()
        except ValueError:
            return None

    @staticmethod
    def _row_to_state(row: sqlite3.Row) -> ProjectLeaseState:
        return ProjectLeaseState(
            project_id=row["project_id"],
            sandbox_id=row["sandbox_id"],
            sandbox_kind=row["sandbox_kind"],
            sandbox_state=row["sandbox_state"],
            sandbox_desired_state=row["sandbox_desired_state"],
            snapshot_id=row["snapshot_id"],
            materialized_revision=row["materialized_revision"],
            node=row["node"],
            last_activity_at=row["last_activity_at"],
            metadata_json=row["metadata_json"],
        )
