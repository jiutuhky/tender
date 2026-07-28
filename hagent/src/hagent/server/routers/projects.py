from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from hagent.server.auth import require_api_key
from hagent.server.project_workspace import get_project_workspace
from hagent.server.projects import (
    PROJECT_STATUS_DELETED,
    ProjectState,
    get_project_store,
)
from hagent.server.routers.sessions import end_session, get_session_manager
from hagent.server.sessions import SessionState, SessionStatus

router = APIRouter(dependencies=[Depends(require_api_key)])


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    metadata: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name 不能为空白")
        return v


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = Field(default=None, min_length=1, max_length=64)
    # 整体替换语义:传入即覆盖原 metadata,不做深合并
    metadata: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("name 不能为空白")
        return v


def _metadata_of(p: ProjectState) -> dict[str, Any] | None:
    if not p.metadata_json:
        return None
    try:
        return json.loads(p.metadata_json)
    except ValueError:
        return None


def _session_dict(s: SessionState) -> dict:
    # 与 routers/sessions.list_sessions 行形状对齐,外加 project_id
    return {
        "id": s.id,
        "status": s.status.value,
        "created_at": s.created_at,
        "last_active": s.last_active,
        "project_id": s.project_id,
    }


def _project_dict(p: ProjectState, *, latest_session: SessionState | None = None) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "status": p.status,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "metadata": _metadata_of(p),
        "latest_session": (
            {"id": latest_session.id, "status": latest_session.status.value}
            if latest_session is not None
            else None
        ),
    }


def _get_or_404(pid: str) -> ProjectState:
    p = get_project_store().get(pid)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    return p


@router.post("/projects")
def create_project(payload: CreateProjectRequest) -> dict:
    metadata_json = (
        json.dumps(payload.metadata, ensure_ascii=False) if payload.metadata is not None else None
    )
    store = get_project_store()
    p = store.create(payload.name, metadata_json=metadata_json)
    try:
        get_project_workspace().initialize(p.id)
    except Exception:
        store.rollback_create(p.id)
        raise
    return _project_dict(p)


@router.get("/projects")
def list_projects() -> list[dict]:
    mgr = get_session_manager()
    latest = mgr.store.latest_per_project()
    return [
        _project_dict(p, latest_session=latest.get(p.id))
        for p in get_project_store().list()
    ]


@router.get("/projects/{pid}")
def get_project(pid: str) -> dict:
    p = _get_or_404(pid)
    mgr = get_session_manager()
    sessions = mgr.store.list(project_id=pid)
    body = _project_dict(p, latest_session=sessions[0] if sessions else None)
    body["sessions"] = [_session_dict(s) for s in sessions]
    return body


@router.patch("/projects/{pid}")
def update_project(pid: str, payload: UpdateProjectRequest) -> dict:
    _get_or_404(pid)
    metadata_json = (
        json.dumps(payload.metadata, ensure_ascii=False) if payload.metadata is not None else None
    )
    p = get_project_store().update(
        pid, name=payload.name, status=payload.status, metadata_json=metadata_json
    )
    mgr = get_session_manager()
    sessions = mgr.store.list(project_id=pid)
    return _project_dict(p, latest_session=sessions[0] if sessions else None)


@router.delete("/projects/{pid}")
def delete_project(pid: str) -> dict:
    _get_or_404(pid)
    mgr = get_session_manager()
    # 软删项目前先结束其 active 子 session,避免泄漏运行中的 agent/sandbox。
    ended: list[str] = []
    for s in mgr.store.list(project_id=pid):
        if s.status == SessionStatus.ACTIVE:
            end_session(s.id)
            ended.append(s.id)
    mgr.release_project(pid)
    get_project_store().delete(pid)
    return {"ok": True, "ended_sessions": ended}
