from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

from hagent.skills.arguments import parse_argument_names
from hagent.skills.models import SkillMetadata, stringify_metadata
from hagent.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)

MAX_SKILL_FILE_SIZE = 10 * 1024 * 1024
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)

SkillSource = tuple[Path, str]


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _split_words(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _split_unquoted(value)
    if isinstance(value, list):
        result: list[str] = []
        for part in value:
            result.extend(_split_unquoted(str(part)))
        return result
    return []


def _split_unquoted(value: str) -> list[str]:
    result: list[str] = []
    current: list[str] = []
    paren_depth = 0
    brace_depth = 0
    for char in value.strip():
        if char == "(":
            paren_depth += 1
        elif char == ")" and paren_depth:
            paren_depth -= 1
        elif char == "{":
            brace_depth += 1
        elif char == "}" and brace_depth:
            brace_depth -= 1

        if char in {",", " ", "\t", "\n"} and paren_depth == 0 and brace_depth == 0:
            item = "".join(current).strip().strip(",")
            if item:
                result.append(item)
            current = []
            continue
        current.append(char)
    item = "".join(current).strip().strip(",")
    if item:
        result.append(item)
    return result


def _quote_problematic_frontmatter_values(frontmatter: str) -> str:
    fixed_lines: list[str] = []
    for line in frontmatter.splitlines():
        match = re.match(r"^(\s*(?:paths|allowed-tools)\s*:\s*)(.+?)\s*$", line)
        if not match:
            fixed_lines.append(line)
            continue
        prefix, value = match.groups()
        stripped = value.strip()
        if not stripped or stripped[0] in {"'", '"', "[", "{", "|", ">"}:
            fixed_lines.append(line)
            continue
        if any(char in stripped for char in "*{}[]"):
            fixed_lines.append(f"{prefix}{stripped!r}")
        else:
            fixed_lines.append(line)
    return "\n".join(fixed_lines)


def _extract_frontmatter(text: str, path: Path) -> tuple[dict[str, Any], str] | None:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    frontmatter = match.group(1)
    try:
        loaded = yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError as err:
        try:
            loaded = yaml.safe_load(_quote_problematic_frontmatter_values(frontmatter)) or {}
        except yaml.YAMLError:
            logger.warning("invalid skill frontmatter in %s: %s", path, err)
            return None
    if not isinstance(loaded, dict):
        logger.warning("skill frontmatter in %s is not a mapping", path)
        return None
    return loaded, match.group(2)


def _extract_description(markdown: str, fallback_name: str) -> str:
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            line = line.lstrip("#").strip()
            if line:
                return line
            continue
        return line
    return f"Skill {fallback_name}"


def _parse_skill(path: Path, source_label: str) -> SkillMetadata | None:
    try:
        if path.stat().st_size > MAX_SKILL_FILE_SIZE:
            logger.warning("skipping oversized skill file %s", path)
            return None
        text = path.read_text(encoding="utf-8-sig")
    except OSError as err:
        logger.warning("failed to read skill file %s: %s", path, err)
        return None

    extracted = _extract_frontmatter(text, path)
    if extracted is None:
        return None
    frontmatter, body = extracted
    skill_name = path.parent.name
    raw_description = frontmatter.get("description")
    description = (
        str(raw_description).strip()
        if raw_description is not None and str(raw_description).strip()
        else _extract_description(body, skill_name)
    )
    model = frontmatter.get("model")
    model_value = None if model in (None, "inherit") else str(model).strip() or None
    execution_context = "fork" if frontmatter.get("context") == "fork" else None

    return SkillMetadata(
        name=skill_name,
        display_name=str(frontmatter["name"]).strip() if frontmatter.get("name") is not None else None,
        description=description,
        skill_file=path.resolve(),
        base_dir=path.parent.resolve(),
        source_label=source_label,
        allowed_tools=_split_words(frontmatter.get("allowed-tools")),
        argument_hint=str(frontmatter["argument-hint"]).strip() if frontmatter.get("argument-hint") is not None else None,
        argument_names=parse_argument_names(frontmatter.get("arguments")),
        when_to_use=str(frontmatter["when_to_use"]).strip() if frontmatter.get("when_to_use") is not None else None,
        version=str(frontmatter["version"]).strip() if frontmatter.get("version") is not None else None,
        model=model_value,
        disable_model_invocation=_parse_bool(frontmatter.get("disable-model-invocation"), default=False),
        user_invocable=_parse_bool(frontmatter.get("user-invocable"), default=True),
        execution_context=execution_context,
        agent=str(frontmatter["agent"]).strip() if frontmatter.get("agent") is not None else None,
        paths=_split_words(frontmatter.get("paths")),
        metadata=stringify_metadata(frontmatter.get("metadata")),
        license=str(frontmatter["license"]).strip() if frontmatter.get("license") is not None else None,
        compatibility=str(frontmatter["compatibility"]).strip() if frontmatter.get("compatibility") is not None else None,
    )


def load_skills_from_sources(sources: Iterable[SkillSource]) -> SkillRegistry:
    by_name: dict[str, SkillMetadata] = {}
    for source_root, source_label in sources:
        root = Path(source_root).expanduser()
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir(), key=lambda p: p.name):
            if not entry.is_dir():
                continue
            skill_file = entry / "SKILL.md"
            if not skill_file.is_file():
                continue
            skill = _parse_skill(skill_file, source_label)
            if skill is not None:
                by_name[skill.name] = skill
    return SkillRegistry(by_name.values())
