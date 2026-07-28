from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from hagent.file_tools import create_claude_file_tools
from hagent.file_tools.diff import structured_patch
from hagent.file_tools.io import read_text_metadata, write_text_preserving_encoding
from hagent.file_tools.paths import check_permission, expand_file_path
from hagent.file_tools.state import FileReadState


def test_expand_file_path_resolves_relative_paths_under_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    assert expand_file_path("src/app.py", workspace) == workspace / "src" / "app.py"


def test_expand_file_path_rejects_home_relative_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="home-relative"):
        expand_file_path("~/secret.txt", tmp_path)


def test_check_permission_uses_first_matching_rule(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    rules = [
        SimpleNamespace(operations=["read"], paths=[str(target)], mode="deny"),
        SimpleNamespace(operations=["read"], paths=[str(target)], mode="allow"),
    ]

    assert check_permission(rules, "read", target) == "deny"


def test_registered_read_returns_error_and_does_not_read_when_read_denied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "secret.txt"
    target.write_text("classified\n", encoding="utf-8")
    permissions = [SimpleNamespace(command="read", pattern=str(target), mode="deny")]
    read_tool = next(
        tool
        for tool in create_claude_file_tools(tmp_path, permissions)
        if tool.name == "Read"
    )

    def fail_if_read(path: Path):
        raise AssertionError(f"read_text_metadata should not read denied file: {path}")

    monkeypatch.setattr("hagent.file_tools.tools.read_text_metadata", fail_if_read)

    result = read_tool.invoke({"file_path": "secret.txt"})

    assert result.startswith("Error:")
    assert "permission denied for read" in result


def test_registered_write_returns_error_and_does_not_create_when_write_denied(
    tmp_path: Path,
) -> None:
    target = tmp_path / "new.txt"
    permissions = [SimpleNamespace(command="write", pattern=str(target), mode="deny")]
    write_tool = next(
        tool
        for tool in create_claude_file_tools(tmp_path, permissions)
        if tool.name == "Write"
    )

    result = write_tool.invoke({"file_path": "new.txt", "content": "blocked\n"})

    assert result.startswith("Error:")
    assert "permission denied for write" in result
    assert not target.exists()


def test_registered_write_returns_error_and_does_not_modify_when_write_denied(
    tmp_path: Path,
) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("original\n", encoding="utf-8")
    permissions = [SimpleNamespace(command="write", pattern=str(target), mode="deny")]
    write_tool = next(
        tool
        for tool in create_claude_file_tools(tmp_path, permissions)
        if tool.name == "Write"
    )

    result = write_tool.invoke({"file_path": "notes.txt", "content": "blocked\n"})

    assert result.startswith("Error:")
    assert "permission denied for write" in result
    assert target.read_text(encoding="utf-8") == "original\n"


def test_registered_edit_returns_error_and_leaves_file_unchanged_when_write_denied(
    tmp_path: Path,
) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    permissions = [SimpleNamespace(command="write", pattern=str(target), mode="deny")]
    tools = create_claude_file_tools(tmp_path, permissions)
    read_tool = next(tool for tool in tools if tool.name == "Read")
    edit_tool = next(tool for tool in tools if tool.name == "Edit")

    read_tool.invoke({"file_path": "notes.txt"})
    result = edit_tool.invoke(
        {"file_path": "notes.txt", "old_string": "beta", "new_string": "blocked"}
    )

    assert result.startswith("Error:")
    assert "permission denied for write" in result
    assert target.read_text(encoding="utf-8") == "alpha\nbeta\n"


def test_file_read_state_records_full_and_partial_reads() -> None:
    state = FileReadState()
    path = Path("/workspace/notes.txt")

    state.record_read(path, "hello\nworld", timestamp_ms=100, offset=None, limit=None)
    full = state.get(path)
    assert full is not None
    assert full.content == "hello\nworld"
    assert full.timestamp_ms == 100
    assert full.is_partial_view is False

    state.record_read(path, "hello", timestamp_ms=200, offset=0, limit=5)
    partial = state.get(path)
    assert partial is not None
    assert partial.content == "hello"
    assert partial.timestamp_ms == 200
    assert partial.offset == 0
    assert partial.limit == 5
    assert partial.is_partial_view is False


def test_file_read_state_uses_resolved_path_keys(tmp_path: Path) -> None:
    state = FileReadState()
    nested = tmp_path / "nested"
    nested.mkdir()
    path = nested / "notes.txt"
    path.write_text("original", encoding="utf-8")
    equivalent_path = nested / ".." / "nested" / "notes.txt"

    state.record_read(equivalent_path, "hello", timestamp_ms=300, offset=None, limit=None)
    snapshot = state.get(path.resolve())

    assert snapshot is not None
    assert snapshot.path == path.resolve()
    assert snapshot.content == "hello"


def test_text_metadata_round_trips_utf8_crlf_and_lf(tmp_path: Path) -> None:
    crlf_path = tmp_path / "crlf.txt"
    crlf_path.write_bytes("alpha\r\nbeta\r\n".encode("utf-8"))
    crlf_metadata = read_text_metadata(crlf_path)
    assert crlf_metadata.content == "alpha\nbeta\n"
    assert crlf_metadata.encoding == "utf-8"
    assert crlf_metadata.line_endings == "CRLF"
    assert isinstance(crlf_metadata.timestamp_ms, int)

    write_text_preserving_encoding(
        crlf_path,
        "gamma\ndelta\n",
        crlf_metadata.encoding,
        crlf_metadata.line_endings,
    )
    assert crlf_path.read_bytes() == b"gamma\r\ndelta\r\n"

    lf_path = tmp_path / "lf.txt"
    lf_path.write_bytes(b"alpha\nbeta\n")
    lf_metadata = read_text_metadata(lf_path)
    assert lf_metadata.content == "alpha\nbeta\n"
    assert lf_metadata.line_endings == "LF"
    assert isinstance(lf_metadata.timestamp_ms, int)

    write_text_preserving_encoding(
        lf_path,
        "gamma\ndelta\n",
        lf_metadata.encoding,
        lf_metadata.line_endings,
    )
    assert lf_path.read_bytes() == b"gamma\ndelta\n"

    nested_lf_path = tmp_path / "nested" / "lf.txt"
    write_text_preserving_encoding(nested_lf_path, "nested\n", "utf-8", "LF")
    assert nested_lf_path.exists()
    assert nested_lf_path.read_bytes() == b"nested\n"


def test_text_metadata_round_trips_utf16_le_bom(tmp_path: Path) -> None:
    utf16_path = tmp_path / "utf16.txt"
    utf16_path.write_bytes(b"\xff\xfea\x00\r\x00\n\x00")

    metadata = read_text_metadata(utf16_path)
    assert metadata.content == "a\n"
    assert metadata.encoding == "utf-16-le"
    assert metadata.line_endings == "CRLF"
    assert isinstance(metadata.timestamp_ms, int)

    write_text_preserving_encoding(
        utf16_path,
        "b\n",
        metadata.encoding,
        metadata.line_endings,
    )
    assert utf16_path.read_bytes() == b"\xff\xfeb\x00\r\x00\n\x00"


def test_structured_patch_returns_hunk_lines_with_old_and_new_lines() -> None:
    hunks = structured_patch(
        "notes.txt",
        "one\nold\nthree\n",
        "one\nnew\nthree\n",
    )

    assert hunks
    assert hunks[0]["oldStart"] == 1
    assert hunks[0]["newStart"] == 1
    assert "-old\n" in hunks[0]["lines"]
    assert "+new\n" in hunks[0]["lines"]
