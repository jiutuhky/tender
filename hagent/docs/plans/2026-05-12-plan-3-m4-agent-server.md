# Plan 3 — M4 Agent Server (FastAPI + SSE + 文件上传 + thread 持久化)

> **存档说明**：本 plan 产出自已退役的 superpowers 工作流，仅作历史参考；新工作一律走仓根 tickets.md（Matt 契约）。

**Goal**: 在 Plan 2 的 `create_hagent` 之上建一个 FastAPI server，提供 spec §5 列出的全部 REST + SSE 端点：session lifecycle、消息流式、todo / files / interrupt。完成后 `curl_smoke.sh` 可端到端跑通；`tests/test_api_e2e.py` 全过。

**Architecture**:
- 单文件 FastAPI app + 几个 router 模块，无 SQLAlchemy，用 stdlib `sqlite3` 直接做 SessionState 存储；LangGraph thread 状态用 `langgraph-checkpoint-sqlite` 自带 checkpointer
- SSE 不用第三方库（不引入 sse-starlette），写一个 60 行的小适配器把 `agent.stream(...)` 的 LangGraph 事件翻译成 spec §5 表格里的 9 种事件
- 每个 session 一个独立 `LocalShellBackend(root_dir=/tmp/hagent/sessions/<session_id>/workspace)`；文件端点用 Path 操作直接读 host 文件系统（DockerBackend 会在 Plan 5 切换到 backend.upload_files / download_files 协议方法）
- API key auth 用 dependency injection；单租户一把 key，从 `HAGENT_API_KEY` env var 读

**Tech Stack**: fastapi, uvicorn, python-multipart, langgraph-checkpoint-sqlite（thread 持久化）, sqlite3（stdlib，session metadata）, httpx（测试）, pytest-asyncio。

**Spec reference**: §5（HTTP API 表面，全节）、§4 M4、§7（interrupt 端点保留）。

**Depends on**: Plan 2 完成；`create_hagent()` 可用；CLI demo 跑通。

---

### Task 1: 加依赖 + FastAPI app scaffold + /healthz + API key 中间件

**Files:**
- Modify: `pyproject.toml`（追加依赖）
- Create: `src/hagent/server/__init__.py`
- Create: `src/hagent/server/app.py`
- Create: `src/hagent/server/auth.py`
- Create: `tests/server/__init__.py`
- Create: `tests/server/conftest.py`
- Create: `tests/server/test_healthz_auth.py`

- [ ] **Step 1: 更新 pyproject.toml**

在 `dependencies` 数组追加：
```toml
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "python-multipart>=0.0.20",
    "langgraph-checkpoint-sqlite>=2.0",
```

在 `[project.optional-dependencies].dev` 数组追加：
```toml
    "httpx>=0.27",
```

- [ ] **Step 2: 重新安装**

```bash
source .venv/bin/activate && pip install -e ".[dev]"
```

- [ ] **Step 3: 写失败测试 `tests/server/test_healthz_auth.py`**

```python
from fastapi.testclient import TestClient

from hagent.server.app import create_app


def test_healthz_is_public():
    app = create_app()
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_protected_endpoint_requires_auth(monkeypatch):
    monkeypatch.setenv("HAGENT_API_KEY", "secret-key")
    app = create_app()
    client = TestClient(app)
    r = client.get("/sessions")
    assert r.status_code == 401


def test_protected_endpoint_accepts_bearer(monkeypatch):
    monkeypatch.setenv("HAGENT_API_KEY", "secret-key")
    app = create_app()
    client = TestClient(app)
    r = client.get("/sessions", headers={"Authorization": "Bearer secret-key"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_protected_endpoint_rejects_wrong_bearer(monkeypatch):
    monkeypatch.setenv("HAGENT_API_KEY", "secret-key")
    app = create_app()
    client = TestClient(app)
    r = client.get("/sessions", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
```

`tests/server/__init__.py` 和 `tests/server/conftest.py` 都创建为空文件。

- [ ] **Step 4: 跑，验证 FAIL**

```bash
pytest tests/server/test_healthz_auth.py -v
```

- [ ] **Step 5: 写 `src/hagent/server/auth.py`**

```python
from __future__ import annotations

import hmac
import os
import warnings

from fastapi import HTTPException, Request, status

_DEV_MODE_WARNED = False


def require_api_key(request: Request) -> None:
    global _DEV_MODE_WARNED
    expected = os.environ.get("HAGENT_API_KEY")
    if not expected:
        if not _DEV_MODE_WARNED:
            warnings.warn(
                "HAGENT_API_KEY unset — server is unauthenticated (dev mode). "
                "Set HAGENT_API_KEY to require Bearer auth.",
                RuntimeWarning,
                stacklevel=2,
            )
            _DEV_MODE_WARNED = True
        return
    auth = request.headers.get("Authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")
```

> 注：本步骤的 auth.py 已 patch（2026-05-12 code-review 反馈）：bearer scheme case-insensitive (RFC 6750)、hmac.compare_digest 常量时间比较、HAGENT_API_KEY 未设时通过 RuntimeWarning 一次性提示 dev-mode 风险（与 core.py 沙箱降级警告同模式）。

- [ ] **Step 6: 写 `src/hagent/server/__init__.py`**

```python
from hagent.server.app import create_app

__all__ = ["create_app"]
```

- [ ] **Step 7: 写 `src/hagent/server/app.py`** (最小骨架，后续 task 加 router)

```python
from __future__ import annotations

from fastapi import Depends, FastAPI

from hagent.server.auth import require_api_key


def create_app() -> FastAPI:
    app = FastAPI(title="Hagent Agent Server", version="0.0.1")

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    @app.get("/sessions", dependencies=[Depends(require_api_key)])
    def list_sessions() -> list:
        # 真实实现在 Task 3 添加；这里先返回空列表满足 healthz_auth 测试
        return []

    return app
```

- [ ] **Step 8: 跑，验证 PASS**

```bash
pytest tests/server/test_healthz_auth.py -v
```

- [ ] **Step 9: 提交**

```bash
git add pyproject.toml src/hagent/server/ tests/server/
git commit -m "feat(server): add FastAPI app scaffold with healthz and API key auth"
```

---

### Task 2: SessionState 模型 + SQLite session store

**Files:**
- Create: `src/hagent/server/sessions.py`
- Create: `tests/server/test_sessions_store.py`

deepagents/LangGraph 的 thread state 由 `SqliteSaver` 自动管理（在 message endpoint 用）。本任务负责 Hagent 自己的"session metadata"——`SessionState`（id / workspace_dir / status / created_at / last_active）——独立一张 SQLite 表（MVP 阶段单租户无 user_id；多租户场景在 Plan 5+ 补）。

- [ ] **Step 1: 写失败测试 `tests/server/test_sessions_store.py`**

```python
from pathlib import Path

import pytest

from hagent.server.sessions import SessionState, SessionStore, SessionStatus


@pytest.fixture
def store(tmp_path):
    return SessionStore(db_path=tmp_path / "hagent.sqlite")


def test_create_returns_new_session(store, tmp_path):
    s = store.create(workspace_root=tmp_path / "wsroot")
    assert isinstance(s, SessionState)
    assert s.id
    assert s.status == SessionStatus.ACTIVE
    assert s.workspace_dir.startswith(str(tmp_path / "wsroot"))
    assert Path(s.workspace_dir).is_dir()


def test_get_returns_same_session(store, tmp_path):
    s = store.create(workspace_root=tmp_path / "wsroot")
    s2 = store.get(s.id)
    assert s2.id == s.id


def test_get_missing_returns_none(store):
    assert store.get("nope") is None


def test_list_returns_all(store, tmp_path):
    a = store.create(workspace_root=tmp_path / "wsroot")
    b = store.create(workspace_root=tmp_path / "wsroot")
    ids = {s.id for s in store.list()}
    assert ids == {a.id, b.id}


def test_delete_marks_ended(store, tmp_path):
    s = store.create(workspace_root=tmp_path / "wsroot")
    store.delete(s.id)
    s2 = store.get(s.id)
    assert s2.status == SessionStatus.ENDED


def test_touch_updates_last_active(store, tmp_path):
    s = store.create(workspace_root=tmp_path / "wsroot")
    before = s.last_active
    import time

    time.sleep(0.01)
    store.touch(s.id)
    s2 = store.get(s.id)
    assert s2.last_active > before
```

- [ ] **Step 2: 跑，验证 FAIL**

```bash
pytest tests/server/test_sessions_store.py -v
```

- [ ] **Step 3: 写 `src/hagent/server/sessions.py`**

```python
from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SessionStatus(str, Enum):
    ACTIVE = "active"
    ENDED = "ended"


@dataclass(frozen=True)
class SessionState:
    id: str
    workspace_dir: str
    status: SessionStatus
    created_at: float
    last_active: float


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    workspace_dir TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    last_active REAL NOT NULL
)
"""


class SessionStore:
    def __init__(self, db_path: Path | str):
        self._db_path = str(db_path)
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, workspace_root: Path | str) -> SessionState:
        sid = uuid.uuid4().hex[:16]
        workspace_dir = Path(workspace_root) / sid / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                (sid, str(workspace_dir), SessionStatus.ACTIVE.value, now, now),
            )
        return SessionState(
            id=sid,
            workspace_dir=str(workspace_dir),
            status=SessionStatus.ACTIVE,
            created_at=now,
            last_active=now,
        )

    def get(self, sid: str) -> SessionState | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        if row is None:
            return None
        return SessionState(
            id=row["id"],
            workspace_dir=row["workspace_dir"],
            status=SessionStatus(row["status"]),
            created_at=row["created_at"],
            last_active=row["last_active"],
        )

    def list(self) -> list[SessionState]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
        return [
            SessionState(
                id=r["id"],
                workspace_dir=r["workspace_dir"],
                status=SessionStatus(r["status"]),
                created_at=r["created_at"],
                last_active=r["last_active"],
            )
            for r in rows
        ]

    def delete(self, sid: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET status = ? WHERE id = ?",
                (SessionStatus.ENDED.value, sid),
            )

    def touch(self, sid: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET last_active = ? WHERE id = ?",
                (time.time(), sid),
            )
```

- [ ] **Step 4: 跑，验证 PASS**

```bash
pytest tests/server/test_sessions_store.py -v
```

- [ ] **Step 5: 提交**

```bash
git add src/hagent/server/sessions.py tests/server/test_sessions_store.py
git commit -m "feat(server): add SessionState model + SQLite session store"
```

---

### Task 3: POST /sessions create + GET list + GET state + DELETE

**Files:**
- Modify: `src/hagent/server/app.py`
- Create: `src/hagent/server/routers/__init__.py`
- Create: `src/hagent/server/routers/sessions.py`
- Modify: `src/hagent/server/__init__.py`（exports）
- Create: `tests/server/test_sessions_api.py`

- [ ] **Step 1: 写失败测试 `tests/server/test_sessions_api.py`**

```python
from fastapi.testclient import TestClient

from hagent.server.app import create_app


def test_create_session_returns_id_and_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)

    r = client.post("/sessions", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "session_id" in body
    assert body["status"] == "active"


def test_list_includes_created(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)

    r = client.post("/sessions", json={})
    sid = r.json()["session_id"]

    r = client.get("/sessions")
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()]
    assert sid in ids


def test_get_session_state(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)
    r = client.post("/sessions", json={})
    sid = r.json()["session_id"]

    r = client.get(f"/sessions/{sid}")
    assert r.status_code == 200
    assert r.json()["id"] == sid


def test_get_missing_session_404(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)
    r = client.get("/sessions/nope")
    assert r.status_code == 404


def test_delete_marks_ended(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)
    r = client.post("/sessions", json={})
    sid = r.json()["session_id"]

    r = client.delete(f"/sessions/{sid}")
    assert r.status_code == 200

    r = client.get(f"/sessions/{sid}")
    assert r.json()["status"] == "ended"
```

- [ ] **Step 2: 跑，验证 FAIL**

```bash
pytest tests/server/test_sessions_api.py -v
```

- [ ] **Step 3: 写 `src/hagent/server/routers/__init__.py`** (空)

```python
```

- [ ] **Step 4: 写 `src/hagent/server/routers/sessions.py`**

```python
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from hagent.server.auth import require_api_key
from hagent.server.sessions import SessionStore

router = APIRouter(dependencies=[Depends(require_api_key)])


def _default_workspace_root() -> Path:
    return Path(os.environ.get("HAGENT_WORKSPACE_ROOT", "/tmp/hagent/sessions"))


def _default_store_path() -> Path:
    return Path(os.environ.get("HAGENT_DB_PATH", "/tmp/hagent/hagent.sqlite"))


def get_store() -> SessionStore:
    db = _default_store_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    return SessionStore(db_path=db)


@router.post("/sessions")
def create_session(body: dict[str, Any]) -> dict:
    store = get_store()
    s = store.create(workspace_root=_default_workspace_root())
    return {
        "session_id": s.id,
        "workspace_dir": s.workspace_dir,
        "status": s.status.value,
    }


@router.get("/sessions")
def list_sessions() -> list[dict]:
    store = get_store()
    return [
        {
            "id": s.id,
            "workspace_dir": s.workspace_dir,
            "status": s.status.value,
            "created_at": s.created_at,
            "last_active": s.last_active,
        }
        for s in store.list()
    ]


@router.get("/sessions/{sid}")
def get_session(sid: str) -> dict:
    store = get_store()
    s = store.get(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "id": s.id,
        "workspace_dir": s.workspace_dir,
        "status": s.status.value,
        "created_at": s.created_at,
        "last_active": s.last_active,
    }


@router.delete("/sessions/{sid}")
def delete_session(sid: str) -> dict:
    store = get_store()
    if store.get(sid) is None:
        raise HTTPException(status_code=404, detail="session not found")
    store.delete(sid)
    return {"ok": True}
```

- [ ] **Step 5: 修改 `src/hagent/server/app.py` 挂上 router**

```python
from __future__ import annotations

from fastapi import FastAPI

from hagent.server.routers import sessions as sessions_router


def create_app() -> FastAPI:
    app = FastAPI(title="Hagent Agent Server", version="0.0.1")

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    app.include_router(sessions_router.router)

    return app
```

- [ ] **Step 6: 跑测试**

```bash
pytest tests/server/ -v
```

注意：之前 `test_healthz_auth.py::test_protected_endpoint_accepts_bearer` 测的是 `GET /sessions`，现在会真实调用 store；用 monkeypatch 把 `HAGENT_DB_PATH` 和 `HAGENT_WORKSPACE_ROOT` 指向 tmp 避免污染。如果失败，更新该测试用 `tmp_path` fixture（参见 sessions_api 测试模式）。

- [ ] **Step 7: 提交**

```bash
git add src/hagent/server/ tests/server/test_sessions_api.py
git commit -m "feat(server): add session lifecycle endpoints (create/list/get/delete)"
```

---

### Task 4: SSE 适配器

**Files:**
- Create: `src/hagent/server/sse.py`
- Create: `tests/server/test_sse_adapter.py`

SSE 适配器把 LangGraph stream（`stream_mode=["updates","messages"]` + `subgraphs=True`）翻译成 spec §5 的 9 种事件。本任务先实现"事件 → SSE 字节序列"格式化，再实现"stream 解析 → 事件序列"。第 5 步接到真实 stream。

- [ ] **Step 1: 写失败测试 `tests/server/test_sse_adapter.py`**

```python
from hagent.server.sse import SSEFormatter, parse_lg_chunk


def test_sse_format_simple_event():
    fmt = SSEFormatter()
    out = fmt.format(event="message.delta", data={"content_chunk": "hello"})
    assert b"event: message.delta\n" in out
    assert b'"content_chunk": "hello"' in out
    assert out.endswith(b"\n\n")


def test_sse_format_includes_id():
    fmt = SSEFormatter()
    first = fmt.format(event="x", data={})
    out = fmt.format(event="y", data={})
    assert b"id: 0\n" in first
    assert b"id: 1\n" in out


def test_parse_messages_chunk_to_message_delta():
    # LangGraph stream_mode='messages' 返回 (token, metadata) 元组
    class FakeAIChunk:
        type = "AIMessageChunk"
        content = "hi"
        tool_call_chunks = []

    out = list(parse_lg_chunk(("messages", (FakeAIChunk(), {}))))
    assert len(out) == 1
    event, data = out[0]
    assert event == "message.delta"
    assert data["content_chunk"] == "hi"


def test_parse_tool_call_chunk_to_tool_call_started():
    class FakeToolCallStart:
        type = "AIMessageChunk"
        content = ""
        tool_call_chunks = [{"name": "read_file", "args": '{"path":', "id": "abc", "index": 0}]

    out = list(parse_lg_chunk(("messages", (FakeToolCallStart(), {}))))
    assert any(e == "tool_call.started" for e, _ in out)


def test_parse_tool_message_to_tool_call_completed():
    class FakeToolMessage:
        type = "tool"
        content = "result"
        tool_call_id = "abc"
        name = "read_file"

    out = list(parse_lg_chunk(("messages", (FakeToolMessage(), {}))))
    assert any(e == "tool_call.completed" for e, _ in out)


def test_parse_write_todos_completion_to_todo_updated():
    class FakeToolMessage:
        type = "tool"
        content = '[{"content": "do x", "status": "pending"}]'
        tool_call_id = "abc"
        name = "write_todos"

    out = list(parse_lg_chunk(("messages", (FakeToolMessage(), {}))))
    todo_events = [d for e, d in out if e == "todo.updated"]
    assert len(todo_events) == 1
    # spec §5 要求 payload 是 {"todos": [...]}
    assert "todos" in todo_events[0]
    assert isinstance(todo_events[0]["todos"], list)
```

- [ ] **Step 2: 跑，验证 FAIL**

```bash
pytest tests/server/test_sse_adapter.py -v
```

- [ ] **Step 3: 写 `src/hagent/server/sse.py`**

```python
from __future__ import annotations

import json
from typing import Any, Iterator


class SSEFormatter:
    def __init__(self) -> None:
        self._next_id = 0

    def format(self, event: str, data: dict[str, Any]) -> bytes:
        eid = self._next_id
        self._next_id += 1
        payload = json.dumps(data, ensure_ascii=False)
        return (
            f"id: {eid}\n"
            f"event: {event}\n"
            f"data: {payload}\n\n"
        ).encode("utf-8")


def _safe_parse_todos(raw: str) -> list:
    """write_todos 工具结果可能是 JSON string，可能是 repr 的 list。
    解析失败时返回空 list，不抛错。
    """
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    return []


def parse_lg_chunk(chunk: Any) -> Iterator[tuple[str, dict[str, Any]]]:
    """把一个 LangGraph stream 元素翻译成 (event, data) 序列。

    输入约定（来自 agent.stream(..., stream_mode=["updates","messages"], subgraphs=True)）：
        chunk = (stream_mode, payload)
    其中：
        - stream_mode == "messages": payload = (token, metadata) 元组
        - stream_mode == "updates": payload = {node_name: node_state} 字典

    注意：调用方负责把 subgraphs=True 时的 3-tuple (namespace, mode, payload) 在喂入前去掉 namespace。
    """
    if not isinstance(chunk, tuple) or len(chunk) != 2:
        return

    mode, payload = chunk

    if mode == "messages":
        token, _meta = payload
        token_type = getattr(token, "type", "")
        # AIMessageChunk
        if token_type in ("AIMessageChunk", "ai"):
            tool_chunks = getattr(token, "tool_call_chunks", None) or []
            for tc in tool_chunks:
                name = tc.get("name")
                if name:
                    yield ("tool_call.started", {
                        "call_id": tc.get("id"),
                        "tool_name": name,
                        "args_chunk": tc.get("args", ""),
                    })
            content = getattr(token, "content", "")
            if content:
                yield ("message.delta", {"role": "assistant", "content_chunk": content})
        # ToolMessage
        elif token_type == "tool":
            tool_name = getattr(token, "name", "")
            call_id = getattr(token, "tool_call_id", None)
            result = getattr(token, "content", "")
            yield ("tool_call.completed", {
                "call_id": call_id,
                "tool_name": tool_name,
                "result_summary": str(result)[:500],
            })
            if tool_name == "write_todos":
                # spec §5 要求 payload 是 {"todos": [...]}
                yield ("todo.updated", {"todos": _safe_parse_todos(str(result))})

    elif mode == "updates":
        # 节点级状态更新；遇到 interrupt 节点抛 interrupt.requested
        if isinstance(payload, dict):
            for node, state in payload.items():
                if node == "__interrupt__":
                    yield ("interrupt.requested", {"payload": str(state)[:1000]})
```

- [ ] **Step 4: 跑，验证 PASS**

```bash
pytest tests/server/test_sse_adapter.py -v
```

- [ ] **Step 5: 提交**

```bash
git add src/hagent/server/sse.py tests/server/test_sse_adapter.py
git commit -m "feat(server): add SSE formatter and LangGraph chunk parser

todo.updated payload uses {todos: list} per spec §5; payload is best-effort
JSON-parsed from write_todos tool result (empty list on parse failure)."
```

---

### Task 5: POST /sessions/{id}/messages SSE endpoint

**Files:**
- Create: `src/hagent/server/agents.py`（缓存/lookup session 的 agent runnable）
- Create: `src/hagent/server/routers/messages.py`
- Modify: `src/hagent/server/app.py`
- Create: `tests/server/test_messages_api.py`

- [ ] **Step 1: 写 `src/hagent/server/agents.py`**

注意 `SqliteSaver.from_conn_string` 是 `@contextmanager`——必须用 `with` 进入，不能当构造函数。我们让模块持有 `sqlite3.Connection`（`check_same_thread=False`）并直接实例化 `SqliteSaver(conn=...)`，避免 context manager 生命周期与 FastAPI 全局对象不匹配的问题。

```python
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.sqlite import SqliteSaver

from hagent.core import create_hagent

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
        _checkpointer = SqliteSaver(conn=_checkpointer_conn)
        _checkpointer.setup()  # 创建必要表
    return _checkpointer


def get_or_build_agent(session_id: str, workspace_dir: str) -> Any:
    if session_id not in _agents:
        backend = LocalShellBackend(root_dir=workspace_dir)
        _agents[session_id] = create_hagent(
            backend=backend,
            checkpointer=get_checkpointer(),
        )
    return _agents[session_id]
```

注意 `SqliteSaver(conn=...)` 是 `langgraph-checkpoint-sqlite` 的标准构造（验证：`from langgraph.checkpoint.sqlite import SqliteSaver; import inspect; print(inspect.signature(SqliteSaver))`）。如果实际构造签名是 `SqliteSaver(conn, *, serde=None)`（位置参数），改成 `SqliteSaver(_checkpointer_conn)` 即可——这是签名细节差异，verification 在 Task 5 Step 4 跑测试时自然暴露。`.setup()` 方法应存在；不存在则忽略（旧版自动建表）。

`create_hagent(checkpointer=get_checkpointer())` 把 checkpointer 传进 `create_deep_agent`——这一路由依赖 Plan 2 Task 4 已经把 `checkpointer` 加进 `create_hagent` 签名。

- [ ] **Step 2: 写 `src/hagent/server/routers/messages.py`**

```python
from __future__ import annotations

from typing import Any, Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from hagent.server.agents import get_or_build_agent
from hagent.server.auth import require_api_key
from hagent.server.routers.sessions import get_store
from hagent.server.sse import SSEFormatter, parse_lg_chunk

router = APIRouter(dependencies=[Depends(require_api_key)])


class MessageBody(BaseModel):
    content: str


def _stream_agent_events(
    agent: Any, content: str, thread_id: str
) -> Iterator[bytes]:
    fmt = SSEFormatter()
    try:
        for chunk in agent.stream(
            {"messages": [{"role": "user", "content": content}]},
            config={"configurable": {"thread_id": thread_id}, "recursion_limit": 40},
            stream_mode=["updates", "messages"],
            subgraphs=True,
        ):
            # subgraphs=True 时 chunk = (namespace, mode, payload); 否则 (mode, payload)
            if isinstance(chunk, tuple) and len(chunk) == 3:
                _ns, mode, payload = chunk
                inner = (mode, payload)
            else:
                inner = chunk
            for event, data in parse_lg_chunk(inner):
                yield fmt.format(event=event, data=data)
        yield fmt.format(event="done", data={"thread_id": thread_id})
    except Exception as e:  # noqa: BLE001
        yield fmt.format(event="error", data={"code": "agent_error", "message": str(e)})


@router.post("/sessions/{sid}/messages")
def post_message(sid: str, body: MessageBody, request: Request) -> StreamingResponse:
    store = get_store()
    s = store.get(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    store.touch(sid)
    agent = get_or_build_agent(sid, s.workspace_dir)
    return StreamingResponse(
        _stream_agent_events(agent, body.content, thread_id=sid),
        media_type="text/event-stream",
    )
```

> 注：本步骤的 stream 调用已 patch（2026-05-13 真实模型 smoke 反馈）：去掉 `version="v2"` —— 该 flag 会把 stream 切到 events-streaming 协议的 dict 形状（`{type, ns, data}`），与本 plan 设计的 `(namespace, mode, payload)` 3-tuple 不兼容，导致 `parse_lg_chunk` 一律早 return。`sse.py` 的 `message.delta` 把 `AIMessageChunk.content` 原样透传（str 或 `list[content-block]`），不在服务端过滤 `thinking` 块——前端按 `block.type` 自行渲染 thinking / text / redacted_thinking。`_normalize_message`（GET /messages 历史回放）同样保留原结构、不做 `str()` 强转。

- [ ] **Step 3: 把 messages router 加到 app**

修改 `src/hagent/server/app.py`：

```python
from __future__ import annotations

from fastapi import FastAPI

from hagent.server.routers import messages as messages_router
from hagent.server.routers import sessions as sessions_router


def create_app() -> FastAPI:
    app = FastAPI(title="Hagent Agent Server", version="0.0.1")

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    app.include_router(sessions_router.router)
    app.include_router(messages_router.router)

    return app
```

- [ ] **Step 4: 写 `tests/server/test_messages_api.py`**（用 monkeypatch 拦截真实 agent）

```python
from fastapi.testclient import TestClient

from hagent.server.app import create_app


class FakeAgent:
    def stream(self, *_args, **_kwargs):
        # 模拟 messages 模式输出一个简单字符片段，再触发 done
        class FakeAIChunk:
            type = "AIMessageChunk"
            content = "ok"
            tool_call_chunks = []

        # subgraphs=True 格式：(namespace_tuple, mode, payload)
        yield ((), "messages", (FakeAIChunk(), {}))


def test_post_message_returns_sse(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd: FakeAgent(),
    )
    app = create_app()
    client = TestClient(app)

    r = client.post("/sessions", json={})
    sid = r.json()["session_id"]

    with client.stream("POST", f"/sessions/{sid}/messages", json={"content": "hi"}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = b"".join(r.iter_bytes())
        assert b"event: message.delta" in body
        assert b'"content_chunk": "ok"' in body
        assert b"event: done" in body


def test_post_message_404_on_missing_session(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)
    r = client.post("/sessions/nope/messages", json={"content": "hi"})
    assert r.status_code == 404
```

- [ ] **Step 5: 跑测试**

```bash
pytest tests/server/test_messages_api.py -v
```

- [ ] **Step 6: 提交**

```bash
git add src/hagent/server/ tests/server/test_messages_api.py
git commit -m "feat(server): add POST /sessions/{id}/messages SSE endpoint"
```

---

### Task 6: GET /sessions/{id}/messages 历史回放

**Files:**
- Modify: `src/hagent/server/routers/messages.py`
- Modify: `tests/server/test_messages_api.py`

LangGraph SqliteSaver 自带回放——`agent.get_state(config)` 返回当前 state；`agent.get_state_history(config)` 返回完整快照列表。我们用最简单的方案：返回当前 messages 列表（不实现增量 `?after=`，因为 MVP 简单）。

- [ ] **Step 1: 给 messages router 加 GET 端点**

修改 `src/hagent/server/routers/messages.py`，在 `post_message` 下面追加：

```python
def _normalize_message(m: Any) -> dict:
    """Convert a LangGraph message (BaseMessage subclass or plain dict) to {role, content}."""
    if isinstance(m, dict):
        return {"role": m.get("role", "unknown"), "content": str(m.get("content", ""))}
    role = getattr(m, "type", "unknown")  # BaseMessage 子类有 .type 属性 (ai/human/tool/system)
    content = getattr(m, "content", "")
    return {"role": role, "content": str(content)}


@router.get("/sessions/{sid}/messages")
def get_messages(sid: str) -> list[dict]:
    store = get_store()
    s = store.get(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    agent = get_or_build_agent(sid, s.workspace_dir)
    state = agent.get_state({"configurable": {"thread_id": sid}})
    msgs = state.values.get("messages", []) if state else []
    return [_normalize_message(m) for m in msgs]
```

- [ ] **Step 2: 加测试** (`tests/server/test_messages_api.py` 追加)

```python
def test_get_messages_returns_history_after_post(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    class FakeState:
        values = {"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "ok"}]}

    class FakeAgent:
        def stream(self, *_a, **_kw):
            yield from ()

        def get_state(self, _cfg):
            return FakeState()

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd: FakeAgent(),
    )
    app = create_app()
    client = TestClient(app)
    r = client.post("/sessions", json={})
    sid = r.json()["session_id"]
    r = client.get(f"/sessions/{sid}/messages")
    assert r.status_code == 200
    assert len(r.json()) == 2
```

- [ ] **Step 3: 跑测试**

```bash
pytest tests/server/test_messages_api.py -v
```

- [ ] **Step 4: 提交**

```bash
git add src/hagent/server/routers/messages.py tests/server/test_messages_api.py
git commit -m "feat(server): add GET /sessions/{id}/messages history endpoint"
```

---

### Task 7: GET /sessions/{id}/todos

**Files:**
- Modify: `src/hagent/server/routers/messages.py`（或拆到新 router；为减小文件数，先放 messages.py，后面 task 重构）

- [ ] **Step 1: 加测试**

```python
def test_get_todos_returns_list(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    class FakeState:
        values = {"todos": [{"content": "do x", "status": "pending"}]}

    class FakeAgent:
        def stream(self, *_a, **_kw):
            yield from ()

        def get_state(self, _cfg):
            return FakeState()

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd: FakeAgent(),
    )
    app = create_app()
    client = TestClient(app)
    r = client.post("/sessions", json={})
    sid = r.json()["session_id"]
    r = client.get(f"/sessions/{sid}/todos")
    assert r.status_code == 200
    assert r.json() == [{"content": "do x", "status": "pending"}]
```

- [ ] **Step 2: 加端点**

在 `src/hagent/server/routers/messages.py` 追加：

```python
@router.get("/sessions/{sid}/todos")
def get_todos(sid: str) -> list[dict]:
    store = get_store()
    s = store.get(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    agent = get_or_build_agent(sid, s.workspace_dir)
    state = agent.get_state({"configurable": {"thread_id": sid}})
    return list(state.values.get("todos", [])) if state else []
```

- [ ] **Step 3: 跑 + 提交**

```bash
pytest tests/server/test_messages_api.py -v
git add src/hagent/server/routers/messages.py tests/server/test_messages_api.py
git commit -m "feat(server): add GET /sessions/{id}/todos endpoint"
```

---

### Task 8: GET /sessions/{id}/files + GET /sessions/{id}/files/{path}（下载）

**Files:**
- Create: `src/hagent/server/routers/files.py`
- Modify: `src/hagent/server/app.py`
- Create: `tests/server/test_files_api.py`

MVP 用 LocalShellBackend，workspace 是 host 文件系统的目录。文件端点直接用 Path 操作，但严格限制在 session 的 workspace 根目录内（防路径穿越）。

- [ ] **Step 1: 写测试 `tests/server/test_files_api.py`**

```python
import os

from fastapi.testclient import TestClient

from hagent.server.app import create_app


def _make_app(monkeypatch, tmp_path):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    return TestClient(create_app())


def test_list_files_empty(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    sid = client.post("/sessions", json={}).json()["session_id"]
    r = client.get(f"/sessions/{sid}/files")
    assert r.status_code == 200
    assert r.json() == []


def test_download_existing_file(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    sid = client.post("/sessions", json={}).json()["session_id"]
    # 手动写一个文件到 workspace
    ws = client.get(f"/sessions/{sid}").json()["workspace_dir"]
    with open(os.path.join(ws, "hello.txt"), "w") as f:
        f.write("hi there")
    r = client.get(f"/sessions/{sid}/files/hello.txt")
    assert r.status_code == 200
    assert r.text == "hi there"


def test_download_nonexistent_404(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    sid = client.post("/sessions", json={}).json()["session_id"]
    r = client.get(f"/sessions/{sid}/files/nope.txt")
    assert r.status_code == 404


def test_path_traversal_blocked(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    sid = client.post("/sessions", json={}).json()["session_id"]
    r = client.get(f"/sessions/{sid}/files/../../etc/passwd")
    assert r.status_code in (400, 404)
```

- [ ] **Step 2: 写 `src/hagent/server/routers/files.py`**

```python
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from hagent.server.auth import require_api_key
from hagent.server.routers.sessions import get_store

router = APIRouter(dependencies=[Depends(require_api_key)])


def _resolve_inside(workspace_dir: str, sub: str) -> Path:
    base = Path(workspace_dir).resolve()
    target = (base / sub.lstrip("/")).resolve()
    if not target.is_relative_to(base):
        raise HTTPException(status_code=400, detail="path traversal")
    return target


@router.get("/sessions/{sid}/files")
def list_files(sid: str, path: str = "") -> list[dict]:
    store = get_store()
    s = store.get(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    base = _resolve_inside(s.workspace_dir, path)
    if not base.exists():
        return []
    if base.is_file():
        return [{"path": str(base.relative_to(s.workspace_dir)), "type": "file", "size": base.stat().st_size}]
    return [
        {
            "path": str(child.relative_to(s.workspace_dir)),
            "type": "dir" if child.is_dir() else "file",
            "size": child.stat().st_size if child.is_file() else None,
        }
        for child in sorted(base.iterdir())
    ]


@router.get("/sessions/{sid}/files/{file_path:path}")
def download_file(sid: str, file_path: str) -> FileResponse:
    store = get_store()
    s = store.get(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    target = _resolve_inside(s.workspace_dir, file_path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path=str(target))
```

> 注：本步骤的 `_resolve_inside` 已 patch（2026-05-12 code-review 反馈）：`startswith` 改为 `Path.is_relative_to`，避免前缀匹配越界（base 为 `/tmp/ws` 时 `/tmp/ws-evil/...` 被误判通过）。Python 3.9+ 自带 `is_relative_to`。

- [ ] **Step 3: 挂到 app**

`src/hagent/server/app.py` 增加 `from hagent.server.routers import files as files_router` 和 `app.include_router(files_router.router)`。

- [ ] **Step 4: 跑测试**

```bash
pytest tests/server/test_files_api.py -v
```

- [ ] **Step 5: 提交**

```bash
git add src/hagent/server/ tests/server/test_files_api.py
git commit -m "feat(server): add GET file list + download endpoints with path traversal guard"
```

---

### Task 9: POST /sessions/{id}/files（multipart 上传）

**Files:**
- Modify: `src/hagent/server/routers/files.py`
- Modify: `tests/server/test_files_api.py`

- [ ] **Step 1: 加测试**

```python
def test_upload_writes_file(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    sid = client.post("/sessions", json={}).json()["session_id"]
    files = {"file": ("greeting.txt", b"hello upload", "text/plain")}
    data = {"path": "greeting.txt"}
    r = client.post(f"/sessions/{sid}/files", files=files, data=data)
    assert r.status_code == 200
    body = r.json()
    assert body["size"] == len(b"hello upload")
    # 真实文件检查
    r = client.get(f"/sessions/{sid}/files/greeting.txt")
    assert r.text == "hello upload"


def test_upload_path_traversal_blocked(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    sid = client.post("/sessions", json={}).json()["session_id"]
    files = {"file": ("x", b"x", "text/plain")}
    data = {"path": "../../bad.txt"}
    r = client.post(f"/sessions/{sid}/files", files=files, data=data)
    assert r.status_code == 400
```

- [ ] **Step 2: 加端点**

修改 `src/hagent/server/routers/files.py`，加 import `from fastapi import File, Form, UploadFile`，然后追加：

```python
@router.post("/sessions/{sid}/files")
async def upload_file(
    sid: str,
    file: UploadFile = File(...),
    path: str = Form(...),
) -> dict:
    store = get_store()
    s = store.get(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    target = _resolve_inside(s.workspace_dir, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = await file.read()
    target.write_bytes(data)
    return {"path": str(target.relative_to(s.workspace_dir)), "size": len(data)}
```

- [ ] **Step 3: 跑测试 + 提交**

```bash
pytest tests/server/test_files_api.py -v
git add src/hagent/server/routers/files.py tests/server/test_files_api.py
git commit -m "feat(server): add POST /sessions/{id}/files multipart upload"
```

---

### Task 10: POST /sessions/{id}/interrupt（端点保留，MVP 无业务）

**Files:**
- Modify: `src/hagent/server/routers/messages.py`（或独立 router；这里仍放 messages.py）
- Modify: `tests/server/test_messages_api.py`

- [ ] **Step 1: 加测试**

```python
def test_interrupt_endpoint_accepts_decision(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)
    sid = client.post("/sessions", json={}).json()["session_id"]
    r = client.post(
        f"/sessions/{sid}/interrupt",
        json={"interrupt_id": "abc", "decision": "approve"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
```

- [ ] **Step 2: 加端点**

修改 `src/hagent/server/routers/messages.py`，追加：

```python
class InterruptBody(BaseModel):
    interrupt_id: str
    decision: str
    reason: str | None = None


@router.post("/sessions/{sid}/interrupt")
def post_interrupt(sid: str, body: InterruptBody) -> dict:
    store = get_store()
    s = store.get(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    # MVP B 方案：interrupt 端点保留，不主动触发；future hookup via Command(resume=...)
    return {"ok": True, "session_id": sid, "decision": body.decision}
```

- [ ] **Step 3: 跑测试 + 提交**

```bash
pytest tests/server/test_messages_api.py -v
git add src/hagent/server/routers/messages.py tests/server/test_messages_api.py
git commit -m "feat(server): add POST /sessions/{id}/interrupt placeholder endpoint"
```

---

### Task 11: 端到端集成测试

**Files:**
- Create: `tests/server/test_api_e2e.py`

整合上述所有端点的端到端流程，模拟前端会做的事：create → upload → message (fake agent) → list files → download → delete。

- [ ] **Step 1: 写测试**

```python
import io

from fastapi.testclient import TestClient

from hagent.server.app import create_app


class FakeAgent:
    def stream(self, *_a, **_kw):
        class FakeAIChunk:
            type = "AIMessageChunk"
            content = "demo answer"
            tool_call_chunks = []

        yield ((), "messages", (FakeAIChunk(), {}))

    def get_state(self, _cfg):
        class S:
            values = {"messages": [], "todos": []}
        return S()


def test_full_session_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd: FakeAgent(),
    )
    app = create_app()
    client = TestClient(app)

    # 1. health
    assert client.get("/healthz").json() == {"ok": True}

    # 2. create
    sid = client.post("/sessions", json={}).json()["session_id"]
    assert sid

    # 3. upload
    r = client.post(
        f"/sessions/{sid}/files",
        files={"file": ("data.csv", b"a,b\n1,2\n", "text/csv")},
        data={"path": "data.csv"},
    )
    assert r.status_code == 200

    # 4. list files
    r = client.get(f"/sessions/{sid}/files")
    paths = [f["path"] for f in r.json()]
    assert "data.csv" in paths

    # 5. POST message + 消费 SSE
    with client.stream(
        "POST", f"/sessions/{sid}/messages", json={"content": "process the csv"}
    ) as r:
        body = b"".join(r.iter_bytes())
        assert b"demo answer" in body
        assert b"event: done" in body

    # 6. todos
    r = client.get(f"/sessions/{sid}/todos")
    assert isinstance(r.json(), list)

    # 7. download
    r = client.get(f"/sessions/{sid}/files/data.csv")
    assert r.text == "a,b\n1,2\n"

    # 8. delete
    r = client.delete(f"/sessions/{sid}")
    assert r.status_code == 200
    assert client.get(f"/sessions/{sid}").json()["status"] == "ended"
```

- [ ] **Step 2: 跑**

```bash
pytest tests/server/test_api_e2e.py -v
```

- [ ] **Step 3: 提交**

```bash
git add tests/server/test_api_e2e.py
git commit -m "test(server): add end-to-end API lifecycle integration test"
```

---

### Task 12: curl smoke 脚本 + 启动指令

**Files:**
- Create: `scripts/curl_smoke.sh`
- Modify: `README.md`（加 server 启动 + smoke 用法）

- [ ] **Step 1: 写 `scripts/curl_smoke.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

# 假设 server 已在 8000 端口跑起来；env 里有可选 HAGENT_API_KEY
BASE=${HAGENT_BASE:-http://localhost:8000}
KEY=${HAGENT_API_KEY:-}

curl_auth() {
    if [[ -n "$KEY" ]]; then
        curl -sS -H "Authorization: Bearer $KEY" "$@"
    else
        curl -sS "$@"
    fi
}

echo "==> /healthz"
curl_auth "$BASE/healthz" | jq .

echo "==> POST /sessions"
SID=$(curl_auth -X POST "$BASE/sessions" -H 'Content-Type: application/json' -d '{}' | jq -r .session_id)
echo "session_id=$SID"

echo "==> POST /sessions/$SID/files (upload)"
echo "hello, hagent" > /tmp/hagent_curl_upload.txt
curl_auth -X POST "$BASE/sessions/$SID/files" \
    -F "file=@/tmp/hagent_curl_upload.txt" \
    -F "path=greeting.txt" | jq .

echo "==> GET /sessions/$SID/files"
curl_auth "$BASE/sessions/$SID/files" | jq .

echo "==> GET /sessions/$SID/files/greeting.txt"
curl_auth "$BASE/sessions/$SID/files/greeting.txt"
echo

echo "==> POST /sessions/$SID/messages (SSE)"
curl_auth -N -X POST "$BASE/sessions/$SID/messages" \
    -H 'Content-Type: application/json' \
    -d '{"content": "say hi"}'

echo "==> DELETE /sessions/$SID"
curl_auth -X DELETE "$BASE/sessions/$SID" | jq .
```

- [ ] **Step 2: 赋可执行权限**

```bash
chmod +x scripts/curl_smoke.sh
```

- [ ] **Step 3: 在 README.md 追加一节 "运行 Agent Server"**

```markdown
## 运行 Agent Server

```bash
source .venv/bin/activate
export ANTHROPIC_API_KEY=sk-ant-...  # 真实 demo 需要
# export HAGENT_API_KEY=secret-key   # 可选；多租户场景用

uvicorn hagent.server.app:create_app --factory --host 0.0.0.0 --port 8000
```

另起一个 shell 跑 smoke 测试：

```bash
./scripts/curl_smoke.sh
```
```

- [ ] **Step 4: 手动 smoke**

在 venv 里启 server（后台或新 shell）：
```bash
source .venv/bin/activate && uvicorn hagent.server.app:create_app --factory --port 8000
```
另一个 shell：
```bash
./scripts/curl_smoke.sh
```

如果在没有 ANTHROPIC_API_KEY 的情况下跑，POST /messages 会因为 agent 调用模型时失败而返回 SSE error 事件——这是预期，不算 fail。重点是其他端点都正常。

- [ ] **Step 5: 提交**

```bash
git add scripts/curl_smoke.sh README.md
git commit -m "docs(server): add curl smoke script and server startup instructions"
```

---

### Task 13: Plan 3 收口

- [ ] **Step 1: 全量测试**

```bash
source .venv/bin/activate && pytest -v
```
Expected: 全过。

- [ ] **Step 2: 用户手动 smoke（可选，含真实模型）**

如果用户设了 ANTHROPIC_API_KEY，启 server 后在浏览器 / curl 跑一次完整 demo：
```bash
curl -N -X POST http://localhost:8000/sessions/$SID/messages \
    -H 'Content-Type: application/json' \
    -d '{"content": "在 workspace 创建一个 hello.txt 文件，写 hi 进去"}'
```
应该看到 message.delta / tool_call.started/.completed / done 事件流。

- [ ] **Step 3: 通知**

> "Plan 3 完成：Agent Server 全部端点 + SSE 适配器 + e2e 集成测试 + curl smoke + 启动指令 ready。准备合 main + 进 Plan 4（Web 前端）。"

---

## Plan 3 完整 Done 标准（对应 spec §5 + §4 M4）

- ✅ `hagent.server.app.create_app` 工厂返回 FastAPI app
- ✅ /healthz 公开；其他端点经 API key bearer 校验（无 key env 时允许所有，便于本地 dev）
- ✅ 所有 spec §5 表里的端点存在：POST/GET/DELETE /sessions、POST /sessions/{id}/messages (SSE)、GET /sessions/{id}/messages 回放、GET /sessions/{id}/todos、GET/POST /sessions/{id}/files、GET /sessions/{id}/files/{path}、POST /sessions/{id}/interrupt
- ✅ SSE 事件类型至少覆盖：message.delta、tool_call.started、tool_call.completed、todo.updated、interrupt.requested、error、done
- ✅ `done` 事件不含 token usage（MVP 不做成本闭环）
- ✅ 路径穿越防护（`..` 不可逃出 workspace）
- ✅ thread 持久化用 SqliteSaver；session metadata 用独立 SQLite 表
- ✅ `tests/test_api_e2e.py` + `tests/server/*` 全过
- ✅ `scripts/curl_smoke.sh` 可执行
- ✅ README 含启动指令
