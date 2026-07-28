from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from hagent.skills.loader import load_skills_from_sources
from hagent.skills.models import SkillInvocation, SkillMetadata


def _write_skill(root: Path, name: str, frontmatter: dict, body: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False)
    path = skill_dir / "SKILL.md"
    path.write_text(f"---\n{fm}---\n{body}", encoding="utf-8")
    return path


def test_skill_metadata_uses_directory_name_as_invocation_name(tmp_path: Path) -> None:
    path = _write_skill(
        tmp_path,
        "code-review",
        {
            "name": "Code Review",
            "description": "Review code changes for correctness.",
            "allowed-tools": "Read, Grep Bash(pytest:*)",
            "argument-hint": "[scope]",
            "arguments": "scope focus",
            "when_to_use": "Use when asked to review diffs.",
            "version": "1.2.3",
            "model": "inherit",
            "disable-model-invocation": False,
            "user-invocable": True,
            "context": "fork",
            "agent": "Plan",
            "paths": "src/**, tests/**",
        },
        "# Code Review\nFollow this review workflow.",
    )

    registry = load_skills_from_sources([(tmp_path, "Project Claude")])
    skill = registry.require("code-review")

    assert skill.name == "code-review"
    assert skill.display_name == "Code Review"
    assert skill.description == "Review code changes for correctness."
    assert skill.allowed_tools == ["Read", "Grep", "Bash(pytest:*)"]
    assert skill.argument_hint == "[scope]"
    assert skill.argument_names == ["scope", "focus"]
    assert skill.when_to_use == "Use when asked to review diffs."
    assert skill.version == "1.2.3"
    assert skill.model is None
    assert skill.disable_model_invocation is False
    assert skill.user_invocable is True
    assert skill.execution_context == "fork"
    assert skill.agent == "Plan"
    assert skill.paths == ["src/**", "tests/**"]
    assert skill.skill_file == path.resolve()
    assert skill.base_dir == path.parent.resolve()
    assert skill.source_label == "Project Claude"


def test_skill_invocation_rejects_empty_skill_name() -> None:
    with pytest.raises(ValidationError):
        SkillInvocation(skill=" ")


def test_skill_metadata_rejects_unknown_extra_fields(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        SkillMetadata(
            name="x",
            description="x",
            skill_file=tmp_path / "x" / "SKILL.md",
            base_dir=tmp_path / "x",
            source_label="Test",
            unexpected=True,
        )


def test_loader_uses_later_source_for_duplicate_skill_names(tmp_path: Path) -> None:
    user = tmp_path / "user"
    project = tmp_path / "project"
    _write_skill(user, "review", {"description": "User review skill."}, "# Review\nUser copy.")
    _write_skill(project, "review", {"description": "Project review skill."}, "# Review\nProject copy.")

    registry = load_skills_from_sources([(user, "User Claude"), (project, "Project Claude")])

    skill = registry.require("review")
    assert skill.description == "Project review skill."
    assert skill.source_label == "Project Claude"
    assert skill.skill_file == (project / "review" / "SKILL.md").resolve()


def test_loader_extracts_description_from_markdown_when_frontmatter_missing(tmp_path: Path) -> None:
    _write_skill(tmp_path, "summarize", {}, "# Summarize\nSummarize long notes into decisions.")

    skill = load_skills_from_sources([(tmp_path, "Project Claude")]).require("summarize")

    assert skill.description == "Summarize"


def test_loader_skips_files_without_skill_md(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("not a skill", encoding="utf-8")
    (tmp_path / "empty").mkdir()

    registry = load_skills_from_sources([(tmp_path, "Project Claude")])

    assert registry.list() == []


def test_loader_skips_oversized_skill_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hagent.skills.loader as loader

    monkeypatch.setattr(loader, "MAX_SKILL_FILE_SIZE", 10)
    _write_skill(tmp_path, "large", {"description": "Too large."}, "01234567890")

    registry = load_skills_from_sources([(tmp_path, "Project Claude")])

    assert registry.list() == []


def test_loader_accepts_allowed_tools_and_paths_lists(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "lint",
        {
            "description": "Run lint checks.",
            "allowed-tools": ["Read,", "Bash(ruff:*)"],
            "paths": ["src/**,", "tests/**"],
        },
        "# Lint\nRun lint checks.",
    )

    skill = load_skills_from_sources([(tmp_path, "Project Claude")]).require("lint")

    assert skill.allowed_tools == ["Read", "Bash(ruff:*)"]
    assert skill.paths == ["src/**", "tests/**"]


def test_loader_splits_comma_separated_tools_and_paths_without_splitting_parens_or_braces(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "lint",
        {
            "description": "Run lint checks.",
            "allowed-tools": "Read,Bash(pytest:*),Bash(npm run test:*)",
            "paths": "src/**,tests/**/*.{py,pyi}",
        },
        "# Lint\nRun lint checks.",
    )

    skill = load_skills_from_sources([(tmp_path, "Project Claude")]).require("lint")

    assert skill.allowed_tools == ["Read", "Bash(pytest:*)", "Bash(npm run test:*)"]
    assert skill.paths == ["src/**", "tests/**/*.{py,pyi}"]


def test_loader_recovers_unquoted_glob_path_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "typescript"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: TypeScript skill.\npaths: **/*.{ts,tsx}\n---\n# TypeScript\n",
        encoding="utf-8",
    )

    skill = load_skills_from_sources([(tmp_path, "Project Claude")]).require("typescript")

    assert skill.paths == ["**/*.{ts,tsx}"]


def test_loader_skips_invalid_yaml_frontmatter(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    skill_dir = tmp_path / "broken"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: [\n---\nBody", encoding="utf-8")

    registry = load_skills_from_sources([(tmp_path, "Project Claude")])

    assert registry.list() == []
    assert "invalid skill frontmatter" in caplog.text
