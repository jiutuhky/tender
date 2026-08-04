from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from hagent.file_tools.io import (
    FileTransport,
    HostFileTransport,
    format_with_line_numbers,
    read_text_metadata,
    write_text_preserving_encoding,
)
from hagent.file_tools.diff import structured_patch
from hagent.file_tools.paths import ensure_allowed, expand_file_path
from hagent.file_tools.readonly import ensure_writable
from hagent.file_tools.state import FileReadState

LEFT_SINGLE_CURLY_QUOTE = "‘"
RIGHT_SINGLE_CURLY_QUOTE = "’"
LEFT_DOUBLE_CURLY_QUOTE = "“"
RIGHT_DOUBLE_CURLY_QUOTE = "”"


class ReadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(description="Path to the file to read.")
    offset: int | None = Field(default=None, description="1-indexed line offset to start reading.")
    limit: int | None = Field(default=None, description="Maximum number of lines to read.")
    pages: str | None = Field(
        default=None,
        description="Page range for PDF files. Only applicable to PDF files.",
    )


class WriteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(description="Path to the file to write.")
    content: str = Field(description="Full file content to write.")


class EditInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(description="Path to the file to edit.")
    old_string: str = Field(description="Exact string to replace.")
    new_string: str = Field(description="Replacement string.")
    replace_all: bool = Field(
        default=False,
        description="Replace every occurrence of old_string instead of one occurrence.",
    )


def _normalize_quotes(value: str) -> str:
    return (
        value.replace(LEFT_SINGLE_CURLY_QUOTE, "'")
        .replace(RIGHT_SINGLE_CURLY_QUOTE, "'")
        .replace(LEFT_DOUBLE_CURLY_QUOTE, '"')
        .replace(RIGHT_DOUBLE_CURLY_QUOTE, '"')
    )


def _find_actual_string(content: str, search: str) -> str | None:
    if search in content:
        return search

    normalized_content = _normalize_quotes(content)
    normalized_search = _normalize_quotes(search)
    index = normalized_content.find(normalized_search)
    if index == -1:
        return None
    return content[index : index + len(search)]


def _is_opening_quote_context(chars: list[str], index: int) -> bool:
    if index == 0:
        return True
    return chars[index - 1] in {" ", "\t", "\n", "\r", "(", "[", "{", "—", "–"}


def _apply_curly_double_quotes(value: str) -> str:
    chars = list(value)
    result: list[str] = []
    for index, char in enumerate(chars):
        if char == '"':
            result.append(
                LEFT_DOUBLE_CURLY_QUOTE
                if _is_opening_quote_context(chars, index)
                else RIGHT_DOUBLE_CURLY_QUOTE
            )
        else:
            result.append(char)
    return "".join(result)


def _apply_curly_single_quotes(value: str) -> str:
    chars = list(value)
    result: list[str] = []
    for index, char in enumerate(chars):
        if char != "'":
            result.append(char)
            continue

        previous = chars[index - 1] if index > 0 else None
        next_char = chars[index + 1] if index < len(chars) - 1 else None
        if (
            previous is not None
            and next_char is not None
            and previous.isalpha()
            and next_char.isalpha()
        ):
            result.append(RIGHT_SINGLE_CURLY_QUOTE)
        else:
            result.append(
                LEFT_SINGLE_CURLY_QUOTE
                if _is_opening_quote_context(chars, index)
                else RIGHT_SINGLE_CURLY_QUOTE
            )
    return "".join(result)


def _preserve_quote_style(old_string: str, actual_old_string: str, new_string: str) -> str:
    if old_string == actual_old_string:
        return new_string

    result = new_string
    if any(quote in actual_old_string for quote in (LEFT_DOUBLE_CURLY_QUOTE, RIGHT_DOUBLE_CURLY_QUOTE)):
        result = _apply_curly_double_quotes(result)
    if any(quote in actual_old_string for quote in (LEFT_SINGLE_CURLY_QUOTE, RIGHT_SINGLE_CURLY_QUOTE)):
        result = _apply_curly_single_quotes(result)
    return result


def _apply_edit(
    content: str,
    old_string: str,
    new_string: str,
    replace_all: bool,
) -> str:
    search = old_string
    if new_string == "" and not old_string.endswith("\n") and f"{old_string}\n" in content:
        search = f"{old_string}\n"

    if replace_all:
        return content.replace(search, new_string)
    return content.replace(search, new_string, 1)


def create_read_tool(
    workspace_root: str | Path,
    permissions: Any | None,
    state: FileReadState,
    transport: FileTransport | None = None,
) -> StructuredTool:
    fs: FileTransport = transport or HostFileTransport()

    def _read(
        file_path: str,
        offset: int | None = None,
        limit: int | None = None,
        pages: str | None = None,
    ) -> str:
        try:
            path = expand_file_path(file_path, workspace_root)
            ensure_allowed(permissions, "read", path)
        except (PermissionError, ValueError) as exc:
            return f"Error: {exc}"

        if not fs.exists(path):
            return "File does not exist"
        if fs.is_directory(path):
            return f"Error: {path} is a directory"
        if pages is not None and path.suffix.lower() != ".pdf":
            return "Error: pages parameter is only applicable to PDF files"

        metadata = fs.read_text_metadata(path)
        start_line = 1 if offset is None else offset
        if start_line < 0:
            return "Error: offset must be a non-negative line number"
        if limit is not None and limit <= 0:
            return "Error: limit must be a positive line count"

        previous = state.get(path)
        if (
            previous is not None
            and previous.offset is not None
            and not previous.is_partial_view
            and previous.limit == limit
            and previous.offset == start_line
            and previous.timestamp_ms == metadata.timestamp_ms
        ):
            return (
                "File unchanged since last read. The content from the earlier Read "
                "tool_result in this conversation is still current — refer to that instead "
                "of re-reading."
            )

        line_offset = 0 if start_line == 0 else start_line - 1
        lines = metadata.content.splitlines()
        selected_lines = lines[line_offset:]
        if limit is not None:
            selected_lines = selected_lines[:limit]
        selected_content = "\n".join(selected_lines)

        state.record_read(
            path,
            selected_content,
            timestamp_ms=metadata.timestamp_ms,
            offset=start_line,
            limit=limit,
        )
        if not selected_content:
            total_lines = len(lines)
            if total_lines == 0:
                return (
                    "<system-reminder>Warning: the file exists but the contents "
                    "are empty.</system-reminder>"
                )
            return (
                "<system-reminder>Warning: the file exists but is shorter than "
                f"the provided offset ({start_line}). The file has {total_lines} "
                "lines.</system-reminder>"
            )
        return format_with_line_numbers(selected_content, start_line=start_line)

    return StructuredTool.from_function(
        func=_read,
        name="Read",
        description="Read a file from the local filesystem.",
        args_schema=ReadInput,
        metadata={"hagent_file_state": state},
    )


def create_write_tool(
    workspace_root: str | Path,
    permissions: Any | None,
    state: FileReadState,
    transport: FileTransport | None = None,
) -> StructuredTool:
    fs: FileTransport = transport or HostFileTransport()

    def _write(file_path: str, content: str) -> str:
        try:
            path = expand_file_path(file_path, workspace_root)
            ensure_allowed(permissions, "write", path)
            ensure_writable(path, workspace_root)
        except (PermissionError, ValueError) as exc:
            return f"Error: {exc}"

        if fs.exists(path) and fs.is_directory(path):
            return f"Error: {path} is a directory"

        if not fs.exists(path):
            fs.write_text(path, content, "utf-8", "LF")
            metadata = fs.read_text_metadata(path)
            state.record_write(path, metadata.content, metadata.timestamp_ms)
            return f"File created successfully at: {path}"

        metadata = fs.read_text_metadata(path)
        snapshot = state.get(path)
        if snapshot is None or snapshot.is_partial_view:
            return "File has not been read yet. Read it first before writing to it."

        if metadata.timestamp_ms > snapshot.timestamp_ms:
            is_full_post_write_state = snapshot.offset is None and snapshot.limit is None
            if not is_full_post_write_state or metadata.content != snapshot.content:
                return (
                    "File has been modified since read, either by the user or by a linter. "
                    "Read it again before attempting to write it."
                )

        fs.write_text(path, content, metadata.encoding, "LF")
        updated_metadata = fs.read_text_metadata(path)
        state.record_write(path, updated_metadata.content, updated_metadata.timestamp_ms)
        return f"The file {file_path} has been updated successfully."

    return StructuredTool.from_function(
        func=_write,
        name="Write",
        description="Write a file to the local filesystem.",
        args_schema=WriteInput,
        metadata={"hagent_file_state": state},
    )


def create_edit_tool(
    workspace_root: str | Path,
    permissions: Any | None,
    state: FileReadState,
    transport: FileTransport | None = None,
) -> StructuredTool:
    fs: FileTransport = transport or HostFileTransport()

    def _edit(
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        try:
            path = expand_file_path(file_path, workspace_root)
            ensure_allowed(permissions, "write", path)
            ensure_writable(path, workspace_root)
        except (PermissionError, ValueError) as exc:
            return f"Error: {exc}"

        if path.suffix == ".ipynb":
            return "File is a Jupyter Notebook. Use the NotebookEdit tool to edit this file."
        if old_string == new_string:
            return "No changes to make: old_string and new_string are exactly the same."
        if fs.exists(path) and fs.is_directory(path):
            return f"Error: {path} is a directory"

        if not fs.exists(path):
            if old_string != "":
                return f"File does not exist: {path}"
            fs.write_text(path, new_string, "utf-8", "LF")
            metadata = fs.read_text_metadata(path)
            state.record_write(path, metadata.content, metadata.timestamp_ms)
            return f"The file {file_path} has been updated successfully."

        metadata = fs.read_text_metadata(path)
        if old_string == "":
            if metadata.content.strip():
                return "Cannot create new file - file already exists."
            updated_content = new_string
        else:
            snapshot = state.get(path)
            if snapshot is None or snapshot.is_partial_view:
                return "File has not been read yet. Read it first before writing to it."

            if metadata.timestamp_ms > snapshot.timestamp_ms:
                is_full_post_write_state = snapshot.offset is None and snapshot.limit is None
                if not is_full_post_write_state or metadata.content != snapshot.content:
                    return (
                        "File has been modified since read, either by the user or by a linter. "
                        "Read it again before attempting to write it."
                    )

            actual_old_string = _find_actual_string(metadata.content, old_string)
            if actual_old_string is None:
                match_count = 0
            else:
                match_count = metadata.content.count(actual_old_string)
            if match_count == 0:
                return f"String to replace not found in file.\nString: {old_string}"
            if match_count > 1 and not replace_all:
                return (
                    f"Found {match_count} matches of the string to replace, but replace_all "
                    "is false. To replace all occurrences, set replace_all to true. "
                    "To replace only one occurrence, please provide more context to uniquely "
                    f"identify the instance.\nString: {old_string}"
                )

            replacement = _preserve_quote_style(old_string, actual_old_string, new_string)
            updated_content = _apply_edit(
                metadata.content,
                actual_old_string,
                replacement,
                replace_all,
            )

        structured_patch(path, metadata.content, updated_content)
        fs.write_text(
            path,
            updated_content,
            metadata.encoding,
            metadata.line_endings,
        )
        updated_metadata = fs.read_text_metadata(path)
        state.record_write(path, updated_metadata.content, updated_metadata.timestamp_ms)
        if replace_all:
            return (
                f"The file {file_path} has been updated. "
                "All occurrences were successfully replaced."
            )
        return f"The file {file_path} has been updated successfully."

    return StructuredTool.from_function(
        func=_edit,
        name="Edit",
        description="Edit a file on the local filesystem.",
        args_schema=EditInput,
        metadata={"hagent_file_state": state},
    )
