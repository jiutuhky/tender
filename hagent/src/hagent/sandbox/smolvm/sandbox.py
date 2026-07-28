"""HagentSmolVMSandbox: SandboxBackendProtocol over smolvm vsock/SSH 通道。

输出格式(stderr 前缀、截断 marker)与 docker provider **byte-equal**(spec §7);
共享常量直接引自 docker provider,改动会同时体现在两个 provider 的测试上。
"""

from __future__ import annotations

import logging
import os
import shlex
import tempfile
import threading
import time
from collections.abc import Callable

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox
from smolvm import OperationTimeoutError, SmolVMManager
from smolvm.utils import ensure_ssh_key

from hagent.sandbox.docker.lifecycle import DEFAULT_SAFE_ENV
from hagent.sandbox.docker.sandbox import (
    DEFAULT_EXEC_TIMEOUT_SECONDS,
    DEFAULT_MAX_OUTPUT_BYTES,
)
from hagent.sandbox.manifest import SandboxManifest
from hagent.sandbox.protocol import HagentSandboxProtocol, SandboxKind
from hagent.sandbox.smolvm.audit import SandboxAuditor
from hagent.sandbox.smolvm.lifecycle import SmolVMLifecycle

logger = logging.getLogger(__name__)

# 连接期瞬时错误(L3 实测):vsock UDS CONNECT 握手在重连/高churn后偶发失败,
# 此时命令**尚未送达 guest**,重试安全;白名单严格限定连接建立阶段的错误
_TRANSIENT_CONNECT_MARKERS = (
    "vsock CONNECT handshake failed",
    "control channel did not become ready",
)
EXEC_CONNECT_RETRIES = 2
EXEC_CONNECT_RETRY_BACKOFF_SECONDS = 0.2


def _is_transient_connect_error(exc: BaseException) -> bool:
    message = str(exc)
    return any(marker in message for marker in _TRANSIENT_CONNECT_MARKERS)


class HagentSmolVMSandbox(BaseSandbox, HagentSandboxProtocol):
    """Hagent sandbox backed by a single Firecracker microVM.

    继承 BaseSandbox,ls/read/grep/glob/edit 经 execute() 的服务端脚本实现;
    本类提供 execute() / upload_files() / download_files() / id。
    SmolVM 实例非线程安全(F4),所有 SDK 调用经 per-instance RLock 串行化。
    """

    def __init__(
        self,
        *,
        lifecycle: SmolVMLifecycle,
        manifest: SandboxManifest,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
        default_timeout_seconds: int = DEFAULT_EXEC_TIMEOUT_SECONDS,
        auditor: SandboxAuditor | None = None,
        project_id: str | None = None,
    ) -> None:
        self._lifecycle = lifecycle
        self._manifest = manifest
        self._max_output_bytes = max_output_bytes
        self._default_timeout_seconds = default_timeout_seconds
        self._lock = threading.RLock()
        self._ssh_ip: str | None = None
        self._ssh_armed = False
        self._auditor = auditor or SandboxAuditor()
        self._project_id = project_id
        self._activity_callback: Callable[[], None] | None = None

    @classmethod
    def start(
        cls, *, project_id: str | None = None, auditor: SandboxAuditor | None = None
    ) -> "HagentSmolVMSandbox":
        auditor = auditor or SandboxAuditor()
        lifecycle = SmolVMLifecycle(project_id=project_id)
        try:
            manifest = lifecycle.start()
        except Exception as exc:
            auditor.record_event(
                event="create_failed",
                project_id=project_id,
                vm_id=lifecycle.vm_id,
                detail={"error": str(exc)},
            )
            raise
        auditor.record_event(event="created", project_id=project_id, vm_id=lifecycle.vm_id)
        return cls(lifecycle=lifecycle, manifest=manifest, auditor=auditor, project_id=project_id)

    @classmethod
    def adopt(
        cls, vm_id: str, *, auditor: SandboxAuditor | None = None
    ) -> "HagentSmolVMSandbox":
        lifecycle = SmolVMLifecycle()
        manifest = lifecycle.adopt(vm_id)
        return cls(lifecycle=lifecycle, manifest=manifest, auditor=auditor)

    @classmethod
    def restore(
        cls,
        snapshot_id: str,
        *,
        project_id: str | None = None,
        auditor: SandboxAuditor | None = None,
    ) -> "HagentSmolVMSandbox":
        """从 DISK 快照重建沙箱(Task C2):snapshotted session 的消息路径入口。"""
        auditor = auditor or SandboxAuditor()
        lifecycle = SmolVMLifecycle(project_id=project_id)
        try:
            manifest = lifecycle.restore_from_snapshot(snapshot_id)
        except Exception as exc:
            auditor.record_event(
                event="restore_failed",
                project_id=project_id,
                vm_id=lifecycle.vm_id,
                detail={"snapshot_id": snapshot_id, "error": str(exc)},
            )
            raise
        auditor.record_event(
            event="restored",
            project_id=project_id,
            vm_id=lifecycle.vm_id,
            detail={"snapshot_id": snapshot_id},
        )
        return cls(lifecycle=lifecycle, manifest=manifest, auditor=auditor, project_id=project_id)

    def persist_to_snapshot(self) -> str:
        """DISK 快照 + 全拆 VM(池 GC 的持久化钩子);失败上抛,调用方退回驱逐。"""
        with self._lock:
            snapshot_id = self._lifecycle.persist_to_snapshot()
        self._auditor.record_event(
            event="snapshotted",
            project_id=self._project_id,
            vm_id=self._manifest.container_id,
            detail={"snapshot_id": snapshot_id},
        )
        return snapshot_id

    def bind_project(self, project_id: str | None) -> None:
        """认领/收养时由池绑定项目审计归属；回 warm 池时解绑。"""
        self._project_id = project_id

    def set_activity_callback(self, callback: Callable[[], None] | None) -> None:
        self._activity_callback = callback

    def _touch(self) -> None:
        self._manifest.touch()
        if self._activity_callback is not None:
            try:
                self._activity_callback()
            except Exception as exc:  # noqa: BLE001
                logger.warning("项目租约活跃时间回写失败(忽略): %s", exc)

    def _audit_command(self, **kwargs) -> None:
        self._auditor.record_command(
            project_id=self._project_id, vm_id=self._manifest.container_id, **kwargs
        )

    # —— 协议面 ————————————————————————————————————————————————

    @property
    def id(self) -> str:
        return f"smolvm-{self._manifest.container_id}"

    @property
    def kind(self) -> SandboxKind:
        return SandboxKind.SMOLVM

    @property
    def workspace_dir(self) -> str:
        return self._manifest.workspace_dir

    @property
    def manifest(self) -> SandboxManifest:
        return self._manifest

    @property
    def pid(self) -> int | None:
        """firecracker 进程 pid(指标采样用);VM 已停时 None。"""
        vm = self._lifecycle.vm
        if vm is None:
            return None
        return getattr(getattr(vm, "info", None), "pid", None)

    # —— execute ——————————————————————————————————————————————

    def _wrap_command(self, command: str) -> str:
        """对齐 docker exec 语义:safe env + workdir /workspace + /bin/bash -c。

        docker export 只保留文件系统,镜像 ENV 不进 VM 进程树,env 在此逐条
        export;shell="raw" 避免 login-shell 二次包装,bash 语义自己给。
        用户命令以换行拼接,避免与 ``&&`` 组合改变首 token 解析。
        """
        exports = "".join(
            f"export {key}={shlex.quote(value)}\n" for key, value in DEFAULT_SAFE_ENV.items()
        )
        script = f"{exports}cd {shlex.quote(self._manifest.workspace_dir)} || exit 1\n{command}"
        return f"/bin/bash -c {shlex.quote(script)}"

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        started = time.monotonic()
        response = self._execute_inner(command, timeout=timeout)
        self._audit_command(
            action="exec",
            command=command,
            exit_code=response.exit_code,
            duration_ms=int((time.monotonic() - started) * 1000),
            bytes_out=len(response.output.encode("utf-8")),
        )
        return response

    def _execute_inner(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        vm = self._lifecycle.vm
        if vm is None:
            return ExecuteResponse(output="sandbox not running", exit_code=137, truncated=False)
        effective_timeout = int(timeout) if timeout else self._default_timeout_seconds
        wrapped = self._wrap_command(command)
        for attempt in range(1 + EXEC_CONNECT_RETRIES):
            try:
                with self._lock:
                    result = vm.run(wrapped, timeout=effective_timeout, shell="raw")
                break
            except OperationTimeoutError:
                return ExecuteResponse(
                    output=f"command timed out after {effective_timeout}s",
                    exit_code=124,
                    truncated=False,
                )
            except Exception as exc:  # noqa: BLE001
                # 只重试连接建立阶段的瞬时错误(命令未送达);其余可能已有副作用
                if attempt < EXEC_CONNECT_RETRIES and _is_transient_connect_error(exc):
                    logger.warning(
                        "[%s] 连接期瞬时错误,重试 %d/%d: %s",
                        self._manifest.container_id,
                        attempt + 1,
                        EXEC_CONNECT_RETRIES,
                        exc,
                    )
                    time.sleep(EXEC_CONNECT_RETRY_BACKOFF_SECONDS)
                    continue
                return ExecuteResponse(
                    output=f"sandbox exec failed: {exc}", exit_code=137, truncated=False
                )

        # 合并逻辑与 docker provider 逐行对齐(bytes 域截断,marker byte-equal)
        stdout = result.stdout.encode("utf-8")
        stderr = result.stderr.encode("utf-8")
        parts: list[bytes] = []
        if stdout:
            parts.append(stdout)
        if stderr:
            for line in stderr.decode("utf-8", errors="replace").rstrip("\n").split("\n"):
                parts.append(f"[stderr] {line}\n".encode("utf-8"))
        combined = b"".join(parts)
        truncated = False
        if len(combined) > self._max_output_bytes:
            combined = combined[: self._max_output_bytes] + (
                f"\n... Output truncated at {self._max_output_bytes} bytes.".encode("utf-8")
            )
            truncated = True
        self._touch()
        return ExecuteResponse(
            output=combined.decode("utf-8", errors="replace"),
            exit_code=int(result.exit_code),
            truncated=truncated,
        )

    # —— 健康探针(supervisor health_loop 用)———————————————————————

    def health_check(self, *, timeout: int = 5) -> bool:
        """直连 ``vm.run("true")`` 的轻量探活:不包 bash、不写审计(防噪音)。"""
        vm = self._lifecycle.vm
        if vm is None:
            return False
        try:
            with self._lock:
                result = vm.run("true", timeout=timeout, shell="raw")
        except Exception:  # noqa: BLE001
            return False
        return int(result.exit_code) == 0

    # —— Bash 工具的宿主 argv 通道(SandboxShellProvider 分派至此)——————————

    def shell_exec_argv(self, command_script: str) -> list[str]:
        """构造宿主侧可 spawn 的 SSH argv(BashRuntime 的流式/超时/后台机器复用)。

        vsock 通道无流式(F4),Bash 工具走 SSH 兜底通道(spec D4):
        镜像已烘焙 sshd + 宿主默认公钥(image.py);ControlMaster 复用连接,
        摊薄每次调用的握手成本;LogLevel=ERROR 防 ssh 告警污染工具输出。
        """
        vm = self._lifecycle.vm
        if vm is None:
            raise RuntimeError("sandbox not running")
        with self._lock:  # F4:facade 非线程安全
            if not self._ssh_armed:
                # F14:vsock 通道 VM 创建时跳过 TAP 路由/NAT,host→guest:22
                # 不可达;经公开 API 懒装配路由+NAT,每 VM 一次。
                # 刻意不用 vm.wait_for_ssh():其 paramiko 轮询对 OpenSSH 10
                # guest 不可靠(实测 banner 读取失败),而 argv 用的 OpenSSH
                # 二进制自带重试(ConnectionAttempts),无需预先轮询。
                vm.refresh()
                with SmolVMManager() as manager:
                    manager.ensure_network_connectivity(vm.info)
                self._ssh_armed = True
            if self._ssh_ip is None:
                self._ssh_ip = vm.get_ip()  # TAP IP 随 VM 生命周期固定,缓存
        private_key, _ = ensure_ssh_key()
        control_path = os.path.join(
            tempfile.gettempdir(), f"hagent-ssh-{self._manifest.container_id}.sock"
        )
        return [
            "ssh",
            "-T",
            "-i",
            str(private_key),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=ERROR",
            # 就绪窗口兜底:vsock 就绪早于 sshd(init 先起 agent 再起 sshd)
            "-o",
            "ConnectTimeout=10",
            "-o",
            "ConnectionAttempts=5",
            "-o",
            "ControlMaster=auto",
            "-o",
            f"ControlPath={control_path}",
            "-o",
            "ControlPersist=60",
            f"root@{self._ssh_ip}",
            f"/bin/bash -c {shlex.quote(command_script)}",
        ]

    # —— 文件传输:tempfile 桥接 SDK 的本地路径 API(F8)———————————————

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        results: list[FileUploadResponse] = []
        with self._lock:
            for path, content in files:
                started = time.monotonic()
                try:
                    self._upload_one(path, content)
                    results.append(FileUploadResponse(path=path, error=None))
                except Exception as exc:  # noqa: BLE001
                    results.append(FileUploadResponse(path=path, error=f"upload_failed: {exc}"))
                self._audit_command(
                    action="upload",
                    path=path,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    bytes_out=len(content),
                    error=results[-1].error,
                )
        self._touch()
        return results

    def _upload_one(self, path: str, content: bytes) -> None:
        vm = self._lifecycle.vm
        if vm is None:
            raise RuntimeError("sandbox not running")
        fd, tmp_path = tempfile.mkstemp(prefix="hagent-upload-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            # make_dirs=True → guest 侧 mkdir -p,对齐 docker provider 行为
            vm.upload_file(tmp_path, path, make_dirs=True)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        results: list[FileDownloadResponse] = []
        with self._lock:
            for path in paths:
                started = time.monotonic()
                result = self._download_one(path)
                results.append(result)
                self._audit_command(
                    action="download",
                    path=path,
                    duration_ms=int((time.monotonic() - started) * 1000),
                    bytes_out=len(result.content or b""),
                    error=result.error,
                )
        self._touch()
        return results

    def _download_one(self, path: str) -> FileDownloadResponse:
        vm = self._lifecycle.vm
        if vm is None:
            return FileDownloadResponse(
                path=path, content=None, error="download_failed: sandbox not running"
            )
        with tempfile.TemporaryDirectory(prefix="hagent-download-") as tmp_dir:
            local_path = os.path.join(tmp_dir, "content")
            try:
                vm.download_file(path, local_path)
                with open(local_path, "rb") as f:
                    return FileDownloadResponse(path=path, content=f.read(), error=None)
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                error = (
                    "file_not_found"
                    if "no such file" in message.lower() or "not found" in message.lower()
                    else f"download_failed: {message.strip()}"
                )
                return FileDownloadResponse(path=path, content=None, error=error)

    # —— 生命周期委派 ——————————————————————————————————————————

    def _audit_event(self, event: str) -> None:
        self._auditor.record_event(
            event=event, project_id=self._project_id, vm_id=self._manifest.container_id
        )

    def pause(self) -> None:
        with self._lock:
            self._lifecycle.pause()
        # manifest.paused 是 pause 态的单一真相源:健康巡检据此豁免冻结 VM
        # (vm.run 对非 RUNNING 必抛),消息路径据此决定 resume。pause/resume 成对维护
        self._manifest.paused = True
        self._audit_event("paused")

    def resume(self) -> None:
        with self._lock:
            self._lifecycle.resume()
        self._manifest.paused = False
        self._audit_event("resumed")

    def close(self) -> None:
        with self._lock:
            had_vm = self._lifecycle.vm is not None
            self._lifecycle.stop()
        if had_vm:
            self._audit_event("evicted")

    def __enter__(self) -> "HagentSmolVMSandbox":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
