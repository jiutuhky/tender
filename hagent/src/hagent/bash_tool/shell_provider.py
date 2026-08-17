"""Shell discovery and command wrapping for the Bash runtime."""

from __future__ import annotations

import os
import shlex
import tempfile
import threading
from pathlib import Path
from shutil import which


COMMON_SHELL_PATHS = (
    "/bin/bash",
    "/usr/bin/bash",
    "/usr/local/bin/bash",
    "/bin/zsh",
    "/usr/bin/zsh",
    "/usr/local/bin/zsh",
)
SNAPSHOT_ENV_ALLOWLIST = (
    "HOME",
    "PATH",
    "SHELL",
    "USER",
    "LOGNAME",
    "LANG",
    "LC_ALL",
    "TERM",
    "TMPDIR",
)


class ShellProviderUnavailable(RuntimeError):
    """ShellProvider 无法给出可执行 argv(沙箱环境不可用)。

    BashRuntime 捕获后直接构造 ``BashResult``(stderr=message, exit_code),
    让模型拿到面向模型的契约文案,而不是异常穿透炸掉整条 agent 流。
    """

    def __init__(self, message: str, *, exit_code: int = 137) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


def _is_executable(path: Path) -> bool:
    return path.exists() and os.access(path, os.X_OK)


def _is_bash_or_zsh(path: Path) -> bool:
    name = path.name.lower()
    return "bash" in name or "zsh" in name


def resolve_shell() -> Path:
    explicit = os.environ.get("HAGENT_BASH_SHELL")
    if explicit:
        path = Path(explicit).expanduser()
        if _is_executable(path):
            return path
        msg = f"HAGENT_BASH_SHELL is not executable: {path}"
        raise RuntimeError(msg)

    env_shell = os.environ.get("SHELL")
    if env_shell:
        path = Path(env_shell).expanduser()
        if _is_bash_or_zsh(path) and _is_executable(path):
            return path

    for candidate in (which("bash"), which("zsh"), *COMMON_SHELL_PATHS):
        if candidate is None:
            continue
        path = Path(candidate)
        if _is_executable(path):
            return path

    msg = "No executable bash or zsh shell found"
    raise RuntimeError(msg)


class ShellProvider:
    """Maintains a reusable sourceable shell snapshot for command execution."""

    def __init__(self, workspace_root: Path, session_env_path: Path | None = None) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.shell_path = resolve_shell()
        self.snapshot_path = session_env_path or self._default_snapshot_path()
        self._current_cwd = self.workspace_root
        self._lock = threading.RLock()
        self._create_snapshot()

    @property
    def current_cwd(self) -> Path:
        with self._lock:
            return self._current_cwd

    def _create_snapshot(self) -> None:
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_snapshot(self._current_cwd)

    def update_cwd(self, cwd: Path) -> None:
        resolved = Path(cwd).resolve()
        with self._lock:
            self._current_cwd = resolved

    def build_command(self, command: str, *, cwd_file: Path) -> str:
        quoted_snapshot = shlex.quote(str(self.snapshot_path))
        quoted_cwd_file = shlex.quote(str(cwd_file))
        with self._lock:
            quoted_cwd = shlex.quote(str(self._current_cwd))
        return "\n".join(
            [
                f"source {quoted_snapshot}",
                f"cd {quoted_cwd} || exit 1",
                "export HAGENT_CURRENT_CWD=\"$PWD\"",
                "_hagent_capture_cwd() {",
                f"  printf '%s\\n' \"$PWD\" > {quoted_cwd_file}",
                "}",
                "trap _hagent_capture_cwd EXIT",
                command,
            ]
        )

    def command_argv(self, command_script: str) -> list[str]:
        return [str(self.shell_path), "-c", command_script]

    def _write_snapshot(self, cwd: Path) -> None:
        env = {
            name: os.environ[name]
            for name in SNAPSHOT_ENV_ALLOWLIST
            if name in os.environ
        }
        env["SHELL"] = str(self.shell_path)
        env["HAGENT_WORKSPACE_ROOT"] = str(self.workspace_root)
        lines = [
            f"export {name}={shlex.quote(value)}"
            for name, value in sorted(env.items())
        ]
        lines.append("")
        content = "\n".join(lines)
        self.snapshot_path.write_text(content, encoding="utf-8")
        self.snapshot_path.chmod(0o600)

    def _default_snapshot_path(self) -> Path:
        temp_dir = tempfile.mkdtemp(prefix="hagent-bash-")
        return Path(temp_dir) / "shell-session.sh"
