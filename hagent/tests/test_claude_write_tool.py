from __future__ import annotations

import os
from pathlib import Path

from hagent.file_tools.state import FileReadState
from hagent.file_tools.tools import create_read_tool, create_write_tool


def test_write_creates_new_file_without_prior_read(tmp_path: Path) -> None:
    state = FileReadState()
    tool = create_write_tool(tmp_path, permissions=None, state=state)
    target = tmp_path / "notes.txt"

    result = tool.invoke({"file_path": "notes.txt", "content": "alpha\nbeta\n"})

    assert result.startswith("File created successfully at:")
    assert target.read_text(encoding="utf-8") == "alpha\nbeta\n"
    snapshot = state.get(target)
    assert snapshot is not None
    assert snapshot.content == "alpha\nbeta\n"
    assert snapshot.is_partial_view is False


def test_write_overwrites_existing_file_only_after_full_read(tmp_path: Path) -> None:
    state = FileReadState()
    target = tmp_path / "notes.txt"
    target.write_text("old\ncontent\n", encoding="utf-8")
    read_tool = create_read_tool(tmp_path, permissions=None, state=state)
    write_tool = create_write_tool(tmp_path, permissions=None, state=state)

    read_tool.invoke({"file_path": "notes.txt"})
    result = write_tool.invoke({"file_path": "notes.txt", "content": "new\ncontent\n"})

    assert "has been updated successfully" in result
    assert target.read_text(encoding="utf-8") == "new\ncontent\n"
    snapshot = state.get(target)
    assert snapshot is not None
    assert snapshot.content == "new\ncontent\n"


def test_write_after_offset_limited_read_can_overwrite_when_file_is_unchanged(
    tmp_path: Path,
) -> None:
    state = FileReadState()
    target = tmp_path / "notes.txt"
    target.write_text("old\ncontent\n", encoding="utf-8")
    read_tool = create_read_tool(tmp_path, permissions=None, state=state)
    write_tool = create_write_tool(tmp_path, permissions=None, state=state)

    read_tool.invoke({"file_path": "notes.txt", "offset": 2, "limit": 1})
    result = write_tool.invoke({"file_path": "notes.txt", "content": "new\ncontent\n"})

    assert "has been updated successfully" in result
    assert target.read_text(encoding="utf-8") == "new\ncontent\n"


def test_write_existing_file_without_prior_read_rejects_and_preserves_file(
    tmp_path: Path,
) -> None:
    state = FileReadState()
    target = tmp_path / "notes.txt"
    target.write_text("original\n", encoding="utf-8")
    tool = create_write_tool(tmp_path, permissions=None, state=state)

    result = tool.invoke({"file_path": "notes.txt", "content": "replacement\n"})

    assert result == "File has not been read yet. Read it first before writing to it."
    assert target.read_text(encoding="utf-8") == "original\n"


def test_write_rejects_stale_existing_file_and_preserves_file(tmp_path: Path) -> None:
    state = FileReadState()
    target = tmp_path / "notes.txt"
    target.write_text("original\n", encoding="utf-8")
    read_tool = create_read_tool(tmp_path, permissions=None, state=state)
    write_tool = create_write_tool(tmp_path, permissions=None, state=state)

    read_tool.invoke({"file_path": "notes.txt"})
    snapshot = state.get(target)
    assert snapshot is not None
    target.write_text("external change\n", encoding="utf-8")
    newer_mtime_ns = (snapshot.timestamp_ms + 1_000) * 1_000_000
    os.utime(target, ns=(newer_mtime_ns, newer_mtime_ns))

    result = write_tool.invoke({"file_path": "notes.txt", "content": "replacement\n"})

    assert (
        result
        == "File has been modified since read, either by the user or by a linter. "
        "Read it again before attempting to write it."
    )
    assert target.read_text(encoding="utf-8") == "external change\n"


def test_write_preserves_model_supplied_crlf_content(tmp_path: Path) -> None:
    state = FileReadState()
    target = tmp_path / "notes.txt"
    tool = create_write_tool(tmp_path, permissions=None, state=state)

    tool.invoke({"file_path": "notes.txt", "content": "alpha\r\nbeta\r\n"})

    assert target.read_bytes() == b"alpha\r\nbeta\r\n"


def test_write_returns_neutral_message_when_sandbox_unavailable(tmp_path):
    from pathlib import Path

    from hagent.file_tools.state import FileReadState
    from hagent.file_tools.tools import create_write_tool
    from hagent.sandbox.errors import SandboxUnavailable, SandboxUnavailableReason

    class BrokenTransport:
        def exists(self, path):
            return False

        def is_directory(self, path):
            return False

        def write_text(self, path, content, encoding, line_endings):
            raise SandboxUnavailable(SandboxUnavailableReason.GONE)

        def read_text_metadata(self, path):
            raise AssertionError("不应到达")

    tool = create_write_tool(
        Path(tmp_path), permissions=None, state=FileReadState(), transport=BrokenTransport()
    )
    result = tool.invoke({"file_path": "out.txt", "content": "x"})
    assert result.startswith("[sandbox_unavailable:gone]")
