from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from hagent.file_tools import create_claude_file_tools
from hagent.file_tools.state import FileReadState
from hagent.file_tools.tools import create_read_tool


def test_read_reads_numbered_text_and_records_shared_state_content(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    state = FileReadState()
    tool = create_read_tool(tmp_path, permissions=None, state=state)

    result = tool.invoke({"file_path": "notes.txt"})

    assert result == "1\talpha\n2\tbeta"
    snapshot = state.get(target)
    assert snapshot is not None
    assert snapshot.content == "alpha\nbeta"
    assert snapshot.offset == 1
    assert snapshot.limit is None


def test_read_supports_offset_and_limit_and_records_partial_view(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")
    state = FileReadState()
    tool = create_read_tool(tmp_path, permissions=None, state=state)

    offset_zero_result = tool.invoke({"file_path": "notes.txt", "offset": 0, "limit": 2})
    offset_two_result = tool.invoke({"file_path": "notes.txt", "offset": 2, "limit": 2})

    assert offset_zero_result == "0\tone\n1\ttwo"
    assert offset_two_result == "2\ttwo\n3\tthree"
    snapshot = state.get(target)
    assert snapshot is not None
    assert snapshot.content == "two\nthree"
    assert snapshot.offset == 2
    assert snapshot.limit == 2
    assert snapshot.is_partial_view is False


def test_duplicate_unchanged_full_read_returns_file_unchanged_stub(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    tool = create_read_tool(tmp_path, permissions=None, state=FileReadState())

    first = tool.invoke({"file_path": "notes.txt"})
    second = tool.invoke({"file_path": "notes.txt"})

    assert first == "1\talpha\n2\tbeta"
    assert (
        second
        == "File unchanged since last read. The content from the earlier Read "
        "tool_result in this conversation is still current — refer to that instead "
        "of re-reading."
    )


def test_duplicate_unchanged_partial_read_returns_file_unchanged_stub(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    tool = create_read_tool(tmp_path, permissions=None, state=FileReadState())

    first = tool.invoke({"file_path": "notes.txt", "offset": 2, "limit": 1})
    second = tool.invoke({"file_path": "notes.txt", "offset": 2, "limit": 1})

    assert first == "2\tbeta"
    assert second.startswith("File unchanged since last read.")


def test_read_empty_file_returns_system_reminder(tmp_path: Path) -> None:
    target = tmp_path / "empty.txt"
    target.write_text("", encoding="utf-8")
    tool = create_read_tool(tmp_path, permissions=None, state=FileReadState())

    result = tool.invoke({"file_path": "empty.txt"})

    assert result == (
        "<system-reminder>Warning: the file exists but the contents "
        "are empty.</system-reminder>"
    )


def test_read_offset_beyond_end_returns_system_reminder(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("alpha\nbeta\n", encoding="utf-8")
    tool = create_read_tool(tmp_path, permissions=None, state=FileReadState())

    result = tool.invoke({"file_path": "notes.txt", "offset": 10})

    assert result == (
        "<system-reminder>Warning: the file exists but is shorter than "
        "the provided offset (10). The file has 2 lines.</system-reminder>"
    )


def test_read_rejects_zero_limit(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("alpha\n", encoding="utf-8")
    tool = create_read_tool(tmp_path, permissions=None, state=FileReadState())

    result = tool.invoke({"file_path": "notes.txt", "limit": 0})

    assert result == "Error: limit must be a positive line count"


def test_read_accepts_pages_parameter_schema_for_pdf_ranges(tmp_path: Path) -> None:
    tool = create_read_tool(tmp_path, permissions=None, state=FileReadState())

    schema = tool.args_schema.model_json_schema()

    assert "pages" in schema["properties"]


def test_read_directory_path_returns_error_mentioning_directory(tmp_path: Path) -> None:
    directory = tmp_path / "docs"
    directory.mkdir()
    tool = create_read_tool(tmp_path, permissions=None, state=FileReadState())

    result = tool.invoke({"file_path": "docs"})

    assert result.startswith("Error:")
    assert "directory" in result.lower()


def test_read_missing_file_returns_file_does_not_exist(tmp_path: Path) -> None:
    tool = create_read_tool(tmp_path, permissions=None, state=FileReadState())

    result = tool.invoke({"file_path": "missing.txt"})

    assert result == "File does not exist"


def test_read_permission_errors_begin_with_error(tmp_path: Path) -> None:
    target = tmp_path / "secret.txt"
    target.write_text("classified\n", encoding="utf-8")
    permissions = [
        SimpleNamespace(operations=["read"], paths=[str(target)], mode="deny"),
    ]
    tool = create_read_tool(tmp_path, permissions=permissions, state=FileReadState())

    result = tool.invoke({"file_path": "secret.txt"})

    assert result.startswith("Error:")


def test_registered_read_tool_uses_shared_state_with_write_and_edit_stubs(tmp_path: Path) -> None:
    tools = create_claude_file_tools(tmp_path, permissions=None)
    read_tool = next(tool for tool in tools if tool.name == "Read")
    target = tmp_path / "notes.txt"
    target.write_text("shared\n", encoding="utf-8")

    result = read_tool.invoke({"file_path": "notes.txt"})

    assert result == "1\tshared"
    states = [tool.metadata["hagent_file_state"] for tool in tools]
    assert states[0] is states[1] is states[2]
    assert states[0].get(target).content == "shared"


def test_read_returns_neutral_message_when_sandbox_unavailable(tmp_path: Path) -> None:
    """沙箱基础设施错误:工具返回契约文案(模型可见、可自愈),不抛异常炸流。"""
    from hagent.sandbox.errors import SandboxUnavailable, SandboxUnavailableReason

    class BrokenTransport:
        def exists(self, path):
            raise SandboxUnavailable(SandboxUnavailableReason.PAUSED)

        def is_directory(self, path):
            return False

        def read_text_metadata(self, path):
            raise AssertionError("不应到达")

    tool = create_read_tool(
        tmp_path, permissions=None, state=FileReadState(), transport=BrokenTransport()
    )
    result = tool.invoke({"file_path": "notes.txt"})
    assert result.startswith("[sandbox_unavailable:paused]")
    assert "File does not exist" not in result
