from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import ExecuteResponse


class HagentLocalShellBackend(LocalShellBackend):
    """Local shell backend that runs commands through bash."""

    def __init__(
        self,
        root_dir: str | Path | None = None,
        *,
        virtual_mode: bool | None = None,
        timeout: int = 120,
        max_output_bytes: int = 100_000,
        env: dict[str, str] | None = None,
        inherit_env: bool = False,
        **kwargs: Any,
    ) -> None:
        if not inherit_env:
            shell_env = {
                "HOME": os.path.expanduser("~"),
                "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                "SHELL": os.environ.get("SHELL", "/bin/bash"),
            }
            if env is not None:
                shell_env.update(env)
            env = shell_env
        super().__init__(
            root_dir=root_dir,
            virtual_mode=virtual_mode,
            timeout=timeout,
            max_output_bytes=max_output_bytes,
            env=env,
            inherit_env=inherit_env,
            **kwargs,
        )

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        if not command or not isinstance(command, str):
            return ExecuteResponse(
                output="Error: Command must be a non-empty string.",
                exit_code=1,
                truncated=False,
            )

        effective_timeout = timeout if timeout is not None else self._default_timeout
        if effective_timeout <= 0:
            msg = f"timeout must be positive, got {effective_timeout}"
            raise ValueError(msg)

        try:
            result = subprocess.run(
                ["bash", "-lc", command],
                check=False,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=effective_timeout,
                env=self._env,
                cwd=str(self.cwd),
            )

            output_parts = []
            if result.stdout:
                output_parts.append(result.stdout)
            if result.stderr:
                stderr_lines = result.stderr.strip().split("\n")
                output_parts.extend(f"[stderr] {line}" for line in stderr_lines)

            output = "\n".join(output_parts) if output_parts else "<no output>"

            truncated = False
            if len(output) > self._max_output_bytes:
                output = output[: self._max_output_bytes]
                output += f"\n\n... Output truncated at {self._max_output_bytes} bytes."
                truncated = True

            if result.returncode != 0:
                output = f"{output.rstrip()}\n\nExit code: {result.returncode}"

            return ExecuteResponse(
                output=output,
                exit_code=result.returncode,
                truncated=truncated,
            )
        except subprocess.TimeoutExpired:
            if timeout is not None:
                msg = f"Error: Command timed out after {effective_timeout} seconds (custom timeout). The command may be stuck or require more time."
            else:
                msg = f"Error: Command timed out after {effective_timeout} seconds. For long-running commands, re-run using the timeout parameter."
            return ExecuteResponse(output=msg, exit_code=124, truncated=False)
        except Exception as e:
            return ExecuteResponse(
                output=f"Error executing command ({type(e).__name__}): {e}",
                exit_code=1,
                truncated=False,
            )
