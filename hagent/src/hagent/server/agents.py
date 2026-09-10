from __future__ import annotations

import asyncio
import os
import sqlite3
from pathlib import Path
from typing import Any

from deepagents.backends import FilesystemBackend
from langgraph.checkpoint.sqlite import SqliteSaver

from hagent.core import create_hagent
from hagent.mcp_tools import prose_http_connection, prose_mcp_disabled

class AsyncCompatibleSqliteSaver(SqliteSaver):
    """共用现有线程数据库和锁，让 Web 异步图与同步历史读取保持一致。"""

    async def aget_tuple(self, config):
        return await asyncio.to_thread(self.get_tuple, config)

    async def aput(self, config, checkpoint, metadata, new_versions):
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        return await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        rows = await asyncio.to_thread(lambda: list(self.list(config, filter=filter, before=before, limit=limit)))
        for row in rows:
            yield row

    async def adelete_thread(self, thread_id):
        await asyncio.to_thread(self.delete_thread, thread_id)


_agents: dict[str, Any] = {}
_checkpointer: SqliteSaver | None = None
_checkpointer_conn: sqlite3.Connection | None = None


def get_checkpointer() -> SqliteSaver:
    """Return a process-wide SqliteSaver.

    `SqliteSaver.from_conn_string` is a contextmanager and can't be used as a
    long-lived global; we open a sqlite3.Connection ourselves (with
    `check_same_thread=False` for FastAPI thread pool reuse) and hand it to
    SqliteSaver directly.
    """
    global _checkpointer, _checkpointer_conn
    if _checkpointer is None:
        db = Path(os.environ.get("HAGENT_THREAD_DB_PATH", "/tmp/hagent/threads.sqlite"))
        db.parent.mkdir(parents=True, exist_ok=True)
        _checkpointer_conn = sqlite3.connect(str(db), check_same_thread=False)
        _checkpointer = AsyncCompatibleSqliteSaver(_checkpointer_conn)
        if hasattr(_checkpointer, "setup"):
            _checkpointer.setup()
    return _checkpointer


def get_or_build_agent(
    session_id: str,
    workspace_dir: str,
    *,
    project_id: str | None = None,
    sandbox: Any | None = None,
) -> Any:
    if session_id not in _agents:
        from hagent.server.hooks_registry import get_or_build_hook_runner

        hook_runner = get_or_build_hook_runner(session_id, workspace_dir)
        # prose MCP 工具面（票 04）：server 模式 loopback 连自家 /mcp；agent
        # 按 session 缓存，run 归属取 session 粒度（header 随连接配置固定）。
        # project_id 同样由 server 绑进 header：sandbox 里的 agent 只看得见
        # /workspace，无从得知自己的 hagent project_id——不绑定它就只能猜
        # （2026-07-13 事故：猜成了招标文件正文里的项目编号）。
        mcp_connection = (
            None
            if prose_mcp_disabled()
            else prose_http_connection(
                actor_ref=f"session:{session_id}", project_id=project_id
            )
        )
        if sandbox is not None:
            # Sandbox path: hand the LIVE sandbox instance (held by SessionManager
            # via SandboxPool.acquire) to create_hagent so core.py wires bash/file
            # tools to the same container — and crucially does NOT auto-start a
            # second one based on env HAGENT_SANDBOX_KIND.
            _agents[session_id] = create_hagent(
                sandbox=sandbox,
                checkpointer=get_checkpointer(),
                task_list_id=session_id,
                hook_runner=hook_runner,
                mcp_connection=mcp_connection,
            )
        else:
            backend = FilesystemBackend(root_dir=workspace_dir, virtual_mode=False)
            _agents[session_id] = create_hagent(
                backend=backend,
                checkpointer=get_checkpointer(),
                task_list_id=session_id,
                hook_runner=hook_runner,
                mcp_connection=mcp_connection,
            )
    return _agents[session_id]


def close_agent(session_id: str) -> None:
    agent = _agents.pop(session_id, None)
    if agent is None:
        return
    runtime = getattr(agent, "_hagent_bash_runtime", None)
    close = getattr(runtime, "close", None)
    if callable(close):
        close()
