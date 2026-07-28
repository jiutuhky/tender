"""结构化资产领域模型：常量与只读数据类（词汇对齐 hagent/CONTEXT.md）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

MATRIX_TYPES = ("basic_info", "business", "technical", "scoring")

# 应答状态仅对 business / technical 的 items 区段有效（spec §3）
RESPONSE_STATUSES = ("pending", "compliant", "positive_deviation", "negative_deviation")
RESPONSE_MATRIX_TYPES = ("business", "technical")

# 各矩阵允许的区段（对齐 references/response-matrix-schema.md 的 chunk 区段契约；
# items 与非 items 区段统一为行，section 区分）
ALLOWED_SECTIONS: dict[str, tuple[str, ...]] = {
    "basic_info": ("timeline", "contacts", "project.packages", "source_refs", "unresolved_items"),
    "business": (
        "items",
        "compliance_overview.qualification_review",
        "compliance_overview.conformity_review",
        "compliance_overview.invalid_bid_triggers",
        "unresolved_items",
    ),
    "technical": ("items", "deliverables", "acceptance_requirements", "unresolved_items"),
    "scoring": ("items", "evaluation.pass_fail_rules", "evaluation.tie_break_rules", "unresolved_items"),
}


class MatrixLifecycle(str, Enum):
    EMPTY = "empty"
    DRAFTING = "drafting"
    PUBLISHED = "published"
    PUBLISHED_DRAFTING = "published_drafting"  # 逃生门重抽中：草稿与当前版并立


class ActorKind(str, Enum):
    AGENT = "agent"
    USER = "user"
    AGENT_ON_BEHALF = "agent_on_behalf"
    SYSTEM = "system"


@dataclass(frozen=True)
class Actor:
    kind: str
    ref: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {k.value for k in ActorKind}:
            raise ValueError(
                f"未知 actor kind：{self.kind}（可用：{', '.join(k.value for k in ActorKind)}）"
            )

    def label(self) -> str:
        return f"{self.kind}:{self.ref}" if self.ref else self.kind


@dataclass(frozen=True)
class DocumentRecord:
    id: str
    project_id: str
    path: str
    sha256: str
    doc_type: str | None
    registered_at: str
    created: bool = False  # 本次调用是否新建（幂等命中为 False）；不落库


@dataclass(frozen=True)
class MatrixInfo:
    project_id: str
    matrix_type: str
    state: MatrixLifecycle
    meta: dict
    draft_meta: dict | None
    current_rev: int
    updated_at: str | None


@dataclass(frozen=True)
class MatrixItem:
    project_id: str
    matrix_type: str
    stage: str  # draft / current
    item_id: str
    section: str
    payload: dict
    response_status: str | None
    response_note: str | None
    confirmed: bool
    version: int


@dataclass(frozen=True)
class AssetEvent:
    id: int
    project_id: str
    ts: str
    actor_kind: str
    actor_ref: str | None
    action: str
    target: str
    before: dict | None
    after: dict | None
    reason: str | None


@dataclass(frozen=True)
class MatrixStats:
    """分组统计（决策触发器数字）：response_status 以 "unset" 桶计未标注行。"""

    stage: str  # draft / current（靶点规则解析结果）
    total: int
    by_section: dict[str, int]
    by_response_status: dict[str, int]  # 仅 items 区段
    confirmed_count: int  # 仅 items 区段
    mandatory_count: int  # 仅 items 区段（payload.mandatory 为 true）
    by_category: dict[str, int]  # 仅 items 区段


@dataclass(frozen=True)
class MatrixOverview:
    info: MatrixInfo
    stats: MatrixStats


@dataclass(frozen=True)
class MatrixStatusEntry:
    matrix_type: str
    state: MatrixLifecycle
    current_rev: int
    updated_at: str | None
    draft_count: int
    current_count: int
    last_validation: dict | None  # 最近一次落审计的校验摘要（validate_matrix + actor）


@dataclass(frozen=True)
class SubmitResult:
    matrix_type: str
    section: str
    stage: str
    item_ids: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.item_ids)


@dataclass(frozen=True)
class PublishResult:
    matrix_type: str
    rev: int
    record_count: int
    state: MatrixLifecycle
