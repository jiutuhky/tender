from __future__ import annotations

from typing import NotRequired, TypedDict

MODEL_ALIASES: dict[str, str | None] = {
    "sonnet": "anthropic:claude-sonnet-4-6",
    "opus": "anthropic:claude-opus-4-7",
    "haiku": "anthropic:claude-haiku-4-5",
    "inherit": None,
}


def resolve_model_alias(model: str | None) -> str | None:
    if model is None:
        return None
    if model in MODEL_ALIASES:
        return MODEL_ALIASES[model]
    return model


class SubagentSpec(TypedDict):
    name: str
    description: str
    system_prompt: str
    tools: NotRequired[list[str]]
    disallowed_tools: NotRequired[list[str]]
    model: NotRequired[str | None]
    color: NotRequired[str]
    skills: NotRequired[list[str]]
    hooks: NotRequired[dict]
    omit_claude_md: NotRequired[bool]
    source: NotRequired[str]
