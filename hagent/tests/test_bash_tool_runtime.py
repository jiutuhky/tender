from __future__ import annotations

from pathlib import Path
import os
import shlex
import sys
import time

from hagent.bash_tool.runtime import BashRuntime
from hagent.bash_tool.shell_provider import ShellProvider, resolve_shell


def wait_for_task(runtime: BashRuntime, task_id: str, *, timeout: float = 3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = runtime.task_registry.get(task_id)
        if task and task.status not in {"running", "backgrounded"}:
            return task
        time.sleep(0.03)
    return runtime.task_registry.get(task_id)


def python_command(code: str, *, unbuffered: bool = False) -> str:
    flag = " -u" if unbuffered else ""
    return f"{shlex.quote(sys.executable)}{flag} -c {shlex.quote(code)}"


def test_resolve_shell_prefers_hagent_bash_shell(monkeypatch, tmp_path: Path) -> None:
    fake_shell = tmp_path / "bash"
    fake_shell.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_shell.chmod(0o755)
    monkeypatch.setenv("HAGENT_BASH_SHELL", str(fake_shell))
    monkeypatch.setenv("SHELL", "/not/used/zsh")

    assert resolve_shell() == fake_shell


def test_resolve_shell_uses_shell_env_when_it_is_bash_or_zsh(monkeypatch, tmp_path: Path) -> None:
    fake_shell = tmp_path / "zsh"
    fake_shell.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_shell.chmod(0o755)
    monkeypatch.delenv("HAGENT_BASH_SHELL", raising=False)
    monkeypatch.setenv("SHELL", str(fake_shell))

    assert resolve_shell() == fake_shell


def test_bash_brace_expansion_works(tmp_path: Path) -> None:
    runtime = BashRuntime(tmp_path)
    try:
        result = runtime.execute("mkdir -p app/{api,core}")

        assert result.exit_code == 0
        assert (tmp_path / "app" / "api").is_dir()
        assert (tmp_path / "app" / "core").is_dir()
    finally:
        runtime.close()


def test_cwd_changes_persist_across_sequential_foreground_commands(tmp_path: Path) -> None:
    runtime = BashRuntime(tmp_path)
    (tmp_path / "sub").mkdir()
    try:
        first = runtime.execute("cd sub")
        second = runtime.execute("pwd")

        assert first.exit_code == 0
        assert second.exit_code == 0
        assert second.stdout.strip() == str(tmp_path / "sub")
    finally:
        runtime.close()


def test_stdin_is_connected_to_dev_null(tmp_path: Path) -> None:
    runtime = BashRuntime(tmp_path)
    try:
        result = runtime.execute(python_command('import sys; print(sys.stdin.read() == "")'))

        assert result.exit_code == 0
        assert result.stdout.strip() == "True"
    finally:
        runtime.close()


def test_stdout_and_stderr_are_merged_chronologically_inline(tmp_path: Path) -> None:
    runtime = BashRuntime(tmp_path)
    try:
        result = runtime.execute(
            python_command(
                (
                    "import sys\n"
                    "print('out1', flush=True)\n"
                    "print('err1', file=sys.stderr, flush=True)\n"
                    "print('out2', flush=True)\n"
                ),
                unbuffered=True,
            )
        )

        assert result.exit_code == 0
        assert result.stdout.splitlines() == ["out1", "err1", "out2"]
        assert result.stderr == ""
    finally:
        runtime.close()


def test_timeout_kills_long_running_foreground_process_group(tmp_path: Path) -> None:
    runtime = BashRuntime(tmp_path)
    marker = tmp_path / "child-survived"
    try:
        result = runtime.execute(
            python_command(
                (
                    "import subprocess, time\n"
                    "subprocess.Popen(['bash', '-c', 'sleep 0.7; touch child-survived'])\n"
                    "time.sleep(5)\n"
                )
            ),
            timeout_ms=100,
        )
        time.sleep(0.9)

        assert result.interrupted is True
        assert result.exit_code != 0
        assert "timed out" in result.stderr
        assert not marker.exists()
    finally:
        runtime.close()


def test_large_output_persists_to_readable_log(tmp_path: Path) -> None:
    runtime = BashRuntime(tmp_path, inline_output_threshold=10)
    try:
        result = runtime.execute("printf 0123456789abcdef")

        assert result.truncated is True
        assert result.stdout == "0123456789"
        assert result.persisted_output_path is not None
        output_path = Path(result.persisted_output_path)
        assert output_path.exists()
        assert output_path.parent == tmp_path / ".hagent" / "tool-results"
        assert output_path.read_text(encoding="utf-8") == "0123456789abcdef"
    finally:
        runtime.close()


def test_shell_snapshot_is_created_once_and_reused_across_commands(tmp_path: Path) -> None:
    class CountingShellProvider(ShellProvider):
        def __init__(self, workspace_root: Path) -> None:
            self.snapshot_creations = 0
            super().__init__(workspace_root)

        def _create_snapshot(self) -> None:
            self.snapshot_creations += 1
            super()._create_snapshot()

    provider = CountingShellProvider(tmp_path)
    runtime = BashRuntime(tmp_path, shell_provider=provider)
    try:
        first_snapshot = provider.snapshot_path
        snapshot_before = first_snapshot.read_text(encoding="utf-8")
        result = runtime.execute('printf "%s" "$HAGENT_CURRENT_CWD"')
        runtime.execute("mkdir -p nested && cd nested")
        cwd = runtime.execute("pwd")

        assert result.stdout == str(tmp_path)
        assert provider.snapshot_creations == 1
        assert provider.snapshot_path == first_snapshot
        assert first_snapshot.read_text(encoding="utf-8") == snapshot_before
        assert cwd.stdout.strip() == str(tmp_path / "nested")
    finally:
        runtime.close()


def test_default_shell_snapshot_path_is_outside_workspace(tmp_path: Path) -> None:
    provider = ShellProvider(tmp_path)

    assert provider.snapshot_path.exists()
    assert not provider.snapshot_path.resolve().is_relative_to(tmp_path.resolve())


def test_explicit_shell_snapshot_path_is_honored(tmp_path: Path) -> None:
    explicit = tmp_path / ".hagent" / "explicit-session.sh"

    provider = ShellProvider(tmp_path, session_env_path=explicit)

    assert provider.snapshot_path == explicit
    assert provider.snapshot_path.exists()


def test_shell_snapshot_only_persists_safe_environment_vars(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")
    monkeypatch.setenv("CUSTOM_TOKEN", "token-secret")
    monkeypatch.setenv("SERVICE_SECRET", "service-secret")
    monkeypatch.setenv("PATH", "/safe/bin")

    provider = ShellProvider(tmp_path)
    snapshot = provider.snapshot_path.read_text(encoding="utf-8")

    assert "anthropic-secret" not in snapshot
    assert "openai-secret" not in snapshot
    assert "token-secret" not in snapshot
    assert "service-secret" not in snapshot
    assert "ANTHROPIC_API_KEY" not in snapshot
    assert "OPENAI_API_KEY" not in snapshot
    assert "CUSTOM_TOKEN" not in snapshot
    assert "SERVICE_SECRET" not in snapshot
    assert "export PATH=/safe/bin" in snapshot
    assert f"export HAGENT_WORKSPACE_ROOT={shlex.quote(str(tmp_path))}" in snapshot


def test_background_task_returns_task_id_and_completed_output_is_readable(tmp_path: Path) -> None:
    runtime = BashRuntime(tmp_path)
    try:
        result = runtime.execute(
            "printf background-ok",
            run_in_background=True,
            description="Print background output",
        )

        assert result.background_task_id is not None
        task = wait_for_task(runtime, result.background_task_id)
        assert task is not None
        assert task.status == "completed"
        assert task.exit_code == 0
        assert task.output_path.read_text(encoding="utf-8") == "background-ok"
    finally:
        runtime.close()


def test_background_output_size_watchdog_kills_excessive_output(tmp_path: Path) -> None:
    runtime = BashRuntime(tmp_path, background_output_limit=128)
    try:
        result = runtime.execute(
            python_command(
                (
                    "import time\n"
                    "for _ in range(1000):\n"
                    "    print('x' * 80, flush=True)\n"
                    "    time.sleep(0.01)\n"
                ),
                unbuffered=True,
            ),
            run_in_background=True,
            description="Print excessive output",
        )

        assert result.background_task_id is not None
        task = wait_for_task(runtime, result.background_task_id)
        assert task is not None
        assert task.status == "killed"
        assert task.interrupted is True
        assert task.output_path.stat().st_size > 128
    finally:
        runtime.close()


def test_close_kills_running_background_tasks(tmp_path: Path) -> None:
    runtime = BashRuntime(tmp_path)
    result = runtime.execute("sleep 5", run_in_background=True, description="Sleep")

    assert result.background_task_id is not None
    runtime.close()

    task = wait_for_task(runtime, result.background_task_id)
    assert task is not None
    assert task.status == "killed"
    assert task.interrupted is True


def test_close_waits_for_background_watcher_cleanup(tmp_path: Path) -> None:
    runtime = BashRuntime(tmp_path)
    result = runtime.execute("printf close-cleanup", run_in_background=True, description="Print")

    assert result.background_task_id is not None
    runtime.close()

    assert result.background_task_id not in runtime._watcher_threads
    assert not any(thread.is_alive() for thread in runtime._watcher_threads.values())


def test_runtime_execute_uses_discovered_shell_env(monkeypatch, tmp_path: Path) -> None:
    shell = tmp_path / "bash"
    shell.write_text(f"#!{os.environ.get('SHELL', '/bin/sh')}\nexec /bin/bash \"$@\"\n", encoding="utf-8")
    shell.chmod(0o755)
    monkeypatch.setenv("HAGENT_BASH_SHELL", str(shell))

    runtime = BashRuntime(tmp_path)
    try:
        assert runtime.shell_provider.shell_path == shell
    finally:
        runtime.close()
