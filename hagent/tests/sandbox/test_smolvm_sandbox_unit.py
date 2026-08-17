"""Task A5 — HagentSmolVMSandbox:输出格式与 docker byte-equal、锁串行化、tempfile 桥接。"""

from __future__ import annotations

import os
import threading
import time

import pytest
from smolvm import OperationTimeoutError, SmolVMError
from smolvm.types import CommandResult

from hagent.sandbox.manifest import SandboxManifest
from hagent.sandbox.protocol import SandboxKind
from hagent.sandbox.smolvm.sandbox import HagentSmolVMSandbox

# ---------------------------------------------------------------------------
# 替身
# ---------------------------------------------------------------------------


class FakeVM:
    def __init__(self):
        self.run_calls: list[dict] = []
        self.uploads: list[tuple[str, str, bool]] = []  # (local, guest, make_dirs)
        self.upload_contents: list[bytes] = []
        self.upload_tmp_paths: list[str] = []
        self.files: dict[str, bytes] = {}  # guest_path -> bytes(download 源)
        self.run_result = CommandResult(exit_code=0, stdout="", stderr="")
        self.run_error: Exception | None = None
        self.run_error_sequence: list[Exception | None] = []  # 按次派发;None 表成功
        self.upload_error: Exception | None = None
        self.download_error: Exception | None = None
        self.in_flight = 0
        self.max_in_flight = 0
        self.run_delay = 0.0

    def run(self, command: str, timeout: int = 30, shell: str = "login") -> CommandResult:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if self.run_delay:
                time.sleep(self.run_delay)
            self.run_calls.append({"command": command, "timeout": timeout, "shell": shell})
            if self.run_error_sequence:
                error = self.run_error_sequence.pop(0)
                if error is not None:
                    raise error
                return self.run_result
            if self.run_error is not None:
                raise self.run_error
            return self.run_result
        finally:
            self.in_flight -= 1

    def upload_file(self, local_path, guest_path: str, *, make_dirs: bool = True) -> str:
        if self.upload_error is not None:
            raise self.upload_error
        with open(local_path, "rb") as f:
            self.upload_contents.append(f.read())
        self.upload_tmp_paths.append(str(local_path))
        self.uploads.append((str(local_path), guest_path, make_dirs))
        return guest_path

    def download_file(self, guest_path: str, local_path, *, make_dirs: bool = True) -> str:
        if self.download_error is not None:
            raise self.download_error
        if guest_path not in self.files:
            raise SmolVMError(f"scp: {guest_path}: No such file or directory")
        with open(local_path, "wb") as f:
            f.write(self.files[guest_path])
        return str(local_path)


class FakeLifecycle:
    def __init__(self, vm: FakeVM):
        self._vm = vm
        self.vm_id = "hagent-abcd1234-a1b2c3"
        self.stopped = 0
        self.paused = 0
        self.resumed = 0
        self.persisted = 0
        self.persist_error: Exception | None = None
        self.persist_snapshot_id = "snap-hagent-abcd1234-a1b2c3-1"

    @property
    def vm(self):
        return self._vm

    def stop(self):
        self.stopped += 1
        self._vm = None

    def pause(self):
        self.paused += 1

    def resume(self):
        self.resumed += 1

    def persist_to_snapshot(self) -> str:
        if self.persist_error is not None:
            raise self.persist_error
        self.persisted += 1
        self._vm = None
        return self.persist_snapshot_id


def make_sandbox(vm: FakeVM | None = None) -> tuple[HagentSmolVMSandbox, FakeVM]:
    vm = vm or FakeVM()
    lifecycle = FakeLifecycle(vm)
    manifest = SandboxManifest(
        sandbox_id=lifecycle.vm_id,
        kind="smolvm",
        image_tag="hagent-sandbox",
        runtime="firecracker",
        container_id=lifecycle.vm_id,
    )
    return HagentSmolVMSandbox(lifecycle=lifecycle, manifest=manifest), vm


# ---------------------------------------------------------------------------
# docker 对照替身:用真 HagentDockerSandbox + fake 容器产出「事实标准」输出
# ---------------------------------------------------------------------------


class FakeContainer:
    def __init__(self, exit_code: int, stdout: bytes, stderr: bytes):
        self._result = (exit_code, (stdout or None, stderr or None))

    def exec_run(self, cmd, **kwargs):
        return self._result


class FakeDockerLifecycle:
    def __init__(self, container):
        self._container = container

    def stop(self):
        pass


def docker_reference_output(exit_code: int, stdout: bytes, stderr: bytes) -> tuple[str, int, bool]:
    """跑真 docker provider 代码路径(fake 容器)拿对照输出。"""
    from hagent.sandbox.docker.sandbox import HagentDockerSandbox

    manifest = SandboxManifest(
        sandbox_id="ref", kind="docker", image_tag="t", runtime="runc", container_id="c"
    )
    sb = HagentDockerSandbox(
        lifecycle=FakeDockerLifecycle(FakeContainer(exit_code, stdout, stderr)),
        manifest=manifest,
    )
    resp = sb.execute("ignored")
    return resp.output, resp.exit_code, resp.truncated


# ---------------------------------------------------------------------------
# execute:输出格式与 docker byte-equal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("exit_code", "stdout", "stderr"),
    [
        (0, b"hello\n", b""),
        (0, b"", b""),
        (1, b"", b"error line\n"),
        (0, b"out\n", b"warn1\nwarn2\n"),
        (0, b"no trailing newline", b"stderr no newline"),
        (2, b"mixed\n", b"\n"),
        (0, "中文输出\n".encode(), "中文告警\n".encode()),
        (0, b"a" * (500 * 1024 + 100), b""),  # 截断路径
        (0, b"a" * (500 * 1024 - 10), b"b" * 100),  # 合并后跨过截断线
    ],
)
def test_execute_output_byte_equal_with_docker(exit_code, stdout, stderr):
    expected_output, expected_exit, expected_trunc = docker_reference_output(
        exit_code, stdout, stderr
    )
    sb, vm = make_sandbox()
    vm.run_result = CommandResult(
        exit_code=exit_code,
        stdout=stdout.decode("utf-8"),
        stderr=stderr.decode("utf-8"),
    )
    resp = sb.execute("whatever")
    assert resp.output == expected_output
    assert resp.exit_code == expected_exit
    assert resp.truncated == expected_trunc


def test_execute_wraps_command_with_bash_and_workspace():
    sb, vm = make_sandbox()
    sb.execute("echo hi")
    call = vm.run_calls[0]
    assert call["shell"] == "raw"
    assert call["command"].startswith("/bin/bash -c ")
    assert "echo hi" in call["command"]
    assert "/workspace" in call["command"]


def test_execute_timeout_maps_to_124():
    sb, vm = make_sandbox()
    vm.run_error = OperationTimeoutError("run", 120.0)
    resp = sb.execute("sleep 999")
    assert resp.exit_code == 124
    assert resp.output.startswith("[sandbox_unavailable:timeout]")
    assert "120s" in resp.output


def test_execute_timeout_uses_explicit_timeout():
    sb, vm = make_sandbox()
    vm.run_error = OperationTimeoutError("run", 5.0)
    resp = sb.execute("sleep 999", timeout=5)
    assert resp.output.startswith("[sandbox_unavailable:timeout]")
    assert "5s" in resp.output
    assert vm.run_calls == [] or vm.run_calls[0]["timeout"] == 5


def test_execute_smolvm_error_maps_to_137():
    sb, vm = make_sandbox()
    vm.run_error = SmolVMError("vsock channel closed")
    resp = sb.execute("true")
    assert resp.exit_code == 137
    # 契约:SDK 原文不进模型可见输出,只给中性文案
    assert resp.output.startswith("[sandbox_unavailable:")
    assert "vsock channel closed" not in resp.output


def test_execute_on_paused_sdk_error_returns_neutral_message():
    """事故 a49b1a3d 回归:SDK 的运维提示("run 'smolvm sandbox start ...'")
    绝不能原样进模型输出。"""
    sb, vm = make_sandbox()
    vm.run_error = SmolVMError(
        "Start sandbox 'hagent-a49b1a3d-324010' before running commands by running "
        "'smolvm sandbox start hagent-a49b1a3d-324010' (current state: paused)."
    )
    resp = sb.execute("rg foo")
    assert resp.exit_code == 137
    assert resp.output.startswith("[sandbox_unavailable:paused]")
    assert "smolvm sandbox start" not in resp.output
    assert "hagent-a49b1a3d" not in resp.output


def test_execute_after_close_returns_gone_message():
    sb, _vm = make_sandbox()
    sb.close()
    resp = sb.execute("true")
    assert resp.exit_code == 137
    assert resp.output.startswith("[sandbox_unavailable:gone]")
    assert sb.manifest.gone is True


def test_execute_after_close_returns_137():
    sb, _vm = make_sandbox()
    sb.close()
    resp = sb.execute("true")
    assert resp.exit_code == 137


def test_execute_serialized_across_threads():
    # F4:SmolVM 实例非线程安全,provider 层 RLock 串行化
    sb, vm = make_sandbox()
    vm.run_delay = 0.05
    threads = [threading.Thread(target=lambda: sb.execute("true")) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert vm.max_in_flight == 1, "并发 execute 必须串行进入 SDK"


# ---------------------------------------------------------------------------
# 连接期瞬时错误重试(Phase B 实测:vsock CONNECT 握手偶发失败,命令未送达)
# ---------------------------------------------------------------------------


def test_execute_retries_transient_vsock_connect_failure():
    sb, vm = make_sandbox()
    vm.run_result = CommandResult(exit_code=0, stdout="ok\n", stderr="")
    vm.run_error_sequence = [
        SmolVMError("vsock CONNECT handshake failed: ''"),
        SmolVMError("vsock CONNECT handshake failed: ''"),
        None,
    ]
    resp = sb.execute("echo ok")
    assert resp.exit_code == 0
    assert resp.output == "ok\n"
    assert len(vm.run_calls) == 3, "连接期失败须重试(命令未送达 guest,重试安全)"


def test_execute_transient_failure_exhausts_to_137():
    sb, vm = make_sandbox()
    vm.run_error = SmolVMError("vsock CONNECT handshake failed: ''")
    resp = sb.execute("echo ok")
    assert resp.exit_code == 137
    assert len(vm.run_calls) == 3, "重试有界(1+2),不得无限"


def test_execute_non_transient_error_not_retried():
    sb, vm = make_sandbox()
    vm.run_error = SmolVMError("guest agent crashed mid-command")
    resp = sb.execute("echo ok")
    assert resp.exit_code == 137
    assert len(vm.run_calls) == 1, "非连接期错误可能已产生副作用,禁止重试"


def test_execute_timeout_not_retried():
    sb, vm = make_sandbox()
    vm.run_error = OperationTimeoutError("run", 5.0)
    resp = sb.execute("sleep 999", timeout=5)
    assert resp.exit_code == 124
    assert len(vm.run_calls) == 1


# ---------------------------------------------------------------------------
# upload / download:tempfile 桥接 + 部分成功语义
# ---------------------------------------------------------------------------


def test_upload_roundtrip_content():
    sb, vm = make_sandbox()
    results = sb.upload_files([("/workspace/a.txt", b"hello"), ("/workspace/b/c.bin", b"\x00\xff")])
    assert all(r.error is None for r in results)
    assert vm.upload_contents == [b"hello", b"\x00\xff"]
    assert [u[1] for u in vm.uploads] == ["/workspace/a.txt", "/workspace/b/c.bin"]
    assert all(u[2] is True for u in vm.uploads), "须 make_dirs=True 对齐 mkdir -p 行为"


def test_upload_empty_file():
    sb, vm = make_sandbox()
    results = sb.upload_files([("/workspace/empty.txt", b"")])
    assert results[0].error is None
    assert vm.upload_contents == [b""]


def test_upload_large_file():
    # >128KB:docker 分片限制的历史雷区,smolvm 路径必须完整传输
    payload = os.urandom(300 * 1024)
    sb, vm = make_sandbox()
    results = sb.upload_files([("/workspace/big.bin", payload)])
    assert results[0].error is None
    assert vm.upload_contents == [payload]


def test_upload_tempfile_cleaned_up():
    sb, vm = make_sandbox()
    sb.upload_files([("/workspace/a.txt", b"data")])
    assert vm.upload_tmp_paths, "应经 tempfile 桥接"
    for tmp in vm.upload_tmp_paths:
        assert not os.path.exists(tmp), f"tempfile 未清理: {tmp}"


def test_upload_partial_success():
    sb, vm = make_sandbox()
    vm.upload_error = SmolVMError("transfer failed")
    results = sb.upload_files([("/workspace/x.txt", b"1")])
    assert results[0].error is not None
    assert results[0].error.startswith("sandbox_unavailable:")


def test_download_roundtrip():
    sb, vm = make_sandbox()
    vm.files["/workspace/out.txt"] = b"result bytes"
    results = sb.download_files(["/workspace/out.txt"])
    assert results[0].content == b"result bytes"
    assert results[0].error is None


def test_download_missing_file_maps_file_not_found():
    sb, vm = make_sandbox()
    results = sb.download_files(["/workspace/nope.txt"])
    assert results[0].content is None
    assert results[0].error == "file_not_found"


def test_download_other_error():
    sb, vm = make_sandbox()
    vm.download_error = SmolVMError("channel broke")
    results = sb.download_files(["/workspace/x"])
    # 基础设施类失败与 file_not_found 区分,机器可解析
    assert results[0].error == "sandbox_unavailable:connect_failed"


def test_download_partial_success_order_preserved():
    sb, vm = make_sandbox()
    vm.files["/workspace/ok.txt"] = b"ok"
    results = sb.download_files(["/workspace/ok.txt", "/workspace/missing.txt"])
    assert results[0].error is None
    assert results[1].error == "file_not_found"


# ---------------------------------------------------------------------------
# 协议面
# ---------------------------------------------------------------------------


def test_identity_and_kind():
    sb, _ = make_sandbox()
    assert sb.id == "smolvm-hagent-abcd1234-a1b2c3"
    assert sb.kind is SandboxKind.SMOLVM
    assert sb.workspace_dir == "/workspace"
    assert sb.manifest.container_id == "hagent-abcd1234-a1b2c3"


def test_close_delegates_and_idempotent():
    sb, _ = make_sandbox()
    lifecycle = sb._lifecycle
    sb.close()
    sb.close()
    assert lifecycle.stopped >= 1


def test_pause_resume_delegate():
    sb, _ = make_sandbox()
    sb.pause()
    sb.resume()
    assert sb._lifecycle.paused == 1
    assert sb._lifecycle.resumed == 1


def test_pause_sets_manifest_flag_resume_clears_it():
    """缺陷修复:manifest.paused 是 pause 态的单一真相源。

    健康巡检据此豁免 paused VM、消息路径据此决定是否 resume——pause/resume
    必须成对维护它,否则 resume 后仍被当 paused(健康巡检漏探/消息路径漏唤醒)。
    """
    sb, _ = make_sandbox()
    assert sb.manifest.paused is False
    sb.pause()
    assert sb.manifest.paused is True
    sb.resume()
    assert sb.manifest.paused is False


def test_backend_name_registered_for_prompt_injection():
    from hagent.config import _SANDBOX_BACKEND_NAMES

    assert "HagentSmolVMSandbox" in _SANDBOX_BACKEND_NAMES


# ---------------------------------------------------------------------------
# Task C2:persist_to_snapshot 委派 + 审计;restore 类方法装配
# ---------------------------------------------------------------------------


def test_persist_to_snapshot_delegates_and_audits():
    from hagent.sandbox.smolvm.audit import SandboxAuditor

    events: list[tuple[str, dict | None]] = []

    class SpyAuditor(SandboxAuditor):
        def record_event(self, *, event, project_id=None, vm_id=None, detail=None):
            events.append((event, detail))

    vm = FakeVM()
    lifecycle = FakeLifecycle(vm)
    manifest = SandboxManifest(
        sandbox_id=lifecycle.vm_id,
        kind="smolvm",
        image_tag="hagent-sandbox",
        runtime="firecracker",
        container_id=lifecycle.vm_id,
    )
    sb = HagentSmolVMSandbox(
        lifecycle=lifecycle, manifest=manifest, auditor=SpyAuditor(), project_id="sid1"
    )
    snapshot_id = sb.persist_to_snapshot()
    assert snapshot_id == lifecycle.persist_snapshot_id
    assert lifecycle.persisted == 1
    assert ("snapshotted", {"snapshot_id": snapshot_id}) in events


def test_persist_failure_propagates_without_audit():
    from hagent.sandbox.smolvm.audit import SandboxAuditor

    events: list[str] = []

    class SpyAuditor(SandboxAuditor):
        def record_event(self, *, event, project_id=None, vm_id=None, detail=None):
            events.append(event)

    vm = FakeVM()
    lifecycle = FakeLifecycle(vm)
    lifecycle.persist_error = RuntimeError("no space")
    manifest = SandboxManifest(
        sandbox_id=lifecycle.vm_id,
        kind="smolvm",
        image_tag="hagent-sandbox",
        runtime="firecracker",
        container_id=lifecycle.vm_id,
    )
    sb = HagentSmolVMSandbox(lifecycle=lifecycle, manifest=manifest, auditor=SpyAuditor())
    with pytest.raises(RuntimeError, match="no space"):
        sb.persist_to_snapshot()
    assert "snapshotted" not in events


def test_restore_classmethod_builds_sandbox(monkeypatch):
    import hagent.sandbox.smolvm.sandbox as sandbox_mod
    from hagent.sandbox.smolvm.audit import SandboxAuditor

    events: list[str] = []

    class SpyAuditor(SandboxAuditor):
        def record_event(self, *, event, project_id=None, vm_id=None, detail=None):
            events.append(event)

    class FakeRestoreLifecycle:
        def __init__(self, *, project_id=None, **kwargs):
            self.project_id = project_id
            self.vm_id = "hagent-abcd1234-x1y2z3"
            self._vm = FakeVM()

        @property
        def vm(self):
            return self._vm

        def restore_from_snapshot(self, snapshot_id: str):
            return SandboxManifest(
                sandbox_id=self.vm_id,
                kind="smolvm",
                image_tag="restored",
                runtime="firecracker",
                container_id=self.vm_id,
            )

    monkeypatch.setattr(sandbox_mod, "SmolVMLifecycle", FakeRestoreLifecycle)
    sb = HagentSmolVMSandbox.restore(
        "snap-x-1", project_id="sid1", auditor=SpyAuditor()
    )
    assert sb.manifest.image_tag == "restored"
    assert sb.manifest.container_id == "hagent-abcd1234-x1y2z3"
    assert "restored" in events


# ---------------------------------------------------------------------------
# 活跃统一 touch(触达即活跃)+ 通道内防御性唤醒(ensure_running)
# ---------------------------------------------------------------------------


def test_execute_touches_on_entry_and_on_failure():
    """execute 通道:进入即 touch,失败也 touch(旧实现只在成功路径末尾 touch)。"""
    sb, vm = make_sandbox()
    touched: list[int] = []
    sb.set_activity_callback(lambda: touched.append(1))
    vm.run_error = SmolVMError("vsock channel closed")
    resp = sb.execute("true")
    assert resp.exit_code == 137
    assert touched == [1]


def test_ensure_running_resumes_paused_and_emits_resumed():
    sb, _vm = make_sandbox()
    events: list[str] = []
    sb.set_lifecycle_callback(events.append)
    sb.pause()
    assert sb.manifest.paused is True
    sb.ensure_running()
    assert sb.manifest.paused is False
    assert sb._lifecycle.resumed == 1
    assert events == ["resumed"]
    # 已 running 时幂等,不重复广播
    sb.ensure_running()
    assert sb._lifecycle.resumed == 1
    assert events == ["resumed"]


def test_execute_on_paused_sandbox_auto_resumes_before_running():
    """A3:通道内自动唤醒——paused 沙箱被工具触达时先 resume 再执行,而不是把
    SDK 的 non-RUNNING 报错回给模型。"""
    sb, vm = make_sandbox()
    sb.pause()
    resp = sb.execute("echo hi")
    assert resp.exit_code == 0
    assert sb.manifest.paused is False
    assert sb._lifecycle.resumed == 1
    assert len(vm.run_calls) == 1


def test_ensure_running_failure_maps_to_paused_contract():
    from hagent.sandbox.errors import SandboxUnavailable, SandboxUnavailableReason

    sb, vm = make_sandbox()
    sb.pause()

    def broken_resume():
        raise SmolVMError("Cannot resume VM in state 'stopped'")

    sb._lifecycle.resume = broken_resume
    with pytest.raises(SandboxUnavailable) as info:
        sb.ensure_running()
    assert info.value.reason is SandboxUnavailableReason.PAUSED
    assert "Cannot resume" in (info.value.detail or "")
    # execute 通道把它变成契约文案而不是异常
    resp = sb.execute("true")
    assert resp.exit_code == 137
    assert resp.output.startswith("[sandbox_unavailable:paused]")
    assert vm.run_calls == []


def test_download_on_paused_sandbox_auto_resumes():
    sb, vm = make_sandbox()
    vm.files["/workspace/a.txt"] = b"x"
    sb.pause()
    results = sb.download_files(["/workspace/a.txt"])
    assert results[0].content == b"x"
    assert sb.manifest.paused is False


def test_download_after_close_marks_gone_not_sdk_text():
    sb, _vm = make_sandbox()
    sb.close()
    results = sb.download_files(["/workspace/a.txt"])
    assert results[0].error == "sandbox_unavailable:gone"
    uploads = sb.upload_files([("/workspace/b.txt", b"1")])
    assert uploads[0].error == "sandbox_unavailable:gone"


def test_persist_to_snapshot_marks_manifest_gone():
    sb, _vm = make_sandbox()
    sb.persist_to_snapshot()
    assert sb.manifest.gone is True
    assert sb.execute("true").output.startswith("[sandbox_unavailable:gone]")
