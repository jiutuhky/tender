"""数据库高频访问必须及时关闭连接，不能依赖循环垃圾回收释放句柄。"""

import gc
import os
import sqlite3
from pathlib import Path

import pytest

from hagent.sandbox.smolvm.audit import SandboxEventStore
from hagent.server.leases import LeaseStore
from hagent.server.projects import ProjectStore
from hagent.server.runs import RunStore
from hagent.server.sessions import SessionStore


@pytest.mark.skipif(not Path("/proc/self/fd").exists(), reason="需要 Linux 文件句柄统计")
@pytest.mark.parametrize(
    ("store_type", "read"),
    [
        (ProjectStore, lambda store: store.get("不存在")),
        (SessionStore, lambda store: store.get("不存在")),
        (LeaseStore, lambda store: store.get("不存在")),
        (RunStore, lambda store: store.active_for_project("不存在")),
        (SandboxEventStore, lambda store: store.list(project_id="不存在")),
    ],
)
def test_repeated_queries_do_not_accumulate_handles(tmp_path, store_type, read):
    db_path = tmp_path / "sessions.db"
    # 复现线上共用 WAL 数据库时，每个连接同时占用数据库和 WAL 句柄的情况。
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    finally:
        conn.close()
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        before = len(os.listdir("/proc/self/fd"))
        store = store_type(db_path)
        for _ in range(300):
            read(store)
        assert len(os.listdir("/proc/self/fd")) <= before + 2
    finally:
        if was_enabled:
            gc.enable()
        gc.collect()


def test_failed_write_closes_connection_and_preserves_existing_data(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / "sessions.db")
    project = store.create("已保存项目")
    connections = []
    original_connect = store._connect

    def capture_connection():
        conn = original_connect()
        connections.append(conn)
        return conn

    monkeypatch.setattr(store, "_connect", capture_connection)
    with pytest.raises(sqlite3.IntegrityError):
        store.create(None)
    for conn in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn.execute("SELECT 1")
    assert store.get(project.id).name == "已保存项目"
    assert len(store.list()) == 1
