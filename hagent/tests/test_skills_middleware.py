from pathlib import Path

from hagent.skills.loader import load_skills_from_sources
from hagent.skills.middleware import format_skills_catalog


def _skill(root: Path, name: str, description: str, when_to_use: str | None = None) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    when_line = f"when_to_use: {when_to_use}\n" if when_to_use else ""
    (skill_dir / "SKILL.md").write_text(
        f"---\ndescription: {description}\n{when_line}---\n# {name}\n",
        encoding="utf-8",
    )


def test_format_skills_catalog_lists_name_description_and_path(tmp_path: Path) -> None:
    _skill(tmp_path, "review", "Review code.", "Use for diffs.")
    registry = load_skills_from_sources([(tmp_path, "Project Claude")])

    catalog = format_skills_catalog(registry)

    assert "## Skills" in catalog
    assert "- review: Review code. - Use for diffs." in catalog
    assert "When a skill matches the user's request, invoke `Skill` before answering." in catalog
    assert str((tmp_path / "review" / "SKILL.md").resolve()) in catalog


def test_format_skills_catalog_empty_registry_is_short() -> None:
    registry = load_skills_from_sources([])

    assert format_skills_catalog(registry) == ""


def test_format_skills_catalog_can_omit_host_path_for_sandbox(tmp_path: Path) -> None:
    _skill(tmp_path, "review", "Review code.")
    registry = load_skills_from_sources([(tmp_path, "Project Claude")])

    catalog = format_skills_catalog(registry, include_source_path=False)

    assert "- review: Review code." in catalog
    assert "-> Source: Project Claude" in catalog
    assert str(tmp_path) not in catalog
