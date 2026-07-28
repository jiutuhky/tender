"""Pydantic schema models for the Claude Code-compatible Bash tool."""

import os

from pydantic import BaseModel, ConfigDict, Field, field_validator


DEFAULT_TIMEOUT_MS = 120_000
MAX_TIMEOUT_MS = 600_000


def get_default_timeout_ms() -> int:
    return min(_get_timeout_env("BASH_DEFAULT_TIMEOUT_MS", DEFAULT_TIMEOUT_MS), get_max_timeout_ms())


def get_max_timeout_ms() -> int:
    return _get_timeout_env("BASH_MAX_TIMEOUT_MS", MAX_TIMEOUT_MS)


def _get_timeout_env(name: str, fallback: int) -> int:
    value = os.getenv(name)
    if value is None:
        return fallback
    try:
        parsed = int(value)
    except ValueError:
        return fallback
    return parsed if parsed >= 0 else fallback


class BashInput(BaseModel):
    """Input accepted by the Bash tool."""

    model_config = ConfigDict(extra="forbid")

    command: str = Field(min_length=1)
    timeout: int | None = Field(default_factory=get_default_timeout_ms, ge=0)
    description: str | None = None
    run_in_background: bool | None = None
    dangerouslyDisableSandbox: bool | None = None

    @field_validator("command")
    @classmethod
    def validate_command_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("command must not be blank")
        return value

    @field_validator("timeout")
    @classmethod
    def validate_timeout_max(cls, value: int | None) -> int | None:
        if value is not None and value > get_max_timeout_ms():
            raise ValueError(f"timeout must be less than or equal to {get_max_timeout_ms()}")
        return value


class BashResult(BaseModel):
    """Runtime result shape reserved for the future Bash execution layer."""

    model_config = ConfigDict(extra="forbid")

    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    interrupted: bool = False
    background_task_id: str | None = None
    backgrounded_by_user: bool | None = None
    assistant_auto_backgrounded: bool | None = None
    return_code_interpretation: str | None = None
    no_output_expected: bool = False
    persisted_output_path: str | None = None
    persisted_output_size: int | None = None
    truncated: bool = False
