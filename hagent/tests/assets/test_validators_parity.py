"""三校验器与原脚本的同语料同判定（票 02 验收锚点）。

同一套语料生成两种形态：文件形态喂给 skill 原脚本（subprocess），对象形态喂给
validators.py；比对 pass/error 集合等价（报错定位从 chunk_file:line / matrix:item
换算为 matrix/item_id）。原脚本由票 05 删除，届时本文件随 skip 条件整体跳过。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from hagent.assets.model import DocumentRecord, MatrixItem
from hagent.assets.validators import (
    validate_consistency,
    validate_source_fidelity,
    validate_structure,
)

SCRIPTS_DIR = (
    Path(__file__).resolve().parents[2]
    / ".hagent" / "skills" / "bid-response-matrix" / "scripts"
)

pytestmark = pytest.mark.skipif(
    not SCRIPTS_DIR.is_dir(), reason="原脚本已随票 05 删除，parity 基准不复存在"
)

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

DOC_ID = "doc-001"


def tech_item(item_id: str, text: str, span: list, *, doc_id: str = DOC_ID, **overrides) -> dict:
    item = {
        "id": item_id,
        "category": "function",
        "title": f"条目 {item_id}",
        "requirement_text": text,
        "mandatory": False,
        "response_required": True,
        "source_refs": [{"document_id": doc_id, "line_span": span}],
        "confidence": "high",
    }
    item.update(overrides)
    return item


def biz_item(item_id: str, text: str, span: list, **overrides) -> dict:
    item = {
        "id": item_id,
        "category": "service",
        "title": f"条目 {item_id}",
        "requirement_text": text,
        "mandatory": False,
        "response_required": True,
        "source_refs": [{"document_id": DOC_ID, "line_span": span}],
        "confidence": "high",
    }
    item.update(overrides)
    return item


def score_item(item_id: str, rule: str, span: list, **overrides) -> dict:
    item = {
        "id": item_id,
        "group": "technical",
        "title": f"条目 {item_id}",
        "max_score": 10,
        "scoring_rule": rule,
        "scoring_method": "subjective",
        "source_refs": [{"document_id": DOC_ID, "line_span": span}],
        "confidence": "high",
    }
    item.update(overrides)
    return item


def corpus_items() -> dict[str, list[dict]]:
    """覆盖原三脚本主要判定路径的语料（合法 / 结构错 / 保真错 / 重复 id / 废弃键）。"""
    fabricated = "本项目要求供应商提供全套量子加密通信模块并附带十年质保服务承诺。"
    tech_002 = tech_item("TECH-002", SOURCE_LINES[3], [0, 3])
    del tech_002["confidence"]
    return {
        "technical": [
            tech_item("TECH-001", SOURCE_LINES[3], [4, 4]),
            tech_002,  # 缺 confidence + line_span 非法
            tech_item("TECH-003", fabricated, [7, 9]),  # 凭空捏造 → 低重叠
            tech_item("TECH-004", "短文本", [4, 4]),  # 过短 → 保真警告
            tech_item("TECH-005", SOURCE_LINES[4], [5, 5], doc_id="doc-nope"),  # 未注册文档
            tech_item(
                "TECH-006",
                SOURCE_LINES[6],
                [7, 7],
                source_refs=[{"document_id": DOC_ID, "line_span": [7, 7], "quote": "旧摘录"}],
            ),  # 废弃 quote → 警告
        ],
        "business": [
            biz_item("BIZ-001", SOURCE_LINES[2], [3, 3], category="qualification", mandatory=True),
            biz_item("BIZ-002", SOURCE_LINES[4], [5, 5], source_refs=[]),  # 空 source_refs
            biz_item("BIZ-003", SOURCE_LINES[4], [5, 5], mandatory="yes"),  # 非布尔
            biz_item("BIZ-004", SOURCE_LINES[8], [9, 9]),
            biz_item("BIZ-004", SOURCE_LINES[8], [9, 9]),  # 重复 id
        ],
        "scoring": [
            score_item("SCORE-001", SOURCE_LINES[7], [8, 8]),
            score_item("SCORE-002", SOURCE_LINES[8], [9, 9], max_score="十分"),  # 非数字
        ],
    }


def metas() -> dict[str, dict]:
    common = {
        "project_id": "ZB-2026-001",
        "project_name": "示例信息化项目",
        "extraction_summary": {"status": "complete", "confidence": "high", "warnings": []},
    }
    return {
        "basic_info": {
            **common,
            "project": {
                "name": "示例信息化项目",
                "number": "ZB-2026-001",
                "procurement_method": "公开招标",
                "evaluation_method": "综合评分法",
                "packages": [],
                "budget": {"amount": 500000, "currency": "CNY", "text": "五十万元"},
                "scope": "信息化系统建设",
            },
        },
        "business": {
            **common,
            # 非法 status → 信封错误（两种形态都应报）
            "extraction_summary": {"status": "done", "confidence": "high", "warnings": []},
        },
        "technical": dict(common),
        "scoring": {
            **common,
            "evaluation": {"method": "综合评分法", "total_score": 100, "pass_fail_rules": [], "tie_break_rules": []},
        },
    }


# —— 文件形态（喂原脚本） ——


def build_file_corpus(run_dir: Path) -> None:
    (run_dir / "docs").mkdir(parents=True)
    (run_dir / "docs" / "tender.md").write_text("\n".join(SOURCE_LINES), encoding="utf-8")
    source_doc = {"document_id": DOC_ID, "file_name": "tender.md", "path": "docs/tender.md"}
    (run_dir / "inputs").mkdir()
    (run_dir / "inputs" / "manifest.json").write_text(
        json.dumps({"documents": [source_doc]}, ensure_ascii=False), encoding="utf-8"
    )

    items = corpus_items()
    all_metas = metas()
    finals = {
        "basic_info": {**all_metas["basic_info"], "timeline": [], "contacts": [], "source_refs": []},
        "business": {
            **all_metas["business"],
            "items": items["business"],
            "compliance_overview": {
                "qualification_review": [],
                "conformity_review": [],
                "invalid_bid_triggers": [],
            },
        },
        "technical": {
            **all_metas["technical"],
            "items": items["technical"],
            "deliverables": [],
            "acceptance_requirements": [],
        },
        "scoring": {**all_metas["scoring"], "items": items["scoring"]},
    }
    (run_dir / "final").mkdir()
    for matrix_type, data in finals.items():
        data = {
            "schema_version": "1.0",
            "matrix_type": matrix_type,
            "generated_at": "2026-07-13T00:00:00+08:00",
            "source_documents": [source_doc],
            **data,
        }
        (run_dir / "final" / f"{matrix_type}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    (run_dir / "validation").mkdir()
    (run_dir / "validation" / "unresolved_items.json").write_text(
        json.dumps({"schema_version": "1.0", "items": []}), encoding="utf-8"
    )


# —— 对象形态（喂 validators.py） ——


def object_rows(matrix_type: str) -> list[MatrixItem]:
    return [
        MatrixItem(
            project_id="p-1",
            matrix_type=matrix_type,
            stage="draft",
            item_id=str(payload.get("id") or f"items:auto-{index}"),
            section="items",
            payload=payload,
            response_status=None,
            response_note=None,
            confirmed=False,
            version=1,
        )
        for index, payload in enumerate(corpus_items()[matrix_type])
    ]


def registry_documents() -> list[DocumentRecord]:
    return [
        DocumentRecord(
            id=DOC_ID,
            project_id="p-1",
            path="docs/tender.md",
            sha256="0" * 64,
            doc_type="tender",
            registered_at="2026-07-13T00:00:00+00:00",
        )
    ]


def run_script(name: str, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / name), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout


ITEM_ERROR_RE = re.compile(r"^(basic_info|business|technical|scoring):([A-Za-z0-9_-]+):")


def flagged_ids(messages: list[str], matrix_type: str) -> set[str]:
    ids = set()
    for message in messages:
        match = ITEM_ERROR_RE.match(message)
        if match and match.group(1) == matrix_type:
            ids.add(match.group(2))
    return ids


@pytest.fixture(scope="module")
def file_corpus(tmp_path_factory):
    run_dir = tmp_path_factory.mktemp("corpus")
    build_file_corpus(run_dir)
    return run_dir


def test_structure_parity(file_corpus):
    """结构校验：原 validate_response_matrix.py 与新校验器对同语料判定等价。"""
    returncode, stdout = run_script("validate_response_matrix.py", str(file_corpus))
    report = json.loads(stdout)
    assert report["status"] == "fail"
    assert returncode == 1

    all_metas = metas()
    for matrix_type in ("business", "technical", "scoring"):
        original_ids = flagged_ids(report["errors"], matrix_type)
        rows = object_rows(matrix_type)
        issues = [
            *validate_structure(matrix_type, all_metas[matrix_type], rows),
            *validate_consistency(matrix_type, all_metas[matrix_type], rows),
        ]
        ours = {
            i.target.split("/", 1)[1]
            for i in issues
            if i.severity == "error" and "/" in i.target
        }
        assert ours == original_ids, f"{matrix_type} 错误条目集合不等价"

    # 信封级错误（business 的非法 extraction_summary.status）两边都报
    assert any("extraction_summary.status" in message for message in report["errors"])
    business_issues = validate_structure("business", all_metas["business"], object_rows("business"))
    assert any(i.code == "invalid_summary_status" for i in business_issues)

    # 警告集合（废弃 quote）等价
    original_warn_ids = flagged_ids(report["warnings"], "technical")
    tech_issues = validate_structure("technical", all_metas["technical"], object_rows("technical"))
    ours_warn = {
        i.target.split("/", 1)[1]
        for i in tech_issues
        if i.severity == "warning" and "/" in i.target
    }
    assert ours_warn == original_warn_ids == {"TECH-006"}


def test_fidelity_parity(file_corpus):
    """源文保真：错误/警告的 (matrix, item, code) 集合与原脚本完全一致。"""
    returncode, stdout = run_script("verify_source_fidelity.py", str(file_corpus), "--json")
    report = json.loads(stdout)
    assert report["status"] == "fail"
    assert returncode == 1

    def script_set(issues):
        return {(i["matrix_type"], i["item_id"], i["code"]) for i in issues}

    ours_errors = set()
    ours_warnings = set()
    for matrix_type in ("business", "technical", "scoring"):
        issues = validate_source_fidelity(
            matrix_type,
            object_rows(matrix_type),
            documents=registry_documents(),
            workspace_root=file_corpus,
        )
        for issue in issues:
            entry = (matrix_type, issue.target.split("/", 1)[1], issue.code)
            (ours_errors if issue.severity == "error" else ours_warnings).add(entry)

    assert ours_errors == script_set(report["errors"])
    assert ours_warnings == script_set(report["warnings"])


def test_fidelity_verdict_details_match(file_corpus):
    """低重叠条目的 coverage 分值与原脚本逐位一致（评分函数逐字移植）。"""
    _, stdout = run_script("verify_source_fidelity.py", str(file_corpus), "--json")
    report = json.loads(stdout)
    original = {
        (i["matrix_type"], i["item_id"]): i
        for i in report["errors"]
        if i["code"] == "low_source_overlap"
    }
    assert ("technical", "TECH-003") in original

    issues = validate_source_fidelity(
        "technical",
        object_rows("technical"),
        documents=registry_documents(),
        workspace_root=file_corpus,
    )
    ours = {i.target: i for i in issues if i.code == "low_source_overlap"}
    issue = ours["technical/TECH-003"]
    script_issue = original[("technical", "TECH-003")]
    assert issue.detail["coverage"] == script_issue["coverage"]
    assert issue.detail["sequence_coverage"] == script_issue["sequence_coverage"]
    assert issue.detail["ngram_recall"] == script_issue["ngram_recall"]
    assert issue.detail["source_preview"] == script_issue["source_preview"]


def test_consistency_parity_with_assembler(tmp_path):
    """组装一致性：meta 类型冲突 / 非法区段 / 缺 id / 重复 id 与 assemble --check 判定等价。"""
    run_dir = tmp_path / "run"
    intermediate = run_dir / "intermediate"
    intermediate.mkdir(parents=True)
    (intermediate / "scoring.meta.json").write_text(
        json.dumps({"evaluation": "综合评分法"}, ensure_ascii=False), encoding="utf-8"
    )
    chunk_lines = [
        {"section": "items", "record": score_item("SCORE-001", SOURCE_LINES[7], [8, 8])},
        {"section": "items", "record": score_item("SCORE-001", SOURCE_LINES[7], [8, 8])},
        {"section": "extras", "record": {"note": "不存在的区段"}},
        {"section": "items", "record": {"title": "缺 id 的条目"}},
    ]
    chunk = intermediate / "scoring.chunk.0001.jsonl"
    chunk.write_text(
        "\n".join(json.dumps(line, ensure_ascii=False) for line in chunk_lines), encoding="utf-8"
    )
    (intermediate / "scoring.done.json").write_text(
        json.dumps({"matrix_type": "scoring", "chunks": [chunk.name], "record_count": 4}),
        encoding="utf-8",
    )

    returncode, stdout = run_script("assemble_matrix.py", str(run_dir), "--check", "scoring")
    report = json.loads(stdout)
    assert report["status"] == "fail"
    assert returncode == 1
    original_errors = report["errors"]

    meta = {"evaluation": "综合评分法"}
    rows = [
        MatrixItem("p-1", "scoring", "draft", "SCORE-001", "items",
                   score_item("SCORE-001", SOURCE_LINES[7], [8, 8]), None, None, False, 1),
        MatrixItem("p-1", "scoring", "draft", "SCORE-001", "items",
                   score_item("SCORE-001", SOURCE_LINES[7], [8, 8]), None, None, False, 1),
        MatrixItem("p-1", "scoring", "draft", "extras:1", "extras",
                   {"note": "不存在的区段"}, None, None, False, 1),
        MatrixItem("p-1", "scoring", "draft", "items:auto-1", "items",
                   {"title": "缺 id 的条目"}, None, None, False, 1),
    ]
    issues = validate_consistency("scoring", meta, rows)
    ours = {i.code for i in issues}

    # 四类判定一一对应：两边同报（等价性按判定类别比对，原脚本无结构化 code）
    expectations = {
        "meta_type_conflict": "'evaluation' must be an object",
        "invalid_section": "section must be one of",
        "missing_item_id": "missing 'id'",
        "duplicate_id": "duplicate id 'SCORE-001'",
    }
    for code, needle in expectations.items():
        assert code in ours, f"新校验器缺少 {code}"
        assert any(needle in message for message in original_errors), f"原脚本缺少 {needle}"
    assert len(ours) == len(expectations)


def test_clean_corpus_passes_both(tmp_path):
    """干净语料双方都判 pass（等价性的另一半）。"""
    run_dir = tmp_path / "clean"
    (run_dir / "docs").mkdir(parents=True)
    (run_dir / "docs" / "tender.md").write_text("\n".join(SOURCE_LINES), encoding="utf-8")
    source_doc = {"document_id": DOC_ID, "file_name": "tender.md", "path": "docs/tender.md"}
    all_metas = metas()
    all_metas["business"]["extraction_summary"] = {
        "status": "complete", "confidence": "high", "warnings": [],
    }
    clean_items = {
        "technical": [tech_item("TECH-001", SOURCE_LINES[3], [4, 4])],
        "business": [biz_item("BIZ-001", SOURCE_LINES[2], [3, 3], category="qualification", mandatory=True)],
        "scoring": [score_item("SCORE-001", SOURCE_LINES[7], [8, 8])],
    }
    finals = {
        "basic_info": {**all_metas["basic_info"], "timeline": [], "contacts": [], "source_refs": []},
        "business": {
            **all_metas["business"],
            "items": clean_items["business"],
            "compliance_overview": {
                "qualification_review": [], "conformity_review": [], "invalid_bid_triggers": [],
            },
        },
        "technical": {
            **all_metas["technical"],
            "items": clean_items["technical"],
            "deliverables": [],
            "acceptance_requirements": [],
        },
        "scoring": {**all_metas["scoring"], "items": clean_items["scoring"]},
    }
    (run_dir / "final").mkdir()
    for matrix_type, data in finals.items():
        data = {
            "schema_version": "1.0",
            "matrix_type": matrix_type,
            "generated_at": "2026-07-13T00:00:00+08:00",
            "source_documents": [source_doc],
            **data,
        }
        (run_dir / "final" / f"{matrix_type}.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    (run_dir / "validation").mkdir()
    (run_dir / "validation" / "unresolved_items.json").write_text(
        json.dumps({"schema_version": "1.0", "items": []}), encoding="utf-8"
    )

    returncode, stdout = run_script("validate_response_matrix.py", str(run_dir))
    assert json.loads(stdout)["status"] == "pass" and returncode == 0
    returncode, stdout = run_script("verify_source_fidelity.py", str(run_dir), "--json")
    assert json.loads(stdout)["status"] == "pass" and returncode == 0

    documents = registry_documents()
    for matrix_type in ("business", "technical", "scoring"):
        rows = [
            MatrixItem("p-1", matrix_type, "draft", payload["id"], "items",
                       payload, None, None, False, 1)
            for payload in clean_items[matrix_type]
        ]
        issues = [
            *validate_structure(matrix_type, all_metas[matrix_type], rows),
            *validate_consistency(matrix_type, all_metas[matrix_type], rows),
            *validate_source_fidelity(
                matrix_type, rows, documents=documents, workspace_root=run_dir
            ),
        ]
        assert [i for i in issues if i.severity == "error"] == []
