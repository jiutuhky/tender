"""对象库表访问层（与 SessionStore 共用同一 SQLite 文件，独立五表）。

纪律：本文件是对象表 SQL 的唯一居所；写方法只允许 service.py 调用——
REST / MCP adapter 及其他模块一律经由服务层，禁止旁路直写
（tests/assets/test_audit_and_no_bypass.py 静态守护此约定）。
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from hagent.assets.model import AssetEvent, DocumentRecord, MatrixItem, MatrixStats

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id             TEXT PRIMARY KEY,
    project_id     TEXT NOT NULL,
    path           TEXT NOT NULL,
    sha256         TEXT NOT NULL,
    doc_type       TEXT,
    registered_at  TEXT NOT NULL,
    -- 原件与预览版按内容寻址存在 workspace 之外（hagent.ingest.blobs）；
    -- 二者为空即该文档没有 PDF 原件（历史项目、开发期 .md 语料），溯源走 md 降级
    origin_sha256  TEXT,
    preview_sha256 TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_project_sha
    ON documents(project_id, sha256);

CREATE TABLE IF NOT EXISTS matrices (
    project_id      TEXT NOT NULL,
    matrix_type     TEXT NOT NULL,
    state           TEXT NOT NULL,
    meta_json       TEXT NOT NULL,
    draft_meta_json TEXT,
    current_rev     INTEGER NOT NULL DEFAULT 0,
    updated_at      TEXT NOT NULL,
    PRIMARY KEY (project_id, matrix_type)
);

CREATE TABLE IF NOT EXISTS matrix_items (
    project_id      TEXT NOT NULL,
    matrix_type     TEXT NOT NULL,
    stage           TEXT NOT NULL,
    item_id         TEXT NOT NULL,
    section         TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    response_status TEXT,
    response_note   TEXT,
    confirmed       INTEGER NOT NULL DEFAULT 0,
    version         INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (project_id, matrix_type, stage, item_id)
);

CREATE TABLE IF NOT EXISTS matrix_revisions (
    project_id    TEXT NOT NULL,
    matrix_type   TEXT NOT NULL,
    rev           INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    published_at  TEXT NOT NULL,
    actor         TEXT NOT NULL,
    PRIMARY KEY (project_id, matrix_type, rev)
);

CREATE TABLE IF NOT EXISTS asset_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL,
    ts          TEXT NOT NULL,
    actor_kind  TEXT NOT NULL,
    actor_ref   TEXT,
    action      TEXT NOT NULL,
    target      TEXT NOT NULL,
    before_json TEXT,
    after_json  TEXT,
    reason      TEXT
);
CREATE INDEX IF NOT EXISTS idx_asset_events_project ON asset_events(project_id, id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# 校验/门禁/投影需要全量注册文档；项目源文件数量级远低于此上限
DOCUMENTS_FETCH_LIMIT = 10_000


def deep_merge(base: dict, patch: dict) -> dict:
    """dict 递归深合并；列表与标量整体替换（set_matrix_meta 与投影拼装共用语义）。"""
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _dumps(value: dict | list | None) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False)


def _loads(raw: str | None) -> dict | None:
    return None if raw is None else json.loads(raw)


class AssetStore:
    def __init__(self, db_path: Path | str):
        self._db_path = str(db_path)
        with self.transaction() as conn:
            # WAL：server 进程与 stdio MCP 子进程共享同一文件（spec §6），
            # 回滚日志模式下并发读写互斥面太大
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)
            self._migrate(conn)

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """增量补列：已有对象库不重建，缺的列补空——旧文档就是「没有 PDF 原件」。"""
        existing = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
        for column in ("origin_sha256", "preview_sha256"):
            if column not in existing:
                conn.execute(f"ALTER TABLE documents ADD COLUMN {column} TEXT")

    def _connect(self) -> sqlite3.Connection:
        # 每次调用新建连接：sqlite3.Connection 不能跨 FastAPI threadpool 线程共享
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """单事务边界：正常退出提交，异常整体回滚（publish 原子性依赖于此）。"""
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    # —— documents ——

    def get_document_by_sha(
        self, conn: sqlite3.Connection, project_id: str, sha256: str
    ) -> DocumentRecord | None:
        row = conn.execute(
            "SELECT * FROM documents WHERE project_id = ? AND sha256 = ?",
            (project_id, sha256),
        ).fetchone()
        return self._row_to_document(row) if row is not None else None

    def document_id_exists(self, conn: sqlite3.Connection, doc_id: str) -> bool:
        return (
            conn.execute("SELECT 1 FROM documents WHERE id = ?", (doc_id,)).fetchone() is not None
        )

    def insert_document(
        self,
        conn: sqlite3.Connection,
        *,
        doc_id: str,
        project_id: str,
        path: str,
        sha256: str,
        doc_type: str | None,
        registered_at: str,
    ) -> None:
        conn.execute(
            "INSERT INTO documents (id, project_id, path, sha256, doc_type, registered_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (doc_id, project_id, path, sha256, doc_type, registered_at),
        )

    def get_document(self, conn: sqlite3.Connection, doc_id: str) -> DocumentRecord | None:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return self._row_to_document(row) if row is not None else None

    def set_document_blobs(
        self,
        conn: sqlite3.Connection,
        *,
        doc_id: str,
        origin_sha256: str | None,
        preview_sha256: str | None,
    ) -> None:
        conn.execute(
            "UPDATE documents SET origin_sha256 = ?, preview_sha256 = ? WHERE id = ?",
            (origin_sha256, preview_sha256, doc_id),
        )

    def list_documents(
        self, conn: sqlite3.Connection, project_id: str, *, limit: int, offset: int
    ) -> tuple[list[DocumentRecord], int]:
        total = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE project_id = ?", (project_id,)
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM documents WHERE project_id = ? ORDER BY registered_at, id LIMIT ? OFFSET ?",
            (project_id, limit, offset),
        ).fetchall()
        return [self._row_to_document(r) for r in rows], total

    # —— matrices ——

    def get_matrix(
        self, conn: sqlite3.Connection, project_id: str, matrix_type: str
    ) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT * FROM matrices WHERE project_id = ? AND matrix_type = ?",
            (project_id, matrix_type),
        ).fetchone()

    def insert_matrix(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        matrix_type: str,
        state: str,
        meta: dict,
        draft_meta: dict | None,
    ) -> None:
        conn.execute(
            "INSERT INTO matrices (project_id, matrix_type, state, meta_json, draft_meta_json, "
            "current_rev, updated_at) VALUES (?, ?, ?, ?, ?, 0, ?)",
            (project_id, matrix_type, state, _dumps(meta), _dumps(draft_meta), now_iso()),
        )

    def update_matrix(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        matrix_type: str,
        *,
        state: str | None = None,
        meta: dict | None = None,
        draft_meta: dict | None = None,
        clear_draft_meta: bool = False,
        current_rev: int | None = None,
    ) -> None:
        sets: list[str] = ["updated_at = ?"]
        params: list[object] = [now_iso()]
        if state is not None:
            sets.append("state = ?")
            params.append(state)
        if meta is not None:
            sets.append("meta_json = ?")
            params.append(_dumps(meta))
        if draft_meta is not None:
            sets.append("draft_meta_json = ?")
            params.append(_dumps(draft_meta))
        elif clear_draft_meta:
            sets.append("draft_meta_json = NULL")
        if current_rev is not None:
            sets.append("current_rev = ?")
            params.append(current_rev)
        params.extend([project_id, matrix_type])
        conn.execute(
            f"UPDATE matrices SET {', '.join(sets)} WHERE project_id = ? AND matrix_type = ?",
            params,
        )

    # —— matrix_items ——

    def get_item(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        matrix_type: str,
        stage: str,
        item_id: str,
    ) -> MatrixItem | None:
        row = conn.execute(
            "SELECT * FROM matrix_items WHERE project_id = ? AND matrix_type = ? "
            "AND stage = ? AND item_id = ?",
            (project_id, matrix_type, stage, item_id),
        ).fetchone()
        return self._row_to_item(row) if row is not None else None

    def insert_item(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        matrix_type: str,
        stage: str,
        item_id: str,
        section: str,
        payload: dict,
        response_status: str | None = None,
        response_note: str | None = None,
        confirmed: bool = False,
        version: int = 1,
    ) -> None:
        conn.execute(
            "INSERT INTO matrix_items (project_id, matrix_type, stage, item_id, section, "
            "payload_json, response_status, response_note, confirmed, version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_id,
                matrix_type,
                stage,
                item_id,
                section,
                _dumps(payload),
                response_status,
                response_note,
                1 if confirmed else 0,
                version,
            ),
        )

    def update_item_row(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        matrix_type: str,
        stage: str,
        item_id: str,
        *,
        expected_version: int,
        payload: dict | None = None,
        response_status: str | None = None,
        clear_response_status: bool = False,
        response_note: str | None = None,
        confirmed: bool | None = None,
    ) -> bool:
        """带 version 守卫的行更新：命中则 version+1，返回是否命中。"""
        sets: list[str] = ["version = version + 1"]
        params: list[object] = []
        if payload is not None:
            sets.append("payload_json = ?")
            params.append(_dumps(payload))
        if response_status is not None:
            sets.append("response_status = ?")
            params.append(response_status)
        elif clear_response_status:
            sets.append("response_status = NULL")
        if response_note is not None:
            sets.append("response_note = ?")
            params.append(response_note)
        if confirmed is not None:
            sets.append("confirmed = ?")
            params.append(1 if confirmed else 0)
        params.extend([project_id, matrix_type, stage, item_id, expected_version])
        cursor = conn.execute(
            f"UPDATE matrix_items SET {', '.join(sets)} WHERE project_id = ? AND matrix_type = ? "
            "AND stage = ? AND item_id = ? AND version = ?",
            params,
        )
        return cursor.rowcount == 1

    def delete_item(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        matrix_type: str,
        stage: str,
        item_id: str,
    ) -> None:
        conn.execute(
            "DELETE FROM matrix_items WHERE project_id = ? AND matrix_type = ? "
            "AND stage = ? AND item_id = ?",
            (project_id, matrix_type, stage, item_id),
        )

    def list_items(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        matrix_type: str,
        stage: str,
        *,
        section: str | None = None,
        response_status: str | None = None,
        confirmed: bool | None = None,
        category: str | None = None,
        mandatory: bool | None = None,
        keyword: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[MatrixItem], int]:
        where = ["project_id = ?", "matrix_type = ?", "stage = ?"]
        params: list[object] = [project_id, matrix_type, stage]
        if section is not None:
            where.append("section = ?")
            params.append(section)
        if response_status is not None:
            where.append("response_status = ?")
            params.append(response_status)
        if confirmed is not None:
            where.append("confirmed = ?")
            params.append(1 if confirmed else 0)
        if category is not None:
            where.append("json_extract(payload_json, '$.category') = ?")
            params.append(category)
        if mandatory is not None:
            where.append("json_extract(payload_json, '$.mandatory') = ?")
            params.append(1 if mandatory else 0)
        if keyword is not None:
            # payload_json 以 ensure_ascii=False 存储，中文关键词可直接子串匹配
            where.append("instr(payload_json, ?) > 0")
            params.append(keyword)
        clause = " AND ".join(where)
        total = conn.execute(
            f"SELECT COUNT(*) FROM matrix_items WHERE {clause}", params
        ).fetchone()[0]
        sql = f"SELECT * FROM matrix_items WHERE {clause} ORDER BY section, item_id"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_item(r) for r in rows], total

    def count_items(
        self, conn: sqlite3.Connection, project_id: str, matrix_type: str, stage: str
    ) -> int:
        return conn.execute(
            "SELECT COUNT(*) FROM matrix_items WHERE project_id = ? AND matrix_type = ? "
            "AND stage = ?",
            (project_id, matrix_type, stage),
        ).fetchone()[0]

    def item_stats(
        self, conn: sqlite3.Connection, project_id: str, matrix_type: str, stage: str
    ) -> MatrixStats:
        """分组统计：区段计数 + items 区段的应答状态 / 确认 / 强制性 / 类别计数。"""
        base = (project_id, matrix_type, stage)
        by_section = dict(
            conn.execute(
                "SELECT section, COUNT(*) FROM matrix_items "
                "WHERE project_id = ? AND matrix_type = ? AND stage = ? GROUP BY section",
                base,
            ).fetchall()
        )
        by_response_status = dict(
            conn.execute(
                "SELECT COALESCE(response_status, 'unset'), COUNT(*) FROM matrix_items "
                "WHERE project_id = ? AND matrix_type = ? AND stage = ? AND section = 'items' "
                "GROUP BY 1",
                base,
            ).fetchall()
        )
        confirmed_count, mandatory_count = conn.execute(
            "SELECT COALESCE(SUM(confirmed), 0), "
            "COALESCE(SUM(json_extract(payload_json, '$.mandatory') = 1), 0) "
            "FROM matrix_items WHERE project_id = ? AND matrix_type = ? AND stage = ? "
            "AND section = 'items'",
            base,
        ).fetchone()
        by_category = dict(
            conn.execute(
                "SELECT COALESCE(json_extract(payload_json, '$.category'), 'unset'), COUNT(*) "
                "FROM matrix_items WHERE project_id = ? AND matrix_type = ? AND stage = ? "
                "AND section = 'items' GROUP BY 1",
                base,
            ).fetchall()
        )
        return MatrixStats(
            stage=stage,
            total=sum(by_section.values()),
            by_section=by_section,
            by_response_status=by_response_status,
            confirmed_count=confirmed_count,
            mandatory_count=mandatory_count,
            by_category=by_category,
        )

    def delete_stage(
        self, conn: sqlite3.Connection, project_id: str, matrix_type: str, stage: str
    ) -> None:
        conn.execute(
            "DELETE FROM matrix_items WHERE project_id = ? AND matrix_type = ? AND stage = ?",
            (project_id, matrix_type, stage),
        )

    def promote_draft_items(
        self, conn: sqlite3.Connection, project_id: str, matrix_type: str
    ) -> None:
        """draft 晋升 current（调用方须先清空 current，避免主键冲突）。"""
        conn.execute(
            "UPDATE matrix_items SET stage = 'current' WHERE project_id = ? "
            "AND matrix_type = ? AND stage = 'draft'",
            (project_id, matrix_type),
        )

    # —— matrix_revisions ——

    def insert_revision(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        matrix_type: str,
        rev: int,
        snapshot: dict,
        published_at: str,
        actor: str,
    ) -> None:
        conn.execute(
            "INSERT INTO matrix_revisions (project_id, matrix_type, rev, snapshot_json, "
            "published_at, actor) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, matrix_type, rev, _dumps(snapshot), published_at, actor),
        )

    def get_revision(
        self, conn: sqlite3.Connection, project_id: str, matrix_type: str, rev: int
    ) -> dict | None:
        row = conn.execute(
            "SELECT snapshot_json FROM matrix_revisions WHERE project_id = ? "
            "AND matrix_type = ? AND rev = ?",
            (project_id, matrix_type, rev),
        ).fetchone()
        return _loads(row["snapshot_json"]) if row is not None else None

    def list_revisions(
        self, conn: sqlite3.Connection, project_id: str, matrix_type: str
    ) -> list[sqlite3.Row]:
        return conn.execute(
            "SELECT project_id, matrix_type, rev, published_at, actor FROM matrix_revisions "
            "WHERE project_id = ? AND matrix_type = ? ORDER BY rev",
            (project_id, matrix_type),
        ).fetchall()

    # —— asset_events ——

    def append_event(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        actor_kind: str,
        actor_ref: str | None,
        action: str,
        target: str,
        before: dict | None = None,
        after: dict | None = None,
        reason: str | None = None,
    ) -> None:
        conn.execute(
            "INSERT INTO asset_events (project_id, ts, actor_kind, actor_ref, action, target, "
            "before_json, after_json, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_id,
                now_iso(),
                actor_kind,
                actor_ref,
                action,
                target,
                _dumps(before),
                _dumps(after),
                reason,
            ),
        )

    def list_events(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        *,
        target: str | None = None,
        action: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[AssetEvent]:
        where = ["project_id = ?"]
        params: list[object] = [project_id]
        if target is not None:
            where.append("target = ?")
            params.append(target)
        if action is not None:
            where.append("action = ?")
            params.append(action)
        sql = f"SELECT * FROM asset_events WHERE {' AND '.join(where)} ORDER BY id"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def last_event(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        *,
        action: str,
        target: str,
    ) -> AssetEvent | None:
        row = conn.execute(
            "SELECT * FROM asset_events WHERE project_id = ? AND action = ? AND target = ? "
            "ORDER BY id DESC LIMIT 1",
            (project_id, action, target),
        ).fetchone()
        return self._row_to_event(row) if row is not None else None

    # —— row mappers ——

    @staticmethod
    def _row_to_document(row: sqlite3.Row) -> DocumentRecord:
        return DocumentRecord(
            id=row["id"],
            project_id=row["project_id"],
            path=row["path"],
            sha256=row["sha256"],
            doc_type=row["doc_type"],
            registered_at=row["registered_at"],
            origin_sha256=row["origin_sha256"],
            preview_sha256=row["preview_sha256"],
            created=False,
        )

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> MatrixItem:
        return MatrixItem(
            project_id=row["project_id"],
            matrix_type=row["matrix_type"],
            stage=row["stage"],
            item_id=row["item_id"],
            section=row["section"],
            payload=json.loads(row["payload_json"]),
            response_status=row["response_status"],
            response_note=row["response_note"],
            confirmed=bool(row["confirmed"]),
            version=row["version"],
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> AssetEvent:
        return AssetEvent(
            id=row["id"],
            project_id=row["project_id"],
            ts=row["ts"],
            actor_kind=row["actor_kind"],
            actor_ref=row["actor_ref"],
            action=row["action"],
            target=row["target"],
            before=_loads(row["before_json"]),
            after=_loads(row["after_json"]),
            reason=row["reason"],
        )
