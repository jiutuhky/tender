"""FastMCP adapter（票 03）：15 个 `prose_*` 工具 + 2 个契约 resource。

薄协议翻译层：全部动作委托 service.py（唯一写入口），本文件不携带任何
抽取方法论（职责剥离：跨工具的认知指南归 skill 与 resource 镜像）。
同一 FastMCP 对象双 transport 复用——server 模式挂 FastAPI `/mcp`
（Streamable HTTP，stateless JSON），CLI host 模式走 stdio（日志只进 stderr）。
草稿态等一切状态只在对象库（SQLite），与 MCP session 无关。
"""

from __future__ import annotations

import inspect
import json
import logging
import os
import sys
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from hagent.assets.errors import AssetError, ConflictError
from hagent.assets.mcp_actor import current_actor_ref, current_project_id
from hagent.assets.mcp_guard import MCP_HTTP_PATH
from hagent.assets.model import (
    ALLOWED_SECTIONS,
    MATRIX_TYPES,
    Actor,
)
from hagent.assets.schemas import (
    QUERY_LIMIT_DEFAULT,
    QUERY_LIMIT_MAX,
    DocumentModel,
    DocumentPage,
    ItemModel,
    MatrixOverviewModel,
    MatrixType,
    ProjectStatusModel,
    QueryItemsModel,
    ResponseStatus,
    document_model,
    document_page_model,
    item_model,
    overview_model,
    project_status_model,
    query_items_model,
)
from hagent.assets.service import AssetService
from hagent.assets.store import AssetStore
from hagent.assets.validators import ValidationFailedError, ValidationReport
from hagent.skills.sources import resolve_skill_sources

logger = logging.getLogger(__name__)

SERVER_NAME = "prose_assets_mcp"

# submit 批量上限（spec §5）；分页常量归 schemas.py（REST/MCP 同源）
SUBMIT_BATCH_MAX = 10

MatrixTypeOrAll = Literal["basic_info", "business", "technical", "scoring", "all"]

_SECTIONS_DOC = "；".join(
    f"{m}: {', '.join(sections)}" for m, sections in ALLOWED_SECTIONS.items()
)

# resource 直读 skill 目录同一份 markdown（单一来源两处暴露，spec §5）
_SKILL_NAME = "bid-response-matrix"
_RESOURCE_FILES = {
    "prose://contracts/matrix-schema": "references/response-matrix-schema.md",
    "prose://guides/extraction": "references/worker-instructions.md",
}


# —— 输出模型（structured output：client 拿到 structuredContent + JSON 文本）——
# DocumentModel / DocumentPage 归 schemas.py（REST documents 端点与 MCP 同源）


class MatrixInfoModel(BaseModel):
    matrix_type: str
    state: str
    current_rev: int
    updated_at: str | None


class SubmitModel(BaseModel):
    matrix_type: str
    section: str
    stage: str
    item_ids: list[str]
    count: int


class DropModel(BaseModel):
    matrix_type: str
    item_id: str
    dropped: bool


class MetaModel(BaseModel):
    matrix_type: str
    meta: dict[str, Any]


class ValidationIssueModel(BaseModel):
    severity: str
    validator: str
    target: str
    code: str
    message: str
    hint: str | None = None
    detail: dict[str, Any] | None = None


class ValidationReportModel(BaseModel):
    matrix_type: str
    status: str
    checked_items: int
    error_count: int
    warning_count: int
    issues: list[ValidationIssueModel]


class ValidateModel(BaseModel):
    reports: list[ValidationReportModel]
    all_pass: bool


class PublishModel(BaseModel):
    matrix_type: str
    rev: int
    record_count: int
    state: str


# —— 协议翻译助手 ——


def _tool_failure(code: str, message: str, hint: str | None = None, **extra: Any) -> ToolError:
    """结构化可行动错误：code + message + hint（下一步建议），不暴露内部栈。"""
    payload: dict[str, Any] = {"code": code, "message": message}
    if hint:
        payload["hint"] = hint
    payload.update(extra)
    return ToolError(json.dumps(payload, ensure_ascii=False))


def _wrap_errors(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        try:
            return fn(*args, **kwargs)
        except ValidationFailedError as exc:
            raise _tool_failure(
                exc.code, exc.message, exc.hint, report=_report_model(exc.report).model_dump()
            ) from None
        except ConflictError as exc:
            raise _tool_failure(
                exc.code, exc.message, exc.hint, current_version=exc.current_version
            ) from None
        except AssetError as exc:
            raise _tool_failure(exc.code, exc.message, exc.hint) from None
        except ToolError:
            raise
        except Exception as exc:  # 内部错误不外泄栈/路径，细节只进 server 日志
            logger.exception("prose 工具内部错误")
            raise _tool_failure(
                "internal_error",
                f"服务内部错误（{type(exc).__name__}）",
                hint="可重试一次；若持续失败，请检查 hagent server 日志",
            ) from None

    return wrapper


def _report_model(report: ValidationReport) -> ValidationReportModel:
    return ValidationReportModel(
        matrix_type=report.matrix_type,
        status=report.status,
        checked_items=report.checked_items,
        error_count=len(report.errors),
        warning_count=len(report.warnings),
        issues=[ValidationIssueModel(**issue.to_dict()) for issue in report.issues],
    )


def _default_workspace_for(project_id: str) -> Path:
    """镜像 server ProjectWorkspace.path_for 的路径约定（stdio 模式无 server 装配）。

    刻意不 import ProjectWorkspace：hagent.server 包 __init__ 会连带加载 app.py
    （其又 import 本模块，成环），且 stdio 子进程不该背上 server 全家桶。
    路径约定若变更，两处同步（tests/assets/test_mcp_transports.py 锁行为）。"""
    root = Path(os.environ.get("HAGENT_WORKSPACE_ROOT", "/tmp/hagent/workspaces"))
    return root / "projects" / project_id / "workspace"


def _skill_reference_text(relative: str) -> str:
    """直读 skill 目录文件：项目层优先，用户层兜底（与 skills 子系统同一发现约定）。"""
    sources = resolve_skill_sources(
        project_root=Path.cwd(), env_value=os.environ.get("HAGENT_SKILLS_PATHS")
    )
    for base, _label in reversed(sources):  # 后者（项目层）优先
        candidate = base / _SKILL_NAME / relative
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"未找到 skill 文件 {_SKILL_NAME}/{relative}；"
        "确认 server 进程 CWD 下存在 .hagent/skills，或设置 HAGENT_SKILLS_PATHS"
    )


def _agent_actor(kind: str = "agent") -> Actor:
    """MCP 调用方即 agent；run 归属见 assets/mcp_actor.py（HTTP header 优先，
    stdio 子进程 env 回退）。"""
    return Actor(kind=kind, ref=current_actor_ref())


# —— project 护栏 ——
#
# agent 在 sandbox 里看到的 workspace 是 /workspace，无从得知自己的 hagent
# project_id。若工具照单全收它传来的任意 project_id，对象库会按该 id 建出一个
# 幽灵命名空间：只读工具返回「四矩阵全 empty」、草稿工具写入成功，唯独碰文件系统的
# register_document 报 file_not_found——agent 用 Bash 明明看得见那个文件，却被工具
# 告知不存在，陷入无法自解的矛盾（2026-07-13 实测：flail 60 余次工具调用直至沙箱被
# 健康巡检杀掉）。这里补上 REST adapter `_require_project` 的同款检查，让错误的
# project_id 在第一次调用就 fail loud，且错误里带上正确答案供 agent 自愈。

_PROJECT_ID_HINT = "project_id 是 hagent 项目 id，不是招标文件正文里的项目编号"


def _project_not_found(project_id: str) -> AssetError:
    return AssetError(
        "project_not_found",
        f"项目不存在：{project_id}",
        hint=f"{_PROJECT_ID_HINT}；确认项目已创建，且 project_id 取自会话所属项目",
    )


def _project_mismatch(project_id: str, bound: str) -> AssetError:
    return AssetError(
        "project_mismatch",
        f"project_id「{project_id}」不是本会话所属项目",
        hint=f"本会话项目为「{bound}」，请改用该值重试（{_PROJECT_ID_HINT}）",
    )


# —— server 工厂 ——


def build_mcp_server(
    service: AssetService,
    *,
    workspace_for: Callable[[str], Path] | None = None,
    project_exists: Callable[[str], bool] | None = None,
) -> FastMCP:
    """装配 FastMCP server：HTTP 侧由 app.py 传 ProjectWorkspace.path_for 与
    ProjectStore 存在性判定，stdio 侧按环境变量镜像同一路径约定、以 workspace
    目录是否存在作为项目存在性的等价判据。"""
    workspace_of = workspace_for or _default_workspace_for
    project_of = project_exists or (lambda project_id: workspace_of(project_id).is_dir())

    def _check_project(project_id: str) -> None:
        # 越界校验先行：调用方已绑定项目时，正确的 project_id 就在错误里，agent 可自愈。
        bound = current_project_id()
        if bound and project_id != bound:
            raise _project_mismatch(project_id, bound)
        if not project_of(project_id):
            raise _project_not_found(project_id)

    def _project_guard(fn: Callable) -> Callable:
        """挂在 tool 装配处（不是逐个工具手写）：新增按 project 命名空间的工具自动继承。"""
        signature = inspect.signature(fn)
        if "project_id" not in signature.parameters:
            return fn

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            bound_args = signature.bind_partial(*args, **kwargs)
            project_id = bound_args.arguments.get("project_id")
            if isinstance(project_id, str):
                _check_project(project_id)
            return fn(*args, **kwargs)

        return wrapper

    mcp = FastMCP(
        SERVER_NAME,
        instructions=(
            "Prose 结构化资产（应答矩阵）管理面。对象库是唯一事实来源；"
            "抽取流程与认知指南见 resource prose://guides/extraction，"
            "数据契约见 prose://contracts/matrix-schema。"
        ),
        stateless_http=True,
        json_response=True,
        streamable_http_path=MCP_HTTP_PATH,
    )

    def tool(
        name: str,
        title: str,
        *,
        read_only: bool = False,
        destructive: bool = False,
        idempotent: bool = False,
    ) -> Callable:
        annotations = ToolAnnotations(
            title=title,
            readOnlyHint=read_only,
            destructiveHint=destructive,
            idempotentHint=idempotent,
            openWorldHint=False,
        )
        def decorate(fn: Callable) -> Callable:
            return mcp.tool(name=name, annotations=annotations)(
                _wrap_errors(_project_guard(fn))
            )
        return decorate

    # —— document registry ——

    @tool("prose_register_document", "注册源文件", idempotent=True)
    def prose_register_document(
        project_id: str,
        path: Annotated[str, Field(description="project workspace 相对路径（OCR Markdown）")],
        doc_type: Annotated[
            Literal["tender", "amendment", "clarification", "other"] | None,
            Field(description="文档类型；不确定可为 null"),
        ] = None,
    ) -> DocumentModel:
        """把 workspace 源文件登记进 document registry，返回 doc_id 供 source_refs 引用。

        服务端读取文件并计算 sha256；同 project + 内容幂等（重复注册返回既有 id，
        created=false）。源文件本体仍是 workspace 普通文件，不入库。"""
        record = service.register_workspace_document(
            project_id,
            path=path,
            doc_type=doc_type,
            workspace_root=workspace_of(project_id),
            actor=_agent_actor(),
        )
        return document_model(record)

    @tool("prose_list_documents", "列出已注册源文件", read_only=True, idempotent=True)
    def prose_list_documents(
        project_id: str,
        limit: Annotated[int, Field(ge=1, le=QUERY_LIMIT_MAX)] = QUERY_LIMIT_DEFAULT,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> DocumentPage:
        """分页列出项目已注册的源文件（doc_id / 路径 / sha256 / 类型）。"""
        documents, total = service.list_documents(project_id, limit=limit, offset=offset)
        return document_page_model(documents, total, limit=limit, offset=offset)

    # —— 草稿生命周期 ——

    @tool("prose_start_matrix_draft", "开启矩阵草稿", destructive=True)
    def prose_start_matrix_draft(
        project_id: str,
        matrix_type: MatrixType,
        discard_manual_states: Annotated[
            bool,
            Field(
                description="已发布矩阵上开草稿（全量重抽）必须显式 true——发布时将丢弃"
                "确认/应答状态等人工标注；增量维护请改用行级工具"
            ),
        ] = False,
    ) -> MatrixInfoModel:
        """开启草稿区。空矩阵直接进入 drafting；已发布矩阵是逃生门重抽
        （published_drafting，需 discard_manual_states=true），草稿与当前版并立。"""
        info = service.start_draft(
            project_id,
            matrix_type,
            discard_manual_states=discard_manual_states,
            actor=_agent_actor(),
        )
        return MatrixInfoModel(
            matrix_type=info.matrix_type,
            state=info.state.value,
            current_rev=info.current_rev,
            updated_at=info.updated_at,
        )

    @tool("prose_submit_matrix_records", "批量提交记录到草稿")
    def prose_submit_matrix_records(
        project_id: str,
        matrix: MatrixType,
        section: Annotated[
            str, Field(description=f"目标区段，按矩阵取值：{_SECTIONS_DOC}")
        ],
        records: Annotated[
            list[dict[str, Any]],
            Field(
                min_length=1,
                max_length=SUBMIT_BATCH_MAX,
                description=f"记录列表（单批最多 {SUBMIT_BATCH_MAX} 条）；items 区段每条必须带"
                "业务 id（如 TECH-001），记录形状见 prose://contracts/matrix-schema",
            ),
        ],
    ) -> SubmitModel:
        """向草稿区追加一批记录（仅草稿态可用）。items 区段 id 与批内/草稿内重复时
        整批拒绝。长清单分多批提交。"""
        result = service.submit_records(
            project_id, matrix, section=section, records=records, actor=_agent_actor()
        )
        return SubmitModel(
            matrix_type=result.matrix_type,
            section=result.section,
            stage=result.stage,
            item_ids=result.item_ids,
            count=result.count,
        )

    # —— 行级动作 ——

    @tool("prose_update_matrix_item", "更新单条记录")
    def prose_update_matrix_item(
        project_id: str,
        matrix: MatrixType,
        item_id: str,
        set: Annotated[  # noqa: A002 —— 参数名对齐 spec §5 的 set{}
            dict[str, Any],
            Field(description="要合并进 payload 的字段（浅合并；不允许改 id 与人工状态字段）"),
        ],
        reason: Annotated[str | None, Field(description="变更理由（进审计）")] = None,
        expected_version: Annotated[
            int | None,
            Field(description="乐观锁：与当前 version 不符则拒绝并返回当前值"),
        ] = None,
    ) -> ItemModel:
        """行级修正条目 payload。靶点规则：有草稿写草稿，无草稿写当前版（=发布后的
        增量维护）。应答状态/确认请用专门工具。"""
        item = service.update_item(
            project_id,
            matrix,
            item_id,
            set=set,
            reason=reason,
            expected_version=expected_version,
            actor=_agent_actor(),
        )
        return item_model(item)

    @tool("prose_drop_matrix_item", "删除单条记录", destructive=True)
    def prose_drop_matrix_item(
        project_id: str,
        matrix: MatrixType,
        item_id: str,
        reason: Annotated[str | None, Field(description="删除理由（进审计）")] = None,
    ) -> DropModel:
        """删除一条记录（靶点规则同 update）。删除前后值留在审计事件里。"""
        service.drop_item(project_id, matrix, item_id, reason=reason, actor=_agent_actor())
        return DropModel(matrix_type=matrix, item_id=item_id, dropped=True)

    @tool("prose_move_matrix_item", "移动记录到另一矩阵")
    def prose_move_matrix_item(
        project_id: str,
        from_matrix: MatrixType,
        to_matrix: MatrixType,
        item_id: str,
        new_id: Annotated[str, Field(description="落点矩阵内的新业务 id（如 BIZ-031）")],
        set: Annotated[  # noqa: A002
            dict[str, Any] | None,
            Field(description="迁移同时合并进 payload 的字段修正"),
        ] = None,
        reason: Annotated[str | None, Field(description="移动理由（进审计）")] = None,
    ) -> ItemModel:
        """把 items 区段的一条记录移到另一矩阵（如 TECH → BIZ 归类修正），
        人工状态随条目迁移。"""
        item = service.move_item(
            project_id,
            from_matrix=from_matrix,
            to_matrix=to_matrix,
            item_id=item_id,
            new_id=new_id,
            set=set,
            reason=reason,
            actor=_agent_actor(),
        )
        return item_model(item)

    @tool("prose_set_matrix_meta", "设置矩阵 envelope")
    def prose_set_matrix_meta(
        project_id: str,
        matrix: MatrixType,
        set: Annotated[  # noqa: A002
            dict[str, Any],
            Field(
                description="深合并进 envelope 的字段（如 project_name / "
                "extraction_summary），列表与标量整体替换"
            ),
        ],
    ) -> MetaModel:
        """深合并矩阵 envelope（项目信息、extraction_summary 等固定标量结构，
        形状见 prose://contracts/matrix-schema）。靶点规则同行级动作。"""
        meta = service.set_meta(project_id, matrix, set=set, actor=_agent_actor())
        return MetaModel(matrix_type=matrix, meta=meta)

    # —— 校验与发布 ——

    # readOnlyHint 与摘要事件不矛盾：对象数据只读，事件是调用行为的审计遥测
    # （spec §5 回写认可）；destructiveHint 等注解是静态的，无法按参数条件化
    @tool("prose_validate_matrix", "校验矩阵", read_only=True)
    def prose_validate_matrix(
        project_id: str,
        matrix: Annotated[
            MatrixTypeOrAll, Field(description="单个矩阵类型，或 all 校验全部四矩阵")
        ] = "all",
    ) -> ValidateModel:
        """跑全套校验（结构 / 组装一致性 / 源文保真），返回结构化报告：每条错误带
        target/code/message 与修复建议 hint。对象数据只读；校验摘要计入审计供
        get_matrix_status 展示。仅 error 拦发布，warning 不拦。"""
        targets = list(MATRIX_TYPES) if matrix == "all" else [matrix]
        reports = [
            service.validate_matrix(
                project_id, m, workspace_root=workspace_of(project_id), actor=_agent_actor()
            )
            for m in targets
        ]
        return ValidateModel(
            reports=[_report_model(r) for r in reports],
            all_pass=all(r.status == "pass" for r in reports),
        )

    @tool("prose_publish_matrix", "发布矩阵")
    def prose_publish_matrix(project_id: str, matrix: MatrixType) -> PublishModel:
        """发布草稿为当前版（原子切换：快照入 revisions → 草稿晋升 → 清草稿）。
        无条件全套校验门禁：任一 error 即拒绝，错误里附完整报告。"""
        result = service.publish_gated(
            project_id, matrix, workspace_root=workspace_of(project_id), actor=_agent_actor()
        )
        return PublishModel(
            matrix_type=result.matrix_type,
            rev=result.rev,
            record_count=result.record_count,
            state=result.state.value,
        )

    # —— 读取 ——

    @tool("prose_get_matrix", "读取矩阵总览", read_only=True, idempotent=True)
    def prose_get_matrix(project_id: str, matrix: MatrixType) -> MatrixOverviewModel:
        """返回 envelope + 分组统计（区段/应答状态/确认/强制性/类别计数），
        不含条目本体——条目用 prose_query_matrix_items 分页查询。"""
        return overview_model(service.get_matrix_overview(project_id, matrix))

    @tool("prose_query_matrix_items", "查询矩阵条目", read_only=True, idempotent=True)
    def prose_query_matrix_items(
        project_id: str,
        matrix: MatrixType,
        section: Annotated[
            str | None, Field(description=f"区段过滤，按矩阵取值：{_SECTIONS_DOC}")
        ] = None,
        category: Annotated[str | None, Field(description="payload.category 过滤")] = None,
        mandatory: Annotated[bool | None, Field(description="payload.mandatory 过滤")] = None,
        response_status: Annotated[
            ResponseStatus | None,
            Field(description="应答状态过滤；偏离表 = response_status 取偏离值的投影"),
        ] = None,
        confirmed: Annotated[bool | None, Field(description="人工确认状态过滤")] = None,
        keyword: Annotated[
            str | None, Field(description="payload 全文关键词（子串匹配）")
        ] = None,
        limit: Annotated[int, Field(ge=1, le=QUERY_LIMIT_MAX)] = QUERY_LIMIT_DEFAULT,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> QueryItemsModel:
        """分页查询条目（靶点规则：有草稿读草稿，无草稿读当前版）。过滤条件可
        组合；结果含乐观锁 version，供后续行级写操作使用。"""
        items, total = service.query_items(
            project_id,
            matrix,
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

    @tool("prose_get_matrix_status", "读取项目四矩阵状态", read_only=True, idempotent=True)
    def prose_get_matrix_status(project_id: str) -> ProjectStatusModel:
        """四矩阵一览：state / 草稿与当前版记录数 / 最近校验摘要。恢复中断流程时
        先调它确认各矩阵进度。"""
        return project_status_model(project_id, service.matrix_status(project_id))

    # —— 人工状态动作（agent 代录，审计记 agent_on_behalf） ——

    @tool("prose_set_item_response_status", "标注应答状态")
    def prose_set_item_response_status(
        project_id: str,
        matrix: Annotated[
            Literal["business", "technical"],
            Field(description="应答状态仅对 business / technical 的 items 区段有效"),
        ],
        item_id: str,
        status: ResponseStatus,
        note: Annotated[str | None, Field(description="应答说明（如偏离描述）")] = None,
        reason: Annotated[str | None, Field(description="标注依据（进审计）")] = None,
    ) -> ItemModel:
        """代用户标注条目应答状态（合规/正偏离/负偏离）。这是人工决策的代录：
        仅在用户明确表态后调用，审计记 agent_on_behalf。"""
        item = service.set_item_response_status(
            project_id,
            matrix,
            item_id,
            status=status,
            note=note,
            reason=reason,
            actor=_agent_actor("agent_on_behalf"),
        )
        return item_model(item)

    @tool("prose_confirm_matrix_item", "确认条目")
    def prose_confirm_matrix_item(
        project_id: str, matrix: MatrixType, item_id: str
    ) -> ItemModel:
        """代用户确认条目（items 区段）。仅在用户明确确认后调用，
        审计记 agent_on_behalf。"""
        item = service.confirm_item(
            project_id, matrix, item_id, actor=_agent_actor("agent_on_behalf")
        )
        return item_model(item)

    # —— resources（契约文档，非对象数据） ——

    @mcp.resource(
        "prose://contracts/matrix-schema",
        name="matrix-schema",
        title="应答矩阵数据契约",
        description="矩阵 envelope 与各区段记录形状的权威契约（skill 目录镜像）",
        mime_type="text/markdown",
    )
    def matrix_schema_contract() -> str:
        return _skill_reference_text(_RESOURCE_FILES["prose://contracts/matrix-schema"])

    @mcp.resource(
        "prose://guides/extraction",
        name="extraction-guide",
        title="抽取指南",
        description="单次抽取 pass 的完整认知指南（skill 目录镜像）",
        mime_type="text/markdown",
    )
    def extraction_guide() -> str:
        return _skill_reference_text(_RESOURCE_FILES["prose://guides/extraction"])

    return mcp


# —— stdio 入口（CLI host 模式：python -m hagent.assets.mcp） ——


def create_stdio_server() -> FastMCP:
    """env 装配：与 server 同一 SQLite 文件约定（WAL 跨进程共享），
    workspace 路径镜像 ProjectWorkspace 约定。"""
    from hagent.config import resolve_sessions_db_path

    db_path = resolve_sessions_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return build_mcp_server(AssetService(AssetStore(db_path)))


def main() -> None:
    # stdio 模式 stdout 只属于 JSON-RPC 帧，日志一律进 stderr
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    create_stdio_server().run(transport="stdio")


if __name__ == "__main__":
    main()
