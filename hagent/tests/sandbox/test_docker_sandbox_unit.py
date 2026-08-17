from __future__ import annotations

import io
import tarfile
from unittest.mock import MagicMock, patch

import pytest

from hagent.sandbox import SandboxKind
from hagent.sandbox.docker.sandbox import HagentDockerSandbox


def _make_sandbox(monkeypatch) -> HagentDockerSandbox:
    lifecycle = MagicMock()
    lifecycle.start.return_value = MagicMock(
        sandbox_id="testid000abc",
        container_id="cidcid",
        kind="docker",
        image_tag="hagent/sandbox:dev",
        runtime="runsc",
        workspace_dir="/workspace",
        paused=False,
        gone=False,
    )
    container = MagicMock()
    container.id = "cidcid"
    lifecycle._container = container
    monkeypatch.setattr("hagent.sandbox.docker.sandbox.DockerContainerLifecycle", lambda **kw: lifecycle)
    sb = HagentDockerSandbox.start()
    sb._container = container
    return sb


def test_id_is_docker_prefixed(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    assert sb.id == "docker-cidcid"
    assert sb.kind is SandboxKind.DOCKER
    assert sb.workspace_dir == "/workspace"


def test_execute_returns_combined_output(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    sb._container.exec_run = MagicMock(return_value=(0, (b"hello\n", b"")))
    resp = sb.execute("echo hello")
    assert resp.exit_code == 0
    assert "hello" in resp.output
    assert resp.truncated is False


def test_execute_includes_stderr_with_prefix(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    sb._container.exec_run = MagicMock(return_value=(2, (b"out\n", b"boom\n")))
    resp = sb.execute("bad")
    assert resp.exit_code == 2
    assert "out" in resp.output
    assert "[stderr] boom" in resp.output


def test_execute_truncates_oversized_output(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    big = b"x" * (sb._max_output_bytes + 100)
    sb._container.exec_run = MagicMock(return_value=(0, (big, b"")))
    resp = sb.execute("yes")
    assert resp.truncated is True
    assert len(resp.output.encode("utf-8")) <= sb._max_output_bytes + 200  # truncation banner


# —— 上传/下载走 exec 通道(base64 进出) ——
# 背景:runsc(gVisor)下沙箱内 exec 创建的目录/文件对宿主 dockerd 不可见,
# put_archive/get_archive 按宿主视角 stat 路径必然 404。exec 是沙箱文件系统的
# 唯一真实视角,故收发都经 exec;这些单测用内存 FS 仿真容器,验证指令序列可回放。


class _FakeExecFs:
    """按 upload/download 用到的指令子集仿真容器内文件系统。"""

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.dirs: set[str] = set()
        self.fail_mkdir = False

    def exec_run(self, cmd, **kwargs):
        import base64 as b64mod
        import re
        import shlex

        if cmd[0] == "mkdir":
            if self.fail_mkdir:
                return (1, (b"", b"mkdir: cannot create directory\n"))
            self.dirs.add(cmd[-1])
            return (0, (b"", b""))
        assert cmd[0] in ("/bin/sh", "/bin/bash") and cmd[1] == "-c"
        script = cmd[2]
        m = re.match(r"^: > (.+)$", script)
        if m:
            self.files[shlex.split(m.group(1))[0]] = b""
            return (0, (b"", b""))
        m = re.match(r"^printf '%s' '([A-Za-z0-9+/=]*)' (>>?) (.+)$", script)
        if m:
            chunk, redir, path = m.group(1), m.group(2), shlex.split(m.group(3))[0]
            prev = self.files.get(path, b"") if redir == ">>" else b""
            self.files[path] = prev + chunk.encode("ascii")
            return (0, (b"", b""))
        m = re.match(r"^base64 -d (.+?) > (.+?) && rm -f (.+)$", script)
        if m:
            src = shlex.split(m.group(1))[0]
            dst = shlex.split(m.group(2))[0]
            self.files[dst] = b64mod.b64decode(self.files.pop(src, b""))
            return (0, (b"", b""))
        m = re.match(r"^base64 (.+)$", script)
        if m:
            path = shlex.split(m.group(1))[0]
            if path not in self.files:
                return (1, (b"", f"base64: {path}: No such file or directory\n".encode()))
            out = b64mod.b64encode(self.files[path])
            # 模拟 base64 默认 76 列换行输出
            wrapped = b"\n".join(out[i : i + 76] for i in range(0, len(out), 76)) + b"\n"
            return (0, (wrapped, b""))
        raise AssertionError(f"未预期的 exec 脚本: {script}")


def test_upload_files_writes_via_exec(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    fs = _FakeExecFs()
    sb._container.exec_run = fs.exec_run
    responses = sb.upload_files([("/workspace/sub/a.txt", b"hello \xe4\xb8\xad\xe6\x96\x87")])
    assert responses[0].error is None
    assert responses[0].path == "/workspace/sub/a.txt"
    assert "/workspace/sub" in fs.dirs
    assert fs.files["/workspace/sub/a.txt"] == b"hello \xe4\xb8\xad\xe6\x96\x87"
    # 临时 b64 文件已清理
    assert all(not p.endswith(".__hagent_upload__") for p in fs.files)


def test_upload_files_chunks_large_content(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    fs = _FakeExecFs()
    sb._container.exec_run = fs.exec_run
    body = bytes(range(256)) * 512  # 128KB,必然多分片
    responses = sb.upload_files([("/workspace/big.bin", body)])
    assert responses[0].error is None
    assert fs.files["/workspace/big.bin"] == body


def test_upload_files_empty_content(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    fs = _FakeExecFs()
    sb._container.exec_run = fs.exec_run
    responses = sb.upload_files([("/workspace/empty.txt", b"")])
    assert responses[0].error is None
    assert fs.files["/workspace/empty.txt"] == b""


def test_upload_files_mkdir_failure_reports_error(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    fs = _FakeExecFs()
    fs.fail_mkdir = True
    sb._container.exec_run = fs.exec_run
    responses = sb.upload_files([("/ro/a.txt", b"x")])
    assert responses[0].error is not None
    assert "upload_failed" in responses[0].error


def test_download_files_decodes_base64(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    fs = _FakeExecFs()
    fs.files["/workspace/a.txt"] = b"hello " * 100
    sb._container.exec_run = fs.exec_run
    responses = sb.download_files(["/workspace/a.txt"])
    assert responses[0].content == b"hello " * 100
    assert responses[0].error is None


def test_download_files_missing_reports_not_found(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    fs = _FakeExecFs()
    sb._container.exec_run = fs.exec_run
    responses = sb.download_files(["/workspace/nope.txt"])
    assert responses[0].content is None
    assert responses[0].error == "file_not_found"


def test_close_calls_lifecycle_stop(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    sb.close()
    sb._lifecycle.stop.assert_called_once()


def test_pause_resume_delegate_to_lifecycle(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    sb.pause()
    sb._lifecycle.pause.assert_called_once()
    sb.resume()
    sb._lifecycle.resume.assert_called_once()
