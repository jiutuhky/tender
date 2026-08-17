"""Hagent sandbox protocol — extends deepagents SandboxBackendProtocol."""

from __future__ import annotations

import abc
from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from deepagents.backends.protocol import SandboxBackendProtocol

if TYPE_CHECKING:
    from hagent.sandbox.manifest import SandboxManifest


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

    # —— 生命周期与活跃度(非抽象默认实现:daytona stub / 旧实现零改动)————
    # 池 GC / manager / health / 各工具通道统一按这组方法协作,不再靠 getattr 鸭子探测。

    @property
    def manifest(self) -> "SandboxManifest | None":
        """运行时元数据(paused / gone / last_used_at);无 manifest 的实现返回 None。"""
        return None

    def touch(self) -> None:
        """刷新活跃时间(触达即活跃);默认 no-op。"""

    def pause(self) -> None:
        """冻结沙箱(idle 降档);默认 no-op。"""

    def resume(self) -> None:
        """显式唤醒;默认 no-op。"""

    def ensure_running(self) -> None:
        """通道入口的防御性唤醒:paused 则 resume 并广播 "resumed";
        不可恢复时抛 ``hagent.sandbox.errors.SandboxUnavailable``。默认 no-op。"""

    def health_check(self, *, timeout: int = 5) -> bool:
        """轻量探活;不支持的实现视为恒健康。"""
        return True

    def bind_project(self, project_id: str | None) -> None:
        """池认领/收养时绑定项目归属(审计);默认 no-op。"""

    def set_activity_callback(self, callback: Callable[[], None] | None) -> None:
        """活跃时间回写钩子(→ 项目租约 last_activity_at);默认 no-op。"""

    def set_lifecycle_callback(self, callback: Callable[[str], None] | None) -> None:
        """沙箱自发生命周期变化(如通道内自动唤醒 → "resumed")的出口;默认 no-op。"""

    def shell_exec_argv(self, command_script: str) -> list[str]:
        """Bash 工具的宿主侧 argv 通道;不支持的 provider 抛 NotImplementedError。"""
        raise NotImplementedError(f"{type(self).__name__} 不支持 shell_exec_argv")


@runtime_checkable
class LifecycleSandbox(Protocol):
    """池 / manager / health 依赖的生命周期能力面(结构化类型,供标注与 isinstance)。"""

    @property
    def manifest(self) -> "SandboxManifest | None": ...

    def touch(self) -> None: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def ensure_running(self) -> None: ...

    def health_check(self, *, timeout: int = 5) -> bool: ...

    def bind_project(self, project_id: str | None) -> None: ...

    def set_activity_callback(self, callback: Callable[[], None] | None) -> None: ...

    def set_lifecycle_callback(self, callback: Callable[[str], None] | None) -> None: ...
