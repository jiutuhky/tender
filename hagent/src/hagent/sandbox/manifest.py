"""Sandbox session metadata dataclasses."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class SandboxManifest:
    """Lightweight metadata describing a live sandbox instance."""

    sandbox_id: str
    kind: str
    image_tag: str
    runtime: str
    container_id: str | None = None
    workspace_dir: str = "/workspace"
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    paused: bool = False

    def touch(self) -> None:
        self.last_used_at = time.time()
