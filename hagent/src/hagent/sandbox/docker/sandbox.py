"""HagentDockerSandbox: SandboxBackendProtocol over docker exec/cp."""

from __future__ import annotations

import base64
import logging
import shlex
from collections.abc import Callable
from pathlib import PurePosixPath

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox

from hagent.sandbox.docker.lifecycle import DockerContainerLifecycle
from hagent.sandbox.manifest import SandboxManifest
from hagent.sandbox.protocol import HagentSandboxProtocol, SandboxKind

logger = logging.getLogger(__name__)

DEFAULT_MAX_OUTPUT_BYTES = 500 * 1024
DEFAULT_EXEC_TIMEOUT_SECONDS = 120
# 上传分片:单个 exec 参数受 Linux MAX_ARG_STRLEN(128KB)限制,留足余量
_UPLOAD_CHUNK_B64_CHARS = 64 * 1024


class HagentDockerSandbox(BaseSandbox, HagentSandboxProtocol):
    """Hagent sandbox backed by a single docker container.

    Inherits BaseSandbox so ls/read/grep/glob/edit are implemented as
    server-side scripts via execute(). We provide execute(), upload_files(),
    download_files() and id.
    """

    def __init__(
        self,
        *,
        lifecycle: DockerContainerLifecycle,
        manifest: SandboxManifest,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
        default_timeout_seconds: int = DEFAULT_EXEC_TIMEOUT_SECONDS,
    ) -> None:
        self._lifecycle = lifecycle
        self._manifest = manifest
        self._activity_callback: Callable[[], None] | None = None
        self._container = lifecycle._container
        self._max_output_bytes = max_output_bytes
        self._default_timeout_seconds = default_timeout_seconds

    @classmethod
    def start(
        cls,
        *,
        image_tag: str | None = None,
        prefer_runtime: str = "runsc",
        env_overrides: dict[str, str] | None = None,
    ) -> "HagentDockerSandbox":
        from hagent.sandbox.docker.image import DEFAULT_IMAGE_TAG

        lifecycle = DockerContainerLifecycle(
            image_tag=image_tag or DEFAULT_IMAGE_TAG,
            prefer_runtime=prefer_runtime,
            env_overrides=env_overrides,
        )
        manifest = lifecycle.start()
        return cls(lifecycle=lifecycle, manifest=manifest)

    @property
    def id(self) -> str:
        return f"docker-{self._manifest.container_id}"

    @property
    def kind(self) -> SandboxKind:
        return SandboxKind.DOCKER

    @property
    def workspace_dir(self) -> str:
        return self._manifest.workspace_dir

    def set_activity_callback(self, callback: Callable[[], None] | None) -> None:
        self._activity_callback = callback

    def _touch(self) -> None:
        self._manifest.touch()
        if self._activity_callback is not None:
            try:
                self._activity_callback()
            except Exception as exc:  # noqa: BLE001
                logger.warning("项目租约活跃时间回写失败(忽略): %s", exc)

    @property
    def manifest(self) -> SandboxManifest:
        return self._manifest

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        if self._container is None:
            return ExecuteResponse(
                output="container not running", exit_code=137, truncated=False
            )
        try:
            exit_code, demux_out = self._container.exec_run(
                cmd=["/bin/bash", "-c", command],
                workdir=self._manifest.workspace_dir,
                demux=True,
                tty=False,
            )
        except Exception as exc:  # noqa: BLE001
            return ExecuteResponse(
                output=f"container exec failed: {exc}", exit_code=137, truncated=False
            )

        stdout, stderr = demux_out if demux_out is not None else (b"", b"")
        stdout = stdout or b""
        stderr = stderr or b""

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
            exit_code=int(exit_code) if exit_code is not None else 1,
            truncated=truncated,
        )

    # —— 上传/下载走 exec 通道(base64 进出),不用 put_archive/get_archive ——
    # runsc(gVisor)下沙箱内 exec 创建的目录/文件对宿主 dockerd 不可见,
    # put_archive/get_archive 按宿主视角 stat 路径必然 404(实测:skill 物料
    # 灌容器与 agent Write 全部 upload_failed)。exec 是沙箱文件系统的唯一
    # 真实视角,收发统一经 exec 在 runc/runsc 下行为一致。

    def _exec_sh(self, script: str) -> tuple[int, bytes, bytes]:
        exit_code, demux_out = self._container.exec_run(
            cmd=["/bin/sh", "-c", script], demux=True
        )
        stdout, stderr = demux_out if demux_out is not None else (b"", b"")
        return (
            int(exit_code) if exit_code is not None else 1,
            stdout or b"",
            stderr or b"",
        )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        results: list[FileUploadResponse] = []
        for path, content in files:
            try:
                self._upload_one(path, content)
                results.append(FileUploadResponse(path=path, error=None))
            except Exception as exc:  # noqa: BLE001
                results.append(FileUploadResponse(path=path, error=f"upload_failed: {exc}"))
        self._touch()
        return results

    def _upload_one(self, path: str, content: bytes) -> None:
        parent = str(PurePosixPath(path).parent)
        exit_code, demux_out = self._container.exec_run(cmd=["mkdir", "-p", parent])
        if exit_code != 0:
            raise RuntimeError(f"mkdir -p {parent} failed: exit {exit_code}")
        q_path = shlex.quote(path)
        q_tmp = shlex.quote(f"{path}.__hagent_upload__")
        b64 = base64.b64encode(content).decode("ascii")
        if not b64:
            code, _, err = self._exec_sh(f": > {q_path}")
            if code != 0:
                raise RuntimeError(f"create empty file failed: {err.decode(errors='replace')}")
            return
        # base64 文本分片追加进临时文件:单个 exec 参数受 MAX_ARG_STRLEN(128KB)限制
        for i in range(0, len(b64), _UPLOAD_CHUNK_B64_CHARS):
            chunk = b64[i : i + _UPLOAD_CHUNK_B64_CHARS]
            redir = ">" if i == 0 else ">>"
            code, _, err = self._exec_sh(f"printf '%s' '{chunk}' {redir} {q_tmp}")
            if code != 0:
                raise RuntimeError(f"write chunk failed: {err.decode(errors='replace')}")
        code, _, err = self._exec_sh(f"base64 -d {q_tmp} > {q_path} && rm -f {q_tmp}")
        if code != 0:
            raise RuntimeError(f"decode failed: {err.decode(errors='replace')}")

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        results: list[FileDownloadResponse] = []
        for path in paths:
            try:
                code, out, err = self._exec_sh(f"base64 {shlex.quote(path)}")
                if code != 0:
                    error_str = err.decode(errors="replace")
                    error_code = (
                        "file_not_found"
                        if "No such file" in error_str
                        else f"download_failed: {error_str.strip()}"
                    )
                    results.append(FileDownloadResponse(path=path, content=None, error=error_code))
                    continue
                content = base64.b64decode(out)
                results.append(FileDownloadResponse(path=path, content=content, error=None))
            except Exception as exc:  # noqa: BLE001
                results.append(
                    FileDownloadResponse(path=path, content=None, error=f"download_failed: {exc}")
                )
        self._touch()
        return results

    def pause(self) -> None:
        """Suspend the underlying container (delegate to lifecycle)."""
        self._lifecycle.pause()
        # manifest.paused 单一真相源,与 smolvm provider 对齐:消息路径据此
        # 唤醒被 idle GC 冻结的容器(docker pause 后 exec 同样不可用)
        self._manifest.paused = True

    def resume(self) -> None:
        """Resume a previously paused container (delegate to lifecycle)."""
        self._lifecycle.resume()
        self._manifest.paused = False

    def close(self) -> None:
        self._lifecycle.stop()
        self._container = None

    def __enter__(self) -> "HagentDockerSandbox":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
