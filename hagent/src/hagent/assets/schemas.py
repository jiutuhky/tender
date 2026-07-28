"""REST / MCP 共用输出模型与转换器（票 07）。

「条目查询与 MCP 工具同参数同结果」由共用模型锁定：两个 adapter 的读输出
（条目 / 分页 envelope / 矩阵总览 / 四矩阵状态）一律经本文件构造，
分页语义（limit 默认 20、上限 100、has_more/next_offset/total_count）单一来源。
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from pydantic import BaseModel, Field

from hagent.assets.model import DocumentRecord, MatrixItem, MatrixOverview, MatrixStatusEntry

# 列表读强制分页（spec §5）
QUERY_LIMIT_DEFAULT = 20
QUERY_LIMIT_MAX = 100

MatrixType = Literal["basic_info", "business", "technical", "scoring"]
ResponseStatus = Literal["pending", "compliant", "positive_deviation", "negative_deviation"]


class ItemModel(BaseModel):
    matrix_type: str
    stage: str
    item_id: str
    section: str
    payload: dict[str, Any]
    response_status: str | None
    response_note: str | None
    confirmed: bool
    version: int = Field(description="乐观锁版本；写操作传 expected_version 用")


class MatrixStatsModel(BaseModel):
    stage: str
    total: int
    by_section: dict[str, int]
    by_response_status: dict[str, int]
    confirmed_count: int
    mandatory_count: int
    by_category: dict[str, int]


class MatrixOverviewModel(BaseModel):
    matrix_type: str
    state: str
    current_rev: int
    updated_at: str | None
    meta: dict[str, Any] = Field(description="envelope（靶点规则：有草稿返回草稿 envelope）")
    stats: MatrixStatsModel


class QueryItemsModel(BaseModel):
    items: list[ItemModel]
    total_count: int
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None


class DocumentModel(BaseModel):
    id: str
    path: str
    sha256: str
    doc_type: str | None
    registered_at: str
    created: bool = Field(description="本次调用是否新建（同 project+sha256 幂等命中为 false）")


class DocumentPage(BaseModel):
    documents: list[DocumentModel]
    total_count: int
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None


class MatrixStatusModel(BaseModel):
    matrix_type: str
    state: str
    current_rev: int
    updated_at: str | None
    draft_count: int
    current_count: int
    last_validation: dict[str, Any] | None = Field(
        description="最近一次 validate_matrix 的摘要（ts/status/error_count 等），从未校验为 null"
    )


class ProjectStatusModel(BaseModel):
    project_id: str
    matrices: list[MatrixStatusModel]


def item_model(item: MatrixItem) -> ItemModel:
    return ItemModel(
        matrix_type=item.matrix_type,
        stage=item.stage,
        item_id=item.item_id,
        section=item.section,
        payload=item.payload,
        response_status=item.response_status,
        response_note=item.response_note,
        confirmed=item.confirmed,
        version=item.version,
    )


def page_bounds(total: int, limit: int, offset: int) -> tuple[bool, int | None]:
    has_more = offset + limit < total
    return has_more, (offset + limit) if has_more else None


def query_items_model(
    items: list[MatrixItem], total: int, *, limit: int, offset: int
) -> QueryItemsModel:
    has_more, next_offset = page_bounds(total, limit, offset)
    return QueryItemsModel(
        items=[item_model(i) for i in items],
        total_count=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
        next_offset=next_offset,
    )


def document_model(record: DocumentRecord) -> DocumentModel:
    return DocumentModel(
        id=record.id,
        path=record.path,
        sha256=record.sha256,
        doc_type=record.doc_type,
        registered_at=record.registered_at,
        created=record.created,
    )


def document_page_model(
    documents: list[DocumentRecord], total: int, *, limit: int, offset: int
) -> DocumentPage:
    has_more, next_offset = page_bounds(total, limit, offset)
    return DocumentPage(
        documents=[document_model(d) for d in documents],
        total_count=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
        next_offset=next_offset,
    )


def overview_model(overview: MatrixOverview) -> MatrixOverviewModel:
    info = overview.info
    meta = (
        info.draft_meta
        if overview.stats.stage == "draft" and info.draft_meta is not None
        else info.meta
    )
    return MatrixOverviewModel(
        matrix_type=info.matrix_type,
        state=info.state.value,
        current_rev=info.current_rev,
        updated_at=info.updated_at,
        meta=meta,
        stats=MatrixStatsModel(**asdict(overview.stats)),
    )


def project_status_model(project_id: str, entries: list[MatrixStatusEntry]) -> ProjectStatusModel:
    return ProjectStatusModel(
        project_id=project_id,
        matrices=[
            MatrixStatusModel(
                matrix_type=e.matrix_type,
                state=e.state.value,
                current_rev=e.current_rev,
                updated_at=e.updated_at,
                draft_count=e.draft_count,
                current_count=e.current_count,
                last_validation=e.last_validation,
            )
            for e in entries
        ],
    )
