from __future__ import annotations

from pathlib import Path

SkillSource = tuple[Path, str]


def parse_skill_source_env(raw: str | None) -> list[SkillSource]:
    if raw is None or not raw.strip():
        return []
    sources: list[SkillSource] = []
    for chunk in raw.split(","):
        item = chunk.strip()
        if not item:
            continue
        if ":" in item:
            path_text, label = item.rsplit(":", 1)
            sources.append((Path(path_text).expanduser(), label.strip() or "Custom"))
        else:
            sources.append((Path(item).expanduser(), "Custom"))
    return sources


def default_skill_sources(
    *,
    project_root: Path,
    home: Path | None = None,
) -> list[SkillSource]:
    user_home = Path.home() if home is None else home
    root = Path(project_root).resolve()
    return [
        (user_home / ".hagent" / "skills", "User Hagent"),
        (root / ".hagent" / "skills", "Project Hagent"),
    ]


def resolve_skill_sources(
    *,
    project_root: Path,
    env_value: str | None,
) -> list[SkillSource]:
    explicit = parse_skill_source_env(env_value)
    if explicit:
        return explicit
    return default_skill_sources(project_root=project_root)
