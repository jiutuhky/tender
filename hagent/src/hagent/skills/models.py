from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SkillMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    skill_file: Path
    base_dir: Path
    source_label: str
    display_name: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    argument_hint: str | None = None
    argument_names: list[str] = Field(default_factory=list)
    when_to_use: str | None = None
    version: str | None = None
    model: str | None = None
    disable_model_invocation: bool = False
    user_invocable: bool = True
    execution_context: Literal["fork"] | None = None
    agent: str | None = None
    paths: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    license: str | None = None
    compatibility: str | None = None

    @field_validator("name", "description", "source_label")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "value must not be empty"
            raise ValueError(msg)
        return stripped

    @field_validator(
        "display_name",
        "argument_hint",
        "when_to_use",
        "version",
        "model",
        "agent",
        "license",
        "compatibility",
    )
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class SkillInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: str
    args: str | None = None

    @field_validator("skill")
    @classmethod
    def _normalize_skill(cls, value: str) -> str:
        stripped = value.strip().lstrip("/")
        if not stripped:
            msg = "skill must not be empty"
            raise ValueError(msg)
        return stripped


class SkillInvocationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    commandName: str
    status: Literal["inline", "unsupported"] = "inline"
    content: str | None = None
    allowedTools: list[str] | None = None
    model: str | None = None
    error: str | None = None


def stringify_metadata(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}
