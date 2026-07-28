from pathlib import Path

from hagent.skills.models import SkillMetadata
from hagent.skills.registry import SkillRegistry


def _skill(name: str, tmp_path: Path) -> SkillMetadata:
    base = tmp_path / name
    return SkillMetadata(
        name=name,
        description=f"{name} description",
        skill_file=base / "SKILL.md",
        base_dir=base,
        source_label="Test",
    )


def test_registry_lists_skills_sorted_by_name(tmp_path: Path) -> None:
    registry = SkillRegistry([_skill("zeta", tmp_path), _skill("alpha", tmp_path)])

    assert [skill.name for skill in registry.list()] == ["alpha", "zeta"]


def test_registry_lookup_accepts_leading_slash(tmp_path: Path) -> None:
    registry = SkillRegistry([_skill("review", tmp_path)])

    assert registry.get("/review").name == "review"
    assert registry.require("review").name == "review"


def test_registry_require_raises_clear_key_error(tmp_path: Path) -> None:
    registry = SkillRegistry([_skill("review", tmp_path)])

    try:
        registry.require("missing")
    except KeyError as exc:
        assert exc.args == ("Unknown skill: missing",)
    else:
        raise AssertionError("require must raise for missing skills")


def test_registry_bool_reflects_non_empty(tmp_path: Path) -> None:
    assert not SkillRegistry()
    assert SkillRegistry([_skill("review", tmp_path)])
