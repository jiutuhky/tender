"""三校验器：结构 / 组装一致性 / 源文保真（bid-response-matrix skill 三脚本逻辑上移，spec §4）。

纯读模块：只依赖传入的 meta、条目行、document registry 记录与 workspace 源文件，
不触对象库写路径、不落审计事件。publish 门禁（make_publish_gate）与单独校验共用同一套实现。
报错定位从原脚本的 chunk_file:line 换算为 matrix[/item_id]（target 字段）。
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from hagent.assets.errors import AssetError
from hagent.assets.model import ALLOWED_SECTIONS, DocumentRecord, MatrixItem

VALID_CONFIDENCE = ("high", "medium", "low")
VALID_STATUS = ("complete", "partial", "needs_review")

# 原 validate_response_matrix.py 的必填字段清单（id 的一致性由组装一致性校验核对）
ITEM_REQUIRED: dict[str, tuple[str, ...]] = {
    "business": (
        "id", "category", "title", "requirement_text",
        "mandatory", "response_required", "source_refs", "confidence",
    ),
    "technical": (
        "id", "category", "title", "requirement_text",
        "mandatory", "response_required", "source_refs", "confidence",
    ),
    "scoring": (
        "id", "group", "title", "max_score",
        "scoring_rule", "scoring_method", "source_refs", "confidence",
    ),
}

# 源文保真比对的文本字段（原 verify_source_fidelity.py TEXT_FIELDS）
TEXT_FIELDS = {"business": "requirement_text", "technical": "requirement_text", "scoring": "scoring_rule"}
HIGH_RISK_CATEGORIES = ("qualification", "conformity", "invalid_bid")

# basic_info meta.project 期望键；packages 已是 project.packages 区段行，不再要求 meta 预置
BASIC_INFO_PROJECT_KEYS = ("name", "number", "procurement_method", "evaluation_method", "budget", "scope")

# meta 类型骨架：键存在时其值类型不得与骨架冲突（原 assemble_matrix.py deep_merge 的类型冲突检查）。
# 记录列表（packages / pass_fail_rules 等）已行化，骨架保留空列表仅作类型核对。
# 公开导出：projection.py 以同一骨架拼装旧路径 final JSON（单一来源）。
_META_SKELETON_COMMON: dict = {
    "project_id": None,
    "project_name": None,
    "extraction_summary": {"status": None, "confidence": None, "warnings": []},
}
META_SKELETONS: dict[str, dict] = {
    "basic_info": {
        **_META_SKELETON_COMMON,
        "project": {
            "name": None,
            "number": None,
            "procurement_method": None,
            "evaluation_method": None,
            "purchaser": {"name": None, "contact": None, "phone": None, "address": None},
            "agency": {"name": None, "contact": None, "phone": None, "address": None},
            "packages": [],
            "budget": {"amount": None, "currency": None, "text": None},
            "scope": None,
            "delivery_or_service_period": None,
            "delivery_location": None,
        },
        "timeline": [],
        "contacts": [],
        "source_refs": [],
    },
    "business": {**_META_SKELETON_COMMON, "compliance_overview": {
        "qualification_review": [],
        "conformity_review": [],
        "invalid_bid_triggers": [],
    }},
    "technical": {**_META_SKELETON_COMMON, "deliverables": [], "acceptance_requirements": []},
    "scoring": {
        **_META_SKELETON_COMMON,
        "evaluation": {
            "method": None,
            "total_score": None,
            "price_score": None,
            "business_score": None,
            "technical_score": None,
            "pass_fail_rules": [],
            "tie_break_rules": [],
            "deviation_rules": [],
        },
    },
}

# 参数性质三态：原文符号照录（★ 实质性 / ▲ 重要），列空或无此列为 None
VALID_PARAM_NATURE = ("★", "▲")
# 偏离计分规则行的枚举面
VALID_DEVIATION_DIRECTION = ("positive", "negative", "zero_out")
VALID_DEVIATION_APPLIES_TO = ("★", "▲", "general")
# business 的符合性/资格审查区段：行可带可选 response_format（附表2「响应格式」列原文）
COMPLIANCE_SECTIONS = (
    "compliance_overview.qualification_review",
    "compliance_overview.conformity_review",
    "compliance_overview.invalid_bid_triggers",
)


@dataclass(frozen=True)
class FidelityThresholds:
    """源文保真阈值（原脚本 CLI 参数默认值）。"""

    pass_threshold: float = 0.88
    warn_threshold: float = 0.75
    high_risk_threshold: float = 0.90
    min_chars: int = 12


@dataclass(frozen=True)
class ValidationIssue:
    severity: str  # error / warning
    validator: str  # structure / consistency / fidelity / cross
    target: str  # matrix_type 或 matrix_type/item_id
    code: str
    message: str
    hint: str | None = None
    detail: dict | None = None

    def to_dict(self) -> dict:
        data = {
            "severity": self.severity,
            "validator": self.validator,
            "target": self.target,
            "code": self.code,
            "message": self.message,
        }
        if self.hint is not None:
            data["hint"] = self.hint
        if self.detail is not None:
            data["detail"] = self.detail
        return data


@dataclass(frozen=True)
class ValidationReport:
    matrix_type: str
    status: str  # pass / fail（仅 error 触发 fail，warning 不拦发布）
    issues: list[ValidationIssue]
    checked_items: int

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def to_dict(self) -> dict:
        return {
            "matrix_type": self.matrix_type,
            "status": self.status,
            "checked_items": self.checked_items,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _error(validator: str, target: str, code: str, message: str, *, hint: str | None = None,
           detail: dict | None = None) -> ValidationIssue:
    return ValidationIssue("error", validator, target, code, message, hint, detail)


def _warning(validator: str, target: str, code: str, message: str, *, hint: str | None = None,
             detail: dict | None = None) -> ValidationIssue:
    return ValidationIssue("warning", validator, target, code, message, hint, detail)


# —— 结构校验（原 validate_response_matrix.py） ——


def validate_structure(matrix_type: str, meta: dict, items: list[MatrixItem]) -> list[ValidationIssue]:
    """信封字段与条目形状校验。

    schema_version / generated_at / source_documents 由服务层与 document registry
    接管，不再属于 meta 的校验面。
    """
    issues: list[ValidationIssue] = []
    _check_meta_envelope(matrix_type, meta, issues)
    if matrix_type == "basic_info":
        _check_basic_info_project(meta, issues)
    for item in items:
        if item.section == "items":
            if matrix_type in ITEM_REQUIRED:
                _check_item_shape(matrix_type, item, issues)
        elif matrix_type == "scoring" and item.section == "evaluation.deviation_rules":
            _check_deviation_rule_shape(item, issues)
        elif matrix_type == "business" and item.section in COMPLIANCE_SECTIONS:
            _check_response_format(item, issues)
    return issues


def _check_meta_envelope(matrix_type: str, meta: dict, issues: list[ValidationIssue]) -> None:
    for key in ("project_id", "project_name"):
        if key not in meta:
            issues.append(_error(
                "structure", matrix_type, "missing_meta_field",
                f"meta 缺少信封字段 {key}",
                hint=f"用 set_matrix_meta 补齐 {key}（暂无信息可置 null）",
            ))
    if "extraction_summary" not in meta:
        issues.append(_error(
            "structure", matrix_type, "missing_meta_field",
            "meta 缺少信封字段 extraction_summary",
            hint="用 set_matrix_meta 置为 {status, confidence, warnings} 对象（不可为 null）",
        ))
        return
    summary = meta["extraction_summary"]
    if not isinstance(summary, dict):
        issues.append(_error(
            "structure", matrix_type, "invalid_extraction_summary",
            f"extraction_summary 必须是对象，得到 {type(summary).__name__}",
            hint="用 set_matrix_meta 置为 {status, confidence, warnings} 对象",
        ))
        return
    if summary.get("status") not in VALID_STATUS:
        issues.append(_error(
            "structure", matrix_type, "invalid_summary_status",
            f"extraction_summary.status 必须是 {' / '.join(VALID_STATUS)} 之一，"
            f"得到 {summary.get('status')!r}",
            hint="用 set_matrix_meta 修正 extraction_summary.status",
        ))
    if summary.get("confidence") not in VALID_CONFIDENCE:
        issues.append(_error(
            "structure", matrix_type, "invalid_summary_confidence",
            f"extraction_summary.confidence 必须是 {' / '.join(VALID_CONFIDENCE)} 之一，"
            f"得到 {summary.get('confidence')!r}",
            hint="用 set_matrix_meta 修正 extraction_summary.confidence",
        ))
    if "warnings" in summary and not isinstance(summary["warnings"], list):
        issues.append(_error(
            "structure", matrix_type, "invalid_summary_warnings",
            "extraction_summary.warnings 必须是列表",
            hint="用 set_matrix_meta 置为字符串列表（无警告时为 []）",
        ))


def _check_basic_info_project(meta: dict, issues: list[ValidationIssue]) -> None:
    project = meta.get("project")
    if not isinstance(project, dict):
        state = "缺失" if "project" not in meta else f"得到 {type(project).__name__}"
        issues.append(_error(
            "structure", "basic_info", "invalid_project",
            f"meta.project 必须是对象（{state}）",
            hint="用 set_matrix_meta 置为项目概要对象（name / number / budget 等）",
        ))
        return
    for key in BASIC_INFO_PROJECT_KEYS:
        if key not in project:
            issues.append(_warning(
                "structure", "basic_info", "missing_project_field",
                f"meta.project 缺少 {key}",
                hint=f"确认招标文件中该信息缺失后可置 null，否则用 set_matrix_meta 补齐 {key}",
            ))


def _check_item_shape(matrix_type: str, item: MatrixItem, issues: list[ValidationIssue]) -> None:
    target = f"{matrix_type}/{item.item_id}"
    payload = item.payload
    for key in ITEM_REQUIRED[matrix_type]:
        if key not in payload:
            issues.append(_error(
                "structure", target, "missing_item_field",
                f"缺少字段 {key}",
                hint=f"用 update_matrix_item 补齐 {key}",
            ))
    if payload.get("confidence") not in VALID_CONFIDENCE:
        issues.append(_error(
            "structure", target, "invalid_confidence",
            f"confidence 必须是 {' / '.join(VALID_CONFIDENCE)} 之一，得到 {payload.get('confidence')!r}",
            hint="用 update_matrix_item 修正 confidence",
        ))
    if "mandatory" in payload and not isinstance(payload["mandatory"], bool):
        issues.append(_error(
            "structure", target, "invalid_mandatory",
            "mandatory 必须是布尔值",
            hint="用 update_matrix_item 置为 true / false",
        ))
    if "response_required" in payload and not isinstance(payload["response_required"], bool):
        issues.append(_error(
            "structure", target, "invalid_response_required",
            "response_required 必须是布尔值",
            hint="用 update_matrix_item 置为 true / false",
        ))
    if matrix_type in ("business", "technical"):
        _check_param_nature(target, payload, issues)
    if matrix_type == "scoring":
        related_format = payload.get("related_format")
        if related_format is not None and not isinstance(related_format, str):
            issues.append(_error(
                "structure", target, "invalid_related_format",
                f"related_format 必须是字符串或 null，得到 {related_format!r}",
                hint="用 update_matrix_item 置为评审标准表「关联格式」列的原文字符串（无此列置 null）",
            ))
        max_score = payload.get("max_score")
        if max_score is not None and not isinstance(max_score, (int, float)):
            issues.append(_error(
                "structure", target, "invalid_max_score",
                f"max_score 必须是数字或 null，得到 {max_score!r}",
                hint="用 update_matrix_item 修正 max_score",
            ))
        # subgroup 是二级评审因素分类（评审标准表「评审因素分类」列的原文用词）。
        # 可选字段：存量抽取没有它，不进 REQUIRED_FIELDS；只在给了值时核类型。
        subgroup = payload.get("subgroup")
        if subgroup is not None and not isinstance(subgroup, str):
            issues.append(_error(
                "structure", target, "invalid_subgroup",
                f"subgroup 必须是字符串或 null，得到 {subgroup!r}",
                hint="用 update_matrix_item 修正 subgroup",
            ))
    _check_source_refs(target, payload.get("source_refs"), issues)


def _check_param_nature(target: str, payload: dict, issues: list[ValidationIssue]) -> None:
    """参数性质三态（★ 实质性 / ▲ 重要 / 一般）与 mandatory 的双写一致性。

    可选字段：存量抽取没有它，不进 ITEM_REQUIRED，只在给了值时核。★ 与 mandatory 双写
    （前端 ★ 展示链读 mandatory）；▲ 不是 mandatory 信号——负偏离重扣分但不废标。
    两者不一致只报 warning：原文确有 ▲ 条款叠加「须」类措辞的情形，留给主 agent 对照裁决。
    """
    nature = payload.get("param_nature")
    if nature is None:
        return
    if nature not in VALID_PARAM_NATURE:
        issues.append(_error(
            "structure", target, "invalid_param_nature",
            f"param_nature 必须是 {' / '.join(VALID_PARAM_NATURE)} 之一或 null，得到 {nature!r}",
            hint="用 update_matrix_item 置为原文符号 ★ / ▲（OCR 变体 * ☆ 归一为 ★，△ Δ 归一为 ▲）；"
            "一般参数置 null",
        ))
        return
    mandatory = payload.get("mandatory")
    if nature == "★" and mandatory is False:
        issues.append(_warning(
            "structure", target, "param_nature_mandatory_mismatch",
            "param_nature 为 ★（实质性条款）但 mandatory 为 false",
            hint="★ 条款负偏离即无效投标：核对原文后用 update_matrix_item 把 mandatory 置 true，"
            "或修正 param_nature",
        ))
    elif nature == "▲" and mandatory is True:
        issues.append(_warning(
            "structure", target, "param_nature_mandatory_mismatch",
            "param_nature 为 ▲（重要参数）但 mandatory 为 true",
            hint="▲ 条款负偏离扣分但不废标：确认同条款另有无效投标措辞才保留 mandatory=true，"
            "否则用 update_matrix_item 置 false",
        ))


def _check_response_format(item: MatrixItem, issues: list[ValidationIssue]) -> None:
    """compliance_overview 行的可选 response_format（符合性审查表「响应格式」列原文）。"""
    value = item.payload.get("response_format")
    if value is not None and not isinstance(value, str):
        issues.append(_error(
            "structure", f"business/{item.item_id}", "invalid_response_format",
            f"response_format 必须是字符串或 null，得到 {value!r}",
            hint="用 update_matrix_item 置为符合性审查表「响应格式」列的原文字符串（无此列置 null）",
        ))


def _check_deviation_rule_shape(item: MatrixItem, issues: list[ValidationIssue]) -> None:
    """偏离计分规则行的形状校验。

    非 items 区段的行原本不做形状校验（pass_fail_rules 等只是文本 + source_refs）。这里是
    有意的例外：deviation_rules 是新区段、无存量数据，契约建立之时即校验的成本最低。**不要**
    照此给旧区段补形状校验——那会让既有已发布矩阵在重新校验时批量失败。
    """
    target = f"scoring/{item.item_id}"
    payload = item.payload

    direction = payload.get("direction")
    if direction not in VALID_DEVIATION_DIRECTION:
        issues.append(_error(
            "structure", target, "invalid_deviation_direction",
            f"direction 必须是 {' / '.join(VALID_DEVIATION_DIRECTION)} 之一，得到 {direction!r}",
            hint="正偏离加分为 positive，负偏离扣分为 negative，达到项数后总分清零为 zero_out",
        ))

    applies_to = payload.get("applies_to")
    if applies_to is not None and (
        not isinstance(applies_to, list)
        or any(v not in VALID_DEVIATION_APPLIES_TO for v in applies_to)
    ):
        issues.append(_error(
            "structure", target, "invalid_deviation_applies_to",
            f"applies_to 必须是 {' / '.join(VALID_DEVIATION_APPLIES_TO)} 组成的列表或 null，"
            f"得到 {applies_to!r}",
            hint='按档写 ["★"] / ["▲"] / ["general"]（列空的一般参数）；规则不分档时置 null',
        ))

    for key, want_int in (("delta_per_item", False), ("cap", False), ("threshold_items", True)):
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int if want_int else (int, float)):
            issues.append(_error(
                "structure", target, "invalid_deviation_number",
                f"{key} 必须是{'整数' if want_int else '数字'}或 null，得到 {value!r}",
                hint=f"用 update_matrix_item 修正 {key}；原文没有明确数字时置 null，"
                "规则原文留在 rule_text",
            ))
            continue
        if value < 0:
            issues.append(_warning(
                "structure", target, "negative_deviation_number",
                f"{key} 为负数（{value}）",
                hint="该字段承载绝对值，加/扣方向由 direction 表达；用 update_matrix_item 改为正值",
            ))

    if payload.get("threshold_items") is not None and direction != "zero_out":
        issues.append(_warning(
            "structure", target, "threshold_without_zero_out",
            f"threshold_items 有值但 direction 为 {direction!r}",
            hint="threshold_items 只用于熔断规则（direction=zero_out）；"
            "逐项加扣分规则请用 delta_per_item",
        ))

    rule_text = payload.get("rule_text")
    if not isinstance(rule_text, str) or not rule_text.strip():
        issues.append(_error(
            "structure", target, "missing_rule_text",
            "rule_text 缺失或为空",
            hint="用 update_matrix_item 按源文补写 rule_text（贴原文措辞，解读进 notes）",
        ))

    refs = payload.get("source_refs")
    if refs is None:
        issues.append(_error(
            "structure", target, "missing_source_refs",
            "缺少字段 source_refs",
            hint="每条偏离规则至少一条 source_ref（document_id + line_span），用 update_matrix_item 补充",
        ))
    else:
        _check_source_refs(target, refs, issues)


def _check_source_refs(target: str, refs, issues: list[ValidationIssue]) -> None:
    if refs is None:
        return  # 缺失已由 missing_item_field 报出
    if not isinstance(refs, list):
        issues.append(_error(
            "structure", target, "invalid_source_refs",
            f"source_refs 必须是列表，得到 {type(refs).__name__}",
            hint="用 update_matrix_item 置为 [{document_id, line_span}] 列表",
        ))
        return
    if not refs:
        issues.append(_error(
            "structure", target, "empty_source_refs",
            "source_refs 不能为空",
            hint="每个条目至少一条 source_ref（document_id + line_span），用 update_matrix_item 补充",
        ))
        return
    for index, ref in enumerate(refs):
        if not isinstance(ref, dict):
            issues.append(_error(
                "structure", target, "invalid_source_ref",
                f"source_refs[{index}] 必须是对象",
                hint="用 update_matrix_item 修正为 {document_id, line_span} 对象",
            ))
            continue
        if not ref.get("document_id"):
            issues.append(_error(
                "structure", target, "missing_document_id",
                f"source_refs[{index}] 缺少 document_id",
                hint="用 list_documents 查已注册文档 id 后 update_matrix_item 补齐",
            ))
        span_message = _line_span_problem(ref.get("line_span"))
        if span_message is not None:
            issues.append(_error(
                "structure", target, "invalid_line_span",
                f"source_refs[{index}] {span_message}",
                hint="line_span 为 1 起始闭区间 [start_line, end_line] 且 start<=end，"
                "用 update_matrix_item 修正",
            ))
        if "locator" in ref:
            issues.append(_warning(
                "structure", target, "deprecated_locator",
                f"source_refs[{index}] 使用了已废弃的 locator，请改用 line_span",
            ))
        if "quote" in ref:
            issues.append(_warning(
                "structure", target, "deprecated_quote",
                f"source_refs[{index}] 使用了已废弃的 quote，请删除（源文摘录由 line_span 复原）",
            ))


def _line_span_problem(span) -> str | None:
    """返回 line_span 的问题描述；合法时返回 None（判定对齐原脚本 check_line_span）。"""
    if not isinstance(span, list) or len(span) != 2:
        return "line_span 必须是两元素列表 [start_line, end_line]"
    start, end = span
    if (
        not isinstance(start, int) or isinstance(start, bool)
        or not isinstance(end, int) or isinstance(end, bool)
    ):
        return "line_span 两个值必须是整数"
    if start < 1 or end < 1:
        return "line_span 必须是 1 起始的正行号"
    if start > end:
        return "line_span 的 start 必须小于等于 end"
    return None


# —— 组装一致性（原 assemble_matrix.py 的 id 唯一 / 区段合法 / meta 类型冲突检查） ——


def validate_consistency(matrix_type: str, meta: dict, items: list[MatrixItem]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    allowed = ALLOWED_SECTIONS[matrix_type]
    payload_ids: Counter[str] = Counter()
    for item in items:
        target = f"{matrix_type}/{item.item_id}"
        if item.section not in allowed:
            issues.append(_error(
                "consistency", target, "invalid_section",
                f"{matrix_type} 不接受区段 {item.section}（可用：{', '.join(allowed)}）",
                hint="用 drop_matrix_item 删除该行后按正确区段重新 submit_matrix_records",
            ))
        if item.section != "items":
            continue
        payload_id = item.payload.get("id")
        if not payload_id:
            issues.append(_error(
                "consistency", target, "missing_item_id",
                "items 区段条目的 payload 缺少 id",
                hint=f"用 update_matrix_item 无法补 id，请 drop 后以 id={item.item_id} 重新提交",
            ))
            continue
        payload_ids[str(payload_id)] += 1
        if str(payload_id) != item.item_id:
            issues.append(_error(
                "consistency", target, "id_mismatch",
                f"payload.id ({payload_id}) 与条目 id ({item.item_id}) 不一致",
                hint="用 move_matrix_item（同矩阵内指定 new_id）统一两者",
            ))
    for payload_id, count in payload_ids.items():
        if count > 1:
            issues.append(_error(
                "consistency", f"{matrix_type}/{payload_id}", "duplicate_id",
                f"id {payload_id!r} 重复出现 {count} 次",
                hint="保留一条，其余用 drop_matrix_item 删除或 move_matrix_item 换 id",
            ))
    _check_meta_types(META_SKELETONS[matrix_type], meta, "", matrix_type, issues)
    return issues


def _check_meta_types(skeleton: dict, meta: dict, path: str, matrix_type: str,
                      issues: list[ValidationIssue]) -> None:
    for key, value in meta.items():
        expected = skeleton.get(key)
        child_path = f"{path}.{key}" if path else key
        if isinstance(expected, dict):
            if isinstance(value, dict):
                _check_meta_types(expected, value, child_path, matrix_type, issues)
            else:
                issues.append(_error(
                    "consistency", matrix_type, "meta_type_conflict",
                    f"meta 的 {child_path} 必须是对象，得到 {type(value).__name__}",
                    hint=f"用 set_matrix_meta 以对象形式重设 {child_path}；记录列表走区段行而非 meta",
                ))
        elif isinstance(expected, list) and not isinstance(value, list):
            issues.append(_error(
                "consistency", matrix_type, "meta_type_conflict",
                f"meta 的 {child_path} 必须是列表，得到 {type(value).__name__}",
                hint=f"用 set_matrix_meta 以列表形式重设 {child_path}",
            ))


# —— 源文保真（原 verify_source_fidelity.py） ——


def validate_source_fidelity(
    matrix_type: str,
    items: list[MatrixItem],
    *,
    documents: Iterable[DocumentRecord],
    workspace_root: Path | str,
    thresholds: FidelityThresholds | None = None,
) -> list[ValidationIssue]:
    """经 document registry 解析 workspace 源文路径，按 line_span 比对字面重叠。"""
    field = TEXT_FIELDS.get(matrix_type)
    if field is None:
        return []
    thresholds = thresholds or FidelityThresholds()
    root = Path(workspace_root)
    doc_paths = {doc.id: doc.path for doc in documents}
    issues: list[ValidationIssue] = []
    line_cache: dict[str, list[str] | None] = {}
    for item in items:
        if item.section != "items":
            continue
        _check_item_fidelity(
            matrix_type, item, field, doc_paths, root, line_cache, thresholds, issues
        )
    return issues


def _check_item_fidelity(
    matrix_type: str,
    item: MatrixItem,
    field: str,
    doc_paths: dict[str, str],
    root: Path,
    line_cache: dict[str, list[str] | None],
    thresholds: FidelityThresholds,
    issues: list[ValidationIssue],
) -> None:
    target = f"{matrix_type}/{item.item_id}"
    field_text = item.payload.get(field)
    if not isinstance(field_text, str) or not field_text.strip():
        issues.append(_warning(
            "fidelity", target, "empty_text_field",
            f"{field} 为空，无法做源文保真比对",
            hint=f"用 update_matrix_item 按源文补写 {field}",
        ))
        return

    source_text, locations = _collect_source_text(
        target, field, item.payload.get("source_refs"), doc_paths, root, line_cache, issues
    )
    if not source_text:
        issues.append(_error(
            "fidelity", target, "no_valid_source_text",
            "没有任何 source_ref 能解析出源文文本",
            hint="逐条修复上面报出的 source_refs 问题（document_id / line_span / 源文件路径）后重试",
        ))
        return

    score = _fidelity_score(field_text, source_text)
    effective_pass = thresholds.pass_threshold
    if _is_high_risk(matrix_type, item.payload):
        effective_pass = max(effective_pass, thresholds.high_risk_threshold)

    detail = {
        "coverage": round(score["coverage"], 4),
        "sequence_coverage": round(score["sequence_coverage"], 4),
        "ngram_recall": round(score["ngram_recall"], 4),
        "normalized_length": score["normalized_length"],
        "pass_threshold": effective_pass,
        "warn_threshold": thresholds.warn_threshold,
        "locations": locations,
        "field_preview": _preview(field_text),
        "source_preview": _preview(source_text),
    }

    if score["normalized_length"] < thresholds.min_chars:
        issues.append(_warning(
            "fidelity", target, "text_too_short_for_reliable_fidelity",
            f"{field} 规范化后不足 {thresholds.min_chars} 字符，保真度不可靠",
            hint="过短条目请人工核对源文，或合并进同来源的相邻条目",
            detail=detail,
        ))
        return

    fix_hint = (
        "对照 detail.source_preview 核对源文：用 update_matrix_item 修正 line_span "
        f"或把 {field} 还原为源文措辞（解释性内容挪到 notes）；"
        "多条款糅合的条目用 drop_matrix_item + submit_matrix_records 拆分为多条各自源文可回溯的条目"
    )
    if score["coverage"] < thresholds.warn_threshold:
        issues.append(_error(
            "fidelity", target, "low_source_overlap",
            f"{field} 与其 line_span 指向的源文重叠度过低"
            f"（coverage={detail['coverage']}，需 >={effective_pass}）",
            hint=fix_hint,
            detail=detail,
        ))
    elif score["coverage"] < effective_pass:
        issues.append(_warning(
            "fidelity", target, "borderline_source_overlap",
            f"{field} 有源文支撑但低于通过阈值"
            f"（coverage={detail['coverage']}，需 >={effective_pass}）",
            hint=fix_hint,
            detail=detail,
        ))


def _collect_source_text(
    target: str,
    field: str,
    refs,
    doc_paths: dict[str, str],
    root: Path,
    line_cache: dict[str, list[str] | None],
    issues: list[ValidationIssue],
) -> tuple[str, list[dict]]:
    if not isinstance(refs, list) or not refs:
        issues.append(_error(
            "fidelity", target, "missing_source_refs",
            "source_refs 为空或不是列表",
            hint="用 update_matrix_item 补充 [{document_id, line_span}]",
        ))
        return "", []

    chunks: list[str] = []
    locations: list[dict] = []
    for index, ref in enumerate(refs):
        if not isinstance(ref, dict):
            issues.append(_error(
                "fidelity", target, "invalid_source_ref",
                f"source_refs[{index}] 不是对象",
                hint="用 update_matrix_item 修正为 {document_id, line_span} 对象",
            ))
            continue
        document_id = ref.get("document_id")
        line_span = ref.get("line_span")
        if not isinstance(document_id, str) or not document_id:
            issues.append(_error(
                "fidelity", target, "missing_document_id",
                f"source_refs[{index}] 缺少 document_id",
                hint="用 list_documents 查已注册文档 id 后 update_matrix_item 补齐",
            ))
            continue
        if _line_span_problem(line_span) is not None:
            issues.append(_error(
                "fidelity", target, "invalid_line_span",
                f"source_refs[{index}] 的 line_span 必须是 [start_line, end_line]",
                hint="用 update_matrix_item 修正 line_span",
                detail={"document_id": document_id, "line_span": line_span},
            ))
            continue
        rel_path = doc_paths.get(document_id)
        if rel_path is None:
            issues.append(_error(
                "fidelity", target, "unknown_document_id",
                f"document_id {document_id!r} 不在 document registry 中",
                hint="先用 register_document 注册该源文件，或改引用 list_documents 中已注册的 id",
                detail={"document_id": document_id, "line_span": line_span},
            ))
            continue
        lines = _load_source_lines(target, rel_path, root, line_cache, issues)
        if lines is None:
            continue
        start, end = line_span
        if end > len(lines):
            issues.append(_error(
                "fidelity", target, "line_span_out_of_bounds",
                f"line_span {line_span} 超出源文行数 {len(lines)}",
                hint="用 update_matrix_item 把 line_span 修正到源文实际行号范围内",
                detail={
                    "document_id": document_id,
                    "path": rel_path,
                    "line_span": line_span,
                    "line_count": len(lines),
                },
            ))
            continue
        chunks.append("\n".join(lines[start - 1 : end]))
        locations.append({"document_id": document_id, "path": rel_path, "line_span": line_span})
    return "\n".join(chunks), locations


def _load_source_lines(
    target: str,
    rel_path: str,
    root: Path,
    line_cache: dict[str, list[str] | None],
    issues: list[ValidationIssue],
) -> list[str] | None:
    if rel_path not in line_cache:
        path = Path(rel_path) if Path(rel_path).is_absolute() else root / rel_path
        try:
            line_cache[rel_path] = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            line_cache[rel_path] = None
        except UnicodeDecodeError:
            line_cache[rel_path] = None
    lines = line_cache[rel_path]
    if lines is None:
        issues.append(_error(
            "fidelity", target, "source_file_missing",
            f"源文件不存在或不可读：{rel_path}",
            hint="确认 register_document 登记的路径相对 project workspace 存在且为 UTF-8 文本",
            detail={"path": rel_path},
        ))
    return lines


# —— 保真评分（逐字对齐原脚本，保证同语料同判定） ——


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return "".join(ch for ch in normalized if ch.isalnum())


def _ngrams(text: str, size: int) -> list[str]:
    if not text:
        return []
    if len(text) <= size:
        return list(text)
    return [text[index : index + size] for index in range(len(text) - size + 1)]


def _ngram_recall(query: str, source: str) -> float:
    if not query:
        return 1.0
    size = min(3, len(query))
    query_counts = Counter(_ngrams(query, size))
    source_counts = Counter(_ngrams(source, size))
    overlap = sum(min(count, source_counts[gram]) for gram, count in query_counts.items())
    total = sum(query_counts.values())
    return overlap / total if total else 0.0


def _sequence_coverage(query: str, source: str) -> float:
    if not query:
        return 1.0
    matcher = SequenceMatcher(None, query, source, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / len(query)


def _fidelity_score(field_text: str, source_text: str) -> dict:
    query = _normalize_text(field_text)
    source = _normalize_text(source_text)
    if not query:
        return {"coverage": 0.0, "sequence_coverage": 0.0, "ngram_recall": 0.0, "normalized_length": 0}
    sequence = _sequence_coverage(query, source)
    recall = _ngram_recall(query, source)
    return {
        "coverage": min(sequence, recall),
        "sequence_coverage": sequence,
        "ngram_recall": recall,
        "normalized_length": len(query),
    }


def _is_high_risk(matrix_type: str, payload: dict) -> bool:
    return (
        matrix_type == "scoring"
        or payload.get("mandatory") is True
        or payload.get("mandatory_gate") is True
        or payload.get("risk_level") == "high"
        or payload.get("category") in HIGH_RISK_CATEGORIES
    )


def _preview(text: str, limit: int = 160) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


# —— 全套聚合与 publish 门禁 ——


def run_full_validation(
    matrix_type: str,
    *,
    meta: dict,
    items: list[MatrixItem],
    documents: Iterable[DocumentRecord],
    workspace_root: Path | str,
    thresholds: FidelityThresholds | None = None,
) -> ValidationReport:
    issues = [
        *validate_structure(matrix_type, meta, items),
        *validate_consistency(matrix_type, meta, items),
        *validate_source_fidelity(
            matrix_type, items,
            documents=documents, workspace_root=workspace_root, thresholds=thresholds,
        ),
    ]
    status = "fail" if any(i.severity == "error" for i in issues) else "pass"
    return ValidationReport(
        matrix_type=matrix_type, status=status, issues=issues, checked_items=len(items)
    )


def cross_matrix_issues(metas: dict[str, dict]) -> list[ValidationIssue]:
    """跨矩阵一致性（原脚本 check_cross_matrix）：project_name / project_id 不一致时告警。"""
    issues: list[ValidationIssue] = []
    for key, code in (("project_name", "inconsistent_project_name"),
                      ("project_id", "inconsistent_project_id")):
        values = {mt: meta.get(key) for mt, meta in metas.items() if meta.get(key)}
        if len(set(values.values())) > 1:
            issues.append(_warning(
                "cross", "all", code,
                f"各矩阵 {key} 不一致：{values}",
                hint=f"用 set_matrix_meta 统一各矩阵的 {key}",
            ))
    return issues


class ValidationFailedError(AssetError):
    """publish 门禁拒绝：任一校验 error 即拒绝，report 携带全量结构化报告。"""

    def __init__(self, report: ValidationReport):
        errors = report.errors
        preview = "；".join(f"[{i.target}] {i.message}" for i in errors[:3])
        if len(errors) > 3:
            preview += f"（等 {len(errors)} 条）"
        super().__init__(
            "validation_failed",
            f"{report.matrix_type} 校验未通过，{len(errors)} 条错误：{preview}",
            hint="按 report.issues 中各条 hint 逐项修复（validate_matrix 可单独重跑）后再 publish",
        )
        self.report = report


def make_publish_gate(
    matrix_type: str,
    *,
    documents: Iterable[DocumentRecord],
    workspace_root: Path | str,
    thresholds: FidelityThresholds | None = None,
    on_report: Callable[[ValidationReport], None] | None = None,
) -> Callable[[dict, list[MatrixItem]], None]:
    """构造 AssetService.publish 的 validate 接缝：全套校验，任一 error 抛 ValidationFailedError。

    on_report 在判定前拿到完整报告（无论 pass/fail），供调用方落校验摘要等旁路记录。
    """
    documents = list(documents)

    def gate(meta: dict, items: list[MatrixItem]) -> None:
        report = run_full_validation(
            matrix_type,
            meta=meta,
            items=items,
            documents=documents,
            workspace_root=workspace_root,
            thresholds=thresholds,
        )
        if on_report is not None:
            on_report(report)
        if report.status != "pass":
            raise ValidationFailedError(report)

    return gate
