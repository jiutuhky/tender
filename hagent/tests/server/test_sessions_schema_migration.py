from __future__ import annotations

import sqlite3
from pathlib import Path

from hagent.server.sessions import SessionStore


def test_sessions_schema_keeps_only_conversation_state_and_requires_project(tmp_path: Path):
    db = tmp_path / "sessions.db"
    SessionStore(db)

    with sqlite3.connect(db) as conn:
        columns = {
            row[1]: {"type": row[2], "not_null": bool(row[3])}
            for row in conn.execute("PRAGMA table_info(sessions)")
        }

    assert set(columns) == {
        "id",
        "project_id",
        "status",
        "created_at",
        "last_active",
    }
    assert columns["project_id"]["not_null"] is True


def test_legacy_session_rows_are_dropped_by_breaking_migration(tmp_path: Path):
    db = tmp_path / "legacy.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE sessions ("
            "id TEXT PRIMARY KEY, workspace_dir TEXT, status TEXT, "
            "created_at REAL, last_active REAL, project_id TEXT, sandbox_id TEXT)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES "
            "('old', '/tmp/old', 'active', 0, 0, 'project-old', 'vm-old')"
        )

    store = SessionStore(db)

    assert store.get("old") is None
    created = store.create(project_id="project-new")
    assert created.project_id == "project-new"
