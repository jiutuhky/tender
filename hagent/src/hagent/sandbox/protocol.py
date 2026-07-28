"""Hagent sandbox protocol — extends deepagents SandboxBackendProtocol."""

from __future__ import annotations

import abc
from enum import Enum
from pathlib import Path

from deepagents.backends.protocol import SandboxBackendProtocol


class SandboxKind(str, Enum):
    NONE = "none"
    DOCKER = "docker"
    DAYTONA = "daytona"
    SMOLVM = "smolvm"

    @classmethod
    def from_str(cls, value: str) -> "SandboxKind":
        try:
            return cls(value.strip().lower())
        except ValueError as exc:
            raise ValueError(f"unknown sandbox kind: {value!r}") from exc


class HagentSandboxProtocol(SandboxBackendProtocol, abc.ABC):
    """Hagent's extension over deepagents SandboxBackendProtocol.

    Adds workspace_dir (sandbox-internal root, default ``/workspace``), kind tag,
    and close() lifecycle. Implementations also expose execute/upload_files/
    download_files inherited from deepagents.
    """

    @property
    @abc.abstractmethod
    def workspace_dir(self) -> str:
        """Sandbox-internal workspace path. LLM-visible files live here."""

    @property
    @abc.abstractmethod
    def kind(self) -> SandboxKind: ...

    @abc.abstractmethod
    def close(self) -> None:
        """Tear down the sandbox (stop+rm container, free resources)."""
