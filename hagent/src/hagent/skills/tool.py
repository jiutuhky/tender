from __future__ import annotations

import os

from langchain_core.tools import StructuredTool

from hagent.skills.arguments import substitute_arguments
from hagent.skills.materialize import SkillMaterializer
from hagent.skills.models import SkillInvocation, SkillInvocationResult, SkillMetadata
from hagent.skills.registry import SkillRegistry

TOOL_NAME = "Skill"


def _skill_body(skill: SkillMetadata) -> str:
    text = skill.skill_file.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    return parts[2].lstrip() if len(parts) == 3 else text


def render_skill_prompt(
    skill: SkillMetadata,
    args: str | None = None,
    *,
    session_id: str | None = None,
    base_dir: str | None = None,
) -> str:
    # base_dir override: in sandbox mode the host base_dir is unreachable from
    # inside the container, so the caller passes the materialized container path.
    effective = base_dir if base_dir is not None else str(skill.base_dir)
    rendered = f"Base directory for this skill: {effective}\n\n{_skill_body(skill)}"
    rendered = substitute_arguments(rendered, args, argument_names=skill.argument_names)
    rendered = rendered.replace("${CLAUDE_SKILL_DIR}", effective)
    rendered = rendered.replace("${HAGENT_SKILL_DIR}", effective)
    rendered = rendered.replace(
        "${CLAUDE_SESSION_ID}",
        session_id or os.environ.get("HAGENT_SESSION_ID", ""),
    )
    return rendered


def create_skill_tool(
    registry: SkillRegistry,
    *,
    session_id: str | None = None,
    materializer: SkillMaterializer | None = None,
) -> StructuredTool:
    def _invoke(skill: str, args: str | None = None) -> dict:
        invocation = SkillInvocation(skill=skill, args=args)
        found = registry.get(invocation.skill)
        if found is None:
            return SkillInvocationResult(
                success=False,
                commandName=invocation.skill,
                error=f"Unknown skill: {invocation.skill}",
            ).model_dump(exclude_none=True)
        if found.disable_model_invocation:
            return SkillInvocationResult(
                success=False,
                commandName=found.name,
                error=(
                    f"Skill {found.name} cannot be used with "
                    "Skill tool due to disable-model-invocation"
                ),
            ).model_dump(exclude_none=True)
        if found.execution_context == "fork":
            return SkillInvocationResult(
                success=False,
                commandName=found.name,
                status="unsupported",
                error="Skill fork execution is not supported in Hagent yet",
            ).model_dump(exclude_none=True)

        base_dir = materializer.materialize(found) if materializer is not None else None
        return SkillInvocationResult(
            success=True,
            commandName=found.name,
            content=render_skill_prompt(
                found, invocation.args, session_id=session_id, base_dir=base_dir
            ),
            allowedTools=found.allowed_tools or None,
            model=found.model,
        ).model_dump(exclude_none=True)

    return StructuredTool.from_function(
        func=_invoke,
        name=TOOL_NAME,
        description=(
            "Execute a skill within the main conversation. Use this before "
            "answering when the user's request matches an available skill."
        ),
        args_schema=SkillInvocation,
    )
