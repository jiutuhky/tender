from __future__ import annotations

from pathlib import Path

from hagent.file_tools.io import FileTransport, HostFileTransport


def test_host_file_transport_round_trip(tmp_path: Path):
    transport: FileTransport = HostFileTransport()
    target = tmp_path / "foo.txt"
    transport.write_text(target, "hello world", encoding="utf-8", line_endings="LF")
    metadata = transport.read_text_metadata(target)
    assert metadata.content == "hello world"
    assert metadata.encoding == "utf-8"
    assert metadata.line_endings == "LF"


def test_host_file_transport_preserves_crlf(tmp_path: Path):
    transport = HostFileTransport()
    target = tmp_path / "foo.txt"
    transport.write_text(target, "a\nb\n", encoding="utf-8", line_endings="CRLF")
    raw = target.read_bytes()
    assert raw == b"a\r\nb\r\n"
