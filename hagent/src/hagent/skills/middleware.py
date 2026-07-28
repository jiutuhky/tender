from __future__ import annotations

from typing import Any

from langchain.agents.middleware import AgentMiddleware

from hagent.skills.models import SkillMetadata
from hagent.skills.registry import SkillRegistry

MAX_LISTING_DESC_CHARS = 250


def _description(skill: SkillMetadata) -> str:
    text = skill.description
    if skill.when_to_use:
        text = f"{text} - {skill.when_to_use}"
    if len(text) > MAX_LISTING_DESC_CHARS:
        return text[: MAX_LISTING_DESC_CHARS - 1] + "…"
    return text


def format_skills_catalog(registry: SkillRegistry) -> str:
    skills = registry.list()
    if not skills:
        return ""
    lines = [
        "## Skills",
        "",
        "Available skills are listed below. When a skill matches the user's request, invoke `Skill` before answering.",
        "Do not mention a skill without invoking it. If a skill has already been loaded in the current turn, follow its instructions directly.",
        "",
    ]
    for skill in skills:
        hidden = " (hidden from user slash invocation)" if not skill.user_invocable else ""
        lines.append(f"- {skill.name}: {_description(skill)}{hidden}")
        lines.append(f"  -> `Skill` name: `{skill.name}`")
        lines.append(f"  -> Source: {skill.source_label}; file: `{skill.skill_file}`")
    return "\n".join(lines)


class HagentSkillsMiddleware(AgentMiddleware):
    name = "HagentSkills"

    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    @staticmethod
    def _append_catalog(request: Any, catalog: str) -> Any:
        system_message = request.system_message
        if system_message is None:
            return request.override(system_message=catalog)
        content = getattr(system_message, "content", "")
        updated = system_message.model_copy(update={"content": f"{content}\n\n{catalog}"})
        return request.override(system_message=updated)

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        catalog = format_skills_catalog(self.registry)
        if not catalog:
            return handler(request)
        return handler(self._append_catalog(request, catalog))

    async def awrap_model_call(self, request: Any, handler: Any) -> Any:
        catalog = format_skills_catalog(self.registry)
        if not catalog:
            return await handler(request)
        return await handler(self._append_catalog(request, catalog))
