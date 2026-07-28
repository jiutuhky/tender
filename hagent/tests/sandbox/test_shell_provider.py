from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hagent.sandbox.providers.shell import SandboxShellProvider


@pytest.fixture
def fake_sandbox():
    sb = MagicMock()
    sb.id = "docker-cidcid"
    sb._container = MagicMock()
    sb._container.id = "cidcid"
    sb.workspace_dir = "/workspace"
    return sb


def test_command_argv_uses_docker_exec(tmp_path, fake_sandbox):
    provider = SandboxShellProvider(sandbox=fake_sandbox, workspace_root=Path("/workspace"))
    argv = provider.command_argv("echo hi")
    assert argv[0] == "docker"
    assert argv[1] == "exec"
    assert "cidcid" in argv
    assert "/bin/bash" in argv
    # script appears at the tail
    assert argv[-1] == "echo hi"


def test_build_command_passes_through_snapshot(tmp_path, fake_sandbox):
    provider = SandboxShellProvider(sandbox=fake_sandbox, workspace_root=Path("/workspace"))
    cwd_file = tmp_path / "cwd"
    script = provider.build_command("ls", cwd_file=cwd_file)
    assert "cd " in script
    # sandbox mode emits a __HAGENT_PWD__ sentinel line instead of writing host cwd_file
    assert "__HAGENT_PWD__" in script
    assert "ls" in script


def test_build_command_sentinel_captures_post_command_cwd(tmp_path, fake_sandbox):
    # 哨兵必须在命令之后经 EXIT trap 打印,否则 cd 不持久(docker/smolvm 同病)
    provider = SandboxShellProvider(sandbox=fake_sandbox, workspace_root=Path("/workspace"))
    script = provider.build_command("cd sub", cwd_file=tmp_path / "cwd")
    assert "trap _hagent_emit_pwd EXIT" in script
    assert script.index("trap _hagent_emit_pwd EXIT") < script.index("cd sub"), (
        "trap 须先装好再跑用户命令"
    )


def test_current_cwd_starts_at_workspace_root(fake_sandbox):
    provider = SandboxShellProvider(sandbox=fake_sandbox, workspace_root=Path("/workspace"))
    assert str(provider.current_cwd) == "/workspace"


def test_update_cwd_changes_only_inside_sandbox(fake_sandbox):
    provider = SandboxShellProvider(sandbox=fake_sandbox, workspace_root=Path("/workspace"))
    provider.update_cwd(Path("/workspace/sub"))
    assert str(provider.current_cwd) == "/workspace/sub"


# ---------------------------------------------------------------------------
# smolvm 分派:Bash 工具的宿主 argv 通道不再假定 docker(修 _container AttributeError)
# ---------------------------------------------------------------------------


class FakeSmolVMSandbox:
    """无 _container 的 smolvm 替身;argv 构造下放给 sandbox 本体。"""

    def __init__(self):
        from hagent.sandbox.protocol import SandboxKind

        self.kind = SandboxKind.SMOLVM
        self.workspace_dir = "/workspace"
        self.argv_calls: list[str] = []

    def shell_exec_argv(self, command_script: str) -> list[str]:
        self.argv_calls.append(command_script)
        return ["ssh", "-T", "root@172.16.0.2", f"/bin/bash -c {command_script!r}"]


def test_command_argv_smolvm_delegates_to_sandbox():
    sb = FakeSmolVMSandbox()
    provider = SandboxShellProvider(sandbox=sb, workspace_root=Path("/workspace"))
    argv = provider.command_argv("echo hi")
    assert argv[0] == "ssh", "smolvm 走 sandbox 自建 argv,不得拼 docker exec"
    assert sb.argv_calls == ["echo hi"]


def _make_smolvm_sandbox(lifecycle):
    from hagent.sandbox.manifest import SandboxManifest
    from hagent.sandbox.smolvm.sandbox import HagentSmolVMSandbox

    manifest = SandboxManifest(
        sandbox_id=lifecycle.vm_id,
        kind="smolvm",
        image_tag="hagent-sandbox",
        runtime="firecracker",
        container_id=lifecycle.vm_id,
    )
    return HagentSmolVMSandbox(lifecycle=lifecycle, manifest=manifest)


class _ArgvFakeVM:
    def __init__(self):
        self.info = object()

    def get_ip(self):
        return "172.16.0.9"

    def refresh(self):
        return self


class _FakeManager:
    ensure_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def ensure_network_connectivity(self, vm_info):
        type(self).ensure_calls += 1


def _patch_ssh_deps(monkeypatch, tmp_path):
    key = tmp_path / "id_ed25519"
    key.write_text("fake-key")
    monkeypatch.setattr(
        "hagent.sandbox.smolvm.sandbox.ensure_ssh_key",
        lambda: (key, tmp_path / "id_ed25519.pub"),
    )
    _FakeManager.ensure_calls = 0
    monkeypatch.setattr("hagent.sandbox.smolvm.sandbox.SmolVMManager", _FakeManager)
    return key


def test_smolvm_sandbox_shell_exec_argv_builds_ssh(monkeypatch, tmp_path):
    class FakeLifecycle:
        vm = _ArgvFakeVM()
        vm_id = "hagent-abcd1234-a1b2c3"

    key = _patch_ssh_deps(monkeypatch, tmp_path)
    sb = _make_smolvm_sandbox(FakeLifecycle())
    argv = sb.shell_exec_argv("printf 'hi'")
    assert argv[0] == "ssh"
    assert "root@172.16.0.9" in argv
    joined = " ".join(argv)
    # 每 VM 新 host key:必须关严格校验且不污染 known_hosts
    assert "StrictHostKeyChecking=no" in joined
    assert "UserKnownHostsFile=/dev/null" in joined
    # ssh 告警不得混进工具输出(byte-parity)
    assert "LogLevel=ERROR" in joined
    # vsock 就绪早于 sshd(F13),连接必须带重试兜底
    assert "ConnectionAttempts" in joined
    assert str(key) in argv
    # 远端命令是单参数的 bash -c,脚本引号完整
    assert argv[-1].startswith("/bin/bash -c ")
    assert "printf" in argv[-1]


def test_sandbox_cwd_persists_across_runtime_calls(monkeypatch, tmp_path):
    """cd 持久化全链(本地仿真,零 VM):哨兵后置 + runtime 在 finalize 前捕获。

    历史坑:finalize_foreground 对小输出 unlink 输出文件,而 cwd 捕获在
    finalize 之后读同一路径 → 静默失败,sandbox 模式 cd 从不持久。
    """
    from hagent.bash_tool.runtime import BashRuntime
    from hagent.sandbox.protocol import SandboxKind

    class LocalExecFakeSandbox:
        # smolvm 分派形态,但 argv 落到本地 bash:全链跑真 runtime
        kind = SandboxKind.SMOLVM

        def __init__(self, workspace: Path):
            self.workspace_dir = str(workspace)

        def shell_exec_argv(self, command_script: str) -> list[str]:
            return ["/bin/bash", "-c", command_script]

    ws = tmp_path / "ws"
    ws.mkdir()
    sandbox = LocalExecFakeSandbox(ws)
    provider = SandboxShellProvider(sandbox=sandbox, workspace_root=ws)
    runtime = BashRuntime(tmp_path / "host", shell_provider=provider)

    r1 = runtime.execute("mkdir -p sub && cd sub")
    assert r1.exit_code == 0
    assert str(provider.current_cwd) == str(ws / "sub"), "cd 后 provider cwd 必须更新"

    r2 = runtime.execute("pwd")
    assert f"{ws}/sub" in r2.stdout
    runtime.close()


def test_smolvm_shell_exec_argv_arms_ssh_connectivity_once(monkeypatch, tmp_path):
    # F14:vsock VM 创建时 TAP 路由/NAT 被跳过,首次 SSH 前须懒装配,且只装一次
    class FakeLifecycle:
        vm = _ArgvFakeVM()
        vm_id = "hagent-abcd1234-d4e5f6"

    _patch_ssh_deps(monkeypatch, tmp_path)
    sb = _make_smolvm_sandbox(FakeLifecycle())
    sb.shell_exec_argv("echo 1")
    sb.shell_exec_argv("echo 2")
    assert _FakeManager.ensure_calls == 1


def test_smolvm_shell_exec_argv_without_vm_raises():
    class FakeLifecycle:
        vm = None
        vm_id = "hagent-x-y"

    sb = _make_smolvm_sandbox(FakeLifecycle())
    with pytest.raises(RuntimeError, match="not running"):
        sb.shell_exec_argv("echo hi")
