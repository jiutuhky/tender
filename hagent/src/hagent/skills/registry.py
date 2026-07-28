from __future__ import annotations

from collections.abc import Iterable

from hagent.skills.models import SkillMetadata


class SkillRegistry:
    def __init__(self, skills: Iterable[SkillMetadata] = ()) -> None:
        self._by_name = {skill.name: skill for skill in skills}

    def list(self) -> list[SkillMetadata]:
        return [self._by_name[name] for name in sorted(self._by_name)]

    def get(self, name: str) -> SkillMetadata | None:
        normalized = name.strip().lstrip("/")
        if not normalized:
            return None
        return self._by_name.get(normalized)

    def require(self, name: str) -> SkillMetadata:
        skill = self.get(name)
        if skill is None:
            normalized = name.strip().lstrip("/")
            msg = f"Unknown skill: {normalized}"
            raise KeyError(msg)
        return skill

    def __bool__(self) -> bool:
        return bool(self._by_name)
