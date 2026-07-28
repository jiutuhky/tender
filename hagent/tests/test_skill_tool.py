from pathlib import Path

from hagent.skills.loader import load_skills_from_sources
from hagent.skills.tool import create_skill_tool, render_skill_prompt


def _skill(root: Path, name: str, body: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "description: Test skill.\n"
        "arguments: scope focus\n"
        "allowed-tools: Read Bash(pytest:*)\n"
        "---\n"
        + body,
        encoding="utf-8",
    )


def test_render_skill_prompt_adds_base_directory_and_substitutes_args(tmp_path: Path) -> None:
    _skill(tmp_path, "review", "Review $scope with $focus in ${CLAUDE_SKILL_DIR}.")
    registry = load_skills_from_sources([(tmp_path, "Project Claude")])
    skill = registry.require("review")

    rendered = render_skill_prompt(skill, 'src "unit tests"', session_id="session-1")

    assert rendered.startswith(f"Base directory for this skill: {skill.base_dir}\n\n")
    assert f"Review src with unit tests in {skill.base_dir}." in rendered


def test_skill_tool_returns_expanded_content(tmp_path: Path) -> None:
    _skill(tmp_path, "review", "Review $ARGUMENTS.")
    registry = load_skills_from_sources([(tmp_path, "Project Claude")])
    tool = create_skill_tool(registry, session_id="session-1")

    result = tool.invoke({"skill": "review", "args": "src"})

    assert result["success"] is True
    assert result["commandName"] == "review"
    assert result["allowedTools"] == ["Read", "Bash(pytest:*)"]
    assert "Review src." in result["content"]


def test_render_skill_prompt_base_dir_override(tmp_path: Path) -> None:
    _skill(tmp_path, "review", "Run in ${CLAUDE_SKILL_DIR} and ${HAGENT_SKILL_DIR}.")
    registry = load_skills_from_sources([(tmp_path, "Project Claude")])
    skill = registry.require("review")

    rendered = render_skill_prompt(skill, "src x", base_dir="/tmp/hagent/skills/n/review")

    assert rendered.startswith("Base directory for this skill: /tmp/hagent/skills/n/review\n\n")
    assert "Run in /tmp/hagent/skills/n/review and /tmp/hagent/skills/n/review." in rendered
    assert str(skill.base_dir) not in rendered


class _FakeMaterializer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def materialize(self, skill) -> str:  # noqa: ANN001
        self.calls.append(skill.name)
        return f"/tmp/hagent/skills/abcd/{skill.name}"


def test_skill_tool_uses_materializer_base_dir(tmp_path: Path) -> None:
    _skill(tmp_path, "review", "Read ${CLAUDE_SKILL_DIR}/references/r.md.")
    registry = load_skills_from_sources([(tmp_path, "Project Claude")])
    materializer = _FakeMaterializer()
    tool = create_skill_tool(registry, materializer=materializer)

    result = tool.invoke({"skill": "review", "args": "src"})

    assert result["success"] is True
    assert materializer.calls == ["review"]
    assert "Base directory for this skill: /tmp/hagent/skills/abcd/review" in result["content"]
    assert "Read /tmp/hagent/skills/abcd/review/references/r.md." in result["content"]


def test_skill_tool_rejects_unknown_skill(tmp_path: Path) -> None:
    tool = create_skill_tool(load_skills_from_sources([(tmp_path, "Project Claude")]))

    result = tool.invoke({"skill": "missing"})

    assert result == {
        "success": False,
        "commandName": "missing",
        "status": "inline",
        "error": "Unknown skill: missing",
    }


def test_skill_tool_respects_disable_model_invocation(tmp_path: Path) -> None:
    skill_dir = tmp_path / "secret"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: Secret skill.\ndisable-model-invocation: true\n---\n# Secret",
        encoding="utf-8",
    )
    tool = create_skill_tool(load_skills_from_sources([(tmp_path, "Project Claude")]))

    result = tool.invoke({"skill": "secret"})

    assert result == {
        "success": False,
        "commandName": "secret",
        "status": "inline",
        "error": "Skill secret cannot be used with Skill tool due to disable-model-invocation",
    }


def test_skill_tool_rejects_fork_context_explicitly(tmp_path: Path) -> None:
    skill_dir = tmp_path / "forked"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: Forked skill.\ncontext: fork\n---\n# Forked",
        encoding="utf-8",
    )
    tool = create_skill_tool(load_skills_from_sources([(tmp_path, "Project Claude")]))

    result = tool.invoke({"skill": "forked"})

    assert result == {
        "success": False,
        "commandName": "forked",
        "status": "unsupported",
        "error": "Skill fork execution is not supported in Hagent yet",
    }
