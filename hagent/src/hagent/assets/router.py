"""REST adapter（票 07）：前端读端点与人工动作。

薄协议翻译层，与 MCP adapter 同委托 service.py（唯一写入口），无独立业务
逻辑；读输出经 schemas.py 共用模型构造，与 MCP 工具同参数同结果。写端点
是人工动作（confirm / set_response_status），审计 actor_kind=user——与
agent 经 MCP 的写（agent / agent_on_behalf）在事件流里可区分。
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from hagent.assets.errors import AssetError, ConflictError
from hagent.assets.model import Actor
from hagent.assets.schemas import (
    QUERY_LIMIT_DEFAULT,
    QUERY_LIMIT_MAX,
    DocumentPage,
    ItemModel,
    MatrixOverviewModel,
    MatrixType,
    ProjectStatusModel,
    QueryItemsModel,
    ResponseStatus,
    document_page_model,
    item_model,
    overview_model,
    project_status_model,
    query_items_model,
)
from hagent.assets.service import get_asset_service
from hagent.ingest.blobs import BLOB_KIND_PREVIEW, get_blob_store
from hagent.ingest.paths import sidecar_path_for
from hagent.server.auth import require_api_key
from hagent.server.project_workspace import get_project_workspace
from hagent.server.projects import get_project_store

router = APIRouter(dependencies=[Depends(require_api_key)])

_USER = Actor(kind="user")

# service 错误码 → HTTP 状态；未列码默认 400（客户端参数/状态问题）
_NOT_FOUND_CODES = {"item_not_found", "matrix_empty", "document_not_found"}


def _http_error(exc: AssetError) -> HTTPException:
    detail: dict[str, Any] = {"code": exc.code, "message": exc.message}
    if exc.hint:
        detail["hint"] = exc.hint
    if isinstance(exc, ConflictError):
        detail["current_version"] = exc.current_version
        return HTTPException(status_code=409, detail=detail)
    status = 404 if exc.code in _NOT_FOUND_CODES else 400
    return HTTPException(status_code=status, detail=detail)


def _translate_errors(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        try:
            return fn(*args, **kwargs)
        except AssetError as exc:
            raise _http_error(exc) from None

    return wrapper


def _require_project(pid: str) -> str:
    """项目存在性是协议层资源检查（对齐 projects 路由的 404 语义），非业务逻辑。"""
    if get_project_store().get(pid) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return pid


class SetResponseStatusRequest(BaseModel):
    status: ResponseStatus
    note: str | None = None
    reason: str | None = None
    expected_version: int | None = None


class ConfirmRequest(BaseModel):
    expected_version: int | None = None


# —— 读端点 ——


@router.get("/projects/{pid}/matrices")
@_translate_errors
def matrix_status(pid: str) -> ProjectStatusModel:
    """四矩阵状态汇总：state / 两 stage 记录数 / 最近校验摘要（恢复路径用）。"""
    _require_project(pid)
    return project_status_model(pid, get_asset_service().matrix_status(pid))


@router.get("/projects/{pid}/matrices/{matrix_type}")
@_translate_errors
def matrix_overview(pid: str, matrix_type: MatrixType) -> MatrixOverviewModel:
    """envelope + 分组统计（决策触发器数字），不含条目本体。"""
    _require_project(pid)
    return overview_model(get_asset_service().get_matrix_overview(pid, matrix_type))


@router.get("/projects/{pid}/matrices/{matrix_type}/items")
@_translate_errors
def query_matrix_items(
    pid: str,
    matrix_type: MatrixType,
    section: str | None = None,
    category: str | None = None,
    mandatory: bool | None = None,
    response_status: ResponseStatus | None = None,
    confirmed: bool | None = None,
    keyword: str | None = None,
    limit: Annotated[int, Query(ge=1, le=QUERY_LIMIT_MAX)] = QUERY_LIMIT_DEFAULT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> QueryItemsModel:
    """条目分页查询：过滤/分页语义与 MCP `prose_query_matrix_items` 同参数同结果
    （靶点规则：有草稿读草稿）；偏离表 = response_status 取偏离值的同源投影。"""
    _require_project(pid)
    items, total = get_asset_service().query_items(
        pid,
        matrix_type,
        section=section,
        category=category,
        mandatory=mandatory,
        response_status=response_status,
        confirmed=confirmed,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )
    return query_items_model(items, total, limit=limit, offset=offset)


@router.get("/projects/{pid}/documents")
@_translate_errors
def list_documents(
    pid: str,
    limit: Annotated[int, Query(ge=1, le=QUERY_LIMIT_MAX)] = QUERY_LIMIT_DEFAULT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentPage:
    """文档注册表分页读：document_id → workspace 路径映射（前端溯源预览解析来源签用），
    与 MCP `prose_list_documents` 同参数同结果。"""
    _require_project(pid)
    documents, total = get_asset_service().list_documents(pid, limit=limit, offset=offset)
    return document_page_model(documents, total, limit=limit, offset=offset)


@router.get("/projects/{pid}/documents/{doc_id}/preview")
@_translate_errors
def read_document_preview(pid: str, doc_id: str) -> Response:
    """预览版 PDF 字节流：溯源预览层的载体。

    预览版按 sha256 存在 project workspace 之外（不进 git），页数与逐页页面尺寸
    与原件逐页一致——sidecar 的归一化 bbox 正是按这套几何算出来的。没有 PDF 原件
    的文档（历史项目、开发期 `.md` 语料）在此 404，前端据此降级到 md 预览。
    """
    _require_project(pid)
    document = get_asset_service().get_document(pid, doc_id)
    if document.preview_sha256 is None:
        raise HTTPException(status_code=404, detail="document has no preview")
    try:
        content = get_blob_store().get(BLOB_KIND_PREVIEW, document.preview_sha256)
    except OSError as exc:
        raise HTTPException(status_code=404, detail="preview blob not found") from exc
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"ETag": f'"{document.preview_sha256}"'},
    )


@router.get("/projects/{pid}/documents/{doc_id}/sidecar")
@_translate_errors
def read_document_sidecar(pid: str, doc_id: str) -> Response:
    """sidecar JSON：md 行号 → 版面块 →(页码, 归一化矩形) 的映射。

    与 md 同目录进 git，故从 workspace 读。缺失即 404——前端据此显示
    「原文映射失效」黄条，照常打开 PDF 但不滚动不高亮。
    """
    _require_project(pid)
    document = get_asset_service().get_document(pid, doc_id)
    try:
        content = get_project_workspace().read_file(pid, sidecar_path_for(document.path))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="sidecar not found") from exc
    return Response(
        content=content,
        media_type="application/json",
        headers={"ETag": f'"{document.sha256}"'},
    )


# —— 人工动作（audit actor_kind=user） ——


@router.post("/projects/{pid}/matrices/{matrix_type}/items/{item_id}/confirm")
@_translate_errors
def confirm_item(
    pid: str, matrix_type: MatrixType, item_id: str, payload: ConfirmRequest | None = None
) -> ItemModel:
    """用户确认条目；expected_version 与当前不符时 409 + 当前 version。"""
    _require_project(pid)
    item = get_asset_service().confirm_item(
        pid,
        matrix_type,
        item_id,
        expected_version=payload.expected_version if payload else None,
        actor=_USER,
    )
    return item_model(item)


@router.put("/projects/{pid}/matrices/{matrix_type}/items/{item_id}/response-status")
@_translate_errors
def set_response_status(
    pid: str, matrix_type: MatrixType, item_id: str, payload: SetResponseStatusRequest
) -> ItemModel:
    """用户标注应答状态（合规/正偏离/负偏离）；并发守卫同 confirm。"""
    _require_project(pid)
    item = get_asset_service().set_item_response_status(
        pid,
        matrix_type,
        item_id,
        status=payload.status,
        note=payload.note,
        reason=payload.reason,
        expected_version=payload.expected_version,
        actor=_USER,
    )
    return item_model(item)
