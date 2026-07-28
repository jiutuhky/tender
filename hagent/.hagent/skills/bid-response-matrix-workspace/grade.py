#!/usr/bin/env python3
"""为 bid-response-matrix 的一次运行打分（对象库口径）。

三大维度（承接原 extract-tech-requirements 评分口径）：
  - schema/发布：四矩阵 published、全套校验（结构/一致性/源文保真）pass
  - 信息完整性：资格/符合性/技术/商务条数下限、评分合计与维度拆分
  - 忠于原文：预算与项目编号、mandatory 信号抽样、requirement_text 直读源文
    抽样命中（独立于校验器的重叠度打分，防自评回路）

用法（hagent venv 内，需与运行时相同的 HAGENT_WORKSPACE_ROOT）:
  python3 grade.py <sessions_db> <project_id> <doc_key> <source_md> [--out grading.json]
  doc_key ∈ {sim, pool, system}
产物: grading.json（{text,passed,evidence} 列表，viewer 兼容格式）
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

from hagent.assets.model import MATRIX_TYPES
from hagent.assets.service import AssetService
from hagent.assets.store import AssetStore

EXPECTED = {
    "sim":    {"budget": 3900000, "number": "2025-JQ04-F1375",
               "score": {"business": 17, "technical": 53, "price": 30},
               "min_qualification": 8, "min_conformity": 5, "min_tech": 60, "min_business": 8},
    "pool":   {"budget": 2700000, "number": "2025-JQ04-F1054",
               "score": {"business": 19, "technical": 56, "price": 25},
               "min_qualification": 6, "min_conformity": 4, "min_tech": 20, "min_business": 5},
    "system": {"budget": 3500000, "number": "2024-JQ05-F1859(1)",
               "score": {"business": 17, "technical": 55, "price": 28},
               "min_qualification": 6, "min_conformity": 4, "min_tech": 15, "min_business": 5},
}

# 只取强信号做门槛（"必须/须/不得"在长句中噪声大，留给 skill 指南而非打分器）
MANDATORY_SIGNALS = ("★", "否则视为无效", "无效投标", "实质性响应", "不允许负偏离")
SAMPLE_SIZE = 15


def norm(text: str) -> str:
    return re.sub(r"\s+", "", str(text))


def workspace_for(project_id: str) -> Path:
    root = Path(os.environ.get("HAGENT_WORKSPACE_ROOT", "/tmp/hagent/workspaces"))
    return root / "projects" / project_id / "workspace"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sessions_db")
    parser.add_argument("project_id")
    parser.add_argument("doc_key", choices=sorted(EXPECTED))
    parser.add_argument("source_md")
    parser.add_argument("--out", default="grading.json")
    args = parser.parse_args()

    expected = EXPECTED[args.doc_key]
    service = AssetService(AssetStore(args.sessions_db))
    project = args.project_id
    results: list[dict] = []

    def check(text: str, passed: bool, evidence: str) -> None:
        results.append({"text": text, "passed": bool(passed), "evidence": evidence})

    # —— schema/发布 ——
    status = {e.matrix_type: e for e in service.matrix_status(project)}
    states = {m: status[m].state.value for m in MATRIX_TYPES}
    check("[schema] 四矩阵均 published",
          all(s == "published" for s in states.values()), json.dumps(states, ensure_ascii=False))

    ws = workspace_for(project)
    verdicts = {}
    for matrix_type in MATRIX_TYPES:
        report = service.validate_matrix(project, matrix_type, workspace_root=ws)
        verdicts[matrix_type] = f"{report.status}({len(report.errors)}E/{len(report.warnings)}W)"
        check(f"[schema] {matrix_type} 全套校验 pass（结构/一致性/源文保真）",
              report.status == "pass",
              "; ".join(f"{i.target}:{i.code}" for i in report.errors[:5]) or verdicts[matrix_type])

    # —— 信息完整性 ——
    def count(matrix_type: str, **filters) -> int:
        _, total = service.query_items(project, matrix_type, limit=1, **filters)
        return total

    # 资格/符合性都有两种合法表示：items 分类条目，或 compliance_overview 区段行
    qualification = count("business", section="items", category="qualification") + count(
        "business", section="compliance_overview.qualification_review")
    check(f"[完整][P0] 资格性条目 ≥ {expected['min_qualification']}",
          qualification >= expected["min_qualification"], f"qualification={qualification}")

    conformity = count("business", section="items", category="conformity") + count(
        "business", section="compliance_overview.conformity_review")
    check(f"[完整][P0] 符合性条目 ≥ {expected['min_conformity']}",
          conformity >= expected["min_conformity"], f"conformity={conformity}")

    tech_total = count("technical", section="items")
    check(f"[完整] technical items ≥ {expected['min_tech']}",
          tech_total >= expected["min_tech"], f"technical={tech_total}")

    business_total = count("business", section="items")
    check(f"[完整] business items ≥ {expected['min_business']}",
          business_total >= expected["min_business"], f"business={business_total}")

    scoring_items, _ = service.query_items(project, "scoring", section="items", limit=None)
    by_group: dict[str, float] = {}
    for item in scoring_items:
        score = item.payload.get("max_score")
        if isinstance(score, (int, float)):
            by_group[item.payload.get("group", "?")] = by_group.get(item.payload.get("group", "?"), 0) + score
    total_score = sum(by_group.values())
    dims = expected["score"]
    check("[完整] 评分合计=100 且各维度=（商务{business}/技术{technical}/价格{price}）".format(**dims),
          total_score == 100 and all(by_group.get(g) == v for g, v in dims.items()),
          json.dumps({"total": total_score, **by_group}, ensure_ascii=False))

    # —— 忠于原文 ——
    overview = service.get_matrix_overview(project, "basic_info")
    project_meta = overview.info.meta.get("project") or {}
    budget = (project_meta.get("budget") or {}).get("amount")
    number = project_meta.get("number")
    check(f"[忠实] budget.amount={expected['budget']}、project.number={expected['number']}",
          budget == expected["budget"] and number == expected["number"],
          f"budget={budget!r} number={number!r}")

    signalled = flagged = 0
    sampled: list[tuple[str, str, str]] = []
    for matrix_type in ("business", "technical"):
        items, _ = service.query_items(project, matrix_type, section="items", limit=None)
        for item in items:
            text = str(item.payload.get("requirement_text", ""))
            if any(sig in text for sig in MANDATORY_SIGNALS):
                signalled += 1
                flagged += bool(item.payload.get("mandatory"))
            sampled.append((matrix_type, item.item_id, text))
    check("[忠实] 带 mandatory 信号的条目 ≥80% 标记 mandatory=true",
          signalled == 0 or flagged / signalled >= 0.8, f"{flagged}/{signalled}")

    # 独立源文抽样：等距取样，归一化后做原文子串命中（不复用校验器的重叠度打分）
    source_text = norm(Path(args.source_md).read_text(encoding="utf-8"))
    picks = sampled[:: max(1, len(sampled) // SAMPLE_SIZE)][:SAMPLE_SIZE]
    misses = [f"{m}/{i}" for m, i, text in picks if norm(text) and norm(text) not in source_text]
    check(f"[忠实] requirement_text 抽样 {len(picks)} 条 ≥80% 逐字命中源文",
          not picks or (len(picks) - len(misses)) / len(picks) >= 0.8,
          "misses: " + ", ".join(misses[:5]) if misses else f"{len(picks)}/{len(picks)} 命中")

    passed = sum(r["passed"] for r in results)
    grading = {"doc_key": args.doc_key, "pass_rate": f"{passed}/{len(results)}", "results": results}
    Path(args.out).write_text(json.dumps(grading, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(grading, ensure_ascii=False, indent=2))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
