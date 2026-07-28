from __future__ import annotations

from pathlib import Path

from hagent.file_tools.state import FileReadState
from hagent.file_tools.tools import create_edit_tool, create_read_tool


def test_edit_existing_file_without_prior_full_read_rejects_and_preserves_file(
    tmp_path: Path,
) -> None:
    state = FileReadState()
    target = tmp_path / "notes.txt"
    target.write_text("original\n", encoding="utf-8")
    tool = create_edit_tool(tmp_path, permissions=None, state=state)

    result = tool.invoke(
        {
            "file_path": "notes.txt",
            "old_string": "original",
            "new_string": "replacement",
        }
    )

    assert "File has not been read yet" in result
    assert target.read_text(encoding="utf-8") == "original\n"


def test_edit_after_offset_limited_read_can_edit_when_file_is_unchanged(
    tmp_path: Path,
) -> None:
    state = FileReadState()
    target = tmp_path / "notes.txt"
    target.write_text("one\ntwo\nthree\n", encoding="utf-8")
    read_tool = create_read_tool(tmp_path, permissions=None, state=state)
    edit_tool = create_edit_tool(tmp_path, permissions=None, state=state)

    read_tool.invoke({"file_path": "notes.txt", "offset": 2, "limit": 1})
    result = edit_tool.invoke(
        {"file_path": "notes.txt", "old_string": "two", "new_string": "deux"}
    )

    assert "has been updated successfully" in result
    assert target.read_text(encoding="utf-8") == "one\ndeux\nthree\n"


def test_edit_replaces_unique_string_after_full_read(tmp_path: Path) -> None:
    state = FileReadState()
    target = tmp_path / "notes.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    read_tool = create_read_tool(tmp_path, permissions=None, state=state)
    edit_tool = create_edit_tool(tmp_path, permissions=None, state=state)

    read_tool.invoke({"file_path": "notes.txt"})
    result = edit_tool.invoke(
        {"file_path": "notes.txt", "old_string": "beta", "new_string": "delta"}
    )

    assert "has been updated successfully" in result
    assert target.read_text(encoding="utf-8") == "alpha\ndelta\ngamma\n"
    snapshot = state.get(target)
    assert snapshot is not None
    assert snapshot.content == "alpha\ndelta\ngamma\n"


def test_edit_rejects_ambiguous_string_without_replace_all_and_preserves_file(
    tmp_path: Path,
) -> None:
    state = FileReadState()
    target = tmp_path / "notes.txt"
    target.write_text("dup\nmiddle\ndup\n", encoding="utf-8")
    read_tool = create_read_tool(tmp_path, permissions=None, state=state)
    edit_tool = create_edit_tool(tmp_path, permissions=None, state=state)

    read_tool.invoke({"file_path": "notes.txt"})
    result = edit_tool.invoke(
        {"file_path": "notes.txt", "old_string": "dup", "new_string": "single"}
    )

    assert "Found 2 matches" in result
    assert target.read_text(encoding="utf-8") == "dup\nmiddle\ndup\n"


def test_edit_with_replace_all_replaces_every_occurrence(tmp_path: Path) -> None:
    state = FileReadState()
    target = tmp_path / "notes.txt"
    target.write_text("dup\nmiddle\ndup\n", encoding="utf-8")
    read_tool = create_read_tool(tmp_path, permissions=None, state=state)
    edit_tool = create_edit_tool(tmp_path, permissions=None, state=state)

    read_tool.invoke({"file_path": "notes.txt"})
    result = edit_tool.invoke(
        {
            "file_path": "notes.txt",
            "old_string": "dup",
            "new_string": "single",
            "replace_all": True,
        }
    )

    assert "All occurrences were successfully replaced" in result
    assert target.read_text(encoding="utf-8") == "single\nmiddle\nsingle\n"


def test_edit_rejects_jupyter_notebook(tmp_path: Path) -> None:
    state = FileReadState()
    target = tmp_path / "analysis.ipynb"
    target.write_text("{}", encoding="utf-8")
    tool = create_edit_tool(tmp_path, permissions=None, state=state)

    result = tool.invoke(
        {"file_path": "analysis.ipynb", "old_string": "{}", "new_string": "[]"}
    )

    assert "File is a Jupyter Notebook" in result
    assert target.read_text(encoding="utf-8") == "{}"


def test_edit_with_empty_old_string_creates_missing_file(tmp_path: Path) -> None:
    state = FileReadState()
    target = tmp_path / "notes.txt"
    tool = create_edit_tool(tmp_path, permissions=None, state=state)

    result = tool.invoke(
        {"file_path": "notes.txt", "old_string": "", "new_string": "created\n"}
    )

    assert "has been updated successfully" in result
    assert target.read_text(encoding="utf-8") == "created\n"
    snapshot = state.get(target)
    assert snapshot is not None
    assert snapshot.content == "created\n"


def test_edit_preserves_crlf_without_doubling_carriage_returns(tmp_path: Path) -> None:
    state = FileReadState()
    target = tmp_path / "notes.txt"
    target.write_bytes(b"alpha\r\nbeta\r\n")
    read_tool = create_read_tool(tmp_path, permissions=None, state=state)
    edit_tool = create_edit_tool(tmp_path, permissions=None, state=state)

    read_tool.invoke({"file_path": "notes.txt"})
    edit_tool.invoke(
        {
            "file_path": "notes.txt",
            "old_string": "beta",
            "new_string": "bravo\r\ncharlie",
        }
    )

    assert target.read_bytes() == b"alpha\r\nbravo\r\ncharlie\r\n"


def test_edit_matches_curly_quotes_and_preserves_quote_style(tmp_path: Path) -> None:
    state = FileReadState()
    target = tmp_path / "notes.txt"
    target.write_text("say “hello” now\n", encoding="utf-8")
    read_tool = create_read_tool(tmp_path, permissions=None, state=state)
    edit_tool = create_edit_tool(tmp_path, permissions=None, state=state)

    read_tool.invoke({"file_path": "notes.txt"})
    result = edit_tool.invoke(
        {
            "file_path": "notes.txt",
            "old_string": '"hello"',
            "new_string": '"goodbye"',
        }
    )

    assert "has been updated successfully" in result
    assert target.read_text(encoding="utf-8") == "say “goodbye” now\n"


def test_edit_deletes_entire_line_when_new_string_empty(tmp_path: Path) -> None:
    state = FileReadState()
    target = tmp_path / "notes.txt"
    target.write_text("alpha\nremove me\nbeta\n", encoding="utf-8")
    read_tool = create_read_tool(tmp_path, permissions=None, state=state)
    edit_tool = create_edit_tool(tmp_path, permissions=None, state=state)

    read_tool.invoke({"file_path": "notes.txt"})
    result = edit_tool.invoke(
        {"file_path": "notes.txt", "old_string": "remove me", "new_string": ""}
    )

    assert "has been updated successfully" in result
    assert target.read_text(encoding="utf-8") == "alpha\nbeta\n"
