from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from deepagents.backends.protocol import FileDownloadResponse, FileUploadResponse
from hagent.sandbox.providers.file import SandboxFileTransport


@pytest.fixture
def fake_sandbox():
    sb = MagicMock()
    sb.workspace_dir = "/workspace"
    return sb


def test_write_text_uploads_via_sandbox(fake_sandbox):
    fake_sandbox.upload_files.return_value = [FileUploadResponse(path="/workspace/a.txt", error=None)]
    transport = SandboxFileTransport(fake_sandbox)
    transport.write_text("/workspace/a.txt", "hello", encoding="utf-8", line_endings="LF")
    fake_sandbox.upload_files.assert_called_once()
    args, _ = fake_sandbox.upload_files.call_args
    assert args[0] == [("/workspace/a.txt", b"hello")]


def test_write_text_crlf_normalized(fake_sandbox):
    fake_sandbox.upload_files.return_value = [FileUploadResponse(path="/workspace/a.txt", error=None)]
    transport = SandboxFileTransport(fake_sandbox)
    transport.write_text("/workspace/a.txt", "a\nb\n", encoding="utf-8", line_endings="CRLF")
    args, _ = fake_sandbox.upload_files.call_args
    assert args[0] == [("/workspace/a.txt", b"a\r\nb\r\n")]


def test_read_text_metadata_via_download(fake_sandbox):
    fake_sandbox.download_files.return_value = [
        FileDownloadResponse(path="/workspace/a.txt", content=b"hello", error=None)
    ]
    transport = SandboxFileTransport(fake_sandbox)
    md = transport.read_text_metadata("/workspace/a.txt")
    assert md.content == "hello"
    assert md.encoding == "utf-8"
    assert md.line_endings == "LF"


def test_exists_false_on_file_not_found(fake_sandbox):
    fake_sandbox.download_files.return_value = [
        FileDownloadResponse(path="/workspace/missing", content=None, error="file_not_found")
    ]
    transport = SandboxFileTransport(fake_sandbox)
    assert transport.exists("/workspace/missing") is False


def test_write_raises_on_upload_error(fake_sandbox):
    fake_sandbox.upload_files.return_value = [
        FileUploadResponse(path="/workspace/a.txt", error="permission_denied")
    ]
    transport = SandboxFileTransport(fake_sandbox)
    with pytest.raises(OSError, match="permission_denied"):
        transport.write_text("/workspace/a.txt", "x", encoding="utf-8", line_endings="LF")


# ---------------------------------------------------------------------------
# 基础设施错误不再伪装成「文件不存在」(事故 a49b1a3d 教训)
# ---------------------------------------------------------------------------


def test_exists_raises_sandbox_unavailable_on_infra_error(fake_sandbox):
    from hagent.sandbox.errors import SandboxUnavailable, SandboxUnavailableReason

    fake_sandbox.download_files.return_value = [
        FileDownloadResponse(
            path="/workspace/a.txt", content=None, error="sandbox_unavailable:paused"
        )
    ]
    transport = SandboxFileTransport(fake_sandbox)
    with pytest.raises(SandboxUnavailable) as info:
        transport.exists("/workspace/a.txt")
    assert info.value.reason is SandboxUnavailableReason.PAUSED
    with pytest.raises(SandboxUnavailable):
        transport.read_text_metadata("/workspace/a.txt")


def test_exists_false_on_guest_level_download_failure(fake_sandbox):
    """guest 内脚本级失败(目录/权限)仍是业务语义,不当作基础设施错误。"""
    fake_sandbox.download_files.return_value = [
        FileDownloadResponse(
            path="/workspace/dir", content=None, error="download_failed: base64: Is a directory"
        )
    ]
    transport = SandboxFileTransport(fake_sandbox)
    assert transport.exists("/workspace/dir") is False


def test_write_text_raises_sandbox_unavailable(fake_sandbox):
    from hagent.sandbox.errors import SandboxUnavailable

    fake_sandbox.upload_files.return_value = [
        FileUploadResponse(path="/workspace/a.txt", error="sandbox_unavailable:gone")
    ]
    transport = SandboxFileTransport(fake_sandbox)
    with pytest.raises(SandboxUnavailable):
        transport.write_text("/workspace/a.txt", "x", encoding="utf-8", line_endings="LF")
    fake_sandbox.upload_files.return_value = [
        FileUploadResponse(path="/workspace/a.txt", error="upload_failed: mkdir failed")
    ]
    with pytest.raises(OSError, match="sandbox write failed"):
        transport.write_text("/workspace/a.txt", "x", encoding="utf-8", line_endings="LF")
