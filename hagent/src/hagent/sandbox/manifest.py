"""Sandbox session metadata dataclasses."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

SandboxRuntimeState = Literal["running", "paused", "gone"]


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
    # pause 态的单一真相源(健康巡检据此豁免、通道据此自动唤醒);pause/resume 成对维护
    paused: bool = False
    # VM/容器已拆(close 后置位):通道据此产出 sandbox_unavailable:gone 契约文案,
    # 而不是让 SDK 抛出的"VM 不存在"原文进模型
    gone: bool = False

    @property
    def state(self) -> SandboxRuntimeState:
        if self.gone:
            return "gone"
        if self.paused:
            return "paused"
        return "running"

    def touch(self) -> None:
        self.last_used_at = time.time()
