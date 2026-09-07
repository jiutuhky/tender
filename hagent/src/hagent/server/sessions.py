"""会话持久化。

会话只承载对话；项目工作区与沙箱生命周期状态刻意放在表外。
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from contextlib import closing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from hagent.server.leases import SandboxState


class SessionStatus(str, Enum):
    ACTIVE = "active"
    ENDED = "ended"


@dataclass(frozen=True)
class SessionState:
    id: str
    project_id: str
    status: SessionStatus
    created_at: float
    last_active: float


_SCHEMA = """
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    last_active REAL NOT NULL
)
"""

_EXPECTED_COLUMNS = {"id", "project_id", "status", "created_at", "last_active"}


class SessionStore:
    def __init__(self, db_path: Path | str):
        self._db_path = str(db_path)
        with closing(self._connect()) as conn, conn:
            self._ensure_schema(conn)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id)"
            )

    @staticmethod
    def _ensure_schema(conn: sqlite3.Connection) -> None:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sessions'"
        ).fetchone()
        if exists is not None:
            columns = conn.execute("PRAGMA table_info(sessions)").fetchall()
            names = {row[1] for row in columns}
            project_column = next((row for row in columns if row[1] == "project_id"), None)
            project_required = project_column is not None and bool(project_column[3])
            if names != _EXPECTED_COLUMNS or not project_required:
                # 开发阶段采用破坏性迁移：旧记录的工作区与沙箱归属语义已失效，
                # 因而不向前迁移。
                conn.execute("DROP TABLE sessions")
        conn.execute(_SCHEMA.replace("CREATE TABLE sessions", "CREATE TABLE IF NOT EXISTS sessions"))

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, *, project_id: str) -> SessionState:
        if not project_id:
            raise ValueError("project_id is required")
        sid = uuid.uuid4().hex[:16]
        now = time.time()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO sessions (id, project_id, status, created_at, last_active) "
                "VALUES (?, ?, ?, ?, ?)",
                (sid, project_id, SessionStatus.ACTIVE.value, now, now),
            )
        return SessionState(
            id=sid,
            project_id=project_id,
            status=SessionStatus.ACTIVE,
            created_at=now,
            last_active=now,
        )

    def get(self, sid: str) -> SessionState | None:
        with closing(self._connect()) as conn, conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        return self._row_to_state(row) if row is not None else None

    def list(self, *, project_id: str | None = None) -> list[SessionState]:
        with closing(self._connect()) as conn, conn:
            if project_id is None:
                rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE project_id = ? ORDER BY created_at DESC",
                    (project_id,),
                ).fetchall()
        return [self._row_to_state(row) for row in rows]

    def latest_per_project(self) -> dict[str, SessionState]:
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                "SELECT *, MAX(created_at) FROM sessions GROUP BY project_id"
            ).fetchall()
        return {row["project_id"]: self._row_to_state(row) for row in rows}

    def delete(self, sid: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE sessions SET status = ? WHERE id = ?",
                (SessionStatus.ENDED.value, sid),
            )

    def touch(self, sid: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE sessions SET last_active = ? WHERE id = ?",
                (time.time(), sid),
            )

    @staticmethod
    def _row_to_state(row: sqlite3.Row) -> SessionState:
        return SessionState(
            id=row["id"],
            project_id=row["project_id"],
            status=SessionStatus(row["status"]),
            created_at=row["created_at"],
            last_active=row["last_active"],
        )
