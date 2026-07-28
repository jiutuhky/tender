from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from hagent.hooks.events import HookEvent
from hagent.sandbox import SandboxKind
from hagent.server.auth import require_api_key
from hagent.server.agents import close_agent
from hagent.server.hooks_registry import (
    clear_session as clear_hook_session,
    get_hook_runner,
    get_or_build_hook_runner,
    set_pending_session_context,
)
from hagent.server.projects import PROJECT_STATUS_DELETED, get_project_store
from hagent.server.sessions import SessionStore

if TYPE_CHECKING:
    from hagent.server.manager import SessionManager

router = APIRouter(dependencies=[Depends(require_api_key)])

# ---------------------------------------------------------------------------
# SessionManager singleton hook — used by T18 app.py assembly and file routes
# ---------------------------------------------------------------------------

_MANAGER: SessionManager | None = None


def get_session_manager() -> SessionManager:
    if _MANAGER is None:
        raise RuntimeError("SessionManager not initialised; check app startup")
    return _MANAGER


def set_session_manager(mgr: SessionManager | None) -> None:
    global _MANAGER
    _MANAGER = mgr


def _default_workspace_root() -> Path:
    return Path(os.environ.get("HAGENT_WORKSPACE_ROOT", "/tmp/hagent/sessions"))


def _default_store_path() -> Path:
    return Path(os.environ.get("HAGENT_DB_PATH", "/tmp/hagent/hagent.sqlite"))


def get_store() -> SessionStore:
    # Prefer the manager's store so reads share the DB that POST /sessions writes
    # into. Falls back to an independent SessionStore for early-import / test
    # scenarios where the manager has not been assembled yet.
    try:
        return get_session_manager().store
    except RuntimeError:
        db = _default_store_path()
        db.parent.mkdir(parents=True, exist_ok=True)
        return SessionStore(db_path=db)


class CreateSessionRequest(BaseModel):
    # None means "use the server-side default from HAGENT_SANDBOX_KIND"; clients
    # that want host mode on a docker-default server should send "none" explicitly.
    sandbox_kind: str | None = None
    # 会话只是项目内的对话容器，必须归属项目。
    project_id: str


# —— graceful drain 旗标(Task B5):shutdown 起点拒新建,存量请求不受影响 ——
_DRAINING = False


def begin_drain() -> None:
    global _DRAINING
    _DRAINING = True


def set_draining(value: bool) -> None:
    global _DRAINING
    _DRAINING = value


def is_draining() -> bool:
    return _DRAINING


# app 装配时由 preflight 降级链写入(spec D5);router 独立使用时回落 env
_DEFAULT_SANDBOX_KIND: str | None = None


def set_default_sandbox_kind(kind: str | None) -> None:
    global _DEFAULT_SANDBOX_KIND
    _DEFAULT_SANDBOX_KIND = kind


def _default_sandbox_kind() -> str:
    if _DEFAULT_SANDBOX_KIND is not None:
        return _DEFAULT_SANDBOX_KIND
    return os.environ.get("HAGENT_SANDBOX_KIND", "none")


@router.post("/sessions")
def create_session(payload: CreateSessionRequest) -> dict:
    from hagent.sandbox.ledger import CapacityExceeded
    from hagent.sandbox.pool import PoolExhausted

    if _DRAINING:
        raise HTTPException(
            status_code=503, detail="server draining", headers={"Retry-After": "30"}
        )
    mgr = get_session_manager()
    kind_str = payload.sandbox_kind or _default_sandbox_kind()
    kind = SandboxKind.from_str(kind_str)
    project_id = payload.project_id
    project_store = get_project_store()
    project = project_store.get(project_id)
    if project is None or project.status == PROJECT_STATUS_DELETED:
        raise HTTPException(status_code=404, detail="project not found")
    try:
        state = mgr.create_session(sandbox_kind=kind, project_id=project_id)
    except (CapacityExceeded, PoolExhausted) as exc:
        # 快速失败语义(spec D7):不排队,让客户端稍后重试
        raise HTTPException(
            status_code=503, detail=str(exc), headers={"Retry-After": "30"}
        ) from exc
    # 项目列表按活跃度排序:新建 session 视为一次项目活动
    project_store.touch(project_id)
    response = {
        # "id" is the canonical field; "session_id" is kept for backward compatibility
        "id": state.id,
        "session_id": state.id,
        "status": state.status.value,
        "created_at": state.created_at,
        "last_active": state.last_active,
        "project_id": state.project_id,
    }
    # SessionStart hooks：blocking 被忽略（CC 语义）；additionalContext 暂存至
    # 首条消息注入；initialUserMessage 随响应体交给前端决定是否自动提交。
    runner = get_or_build_hook_runner(state.id, mgr.workspace_dir(state.id))
    if runner is not None and runner.has_hooks(HookEvent.SESSION_START):
        agg = runner.run(HookEvent.SESSION_START, {"source": "startup"})
        if agg.contexts:
            set_pending_session_context(state.id, "\n".join(agg.contexts))
        if agg.initial_user_message:
            response["initial_user_message"] = agg.initial_user_message
    return response


@router.get("/sessions")
def list_sessions(project_id: str | None = None) -> list[dict]:
    # spec §4.5:项目内会话列表 = GET /sessions?project_id=
    mgr = get_session_manager()
    return [
        {
            "id": s.id,
            "status": s.status.value,
            "created_at": s.created_at,
            "last_active": s.last_active,
            "project_id": s.project_id,
        }
        for s in mgr.store.list(project_id=project_id)
    ]


@router.get("/sessions/{sid}")
def get_session(sid: str) -> dict:
    mgr = get_session_manager()
    s = mgr.store.get(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "id": s.id,
        "status": s.status.value,
        "created_at": s.created_at,
        "last_active": s.last_active,
        "project_id": s.project_id,
    }


def end_session(sid: str) -> None:
    """结束一个 session 的完整路径:SessionEnd hooks（默认超时 1.5s，CC 同款，
    输出全忽略）→ 清 hook session → close_agent → SessionManager 释放。
    供 DELETE /sessions/{sid} 与项目软删级联复用。"""
    mgr = get_session_manager()
    runner = get_hook_runner(sid)
    if runner is not None and runner.has_hooks(HookEvent.SESSION_END):
        runner.run(HookEvent.SESSION_END, {"reason": "other"})
    clear_hook_session(sid)
    close_agent(sid)
    mgr.delete_session(sid)


@router.delete("/sessions/{sid}")
def delete_session(sid: str) -> dict:
    mgr = get_session_manager()
    if mgr.store.get(sid) is None:
        raise HTTPException(status_code=404, detail="session not found")
    end_session(sid)
    return {"ok": True}
