from pathlib import Path

from hagent.skills.sources import default_skill_sources, parse_skill_source_env


def test_parse_skill_source_env_uses_paths_and_labels(tmp_path: Path) -> None:
    one = tmp_path / "one"
    two = tmp_path / "two"

    assert parse_skill_source_env(f"{one}:One Skills,{two}:Two Skills") == [
        (one, "One Skills"),
        (two, "Two Skills"),
    ]


def test_default_skill_sources_order_lowest_to_highest(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project_root = tmp_path / "repo"

    sources = default_skill_sources(project_root=project_root, home=home)

    assert sources == [
        (home / ".hagent" / "skills", "User Hagent"),
        (project_root / ".hagent" / "skills", "Project Hagent"),
    ]
