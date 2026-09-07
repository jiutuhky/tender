"""ProjectStore — 项目实体持久化(与 sessions 共用同一 sqlite 文件,独立表)。"""

from __future__ import annotations

import os
import sqlite3
import time
import uuid
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

# status 为开放字符串(产品侧可经 PATCH 写入 parsing/parsed 等阶段值);
# 仅两个保留值有后端语义:active 默认态、deleted 软删态。
PROJECT_STATUS_ACTIVE = "active"
PROJECT_STATUS_DELETED = "deleted"


@dataclass(frozen=True)
class ProjectState:
    id: str
    name: str
    status: str
    created_at: float
    updated_at: float
    metadata_json: str | None = None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata_json TEXT
)
"""

# 预留:未来加列时按 sessions._MIGRATION_COLUMNS 的模式追加。
_MIGRATION_COLUMNS: tuple[tuple[str, str], ...] = ()


class ProjectStore:
    def __init__(self, db_path: Path | str):
        self._db_path = str(db_path)
        with closing(self._connect()) as conn, conn:
            conn.execute(_SCHEMA)
            self._migrate(conn)

    def _migrate(self, conn) -> None:
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(projects)").fetchall()}
        for column_name, ddl in _MIGRATION_COLUMNS:
            if column_name not in existing:
                conn.execute(f"ALTER TABLE projects ADD COLUMN {column_name} {ddl}")

    def _connect(self) -> sqlite3.Connection:
        # New connection per call — sqlite3.Connection isn't safe to share across
        # FastAPI threadpool workers (check_same_thread=True by default).
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, name: str, *, metadata_json: str | None = None) -> ProjectState:
        pid = uuid.uuid4().hex[:16]
        now = time.time()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO projects (id, name, status, created_at, updated_at, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (pid, name, PROJECT_STATUS_ACTIVE, now, now, metadata_json),
            )
        return ProjectState(
            id=pid,
            name=name,
            status=PROJECT_STATUS_ACTIVE,
            created_at=now,
            updated_at=now,
            metadata_json=metadata_json,
        )

    def get(self, pid: str) -> ProjectState | None:
        with closing(self._connect()) as conn, conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        if row is None:
            return None
        return self._row_to_state(row)

    def list(self, *, include_deleted: bool = False) -> list[ProjectState]:
        with closing(self._connect()) as conn, conn:
            if include_deleted:
                rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM projects WHERE status != ? ORDER BY updated_at DESC",
                    (PROJECT_STATUS_DELETED,),
                ).fetchall()
        return [self._row_to_state(r) for r in rows]

    def update(
        self,
        pid: str,
        *,
        name: str | None = None,
        status: str | None = None,
        metadata_json: str | None = None,
    ) -> ProjectState:
        """按传入字段更新(None 表示不动;metadata_json 为整体替换),并 bump updated_at。"""
        sets: list[str] = []
        params: list[object] = []
        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if status is not None:
            sets.append("status = ?")
            params.append(status)
        if metadata_json is not None:
            sets.append("metadata_json = ?")
            params.append(metadata_json)
        if sets:
            sets.append("updated_at = ?")
            params.append(time.time())
            params.append(pid)
            with closing(self._connect()) as conn, conn:
                conn.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id = ?", params)
        state = self.get(pid)
        if state is None:
            raise KeyError(pid)
        return state

    def delete(self, pid: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE projects SET status = ?, updated_at = ? WHERE id = ?",
                (PROJECT_STATUS_DELETED, time.time(), pid),
            )

    def rollback_create(self, pid: str) -> None:
        """回滚尚未对外成功的创建；用户发起的删除始终走软删。"""
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (pid,))

    def touch(self, pid: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE projects SET updated_at = ? WHERE id = ?",
                (time.time(), pid),
            )

    @staticmethod
    def _row_to_state(row) -> ProjectState:
        return ProjectState(
            id=row["id"],
            name=row["name"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata_json=row["metadata_json"],
        )


# —— 单例接线 ——
# 放在本模块(而非 routers/)是刻意的:routers/sessions.py 与 routers/projects.py
# 都要拿 ProjectStore,放任一 router 内都会形成互相 import 的环。
_PROJECT_STORE: ProjectStore | None = None


def set_project_store(store: ProjectStore | None) -> None:
    global _PROJECT_STORE
    _PROJECT_STORE = store


def get_project_store() -> ProjectStore:
    global _PROJECT_STORE
    if _PROJECT_STORE is None:
        # 兜底路径镜像 routers/sessions.get_store():app 装配未跑时(测试/早期 import)
        # 按同一环境变量约定自建。
        db_path = os.environ.get("HAGENT_DB_PATH", "/tmp/hagent/hagent.sqlite")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _PROJECT_STORE = ProjectStore(db_path)
    return _PROJECT_STORE
