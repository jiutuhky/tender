"""OCR 原文只读锁：agent 改不动 `sources/` 下的 md 与 sidecar。

`line_span` 的正确性完全建立在「md 只读」之上——放松这条，溯源会静默错位。
拒绝必须给出可读的中文原因并指出该往哪写，否则 agent 只会反复重试。
"""

from __future__ import annotations

import pytest

from hagent.file_tools import create_claude_file_tools
from hagent.file_tools.readonly import ReadOnlySourceError, ensure_writable, is_protected


@pytest.fixture
def workspace(tmp_path):
    for directory in ("sources", "structured", "deliverables"):
        (tmp_path / directory).mkdir()
    (tmp_path / "sources" / "招标文件.md").write_text("# 原文\n", encoding="utf-8")
    (tmp_path / "sources" / "招标文件.sidecar.json").write_text("{}", encoding="utf-8")
    return tmp_path


@pytest.fixture
def tools(workspace):
    return {tool.name: tool for tool in create_claude_file_tools(workspace_root=workspace)}


@pytest.mark.parametrize(
    "relative",
    ["sources/招标文件.md", "sources/招标文件.sidecar.json", "sources/子目录/别的.md"],
)
def test_ocr_outputs_are_protected(workspace, relative):
    assert is_protected(workspace / relative, workspace)


@pytest.mark.parametrize(
    "relative",
    [
        "structured/matrix.md",
        "deliverables/chapter.md",
        "sources/招标文件.pdf",
        "notes.md",
    ],
)
def test_other_paths_are_not_protected(workspace, relative):
    assert not is_protected(workspace / relative, workspace)


def test_error_message_says_why_and_where_to_write_instead(workspace):
    with pytest.raises(ReadOnlySourceError) as excinfo:
        ensure_writable(workspace / "sources" / "招标文件.md", workspace)
    message = str(excinfo.value)
    assert "只读" in message
    assert "structured/" in message and "deliverables/" in message


# —— 工具层 ——


def test_write_tool_rejects_ocr_markdown(tools, workspace):
    result = tools["Write"].invoke({"file_path": "sources/招标文件.md", "content": "篡改"})
    assert "只读" in result
    assert (workspace / "sources" / "招标文件.md").read_text(encoding="utf-8") == "# 原文\n"


def test_write_tool_rejects_sidecar(tools, workspace):
    result = tools["Write"].invoke({"file_path": "sources/招标文件.sidecar.json", "content": "{}"})
    assert "只读" in result
    assert (workspace / "sources" / "招标文件.sidecar.json").read_text(encoding="utf-8") == "{}"


def test_edit_tool_rejects_ocr_markdown(tools, workspace):
    result = tools["Edit"].invoke(
        {"file_path": "sources/招标文件.md", "old_string": "原文", "new_string": "篡改"}
    )
    assert "只读" in result
    assert (workspace / "sources" / "招标文件.md").read_text(encoding="utf-8") == "# 原文\n"


def test_read_tool_still_works_on_protected_files(tools):
    assert "原文" in tools["Read"].invoke({"file_path": "sources/招标文件.md"})


def test_structured_and_deliverables_writes_are_unaffected(tools, workspace):
    for relative in ("structured/matrix.md", "deliverables/chapter.md"):
        result = tools["Write"].invoke({"file_path": relative, "content": "内容"})
        assert "只读" not in result
        assert (workspace / relative).read_text(encoding="utf-8") == "内容"
