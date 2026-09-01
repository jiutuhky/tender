"""三校验器单测：结构 / 组装一致性 / 源文保真（票 02）。

与原脚本的同语料同判定见 test_validators_parity.py；本文件直接断言各校验点。
"""

from __future__ import annotations

import pytest

from hagent.assets.model import DocumentRecord, MatrixItem
from hagent.assets.validators import (
    FidelityThresholds,
    ValidationReport,
    cross_matrix_issues,
    run_full_validation,
    validate_consistency,
    validate_source_fidelity,
    validate_structure,
)

# —— 构造助手 ——

SOURCE_LINES = [
    "# 招标文件",
    "",
    "投标人须具备有效的信息系统建设资质，并提供近三年同类项目业绩证明。",
    "系统须支持每秒一千次并发查询，响应时间不超过两百毫秒。",
    "所有数据须在境内存储，并通过等级保护三级测评。",
    "",
    "交付物包括系统源代码、部署手册与培训材料。",
    "评标采用综合评分法，技术分占百分之六十。",
    "投标保证金为人民币五万元整。",
]


def row(
    matrix_type: str,
    item_id: str,
    payload: dict,
    *,
    section: str = "items",
    stage: str = "draft",
) -> MatrixItem:
    return MatrixItem(
        project_id="p-1",
        matrix_type=matrix_type,
        stage=stage,
        item_id=item_id,
        section=section,
        payload=payload,
        response_status=None,
        response_note=None,
        confirmed=False,
        version=1,
    )


def tech_payload(item_id: str, **overrides) -> dict:
    payload = {
        "id": item_id,
        "category": "function",
        "title": "示例条目",
        "requirement_text": SOURCE_LINES[3],
        "mandatory": False,
        "response_required": True,
        "source_refs": [{"document_id": "doc-001", "line_span": [4, 4]}],
        "confidence": "high",
    }
    payload.update(overrides)
    return payload


def valid_meta() -> dict:
    return {
        "project_id": "ZB-2026-001",
        "project_name": "示例信息化项目",
        "extraction_summary": {"status": "complete", "confidence": "high", "warnings": []},
    }


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "tender.md").write_text("\n".join(SOURCE_LINES), encoding="utf-8")
    return tmp_path


@pytest.fixture
def documents():
    return [
        DocumentRecord(
            id="doc-001",
            project_id="p-1",
            path="docs/tender.md",
            sha256="0" * 64,
            doc_type="tender",
            registered_at="2026-07-13T00:00:00+00:00",
        )
    ]


def codes(issues, *, severity=None):
    return {
        (i.target, i.code)
        for i in issues
        if severity is None or i.severity == severity
    }


# —— 结构校验 ——


class TestStructure:
    def test_valid_matrix_has_no_issues(self):
        items = [row("technical", "TECH-001", tech_payload("TECH-001"))]
        assert validate_structure("technical", valid_meta(), items) == []

    def test_missing_meta_fields(self):
        issues = validate_structure("technical", {}, [])
        assert {i.code for i in issues} == {"missing_meta_field"}
        assert {i.target for i in issues} == {"technical"}
        assert len(issues) == 3  # project_id / project_name / extraction_summary

    def test_extraction_summary_enums(self):
        meta = valid_meta()
        meta["extraction_summary"] = {"status": "done", "confidence": "sure", "warnings": "无"}
        issues = validate_structure("technical", meta, [])
        assert {i.code for i in issues} == {
            "invalid_summary_status",
            "invalid_summary_confidence",
            "invalid_summary_warnings",
        }

    def test_extraction_summary_must_be_object(self):
        meta = valid_meta()
        meta["extraction_summary"] = "complete"
        issues = validate_structure("technical", meta, [])
        assert {i.code for i in issues} == {"invalid_extraction_summary"}

    def test_extraction_summary_null_is_rejected(self):
        # 对齐原脚本：显式 null 同样是 error，不得绕过枚举校验
        meta = valid_meta()
        meta["extraction_summary"] = None
        issues = validate_structure("technical", meta, [])
        assert {i.code for i in issues} == {"invalid_extraction_summary"}
        assert {i.severity for i in issues} == {"error"}

    def test_missing_item_fields_and_bad_enums(self):
        payload = tech_payload("TECH-002")
        del payload["title"]
        del payload["confidence"]
        items = [row("technical", "TECH-002", payload)]
        issues = validate_structure("technical", valid_meta(), items)
        assert ("technical/TECH-002", "missing_item_field") in codes(issues)
        # confidence 缺失同时触发枚举校验（对齐原脚本双报）
        assert ("technical/TECH-002", "invalid_confidence") in codes(issues)

    def test_boolean_fields(self):
        payload = tech_payload("TECH-003", mandatory="yes", response_required=1)
        issues = validate_structure("technical", valid_meta(), [row("technical", "TECH-003", payload)])
        assert {i.code for i in issues} == {"invalid_mandatory", "invalid_response_required"}

    def test_scoring_max_score(self):
        payload = {
            "id": "SCORE-001",
            "group": "technical",
            "title": "技术方案",
            "max_score": "十分",
            "scoring_rule": SOURCE_LINES[7],
            "scoring_method": "subjective",
            "source_refs": [{"document_id": "doc-001", "line_span": [8, 8]}],
            "confidence": "high",
        }
        issues = validate_structure("scoring", valid_meta(), [row("scoring", "SCORE-001", payload)])
        assert {i.code for i in issues} == {"invalid_max_score"}

    def test_source_refs_shapes(self):
        cases = {
            "TECH-010": tech_payload("TECH-010", source_refs="not-a-list"),
            "TECH-011": tech_payload("TECH-011", source_refs=[]),
            "TECH-012": tech_payload("TECH-012", source_refs=["ref"]),
            "TECH-013": tech_payload("TECH-013", source_refs=[{"line_span": [1, 2]}]),
            "TECH-014": tech_payload(
                "TECH-014", source_refs=[{"document_id": "doc-001", "line_span": [0, 2]}]
            ),
            "TECH-015": tech_payload(
                "TECH-015", source_refs=[{"document_id": "doc-001", "line_span": [5, 2]}]
            ),
        }
        items = [row("technical", item_id, payload) for item_id, payload in cases.items()]
        issues = validate_structure("technical", valid_meta(), items)
        got = codes(issues, severity="error")
        assert got == {
            ("technical/TECH-010", "invalid_source_refs"),
            ("technical/TECH-011", "empty_source_refs"),
            ("technical/TECH-012", "invalid_source_ref"),
            ("technical/TECH-013", "missing_document_id"),
            ("technical/TECH-014", "invalid_line_span"),
            ("technical/TECH-015", "invalid_line_span"),
        }

    def test_deprecated_ref_keys_warn(self):
        payload = tech_payload(
            "TECH-020",
            source_refs=[
                {"document_id": "doc-001", "line_span": [4, 4], "quote": "原文", "locator": "第4行"}
            ],
        )
        issues = validate_structure("technical", valid_meta(), [row("technical", "TECH-020", payload)])
        assert codes(issues, severity="warning") == {
            ("technical/TECH-020", "deprecated_quote"),
            ("technical/TECH-020", "deprecated_locator"),
        }
        assert codes(issues, severity="error") == set()

    def test_basic_info_project(self):
        # 对齐原脚本：project 缺失 / null / 非对象均为 error
        issues = validate_structure("basic_info", valid_meta(), [])
        assert {i.code for i in issues} == {"invalid_project"}

        meta = valid_meta()
        meta["project"] = None
        issues = validate_structure("basic_info", meta, [])
        assert {i.code for i in issues} == {"invalid_project"}

        meta = valid_meta()
        meta["project"] = "示例项目"
        issues = validate_structure("basic_info", meta, [])
        assert {i.code for i in issues} == {"invalid_project"}

        meta["project"] = {"name": "示例项目"}
        issues = validate_structure("basic_info", meta, [])
        assert {i.severity for i in issues} == {"warning"}
        assert {i.code for i in issues} == {"missing_project_field"}

    def test_issues_carry_hint(self):
        issues = validate_structure("technical", {}, [])
        assert all(i.hint for i in issues)


# —— 可选字段（给了值才核，缺省不报） ——


class TestOptionalFields:
    def test_param_nature_valid_values(self):
        items = [
            row("technical", "TECH-001", tech_payload("TECH-001", param_nature="★", mandatory=True)),
            row("technical", "TECH-002", tech_payload("TECH-002", param_nature="▲")),
            row("technical", "TECH-003", tech_payload("TECH-003", param_nature=None)),
            row("technical", "TECH-004", tech_payload("TECH-004")),  # 存量：无此字段
        ]
        assert validate_structure("technical", valid_meta(), items) == []

    def test_param_nature_invalid_value(self):
        # 未归一的 OCR 变体不放行——归一在抽取侧做
        payload = tech_payload("TECH-005", param_nature="△")
        issues = validate_structure("technical", valid_meta(), [row("technical", "TECH-005", payload)])
        assert codes(issues) == {("technical/TECH-005", "invalid_param_nature")}
        assert {i.severity for i in issues} == {"error"}

    def test_param_nature_mandatory_mismatch_warns(self):
        items = [
            row("technical", "TECH-006", tech_payload("TECH-006", param_nature="★", mandatory=False)),
            row("technical", "TECH-007", tech_payload("TECH-007", param_nature="▲", mandatory=True)),
        ]
        issues = validate_structure("technical", valid_meta(), items)
        assert codes(issues, severity="warning") == {
            ("technical/TECH-006", "param_nature_mandatory_mismatch"),
            ("technical/TECH-007", "param_nature_mandatory_mismatch"),
        }
        assert codes(issues, severity="error") == set()

    def test_param_nature_applies_to_business_too(self):
        payload = tech_payload("BIZ-001", param_nature="invalid")
        issues = validate_structure("business", valid_meta(), [row("business", "BIZ-001", payload)])
        assert ("business/BIZ-001", "invalid_param_nature") in codes(issues)

    def test_scoring_optional_string_fields(self):
        def scoring_payload(item_id: str, **overrides) -> dict:
            payload = {
                "id": item_id,
                "group": "technical",
                "title": "技术方案",
                "max_score": 20,
                "scoring_rule": SOURCE_LINES[7],
                "scoring_method": "subjective",
                "source_refs": [{"document_id": "doc-001", "line_span": [8, 8]}],
                "confidence": "high",
            }
            payload.update(overrides)
            return payload

        ok = [
            row("scoring", "S-1", scoring_payload("S-1", related_format="「技术方案」相关证明材料")),
            row("scoring", "S-2", scoring_payload("S-2", related_format=None, subgroup="技术方案")),
            row("scoring", "S-3", scoring_payload("S-3")),
        ]
        assert validate_structure("scoring", valid_meta(), ok) == []

        bad = [
            row("scoring", "S-4", scoring_payload("S-4", related_format=["技术方案"])),
            row("scoring", "S-5", scoring_payload("S-5", subgroup=1)),
        ]
        assert codes(validate_structure("scoring", valid_meta(), bad)) == {
            ("scoring/S-4", "invalid_related_format"),
            ("scoring/S-5", "invalid_subgroup"),
        }

    def test_compliance_response_format(self):
        section = "compliance_overview.conformity_review"
        ok = [
            row("business", "CONF-1", {"text": "符合性审查项", "response_format": "格式二"},
                section=section),
            row("business", "CONF-2", {"text": "符合性审查项"}, section=section),
        ]
        assert validate_structure("business", valid_meta(), ok) == []

        bad = row("business", "CONF-3", {"text": "x", "response_format": 2}, section=section)
        assert codes(validate_structure("business", valid_meta(), [bad])) == {
            ("business/CONF-3", "invalid_response_format")
        }


# —— 偏离计分规则行（新区段，契约即校验） ——


def deviation_payload(item_id: str, **overrides) -> dict:
    payload = {
        "id": item_id,
        "direction": "negative",
        "applies_to": ["▲"],
        "delta_per_item": 0.3,
        "cap": None,
        "threshold_items": None,
        "effect_text": None,
        "rule_text": SOURCE_LINES[7],
        "source_refs": [{"document_id": "doc-001", "line_span": [8, 8]}],
    }
    payload.update(overrides)
    return payload


def deviation_row(item_id: str, **overrides) -> MatrixItem:
    return row(
        "scoring", item_id, deviation_payload(item_id, **overrides),
        section="evaluation.deviation_rules",
    )


class TestDeviationRules:
    def test_valid_rules_pass(self):
        items = [
            deviation_row("DEVR-001", direction="positive", applies_to=None,
                          delta_per_item=2, cap=10),
            deviation_row("DEVR-002"),
            deviation_row("DEVR-003", direction="zero_out", applies_to=None,
                          delta_per_item=None, threshold_items=3,
                          effect_text="技术指标部分得分为0分"),
            deviation_row("DEVR-004", applies_to=["★", "▲", "general"]),
        ]
        assert validate_structure("scoring", valid_meta(), items) == []

    def test_direction_required_and_enumerated(self):
        items = [
            deviation_row("DEVR-010", direction=None),
            deviation_row("DEVR-011", direction="deduct"),
        ]
        assert codes(validate_structure("scoring", valid_meta(), items), severity="error") == {
            ("scoring/DEVR-010", "invalid_deviation_direction"),
            ("scoring/DEVR-011", "invalid_deviation_direction"),
        }

    def test_applies_to_shape(self):
        items = [
            deviation_row("DEVR-020", applies_to="▲"),  # 非列表
            deviation_row("DEVR-021", applies_to=["重要"]),  # 元素不在枚举内
        ]
        assert codes(validate_structure("scoring", valid_meta(), items)) == {
            ("scoring/DEVR-020", "invalid_deviation_applies_to"),
            ("scoring/DEVR-021", "invalid_deviation_applies_to"),
        }

    def test_number_fields(self):
        items = [
            deviation_row("DEVR-030", delta_per_item="0.3"),
            deviation_row("DEVR-031", cap=True),  # bool 不是数字
            deviation_row("DEVR-032", direction="zero_out", threshold_items=3.5),
        ]
        assert codes(validate_structure("scoring", valid_meta(), items), severity="error") == {
            ("scoring/DEVR-030", "invalid_deviation_number"),
            ("scoring/DEVR-031", "invalid_deviation_number"),
            ("scoring/DEVR-032", "invalid_deviation_number"),
        }

    def test_negative_number_warns(self):
        # 字段承载绝对值，加/扣方向由 direction 表达
        items = [deviation_row("DEVR-040", delta_per_item=-0.3)]
        issues = validate_structure("scoring", valid_meta(), items)
        assert codes(issues, severity="warning") == {
            ("scoring/DEVR-040", "negative_deviation_number")
        }
        assert codes(issues, severity="error") == set()

    def test_threshold_without_zero_out_warns(self):
        items = [deviation_row("DEVR-050", threshold_items=3)]
        issues = validate_structure("scoring", valid_meta(), items)
        assert codes(issues, severity="warning") == {
            ("scoring/DEVR-050", "threshold_without_zero_out")
        }

    def test_rule_text_required(self):
        items = [
            deviation_row("DEVR-060", rule_text=None),
            deviation_row("DEVR-061", rule_text="   "),
        ]
        assert codes(validate_structure("scoring", valid_meta(), items), severity="error") == {
            ("scoring/DEVR-060", "missing_rule_text"),
            ("scoring/DEVR-061", "missing_rule_text"),
        }

    def test_source_refs_required_and_shaped(self):
        items = [
            deviation_row("DEVR-070", source_refs=None),
            deviation_row("DEVR-071", source_refs=[]),
            deviation_row("DEVR-072", source_refs=[{"line_span": [1, 2]}]),
        ]
        assert codes(validate_structure("scoring", valid_meta(), items), severity="error") == {
            ("scoring/DEVR-070", "missing_source_refs"),
            ("scoring/DEVR-071", "empty_source_refs"),
            ("scoring/DEVR-072", "missing_document_id"),
        }

    def test_issues_carry_hint(self):
        items = [deviation_row("DEVR-080", direction=None, rule_text=None, source_refs=None)]
        issues = validate_structure("scoring", valid_meta(), items)
        assert len(issues) == 3
        assert all(i.hint for i in issues)

    def test_section_is_allowed_for_scoring_only(self):
        item = deviation_row("DEVR-090")
        assert validate_consistency("scoring", valid_meta(), [item]) == []
        stray = row("technical", "DEVR-090", {"direction": "positive"},
                    section="evaluation.deviation_rules")
        assert codes(validate_consistency("technical", valid_meta(), [stray])) == {
            ("technical/DEVR-090", "invalid_section")
        }

    def test_meta_skeleton_type_conflict(self):
        meta = valid_meta()
        meta["evaluation"] = {"deviation_rules": "负偏离每项扣2分"}  # 应为列表
        assert codes(validate_consistency("scoring", meta, [])) == {
            ("scoring", "meta_type_conflict")
        }


# —— 组装一致性 ——


class TestConsistency:
    def test_clean_items_pass(self):
        items = [row("technical", "TECH-001", tech_payload("TECH-001"))]
        assert validate_consistency("technical", valid_meta(), items) == []

    def test_invalid_section(self):
        items = [row("technical", "extras:1", {"note": "x"}, section="extras")]
        issues = validate_consistency("technical", valid_meta(), items)
        assert codes(issues) == {("technical/extras:1", "invalid_section")}

    def test_items_payload_id_rules(self):
        items = [
            row("technical", "TECH-001", tech_payload("TECH-001")),
            # payload 无 id
            row("technical", "TECH-002", {k: v for k, v in tech_payload("TECH-002").items() if k != "id"}),
            # payload id 与行 item_id 不一致
            row("technical", "TECH-003", tech_payload("TECH-099")),
        ]
        issues = validate_consistency("technical", valid_meta(), items)
        got = codes(issues)
        assert ("technical/TECH-002", "missing_item_id") in got
        assert ("technical/TECH-003", "id_mismatch") in got

    def test_duplicate_payload_ids(self):
        items = [
            row("technical", "TECH-001", tech_payload("TECH-001")),
            row("technical", "TECH-001-bis", tech_payload("TECH-001")),
        ]
        issues = validate_consistency("technical", valid_meta(), items)
        assert any(i.code == "duplicate_id" and "TECH-001" in i.message for i in issues)

    def test_meta_type_conflicts(self):
        meta = valid_meta()
        meta["evaluation"] = "综合评分法"  # 应为对象
        issues = validate_consistency("scoring", meta, [])
        assert codes(issues) == {("scoring", "meta_type_conflict")}
        assert "evaluation" in issues[0].message

        meta = valid_meta()
        meta["evaluation"] = {"pass_fail_rules": "无"}  # 应为列表
        issues = validate_consistency("scoring", meta, [])
        assert codes(issues) == {("scoring", "meta_type_conflict")}

    def test_meta_nested_object_conflict(self):
        meta = valid_meta()
        meta["project"] = {"budget": "五万元"}  # budget 应为对象
        issues = validate_consistency("basic_info", meta, [])
        assert codes(issues) == {("basic_info", "meta_type_conflict")}

    def test_unknown_meta_keys_allowed(self):
        meta = valid_meta()
        meta["custom_note"] = "任意扩展键"
        assert validate_consistency("technical", meta, []) == []


# —— 源文保真 ——


class TestFidelity:
    def check(self, items, documents, workspace, **kw):
        return validate_source_fidelity(
            "technical", items, documents=documents, workspace_root=workspace, **kw
        )

    def test_verbatim_text_passes(self, workspace, documents):
        items = [row("technical", "TECH-001", tech_payload("TECH-001"))]
        assert self.check(items, documents, workspace) == []

    def test_fabricated_text_reports_low_overlap_with_excerpt_and_hint(self, workspace, documents):
        payload = tech_payload(
            "TECH-002",
            requirement_text="本项目要求供应商提供全套量子加密通信模块并附带十年质保服务承诺。",
        )
        issues = self.check([row("technical", "TECH-002", payload)], documents, workspace)
        assert codes(issues, severity="error") == {("technical/TECH-002", "low_source_overlap")}
        issue = issues[0]
        # 报告含源 span 摘录与建议操作（update line_span / 拆分条目）
        assert issue.detail is not None
        assert issue.detail["source_preview"]
        assert SOURCE_LINES[3][:10] in issue.detail["source_preview"]
        assert issue.detail["locations"] == [
            {"document_id": "doc-001", "path": "docs/tender.md", "line_span": [4, 4]}
        ]
        assert "line_span" in issue.hint and "拆分" in issue.hint

    def test_unknown_document_id(self, workspace, documents):
        payload = tech_payload(
            "TECH-003", source_refs=[{"document_id": "doc-nope", "line_span": [4, 4]}]
        )
        issues = self.check([row("technical", "TECH-003", payload)], documents, workspace)
        got = codes(issues, severity="error")
        assert ("technical/TECH-003", "unknown_document_id") in got
        assert ("technical/TECH-003", "no_valid_source_text") in got

    def test_line_span_out_of_bounds(self, workspace, documents):
        payload = tech_payload(
            "TECH-004", source_refs=[{"document_id": "doc-001", "line_span": [4, 999]}]
        )
        issues = self.check([row("technical", "TECH-004", payload)], documents, workspace)
        got = codes(issues, severity="error")
        assert ("technical/TECH-004", "line_span_out_of_bounds") in got

    def test_source_file_missing(self, workspace, documents):
        gone = [
            DocumentRecord(
                id="doc-001",
                project_id="p-1",
                path="docs/removed.md",
                sha256="0" * 64,
                doc_type="tender",
                registered_at="2026-07-13T00:00:00+00:00",
            )
        ]
        items = [row("technical", "TECH-005", tech_payload("TECH-005"))]
        issues = self.check(items, gone, workspace)
        got = codes(issues, severity="error")
        assert ("technical/TECH-005", "source_file_missing") in got

    def test_short_text_warns(self, workspace, documents):
        payload = tech_payload("TECH-006", requirement_text="短文本")
        issues = self.check([row("technical", "TECH-006", payload)], documents, workspace)
        assert codes(issues, severity="warning") == {
            ("technical/TECH-006", "text_too_short_for_reliable_fidelity")
        }
        assert codes(issues, severity="error") == set()

    def test_empty_text_warns(self, workspace, documents):
        payload = tech_payload("TECH-007", requirement_text="  ")
        issues = self.check([row("technical", "TECH-007", payload)], documents, workspace)
        assert codes(issues) == {("technical/TECH-007", "empty_text_field")}

    def test_basic_info_skipped(self, workspace, documents):
        issues = validate_source_fidelity(
            "basic_info", [], documents=documents, workspace_root=workspace
        )
        assert issues == []

    def test_thresholds_configurable(self, workspace, documents):
        # 阈值拉到 0 后，任何非空文本都能通过
        payload = tech_payload("TECH-008", requirement_text="与源文完全无关的一段足够长的描述文字。")
        issues = self.check(
            [row("technical", "TECH-008", payload)],
            documents,
            workspace,
            thresholds=FidelityThresholds(pass_threshold=0.0, warn_threshold=0.0),
        )
        assert issues == []


# —— 全套聚合 ——


class TestFullValidation:
    def test_report_shape(self, workspace, documents):
        items = [
            row("technical", "TECH-001", tech_payload("TECH-001")),
            row(
                "technical",
                "TECH-002",
                tech_payload("TECH-002", requirement_text="完全凭空捏造的一条与源文无关的要求。"),
            ),
        ]
        report = run_full_validation(
            "technical",
            meta=valid_meta(),
            items=items,
            documents=documents,
            workspace_root=workspace,
        )
        assert isinstance(report, ValidationReport)
        assert report.status == "fail"
        assert report.checked_items == 2
        assert report.errors and not report.warnings
        data = report.to_dict()
        assert data["matrix_type"] == "technical"
        assert data["status"] == "fail"
        issue = data["issues"][0]
        assert {"severity", "validator", "target", "code", "message"} <= issue.keys()

    def test_pass_report(self, workspace, documents):
        items = [row("technical", "TECH-001", tech_payload("TECH-001"))]
        report = run_full_validation(
            "technical",
            meta=valid_meta(),
            items=items,
            documents=documents,
            workspace_root=workspace,
        )
        assert report.status == "pass"
        assert report.issues == []

    def test_warnings_do_not_fail(self, workspace, documents):
        meta = valid_meta()
        meta["project"] = {"name": "示例项目"}  # 触发 missing_project_field 警告
        report = run_full_validation(
            "basic_info", meta=meta, items=[], documents=documents, workspace_root=workspace
        )
        assert report.status == "pass"
        assert report.warnings


def test_cross_matrix_issues():
    metas = {
        "basic_info": {"project_name": "项目甲", "project_id": "ZB-1"},
        "technical": {"project_name": "项目乙", "project_id": "ZB-1"},
    }
    issues = cross_matrix_issues(metas)
    assert {i.code for i in issues} == {"inconsistent_project_name"}
    assert all(i.severity == "warning" for i in issues)
    assert cross_matrix_issues({"basic_info": {"project_name": "同名"}, "technical": {"project_name": "同名"}}) == []
