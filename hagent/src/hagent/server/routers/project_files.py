"""项目 workspace 的 HTTP 数据面：上传落 sources/ + 列举 / 读取 / 历史（spec §4.4）。"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

from hagent.ingest.pipeline import UploadRejected, check_upload
from hagent.ingest.tasks import get_ingest_registry
from hagent.server.auth import require_api_key
from hagent.server.project_workspace import get_project_workspace
from hagent.server.projects import get_project_store
from hagent.server.routers.sessions import get_session_manager

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_api_key)])

UPLOAD_ROOT = "sources"


def _require_project(pid: str) -> None:
    if get_project_store().get(pid) is None:
        raise HTTPException(status_code=404, detail="project not found")


def _normalize_upload_path(path: str | None, filename: str | None) -> str:
    """把上传目标规范为 sources/ 下的 workspace 相对路径。"""
    if path is None or not path.strip():
        name = PurePosixPath(filename or "").name
        if not name or name in (".", ".."):
            raise HTTPException(status_code=400, detail="缺少有效文件名")
        return f"{UPLOAD_ROOT}/{name}"
    parts = PurePosixPath(path).parts
    if not parts or parts[0] == "/" or any(part in ("..", ".git") for part in parts):
        raise HTTPException(status_code=400, detail="非法上传路径")
    if parts[0] != UPLOAD_ROOT or len(parts) < 2:
        raise HTTPException(
            status_code=400, detail=f"上传路径必须位于 {UPLOAD_ROOT}/ 下"
        )
    return PurePosixPath(path).as_posix()


def _normalize_read_path(path: str) -> str:
    parts = PurePosixPath(path).parts
    if not parts or parts[0] == "/" or any(part in ("..", ".git") for part in parts):
        raise HTTPException(status_code=400, detail="非法路径")
    return PurePosixPath(path).as_posix()


def _accept_pdf(pid: str, relative_path: str, data: bytes) -> dict:
    """PDF 不进 workspace：原件按 sha256 存到 git 之外，仓内只留 OCR 出的 md 与 sidecar。

    页数与体积的硬上限在这里判——超限**立即明确报错**，不让用户等一个注定失败的
    漫长解析。通过后就地起后台解析任务，本请求立即返回。
    """
    try:
        total_pages = check_upload(data, relative_path)
    except UploadRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = get_ingest_registry().submit(
        pid, data=data, pdf_path=relative_path, total_pages=total_pages
    )
    return {
        "path": job.pdf_path,
        "size": len(data),
        "revision": None,
        "sandbox_synced": False,
        "parsing": {"pages": total_pages},
    }


@router.post("/projects/{pid}/files")
async def upload_project_file(
    pid: str,
    file: UploadFile = File(...),
    path: str | None = Form(None),
) -> dict:
    _require_project(pid)
    relative_path = _normalize_upload_path(path, file.filename)
    data = await file.read()

    if relative_path.lower().endswith(".pdf"):
        return _accept_pdf(pid, relative_path, data)

    workspace = get_project_workspace()
    try:
        workspace.apply_changes(pid, updated={relative_path: data}, deleted=())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    revision = workspace.commit(
        pid,
        summary=f"upload: {relative_path}",
        kind="upload",
        paths=[relative_path],
    )

    # 租约活跃时同步注入 VM；失败不影响上传结果（下一轮 ensure 追平自愈），
    # 且绝不触发 VM 创建。
    sandbox_synced = False
    try:
        manager = get_session_manager()
    except RuntimeError:
        manager = None  # manager 未装配（如单测直连 router）
    if manager is not None:
        try:
            sandbox_synced = manager.sync_project_workspace(pid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("project %s 上传后注入 VM 失败(留待追平): %s", pid, exc)

    return {
        "path": relative_path,
        "size": len(data),
        "revision": revision,
        "sandbox_synced": sandbox_synced,
    }


@router.get("/projects/{pid}/workspace/files")
def list_workspace_files(pid: str) -> list[dict]:
    _require_project(pid)
    return [
        {"path": file.path, "size": file.size}
        for file in get_project_workspace().list_files(pid)
    ]


@router.get("/projects/{pid}/workspace/files/{file_path:path}")
def read_workspace_file(pid: str, file_path: str) -> Response:
    _require_project(pid)
    relative_path = _normalize_read_path(file_path)
    try:
        content = get_project_workspace().read_file(pid, relative_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError) as exc:
        raise HTTPException(status_code=404, detail="file not found") from exc
    media_type = mimetypes.guess_type(relative_path)[0] or "application/octet-stream"
    return Response(content=content, media_type=media_type)


@router.get("/projects/{pid}/workspace/history")
def workspace_history(pid: str, limit: int = Query(default=50, ge=1, le=500)) -> list[dict]:
    _require_project(pid)
    return [
        {
            "sha": revision.sha,
            "committed_at": revision.committed_at,
            "summary": revision.summary,
            "run_id": revision.run_id,
            "session_id": revision.session_id,
            "kind": revision.kind,
            "interrupted": revision.interrupted,
        }
        for revision in get_project_workspace().history(pid, limit=limit)
    ]
