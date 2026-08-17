"""SandboxFileTransport — adapts HagentSandbox upload/download to FileTransport."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from hagent.file_tools.io import LineEndings, TextMetadata
from hagent.sandbox.errors import (
    SandboxUnavailable,
    SandboxUnavailableReason,
    parse_transfer_error,
)

if TYPE_CHECKING:
    from hagent.sandbox.protocol import HagentSandboxProtocol


class SandboxFileTransport:
    """FileTransport implementation that routes through a HagentSandbox.

    The sandbox stores files inside the container; reads/writes go through
    its ``upload_files`` / ``download_files`` API. Timestamps are not surfaced
    by the sandbox API, so ``read_text_metadata`` returns ``timestamp_ms=0``
    and the caller's FileReadState should rely on content equality.
    """

    def __init__(self, sandbox: "HagentSandboxProtocol") -> None:
        self.sandbox = sandbox

    @staticmethod
    def _raise_if_infra_error(error: str | None) -> None:
        """基础设施类失败抛 ``SandboxUnavailable``;``file_not_found`` 等业务错误放行。"""
        reason = parse_transfer_error(error)
        if reason is not None:
            raise SandboxUnavailable(reason, detail=error)

    def read_text_metadata(self, path: str | Path) -> TextMetadata:
        responses = self.sandbox.download_files([str(path)])
        if not responses:
            raise SandboxUnavailable(SandboxUnavailableReason.CONNECT_FAILED)
        self._raise_if_infra_error(responses[0].error)
        if responses[0].error or responses[0].content is None:
            raise FileNotFoundError(str(path))
        data = responses[0].content
        line_endings: LineEndings = "CRLF" if b"\r\n" in data else "LF"
        raw_text = data.decode("utf-8")
        normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        return TextMetadata(
            content=normalized,
            encoding="utf-8",
            line_endings=line_endings,
            timestamp_ms=0,
        )

    def write_text(
        self,
        path: str | Path,
        content: str,
        encoding: str,
        line_endings: LineEndings,
    ) -> None:
        text = content
        if line_endings == "CRLF":
            text = content.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
        data = text.encode(encoding)
        responses = self.sandbox.upload_files([(str(path), data)])
        if not responses:
            raise SandboxUnavailable(SandboxUnavailableReason.CONNECT_FAILED)
        self._raise_if_infra_error(responses[0].error)
        if responses[0].error:
            raise OSError(f"sandbox write failed: {responses[0].error}")

    def exists(self, path: str | Path) -> bool:
        """文件是否存在。**基础设施失败不再伪装成「不存在」**,而是抛
        ``SandboxUnavailable``——否则模型会去新建文件而不是报告环境故障。"""
        responses = self.sandbox.download_files([str(path)])
        if not responses:
            raise SandboxUnavailable(SandboxUnavailableReason.CONNECT_FAILED)
        self._raise_if_infra_error(responses[0].error)
        return responses[0].error is None

    def is_directory(self, path: str | Path) -> bool:
        # ls returns the entry; if listed with is_dir=True it's a directory.
        ls = self.sandbox.ls(str(path))
        if ls.error is not None:
            return False
        # Heuristic: if path is not a file (exists() returns False) but ls
        # returns entries, treat as directory.
        return not self.exists(path) and ls.entries is not None
