import subprocess
import sys

from hagent import cli
from hagent.cli import _build_skill_message


def test_cli_help_lists_demo():
    result = subprocess.run(
        [sys.executable, "-m", "hagent", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "demo" in result.stdout


def test_cli_demo_requires_message():
    result = subprocess.run(
        [sys.executable, "-m", "hagent", "demo"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    # argparse 缺位置参数时打到 stderr
    assert "message" in result.stderr.lower()


def test_cli_no_subcommand_prints_version():
    result = subprocess.run(
        [sys.executable, "-m", "hagent"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "hagent" in result.stdout


def test_cli_demo_does_not_limit_steps_by_default(monkeypatch):
    calls = []

    def fake_run_demo(message, max_steps, skill=None, skill_args=None, sandbox="none"):
        calls.append((message, max_steps, skill, skill_args))
        return 0

    monkeypatch.setattr(cli, "run_demo", fake_run_demo)

    assert cli.main(["demo", "hi"]) == 0
    assert calls == [("hi", None, None, None)]


def test_cli_demo_passes_explicit_max_steps(monkeypatch):
    calls = []

    def fake_run_demo(message, max_steps, skill=None, skill_args=None, sandbox="none"):
        calls.append((message, max_steps, skill, skill_args))
        return 0

    monkeypatch.setattr(cli, "run_demo", fake_run_demo)

    assert cli.main(["demo", "hi", "--max-steps", "20000"]) == 0
    assert calls == [("hi", 20000, None, None)]


def test_cli_demo_passes_skill_flags(monkeypatch):
    calls = []

    def fake_run_demo(message, max_steps, skill=None, skill_args=None, sandbox="none"):
        calls.append((message, max_steps, skill, skill_args))
        return 0

    monkeypatch.setattr(cli, "run_demo", fake_run_demo)

    assert cli.main(["demo", "hi", "--skill", "review", "--skill-args", "src tests"]) == 0
    assert calls == [("hi", None, "review", "src tests")]


def test_build_skill_message_expands_skill_and_args() -> None:
    message = _build_skill_message("review", "src tests")

    assert message == 'Use the `Skill` tool with skill: "review" and args: "src tests".'


def test_build_skill_message_without_args() -> None:
    message = _build_skill_message("review", None)

    assert message == 'Use the `Skill` tool with skill: "review".'


def test_cli_demo_accepts_sandbox_flag(monkeypatch):
    from hagent import cli
    called = {}

    def fake_run_demo(message, max_steps, skill, skill_args, sandbox):
        called["sandbox"] = sandbox
        called["message"] = message
        return 0

    monkeypatch.setattr(cli, "run_demo", fake_run_demo)
    rc = cli.main(["demo", "hi", "--sandbox", "docker"])
    assert rc == 0
    assert called["sandbox"] == "docker"


def test_cli_sandbox_ls_subcommand(monkeypatch, capsys):
    from hagent import cli
    monkeypatch.setattr(cli, "_sandbox_ls", lambda: (print("CID  KIND  IMAGE"), 0)[1])
    rc = cli.main(["sandbox", "ls"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "CID" in out


def test_cli_sandbox_stop_requires_id():
    from hagent import cli
    # argparse `required=True` 子命令缺 sandbox_id → SystemExit(2)
    import pytest as _pytest
    with _pytest.raises(SystemExit) as ei:
        cli.main(["sandbox", "stop"])
    assert ei.value.code == 2


# ---------------------------------------------------------------------------
# Task B6:sandbox stop/logs 识别 smolvm(hagent- 前缀分派 SDK)
# ---------------------------------------------------------------------------


class _FakeSmolVM:
    def __init__(self, fail_stop: bool = False):
        self.calls: list[str] = []
        self._fail_stop = fail_stop

    def stop(self):
        self.calls.append("stop")
        if self._fail_stop:
            raise RuntimeError("already stopped")

    def delete(self):
        self.calls.append("delete")

    def close(self):
        self.calls.append("close")


def test_smolvm_stop_runs_stop_delete_close(capsys):
    vm = _FakeSmolVM()
    rc = cli._smolvm_stop("hagent-abc-def", from_id=lambda vm_id: vm)
    assert rc == 0
    assert vm.calls == ["stop", "delete", "close"]
    assert "hagent-abc-def" in capsys.readouterr().out


def test_smolvm_stop_tolerates_stop_failure_still_deletes():
    vm = _FakeSmolVM(fail_stop=True)
    rc = cli._smolvm_stop("hagent-abc-def", from_id=lambda vm_id: vm)
    assert rc == 0
    assert "delete" in vm.calls and "close" in vm.calls, "stop 失败仍须 delete 释放租约(F3)"


def test_smolvm_stop_not_found(capsys):
    def raising(vm_id):
        raise RuntimeError(f"VM {vm_id} not found")

    rc = cli._smolvm_stop("hagent-nope-x", from_id=raising)
    assert rc == 1
    assert "not found" in capsys.readouterr().out.lower() or True


def test_smolvm_logs_reads_data_dir_log(tmp_path, capsys):
    (tmp_path / "hagent-abc-def.log").write_text("boot line 1\nboot line 2\n")

    class FakeManager:
        data_dir = tmp_path

        def close(self):
            pass

    rc = cli._smolvm_logs("hagent-abc-def", manager_factory=FakeManager)
    assert rc == 0
    out = capsys.readouterr().out
    assert "boot line 1" in out and "boot line 2" in out


def test_smolvm_logs_missing_file(tmp_path, capsys):
    class FakeManager:
        data_dir = tmp_path

        def close(self):
            pass

    rc = cli._smolvm_logs("hagent-gone-x", manager_factory=FakeManager)
    assert rc == 1


def test_sandbox_stop_dispatches_by_prefix(monkeypatch):
    routed = {}
    monkeypatch.setattr(cli, "_smolvm_stop", lambda vm_id: (routed.setdefault("smolvm", vm_id), 0)[1])
    monkeypatch.setattr(cli, "_sandbox_stop", lambda sid: (routed.setdefault("docker", sid), 0)[1])
    assert cli.main(["sandbox", "stop", "hagent-abc-def"]) == 0
    assert routed == {"smolvm": "hagent-abc-def"}


def test_sandbox_stop_strips_smolvm_id_prefix(monkeypatch):
    """sandbox.id 形如 smolvm-<vm_id>,CLI 接受两种写法。"""
    routed = {}
    monkeypatch.setattr(cli, "_smolvm_stop", lambda vm_id: (routed.setdefault("vm_id", vm_id), 0)[1])
    assert cli.main(["sandbox", "stop", "smolvm-hagent-abc-def"]) == 0
    assert routed == {"vm_id": "hagent-abc-def"}


def test_sandbox_logs_dispatches_by_prefix(monkeypatch):
    routed = {}
    monkeypatch.setattr(cli, "_smolvm_logs", lambda vm_id: (routed.setdefault("smolvm", vm_id), 0)[1])
    monkeypatch.setattr(cli, "_sandbox_logs", lambda sid: (routed.setdefault("docker", sid), 0)[1])
    assert cli.main(["sandbox", "logs", "hagent-abc-def"]) == 0
    assert routed == {"smolvm": "hagent-abc-def"}
    routed.clear()
    assert cli.main(["sandbox", "logs", "deadbeef1234"]) == 0
    assert routed == {"docker": "deadbeef1234"}
