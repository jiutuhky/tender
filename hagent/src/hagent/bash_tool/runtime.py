"""Local Bash runtime with foreground and background process lifecycle support."""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import IO

from hagent.bash_tool.output import OutputManager
from hagent.bash_tool.schema import BashResult, get_default_timeout_ms
from hagent.bash_tool.shell_provider import ShellProvider
from hagent.bash_tool.tasks import TaskRegistry


DEFAULT_INLINE_OUTPUT_THRESHOLD = 30_000
DEFAULT_BACKGROUND_OUTPUT_LIMIT = 1_000_000


class BashRuntime:
    """Executes shell commands using short-lived local bash/zsh processes."""

    def __init__(
        self,
        workspace_root: Path,
        *,
        shell_provider: ShellProvider | None = None,
        task_registry: TaskRegistry | None = None,
        output_manager: OutputManager | None = None,
        inline_output_threshold: int = DEFAULT_INLINE_OUTPUT_THRESHOLD,
        background_output_limit: int = DEFAULT_BACKGROUND_OUTPUT_LIMIT,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.shell_provider = shell_provider or ShellProvider(self.workspace_root)
        self.task_registry = task_registry or TaskRegistry()
        self.output_manager = output_manager or OutputManager(
            self.workspace_root,
            inline_threshold=inline_output_threshold,
        )
        self.background_output_limit = background_output_limit
        self._watcher_lock = threading.RLock()
        self._watcher_threads: dict[str, threading.Thread] = {}
        self._closed = False

    def execute(
        self,
        command: str,
        *,
        timeout_ms: int | None = None,
        run_in_background: bool = False,
        description: str | None = None,
    ) -> BashResult:
        if self._closed:
            msg = "BashRuntime is closed"
            raise RuntimeError(msg)
        if run_in_background:
            return self._start_background(command, description=description)
        return self._execute_foreground(command, timeout_ms=timeout_ms, description=description)

    def close(self) -> None:
        self._closed = True
        self.task_registry.cleanup()
        self._wait_for_background_watchers(timeout_seconds=2.0)

    def _execute_foreground(
        self,
        command: str,
        *,
        timeout_ms: int | None,
        description: str | None,
    ) -> BashResult:
        task_id = self._new_task_id()
        output_path = self.output_manager.create_output_file(task_id)
        cwd_file = self._cwd_file(task_id)
        command_script = self.shell_provider.build_command(command, cwd_file=cwd_file)
        timeout_seconds = (timeout_ms if timeout_ms is not None else get_default_timeout_ms()) / 1000

        interrupted = False
        stderr = ""
        exit_code: int | None = None
        with output_path.open("ab", buffering=0) as output_handle:
            proc = subprocess.Popen(
                self.shell_provider.command_argv(command_script),
                cwd=str(self.workspace_root),
                env=self._process_env(),
                stdin=subprocess.DEVNULL,
                stdout=output_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            self.task_registry.start(
                task_id=task_id,
                command=command,
                description=description,
                pid=proc.pid,
                process_group_id=proc.pid,
                output_path=output_path,
            )
            try:
                exit_code = proc.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                interrupted = True
                stderr = f"Command timed out after {int(timeout_seconds * 1000)}ms"
                self._kill_process_group(proc.pid)
                exit_code = proc.wait()

        if not interrupted:
            self._update_cwd_from_file(cwd_file)
        cwd_file.unlink(missing_ok=True)
        self.task_registry.mark_completed(task_id, exit_code=exit_code, interrupted=interrupted)

        # cwd 捕获必须在 finalize 之前:finalize 对未截断的小输出会 unlink
        # 输出文件,之后再读哨兵只会静默失败(sandbox 模式 cd 从不持久的根因)
        if getattr(self.shell_provider, "sandbox", None) is not None:
            self._capture_sandbox_cwd_from_output(output_path)
        summary = self.output_manager.finalize_foreground(output_path)
        return BashResult(
            stdout=summary.inline_text,
            stderr=stderr,
            exit_code=exit_code,
            interrupted=interrupted,
            persisted_output_path=summary.persisted_output_path,
            persisted_output_size=summary.persisted_output_size if summary.truncated else None,
            truncated=summary.truncated,
            no_output_expected=not summary.inline_text and exit_code == 0 and not stderr,
        )

    def _start_background(self, command: str, *, description: str | None) -> BashResult:
        task_id = self._new_task_id()
        output_path = self.output_manager.create_output_file(task_id)
        cwd_file = self._cwd_file(task_id)
        command_script = self.shell_provider.build_command(command, cwd_file=cwd_file)
        output_handle = output_path.open("ab", buffering=0)
        proc = subprocess.Popen(
            self.shell_provider.command_argv(command_script),
            cwd=str(self.workspace_root),
            env=self._process_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.task_registry.start(
            task_id=task_id,
            command=command,
            description=description,
            pid=proc.pid,
            process_group_id=proc.pid,
            output_path=output_path,
            status="backgrounded",
        )
        thread = threading.Thread(
            target=self._watch_background,
            args=(task_id, proc, output_handle, cwd_file),
            daemon=True,
        )
        with self._watcher_lock:
            self._watcher_threads[task_id] = thread
        thread.start()
        return BashResult(
            stdout="",
            exit_code=None,
            background_task_id=task_id,
            backgrounded_by_user=True,
            persisted_output_path=str(output_path),
            persisted_output_size=0,
        )

    def _watch_background(
        self,
        task_id: str,
        proc: subprocess.Popen[bytes],
        output_handle: IO[bytes],
        cwd_file: Path,
    ) -> None:
        killed_for_output = False
        output_size = 0
        try:
            if proc.stdout is not None:
                for chunk in iter(lambda: proc.stdout.read(8192), b""):
                    output_handle.write(chunk)
                    output_size += len(chunk)
                    if not killed_for_output and output_size > self.background_output_limit:
                        killed_for_output = True
                        self.task_registry.kill(task_id)
            else:
                proc.wait()
            if self._output_exceeds_background_limit(output_size) and not killed_for_output:
                if proc.poll() is None:
                    killed_for_output = True
                    self.task_registry.kill(task_id)
            exit_code = proc.wait()
            record = self.task_registry.get(task_id)
            interrupted = killed_for_output or exit_code < 0 or bool(record and record.interrupted)
            self.task_registry.mark_completed(task_id, exit_code=exit_code, interrupted=interrupted)
        finally:
            output_handle.close()
            cwd_file.unlink(missing_ok=True)
            with self._watcher_lock:
                self._watcher_threads.pop(task_id, None)

    def _process_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update(
            {
                "SHELL": str(self.shell_provider.shell_path),
                "GIT_EDITOR": "true",
                "CLAUDECODE": "1",
            }
        )
        return env

    def _output_exceeds_background_limit(self, output_size: int) -> bool:
        return output_size > self.background_output_limit

    def _update_cwd_from_file(self, cwd_file: Path) -> None:
        if not cwd_file.exists():
            return
        raw_cwd = cwd_file.read_text(encoding="utf-8", errors="replace").strip()
        if raw_cwd:
            self.shell_provider.update_cwd(Path(raw_cwd))

    def _capture_sandbox_cwd_from_output(self, output_path: Path) -> None:
        """Parse __HAGENT_PWD__: lines from sandbox output to update shell_provider cwd."""
        try:
            text = output_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        sentinel = "__HAGENT_PWD__:"
        last: str | None = None
        for line in text.splitlines():
            if line.startswith(sentinel):
                last = line[len(sentinel):].strip()
        if last:
            self.shell_provider.update_cwd(Path(last))

    def _kill_process_group(self, process_group_id: int) -> None:
        try:
            os.killpg(process_group_id, signal.SIGKILL)
        except ProcessLookupError:
            return

    def _cwd_file(self, task_id: str) -> Path:
        return Path(tempfile.gettempdir()) / f"hagent-{task_id}.cwd"

    def _new_task_id(self) -> str:
        return f"bash_{uuid.uuid4().hex}"

    def _wait_for_background_watchers(self, *, timeout_seconds: float) -> None:
        deadline = time.monotonic() + timeout_seconds
        while True:
            with self._watcher_lock:
                items = list(self._watcher_threads.items())
            if not items:
                return

            for task_id, thread in items:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                thread.join(timeout=min(0.1, remaining))
                if not thread.is_alive():
                    with self._watcher_lock:
                        self._watcher_threads.pop(task_id, None)
