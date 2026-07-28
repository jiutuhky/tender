"""发布物化双轨（票 06）：publish 成功后把矩阵物化为旧路径兼容 JSON。

对拍锚点：`frontend/lib/hagent/matrix.ts` 的类型契约 + `frontend/lib/store/workspace.ts`
的扫描正则（MATRIX_FINAL_RE / runDirSortKey）；区段嵌套路径对拍 validators.META_SKELETONS。
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess

import pytest

from hagent.assets import service as service_module
from hagent.assets.projection import export_deviation_table

SOURCE_LINES = [
    "# 招标文件",
    "",
    "投标人须具备有效的信息系统建设资质，并提供近三年同类项目业绩证明。",
    "系统须支持每秒一千次并发查询，响应时间不超过两百毫秒。",
    "技术方案评分：方案完整性与可行性最高可得三十分。",
]

PROJECT = "p-projection"

# 对拍 frontend/lib/store/workspace.ts 的 MATRIX_FINAL_RE 与 runDirSortKey 时间戳约定
MATRIX_FINAL_RE = re.compile(
    r"(?:^|/)bid_response_matrix_[^/]+/final/(?:basic_info|business|technical|scoring)\.json$"
)
RUN_DIR_RE = re.compile(r"^bid_response_matrix_.+_\d{8}_\d{6}$")

ENVELOPE = {
    "project_id": "ZB-2026-001",
    "project_name": "示例信息化项目",
    "extraction_summary": {"status": "complete", "confidence": "high", "warnings": []},
}


@pytest.fixture(autouse=True)
def projection_on(monkeypatch):
    """票 08 收口后开关默认关闭；本模块验证物化行为本身，显式开启（关断测试再覆盖）。"""
    monkeypatch.setenv("HAGENT_PUBLISH_PROJECTION", "1")


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "tender.md").write_text("\n".join(SOURCE_LINES), encoding="utf-8")
    return tmp_path


@pytest.fixture
def doc(service, workspace, agent_actor):
    content = (workspace / "docs" / "tender.md").read_bytes()
    return service.register_document(
        PROJECT,
        path="docs/tender.md",
        sha256=hashlib.sha256(content).hexdigest(),
        doc_type="tender",
        actor=agent_actor,
    )


def tech_item(doc, i: int = 1) -> dict:
    return {
        "id": f"TECH-{i:03d}",
        "category": "function",
        "title": f"并发性能 {i}",
        "requirement_text": SOURCE_LINES[3],
        "mandatory": False,
        "response_required": True,
        "source_refs": [{"document_id": doc.id, "line_span": [4, 4]}],
        "confidence": "high",
    }


def biz_item(doc) -> dict:
    return {
        "id": "BIZ-001",
        "category": "qualification",
        "title": "供应商资格要求",
        "requirement_text": SOURCE_LINES[2],
        "mandatory": True,
        "response_required": True,
        "source_refs": [{"document_id": doc.id, "line_span": [3, 3]}],
        "confidence": "high",
    }


def score_item(doc) -> dict:
    return {
        "id": "SCORE-001",
        "group": "technical",
        "title": "技术方案评分",
        "max_score": 30,
        "scoring_rule": SOURCE_LINES[4],
        "scoring_method": "subjective",
        "source_refs": [{"document_id": doc.id, "line_span": [5, 5]}],
        "confidence": "high",
    }


UNRESOLVED_ROW = {
    "id": "UNRESOLVED-001",
    "severity": "low",
    "issue": "交付期表述含糊",
    "source_refs": [],
    "recommended_review": "人工确认交付期",
}

PACKAGE_ROW = {
    "package_id": "1",
    "package_name": "软件开发服务",
    "budget": {"amount": 3900000, "currency": "CNY", "text": "3,900,000元"},
    "scope": None,
    "source_refs": [],
}

TIMELINE_ROW = {
    "event": "bid_deadline",
    "datetime": "2026-08-01T09:00:00",
    "timezone": "Asia/Shanghai",
    "location": None,
    "source_refs": [],
}

QUALIFICATION_ROW = {"text": "具备独立承担民事责任的能力", "source_refs": []}
PASS_FAIL_ROW = {"text": "未提供有效资质证明的作否决处理", "source_refs": []}

BASIC_INFO_PROJECT = {
    "name": "示例信息化项目",
    "number": "ZB-2026-001",
    "procurement_method": "公开招标",
    "evaluation_method": "综合评分法",
    "budget": {"amount": 3900000, "currency": "CNY", "text": None},
    "scope": "信息系统建设",
}


def publish_matrix(service, workspace, actor, matrix_type, *, meta=None, sections=()):
    service.start_draft(PROJECT, matrix_type, actor=actor)
    service.set_meta(PROJECT, matrix_type, set={**ENVELOPE, **(meta or {})}, actor=actor)
    for section, records in sections:
        service.submit_records(
            PROJECT, matrix_type, section=section, records=records, actor=actor
        )
    return service.publish_gated(
        PROJECT, matrix_type, workspace_root=workspace, actor=actor
    )


def publish_all_four(service, doc, workspace, actor) -> None:
    publish_matrix(
        service, workspace, actor, "basic_info",
        meta={"project": BASIC_INFO_PROJECT},
        sections=[
            ("project.packages", [PACKAGE_ROW]),
            ("timeline", [TIMELINE_ROW]),
        ],
    )
    publish_matrix(
        service, workspace, actor, "business",
        sections=[
            ("items", [biz_item(doc)]),
            ("compliance_overview.qualification_review", [QUALIFICATION_ROW]),
        ],
    )
    publish_matrix(
        service, workspace, actor, "technical",
        sections=[
            ("items", [tech_item(doc)]),
            ("unresolved_items", [UNRESOLVED_ROW]),
        ],
    )
    publish_matrix(
        service, workspace, actor, "scoring",
        meta={"evaluation": {"method": "综合评分法", "total_score": 100}},
        sections=[
            ("items", [score_item(doc)]),
            ("evaluation.pass_fail_rules", [PASS_FAIL_ROW]),
        ],
    )


def run_dirs(workspace) -> list:
    return sorted(
        p for p in workspace.iterdir()
        if p.is_dir() and p.name.startswith("bid_response_matrix_")
    )


def load_final(workspace, matrix_type: str) -> dict:
    (run_dir,) = run_dirs(workspace)
    return json.loads(
        (run_dir / "final" / f"{matrix_type}.json").read_text(encoding="utf-8")
    )


class TestOldContractDocuments:
    def test_run_dir_and_paths_match_frontend_scan(self, service, doc, workspace, agent_actor):
        publish_all_four(service, doc, workspace, agent_actor)

        dirs = run_dirs(workspace)
        assert len(dirs) == 1
        assert RUN_DIR_RE.match(dirs[0].name)
        for matrix_type in ("basic_info", "business", "technical", "scoring"):
            relative = f"{dirs[0].name}/final/{matrix_type}.json"
            assert (workspace / relative).is_file()
            assert MATRIX_FINAL_RE.search(relative)

    def test_envelope_fields_from_object_store(self, service, doc, workspace, agent_actor):
        publish_all_four(service, doc, workspace, agent_actor)

        for matrix_type in ("basic_info", "business", "technical", "scoring"):
            final = load_final(workspace, matrix_type)
            assert final["schema_version"] == "1.0"
            assert final["matrix_type"] == matrix_type
            assert final["project_id"] == "ZB-2026-001"
            assert final["project_name"] == "示例信息化项目"
            assert isinstance(final["generated_at"], str) and final["generated_at"]
            assert final["source_documents"] == [
                {
                    "document_id": doc.id,
                    "path": "docs/tender.md",
                    "sha256": doc.sha256,
                    "doc_type": "tender",
                }
            ]
            assert final["extraction_summary"] == ENVELOPE["extraction_summary"]

    def test_sections_nest_at_old_contract_paths(self, service, doc, workspace, agent_actor):
        publish_all_four(service, doc, workspace, agent_actor)

        basic = load_final(workspace, "basic_info")
        assert basic["project"]["name"] == "示例信息化项目"
        assert basic["project"]["packages"] == [PACKAGE_ROW]
        assert basic["timeline"] == [TIMELINE_ROW]
        assert basic["contacts"] == []

        business = load_final(workspace, "business")
        assert business["items"] == [biz_item(doc)]
        assert business["compliance_overview"]["qualification_review"] == [QUALIFICATION_ROW]
        assert business["compliance_overview"]["conformity_review"] == []

        technical = load_final(workspace, "technical")
        assert technical["items"] == [tech_item(doc)]
        assert technical["deliverables"] == []
        assert technical["validation"]["unresolved_items"] == [UNRESOLVED_ROW]

        scoring = load_final(workspace, "scoring")
        assert scoring["items"] == [score_item(doc)]
        assert scoring["evaluation"]["method"] == "综合评分法"
        assert scoring["evaluation"]["total_score"] == 100
        assert scoring["evaluation"]["pass_fail_rules"] == [PASS_FAIL_ROW]
        assert scoring["evaluation"]["tie_break_rules"] == []


class TestWorkspaceGitVisibility:
    def test_projection_files_committed_when_workspace_is_git(
        self, service, doc, workspace, agent_actor
    ):
        """前端经 git ls-files 列举 workspace：物化文件必须被投影自己提交
        （sandbox 模式的 checkpoint 只收 guest 变更，不会替 host 侧投影补提交）。"""
        subprocess.run(
            ["git", "-C", str(workspace), "init", "--initial-branch=main"],
            check=True, capture_output=True,
        )
        for key, value in (("user.name", "hagent"), ("user.email", "hagent@local")):
            subprocess.run(
                ["git", "-C", str(workspace), "config", key, value],
                check=True, capture_output=True,
            )

        publish_matrix(
            service, workspace, agent_actor, "technical",
            sections=[("items", [tech_item(doc)])],
        )

        (run_dir,) = run_dirs(workspace)
        tracked = subprocess.run(
            ["git", "-C", str(workspace), "ls-files"],
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
        assert f"{run_dir.name}/final/technical.json" in tracked

    def test_plain_directory_workspace_still_materializes(
        self, service, doc, workspace, agent_actor
    ):
        # CLI host 模式 workspace 可能不是 git 仓库：跳过提交但文件照常落地
        publish_matrix(
            service, workspace, agent_actor, "technical",
            sections=[("items", [tech_item(doc)])],
        )
        assert load_final(workspace, "technical")["items"] == [tech_item(doc)]


class TestSingleDirLifecycle:
    def test_progressive_fill_reuses_one_dir(self, service, doc, workspace, agent_actor):
        publish_matrix(
            service, workspace, agent_actor, "technical",
            sections=[("items", [tech_item(doc)])],
        )
        (first,) = run_dirs(workspace)
        assert (first / "final" / "technical.json").is_file()
        assert not (first / "final" / "business.json").exists()

        publish_matrix(
            service, workspace, agent_actor, "business",
            sections=[("items", [biz_item(doc)])],
        )
        (second,) = run_dirs(workspace)
        assert second == first
        assert (second / "final" / "technical.json").is_file()
        assert (second / "final" / "business.json").is_file()

    def test_newer_unmarked_legacy_dir_triggers_fresh_dir(
        self, service, doc, workspace, agent_actor
    ):
        """无标记目录（旧 skill 遗留/外部还原）时间戳更新时不复用旧投影目录，
        改为新建当前时间戳目录自愈——否则前端 latestRunDir 永远读到陈旧数据。"""
        stale = workspace / "bid_response_matrix_stale_20200101_000000"
        (stale / "final").mkdir(parents=True)
        (stale / ".prose_projection.json").write_text("{}", encoding="utf-8")
        legacy = workspace / "bid_response_matrix_legacy_20200102_000000"
        (legacy / "final").mkdir(parents=True)

        publish_matrix(
            service, workspace, agent_actor, "technical",
            sections=[("items", [tech_item(doc)])],
        )

        fresh = [d for d in run_dirs(workspace) if d not in (stale, legacy)]
        assert len(fresh) == 1
        assert (fresh[0] / "final" / "technical.json").is_file()
        assert not (stale / "final" / "technical.json").exists()

    def test_republish_overwrites_in_place(self, service, doc, workspace, agent_actor):
        publish_matrix(
            service, workspace, agent_actor, "technical",
            sections=[("items", [tech_item(doc)])],
        )
        service.start_draft(
            PROJECT, "technical", discard_manual_states=True, actor=agent_actor
        )
        changed = {**tech_item(doc), "title": "并发性能（修订）"}
        service.submit_records(
            PROJECT, "technical", section="items", records=[changed], actor=agent_actor
        )
        service.publish_gated(
            PROJECT, "technical", workspace_root=workspace, actor=agent_actor
        )

        (run_dir,) = run_dirs(workspace)
        assert load_final(workspace, "technical")["items"] == [changed]


class TestToggle:
    def test_disabled_writes_nothing(self, service, doc, workspace, agent_actor, monkeypatch):
        monkeypatch.setenv("HAGENT_PUBLISH_PROJECTION", "0")
        before = sorted(p.name for p in workspace.rglob("*"))

        result = publish_matrix(
            service, workspace, agent_actor, "technical",
            sections=[("items", [tech_item(doc)])],
        )

        assert result.rev == 1  # publish 本身不受开关影响
        assert sorted(p.name for p in workspace.rglob("*")) == before
        assert run_dirs(workspace) == []

    def test_default_off_writes_nothing(self, service, doc, workspace, agent_actor, monkeypatch):
        """票 08 收口：未显式开启时零文件写入，workspace 不再出现 bid_response_matrix_* 目录。"""
        monkeypatch.delenv("HAGENT_PUBLISH_PROJECTION", raising=False)

        result = publish_matrix(
            service, workspace, agent_actor, "technical",
            sections=[("items", [tech_item(doc)])],
        )

        assert result.rev == 1
        assert run_dirs(workspace) == []


class TestBestEffort:
    def test_projection_failure_keeps_publish(
        self, service, doc, workspace, agent_actor, monkeypatch, caplog
    ):
        def boom(*args, **kwargs):
            raise OSError("磁盘只读")

        monkeypatch.setattr(service_module, "materialize_published_matrices", boom)

        with caplog.at_level("WARNING", logger="hagent.assets.service"):
            result = publish_matrix(
                service, workspace, agent_actor, "technical",
                sections=[("items", [tech_item(doc)])],
            )

        assert result.rev == 1
        info = service.get_matrix_info(PROJECT, "technical")
        assert info.state.value == "published"
        assert any("物化" in record.message for record in caplog.records)


class TestDeviationExport:
    def test_filters_items_by_response_status(self, service, doc, workspace, agent_actor, user_actor):
        publish_matrix(
            service, workspace, agent_actor, "technical",
            sections=[("items", [tech_item(doc, 1), tech_item(doc, 2)])],
        )
        service.set_item_response_status(
            PROJECT, "technical", "TECH-001",
            status="negative_deviation", note="仅支持每秒五百次", actor=user_actor,
        )
        service.set_item_response_status(
            PROJECT, "technical", "TECH-002", status="compliant", actor=user_actor,
        )

        rows = export_deviation_table(service, PROJECT, "technical")

        assert [row["item_id"] for row in rows] == ["TECH-001"]
        (row,) = rows
        assert row["matrix_type"] == "technical"
        assert row["response_status"] == "negative_deviation"
        assert row["response_note"] == "仅支持每秒五百次"
        assert row["confirmed"] is False
        assert row["payload"] == tech_item(doc, 1)
