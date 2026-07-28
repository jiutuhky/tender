"""Claude Code-compatible file tool registration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool

from hagent.file_tools.io import FileTransport
from hagent.file_tools.state import FileReadState
from hagent.file_tools.tools import create_edit_tool, create_read_tool, create_write_tool


def create_claude_file_tools(
    workspace_root: Path,
    permissions: Any | None = None,
    transport: FileTransport | None = None,
) -> list[StructuredTool]:
    state = FileReadState()

    read_tool = create_read_tool(
        workspace_root=Path(workspace_root),
        permissions=permissions,
        state=state,
        transport=transport,
    )
    write_tool = create_write_tool(
        workspace_root=Path(workspace_root),
        permissions=permissions,
        state=state,
        transport=transport,
    )
    edit_tool = create_edit_tool(
        workspace_root=Path(workspace_root),
        permissions=permissions,
        state=state,
        transport=transport,
    )
    return [read_tool, write_tool, edit_tool]
