"""SandboxShellProvider — drop-in ShellProvider that targets a sandbox.

Bash 工具的命令不走 ``sandbox.execute()``,而是由 BashRuntime 在宿主侧
spawn 子进程(流式输出/超时杀进程组/后台任务都绑在这条通道上)。
argv 形态因 provider 而异:docker 拼 ``docker exec``;smolvm 由
``sandbox.shell_exec_argv()`` 自建(SSH 兜底通道,spec D4——vsock 无流式,F4)。
"""

from __future__ import annotations

import shlex
import tempfile
import threading
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from hagent.bash_tool.shell_provider import ShellProvider
from hagent.sandbox.protocol import SandboxKind

if TYPE_CHECKING:
    from hagent.sandbox.protocol import HagentSandboxProtocol


SANDBOX_SAFE_ENV: tuple[tuple[str, str], ...] = (
    ("PATH", "/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin"),
    ("HOME", "/workspace"),
    ("LANG", "C.UTF-8"),
    ("TERM", "dumb"),
)


class SandboxShellProvider(ShellProvider):
    """Replacement ShellProvider that targets a sandbox (docker / smolvm).

    We deliberately do NOT call ``super().__init__``: the base class would
    resolve a host shell and write a host-side env snapshot. In sandbox mode
    the env is injected per-provider(docker 经 ``docker exec -e``,smolvm 经
    build_command 的 export 前缀)and the snapshot file is only kept to
    satisfy callers that read ``snapshot_path``.
    """

    def __init__(
        self,
        *,
        sandbox: "HagentSandboxProtocol",
        workspace_root: Path,
        session_env_path: Path | None = None,
    ) -> None:
        self.sandbox = sandbox
        self.workspace_root = Path(workspace_root)
        # bash inside the container
        self.shell_path = Path("/bin/bash")
        self.snapshot_path = session_env_path or self._default_snapshot_path()
        # PurePosixPath because we are addressing container-internal paths.
        self._current_cwd: PurePosixPath = PurePosixPath(str(workspace_root))
        self._lock = threading.RLock()
        self._write_snapshot_stub()

    @property
    def current_cwd(self) -> Path:
        with self._lock:
            return Path(str(self._current_cwd))

    def update_cwd(self, cwd: Path) -> None:
        with self._lock:
            self._current_cwd = PurePosixPath(str(cwd))

    def build_command(self, command: str, *, cwd_file: Path) -> str:
        # cwd_file is host-visible; sandbox cannot write to it. Instead we emit
        # a __HAGENT_PWD__ sentinel line that BashRuntime parses post-execution.
        # 哨兵经 EXIT trap 在命令结束后打印(对齐 host ShellProvider 的
        # trap 捕获)——放命令前只会打起始 cwd,cd 永远不持久。
        _ = cwd_file
        with self._lock:
            quoted_cwd = shlex.quote(str(self._current_cwd))
        env_exports = "\n".join(
            f"export {name}={shlex.quote(value)}" for name, value in SANDBOX_SAFE_ENV
        )
        return "\n".join(
            [
                env_exports,
                f"cd {quoted_cwd} || exit 1",
                'export HAGENT_CURRENT_CWD="$PWD"',
                "_hagent_emit_pwd() {",
                "  printf '__HAGENT_PWD__:%s\\n' \"$PWD\"",
                "}",
                "trap _hagent_emit_pwd EXIT",
                command,
            ]
        )

    def command_argv(self, command_script: str) -> list[str]:
        # smolvm 等非 docker provider:argv 构造下放给 sandbox 本体
        #(它掌握 guest ip / 密钥等 SDK 细节;docker 分支保持原状零影响)
        kind = getattr(self.sandbox, "kind", None)
        if getattr(kind, "value", kind) == SandboxKind.SMOLVM.value:
            return self.sandbox.shell_exec_argv(command_script)
        container_id = self.sandbox._container.id  # noqa: SLF001
        with self._lock:
            cwd_str = str(self._current_cwd)
        argv: list[str] = [
            "docker",
            "exec",
            "-i",
            "-w",
            cwd_str,
        ]
        for name, value in SANDBOX_SAFE_ENV:
            argv.extend(["-e", f"{name}={value}"])
        argv.extend([container_id, "/bin/bash", "-c", command_script])
        return argv

    def _write_snapshot_stub(self) -> None:
        """Write a placeholder env snapshot so callers that probe the path do not fail.

        The actual env is injected via ``docker exec -e`` in ``command_argv``.
        """
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"export {name}={shlex.quote(value)}"
            for name, value in SANDBOX_SAFE_ENV
        ]
        lines.append("")
        self.snapshot_path.write_text("\n".join(lines), encoding="utf-8")
        self.snapshot_path.chmod(0o600)

    @staticmethod
    def _default_snapshot_path() -> Path:
        tmp_dir = tempfile.mkdtemp(prefix="hagent-sandbox-shell-")
        return Path(tmp_dir) / "shell-session.sh"
