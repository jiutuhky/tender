from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol


UTF_16_LE_BOM = b"\xff\xfe"
LineEndings = Literal["LF", "CRLF"]


@dataclass(frozen=True)
class TextMetadata:
    content: str
    encoding: str
    line_endings: LineEndings
    timestamp_ms: int


def read_text_metadata(path: str | Path) -> TextMetadata:
    resolved_path = Path(path)
    data = resolved_path.read_bytes()
    encoding = "utf-16-le" if data.startswith(UTF_16_LE_BOM) else "utf-8"
    text_bytes = data[len(UTF_16_LE_BOM) :] if encoding == "utf-16-le" else data
    raw_text = text_bytes.decode(encoding)
    return TextMetadata(
        content=raw_text.replace("\r\n", "\n").replace("\r", "\n"),
        encoding=encoding,
        line_endings="CRLF" if _includes_crlf(data, encoding) else "LF",
        timestamp_ms=resolved_path.stat().st_mtime_ns // 1_000_000,
    )


def write_text_preserving_encoding(
    path: str | Path,
    content: str,
    encoding: str,
    line_endings: LineEndings,
) -> None:
    text = content
    if line_endings == "CRLF":
        text = content.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    data = text.encode(encoding)
    if encoding == "utf-16-le":
        data = UTF_16_LE_BOM + data
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_bytes(data)


def format_with_line_numbers(content: str, start_line: int = 1) -> str:
    lines = content.splitlines()
    return "\n".join(
        f"{line_number}\t{line}"
        for line_number, line in enumerate(lines, start=start_line)
    )


def _includes_crlf(data: bytes, encoding: str) -> bool:
    if encoding == "utf-16-le":
        return b"\r\x00\n\x00" in data
    return b"\r\n" in data


class FileTransport(Protocol):
    """Abstract file IO used by the Hagent file tools.

    Host implementations operate on a local Path; sandbox implementations route
    through HagentSandbox upload/download.
    """

    def read_text_metadata(self, path: str | Path) -> TextMetadata: ...

    def write_text(
        self,
        path: str | Path,
        content: str,
        encoding: str,
        line_endings: LineEndings,
    ) -> None: ...

    def exists(self, path: str | Path) -> bool: ...

    def is_directory(self, path: str | Path) -> bool: ...


class HostFileTransport:
    """Default FileTransport backed by the local filesystem."""

    def read_text_metadata(self, path: str | Path) -> TextMetadata:
        return read_text_metadata(path)

    def write_text(
        self,
        path: str | Path,
        content: str,
        encoding: str,
        line_endings: LineEndings,
    ) -> None:
        write_text_preserving_encoding(path, content, encoding, line_endings)

    def exists(self, path: str | Path) -> bool:
        return Path(path).exists()

    def is_directory(self, path: str | Path) -> bool:
        return Path(path).is_dir()
