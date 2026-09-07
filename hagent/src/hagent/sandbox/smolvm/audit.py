"""审计与事件(spec §4.5 / D11):命令审计 JSONL + 生命周期事件表。

三流之二(VM 运行日志复用 SDK 的 ``data_dir/{vm_id}.log``,不在此处):
- ``CommandAuditLog``:宿主侧命令审计,append-only JSONL,按 sid 分文件;
  审计记在 provider 调用点而非 SDK callback(F4:async 路径 callback 不触发)。
- ``SandboxEventStore``:生命周期事件落 hagent SQLite(与 sessions 同库分表)。
- ``SandboxAuditor``:埋点门面,**永远 best-effort** —— 审计失败只告警,
  不得影响 execute/upload/download 主链路。
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_AUDIT_DIR = ".logs/sandbox"

# 事件枚举(spec §4.5);metrics 为 Phase B4 的资源采样行
SANDBOX_EVENT_KINDS = frozenset(
    {
        "created",
        "adopted",
        "paused",
        "resumed",
        "evicted",
        "orphaned",
        "health_fail",
        "reaped",
        "create_failed",
        "metrics",
        "snapshotted",
        "restored",
        "restore_failed",
    }
)


class CommandAuditLog:
    """命令审计 JSONL:``<root>/audit-<sid>.jsonl``,append-only。

    session 未绑定(warm 池预热的 VM)时回落 vm_id 命名,归属仍可追。
    """

    def __init__(self, root: Path | str | None = None) -> None:
        self._root = Path(
            root or os.environ.get("HAGENT_SANDBOX_AUDIT_DIR", "").strip() or DEFAULT_AUDIT_DIR
        )
        self._lock = threading.Lock()

    def record(
        self,
        *,
        project_id: str | None,
        vm_id: str | None,
        action: str,
        command: str | None = None,
        path: str | None = None,
        exit_code: int | None = None,
        duration_ms: int | None = None,
        bytes_out: int | None = None,
        error: str | None = None,
    ) -> None:
        record: dict[str, object] = {
            "ts": time.time(),
            "project_id": project_id,
            "vm_id": vm_id,
            "action": action,
        }
        if command is not None:
            record["command"] = command
        if path is not None:
            record["path"] = path
        if exit_code is not None:
            record["exit_code"] = exit_code
        record["duration_ms"] = duration_ms if duration_ms is not None else 0
        record["bytes_out"] = bytes_out if bytes_out is not None else 0
        if error is not None:
            record["error"] = error
        target = self._root / f"audit-{project_id or vm_id or 'unknown'}.jsonl"
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            self._root.mkdir(parents=True, exist_ok=True)
            with open(target, "a", encoding="utf-8") as f:
                f.write(line + "\n")


@dataclass(frozen=True)
class SandboxEventRow:
    ts: float
    project_id: str | None
    session_id: str | None
    vm_id: str | None
    event: str
    detail: dict | None


_EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS sandbox_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    project_id TEXT,
    session_id TEXT,
    vm_id TEXT,
    event TEXT NOT NULL,
    detail_json TEXT
)
"""


class SandboxEventStore:
    """生命周期事件表(hagent SQLite,与 sessions 同库分表)。"""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = str(db_path)
        with closing(self._connect()) as conn, conn:
            conn.execute(_EVENTS_SCHEMA)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(sandbox_events)")}
            if "project_id" not in columns:
                conn.execute("ALTER TABLE sandbox_events ADD COLUMN project_id TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sandbox_events_project_id "
                "ON sandbox_events(project_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_sandbox_events_session_id "
                "ON sandbox_events(session_id)"
            )

    def _connect(self) -> sqlite3.Connection:
        # 每调一连接:与 SessionStore 同一理由(跨线程共享 Connection 不安全)
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def record(
        self,
        *,
        event: str,
        project_id: str | None = None,
        session_id: str | None = None,
        vm_id: str | None = None,
        detail: dict | None = None,
    ) -> None:
        if event not in SANDBOX_EVENT_KINDS:
            raise ValueError(f"未知 sandbox 事件: {event!r}")
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO sandbox_events "
                "(ts, project_id, session_id, vm_id, event, detail_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    project_id,
                    session_id,
                    vm_id,
                    event,
                    json.dumps(detail, ensure_ascii=False) if detail is not None else None,
                ),
            )

    def list(
        self,
        *,
        project_id: str | None = None,
        session_id: str | None = None,
        event: str | None = None,
        limit: int | None = None,
    ) -> list[SandboxEventRow]:
        clauses: list[str] = []
        params: list[object] = []
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if event is not None:
            clauses.append("event = ?")
            params.append(event)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        # limit 指定时取最近 N 条(倒序,ops 事件尾随);不指定时正序全量(既有语义)
        order = "DESC" if limit is not None else "ASC"
        tail = f" LIMIT {int(limit)}" if limit is not None else ""
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                f"SELECT * FROM sandbox_events{where} ORDER BY id {order}{tail}", params
            ).fetchall()
        return [
            SandboxEventRow(
                ts=row["ts"],
                project_id=row["project_id"],
                session_id=row["session_id"],
                vm_id=row["vm_id"],
                event=row["event"],
                detail=json.loads(row["detail_json"]) if row["detail_json"] else None,
            )
            for row in rows
        ]


class SandboxAuditor:
    """埋点门面:两路 sink 均可缺省;所有失败吞掉只告警(best-effort)。"""

    def __init__(
        self,
        *,
        command_log: CommandAuditLog | None = None,
        event_store: SandboxEventStore | None = None,
    ) -> None:
        self._command_log = command_log
        self._event_store = event_store

    def record_command(self, **kwargs) -> None:
        if self._command_log is None:
            return
        try:
            self._command_log.record(**kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("命令审计写入失败(忽略): %s", exc)

    def record_event(self, **kwargs) -> None:
        if self._event_store is None:
            return
        try:
            self._event_store.record(**kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("sandbox 事件写入失败(忽略): %s", exc)
