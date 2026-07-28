# Claude-Compatible File Tools Implementation Plan

> **存档说明**：本 plan 产出自已退役的 superpowers 工作流，仅作历史参考；新工作一律走仓根 tickets.md（Matt 契约）。

**Goal:** Replace Hagent's deepagents-provided `read_file` / `write_file` / `edit_file` tools with Python implementations of Claude Code-compatible `Read` / `Write` / `Edit` tools.

**Architecture:** Hagent will keep deepagents as the agent harness, but exclude deepagents' built-in filesystem tools and inject Hagent-owned file tools with Claude Code tool names, schemas, read-state semantics, stale-write protection, and result messages. The implementation targets Claude Code's model-visible behavior and filesystem safety semantics; telemetry, GrowthBook feature gates, VSCode notifications, and LSP notifications are represented by inert extension hooks because Hagent does not currently have those subsystems.

**Tech Stack:** Python 3.11+, deepagents `FilesystemBackend`, LangChain `StructuredTool` / `ToolMessage`, Pydantic schemas, `difflib`, `pytest`.

---

## Required Context

- Hagent currently creates agents in `src/hagent/core.py` with `deepagents.create_deep_agent(...)`, passes a deepagents `FilesystemBackend`, and only adds a custom `Bash` tool.
- deepagents injects filesystem tools from `FilesystemMiddleware`: `read_file`, `write_file`, `edit_file`, `ls`, `glob`, `grep`, and an `execute` tool. Hagent already excludes deepagents `execute`.
- Claude Code recovered source uses tool names `Read`, `Write`, and `Edit`.
- Claude Code `Write` can create or overwrite files. Existing-file overwrite requires a previous full `Read`, then rejects if the file changed after that read.
- Claude Code `Edit` requires a previous full `Read`, rejects partial reads, rejects stale files, rejects ambiguous `old_string` unless `replace_all` is true, and rejects `.ipynb` with a notebook-tool message.
- Claude Code `Read` records read state, supports `offset`, `limit`, and `pages`, returns numbered text, returns a file-unchanged stub for duplicate unchanged reads, and enables `Write` / `Edit` safety checks.
- Hagent's default permissions are in `src/hagent/permissions.py`; the new tools must enforce them directly because deepagents permissions will no longer cover the excluded tools.

## File Structure

- Create `src/hagent/file_tools/__init__.py`: public factory `create_claude_file_tools(...)` and exports.
- Create `src/hagent/file_tools/state.py`: read-state dataclasses and session-local state store.
- Create `src/hagent/file_tools/paths.py`: path expansion, permission matching, and filesystem guard helpers.
- Create `src/hagent/file_tools/io.py`: text read/write helpers with encoding and line-ending metadata.
- Create `src/hagent/file_tools/diff.py`: structured patch generation for `Write` and `Edit` results.
- Create `src/hagent/file_tools/tools.py`: `Read`, `Write`, and `Edit` `StructuredTool` definitions.
- Modify `src/hagent/core.py`: exclude deepagents filesystem tools and inject Hagent file tools.
- Modify `prompts/hagent_base.zh.md`: replace user-visible tool names with `Read`, `Write`, and `Edit`.
- Modify `prompts/decisions.md`: update prompt decision counts and mapping rationale.
- Test `tests/test_claude_file_tools_registration.py`: agent wiring and tool names.
- Test `tests/test_claude_file_tool_permissions.py`: permission and path behavior.
- Test `tests/test_claude_read_tool.py`: `Read` behavior.
- Test `tests/test_claude_write_tool.py`: `Write` behavior.
- Test `tests/test_claude_edit_tool.py`: `Edit` behavior.

---

### Task 1: Register Claude Tool Names and Exclude deepagents File Tools

**Files:**
- Create: `src/hagent/file_tools/__init__.py`
- Modify: `src/hagent/core.py:18-119`
- Test: `tests/test_claude_file_tools_registration.py`

- [ ] **Step 1: Write failing registration tests**

Create `tests/test_claude_file_tools_registration.py`:

```python
from hagent.core import create_hagent


def test_create_hagent_injects_claude_file_tools(monkeypatch):
    captured: dict = {}
    registered: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    def fake_register_harness_profile(key, profile):
        registered["key"] = key
        registered["profile"] = profile

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    monkeypatch.setattr("hagent.core.register_harness_profile", fake_register_harness_profile)

    create_hagent()

    tool_names = {tool.name for tool in captured["tools"]}
    assert {"Read", "Write", "Edit", "Bash"}.issubset(tool_names)
    assert {"read_file", "write_file", "edit_file", "execute"}.issubset(
        registered["profile"].excluded_tools
    )


def test_create_hagent_file_tools_share_one_read_state(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    create_hagent()

    tools_by_name = {tool.name: tool for tool in captured["tools"]}
    assert tools_by_name["Read"].metadata["hagent_file_state"] is tools_by_name["Write"].metadata["hagent_file_state"]
    assert tools_by_name["Read"].metadata["hagent_file_state"] is tools_by_name["Edit"].metadata["hagent_file_state"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_claude_file_tools_registration.py -v
```

Expected: FAIL because `src/hagent/file_tools` does not exist and Hagent only injects `Bash`.

- [ ] **Step 3: Add the file-tools factory stub**

Create `src/hagent/file_tools/__init__.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool

from hagent.permissions import DEFAULT_PERMISSIONS


def _stub_tool(name: str, state: object) -> StructuredTool:
    def run_stub() -> str:
        return f"{name} is not implemented yet."

    tool = StructuredTool.from_function(
        name=name,
        description=f"Claude-compatible {name} file tool.",
        func=run_stub,
    )
    tool.metadata = {"hagent_file_state": state}
    return tool


def create_claude_file_tools(
    *,
    workspace_root: Path,
    permissions: list[Any] | None = None,
) -> list[StructuredTool]:
    state = object()
    _ = workspace_root
    _ = permissions or DEFAULT_PERMISSIONS
    return [_stub_tool("Read", state), _stub_tool("Write", state), _stub_tool("Edit", state)]
```

- [ ] **Step 4: Wire the factory and excluded tools into `create_hagent`**

Modify `src/hagent/core.py`:

```python
from hagent.file_tools import create_claude_file_tools
```

Replace the excluded tool constant with:

```python
DISABLED_DEEPAGENTS_TOOLS = frozenset({"execute", "read_file", "write_file", "edit_file"})
```

Insert after `bash_tool = create_bash_tool(...)`:

```python
    file_tools = create_claude_file_tools(
        workspace_root=working_directory,
        permissions=DEFAULT_PERMISSIONS,
    )
```

Change the tools list to:

```python
        tools=[bash_tool, *file_tools, *list(extra_tools or [])],
```

Change `HarnessProfile(...)` construction to include:

```python
            excluded_tools=DISABLED_DEEPAGENTS_TOOLS,
```

- [ ] **Step 5: Run registration tests**

Run:

```bash
pytest tests/test_claude_file_tools_registration.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/hagent/core.py src/hagent/file_tools/__init__.py tests/test_claude_file_tools_registration.py
git commit -m "feat(file-tools): register claude-compatible tool names"
```

---

### Task 2: Implement Shared State, Paths, Permissions, and I/O Primitives

**Files:**
- Create: `src/hagent/file_tools/state.py`
- Create: `src/hagent/file_tools/paths.py`
- Create: `src/hagent/file_tools/io.py`
- Create: `src/hagent/file_tools/diff.py`
- Test: `tests/test_claude_file_tool_permissions.py`

- [ ] **Step 1: Write failing primitive tests**

Create `tests/test_claude_file_tool_permissions.py`:

```python
from pathlib import Path

from deepagents import FilesystemPermission

from hagent.file_tools.diff import structured_patch
from hagent.file_tools.io import read_text_metadata, write_text_preserving_encoding
from hagent.file_tools.paths import check_permission, expand_file_path
from hagent.file_tools.state import FileReadState


def test_expand_file_path_resolves_relative_paths_under_workspace(tmp_path):
    path = expand_file_path("src/app.py", tmp_path)
    assert path == (tmp_path / "src/app.py").resolve()


def test_expand_file_path_rejects_home_paths(tmp_path):
    try:
        expand_file_path("~/secret.txt", tmp_path)
    except ValueError as exc:
        assert "Home-relative paths are not allowed" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_check_permission_uses_first_matching_rule():
    rules = [
        FilesystemPermission(operations=["write"], paths=["/tmp/hagent/**"], mode="deny"),
        FilesystemPermission(operations=["write"], paths=["/tmp/hagent/workspace/**"], mode="allow"),
    ]
    assert check_permission(rules, "write", "/tmp/hagent/workspace/a.py") == "deny"


def test_read_state_tracks_full_and_partial_reads(tmp_path):
    state = FileReadState()
    file_path = tmp_path / "a.py"
    file_path.write_text("a\nb\n", encoding="utf-8")

    state.record_read(file_path, content="a\nb\n", timestamp_ms=file_path.stat().st_mtime_ns // 1_000_000, offset=1, limit=None)
    snapshot = state.get(file_path)

    assert snapshot is not None
    assert snapshot.content == "a\nb\n"
    assert snapshot.is_partial_view is False

    state.record_read(file_path, content="a\n", timestamp_ms=file_path.stat().st_mtime_ns // 1_000_000, offset=1, limit=1)
    assert state.get(file_path).is_partial_view is True


def test_text_metadata_round_trips_utf8_and_line_endings(tmp_path):
    file_path = tmp_path / "script.sh"
    file_path.write_bytes(b"one\r\ntwo\r\n")

    meta = read_text_metadata(file_path)
    assert meta.content == "one\ntwo\n"
    assert meta.line_endings == "CRLF"

    write_text_preserving_encoding(file_path, "three\n", meta.encoding, "LF")
    assert file_path.read_bytes() == b"three\n"


def test_structured_patch_contains_old_and_new_lines():
    patch = structured_patch("a.py", "one\ntwo\n", "one\nthree\n")
    flattened = "\n".join(line for hunk in patch for line in hunk["lines"])
    assert "-two" in flattened
    assert "+three" in flattened
```

- [ ] **Step 2: Run primitive tests to verify they fail**

Run:

```bash
pytest tests/test_claude_file_tool_permissions.py -v
```

Expected: FAIL because the modules do not exist.

- [ ] **Step 3: Implement read state**

Create `src/hagent/file_tools/state.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock


@dataclass(frozen=True)
class ReadSnapshot:
    content: str
    timestamp_ms: int
    offset: int | None
    limit: int | None

    @property
    def is_partial_view(self) -> bool:
        return self.limit is not None


class FileReadState:
    def __init__(self) -> None:
        self._lock = RLock()
        self._snapshots: dict[str, ReadSnapshot] = {}

    def get(self, file_path: str | Path) -> ReadSnapshot | None:
        with self._lock:
            return self._snapshots.get(str(Path(file_path).resolve()))

    def record_read(
        self,
        file_path: str | Path,
        *,
        content: str,
        timestamp_ms: int,
        offset: int | None,
        limit: int | None,
    ) -> None:
        with self._lock:
            self._snapshots[str(Path(file_path).resolve())] = ReadSnapshot(
                content=content,
                timestamp_ms=timestamp_ms,
                offset=offset,
                limit=limit,
            )

    def record_write(self, file_path: str | Path, *, content: str, timestamp_ms: int) -> None:
        with self._lock:
            self._snapshots[str(Path(file_path).resolve())] = ReadSnapshot(
                content=content,
                timestamp_ms=timestamp_ms,
                offset=None,
                limit=None,
            )
```

- [ ] **Step 4: Implement paths and permissions**

Create `src/hagent/file_tools/paths.py`:

```python
from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
from typing import Literal, Sequence

from deepagents import FilesystemPermission

Operation = Literal["read", "write"]


def expand_file_path(file_path: str, workspace_root: Path) -> Path:
    if file_path.startswith("~"):
        raise ValueError(f"Home-relative paths are not allowed: {file_path}")
    raw = Path(file_path)
    path = raw if raw.is_absolute() else workspace_root / raw
    return path.resolve()


def check_permission(
    rules: Sequence[FilesystemPermission],
    operation: Operation,
    file_path: str | Path,
) -> Literal["allow", "deny"]:
    normalized = Path(file_path).resolve().as_posix()
    for rule in rules:
        if operation not in rule.operations:
            continue
        if any(fnmatchcase(normalized, pattern) for pattern in rule.paths):
            return rule.mode
    return "allow"


def ensure_allowed(
    rules: Sequence[FilesystemPermission],
    operation: Operation,
    file_path: str | Path,
) -> None:
    if check_permission(rules, operation, file_path) == "deny":
        raise PermissionError(f"permission denied for {operation} on {Path(file_path).resolve().as_posix()}")
```

- [ ] **Step 5: Implement I/O helpers**

Create `src/hagent/file_tools/io.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

LineEndings = Literal["LF", "CRLF"]


@dataclass(frozen=True)
class TextMetadata:
    content: str
    encoding: str
    line_endings: LineEndings
    timestamp_ms: int


def _line_endings(raw: bytes) -> LineEndings:
    return "CRLF" if b"\r\n" in raw else "LF"


def _encoding(raw: bytes) -> str:
    return "utf-16-le" if raw.startswith(b"\xff\xfe") else "utf-8"


def read_text_metadata(file_path: Path) -> TextMetadata:
    raw = file_path.read_bytes()
    encoding = _encoding(raw)
    content = raw.decode(encoding)
    if encoding == "utf-16-le" and content.startswith("\ufeff"):
        content = content.removeprefix("\ufeff")
    return TextMetadata(
        content=content.replace("\r\n", "\n").replace("\r", "\n"),
        encoding=encoding,
        line_endings=_line_endings(raw),
        timestamp_ms=file_path.stat().st_mtime_ns // 1_000_000,
    )


def write_text_preserving_encoding(
    file_path: Path,
    content: str,
    encoding: str,
    line_endings: LineEndings,
) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    text = content if line_endings == "LF" else content.replace("\n", "\r\n")
    if encoding == "utf-16-le":
        file_path.write_bytes(("\ufeff" + text).encode("utf-16-le"))
    else:
        file_path.write_text(text, encoding="utf-8", newline="")


def format_with_line_numbers(content: str, start_line: int) -> str:
    lines = content.splitlines()
    if content.endswith("\n"):
        lines = content[:-1].split("\n")
    return "\n".join(f"{idx:>6}\t{line}" for idx, line in enumerate(lines, start=start_line))
```

- [ ] **Step 6: Implement structured patch helper**

Create `src/hagent/file_tools/diff.py`:

```python
from __future__ import annotations

import difflib
from typing import Any


def structured_patch(file_path: str, old_content: str, new_content: str) -> list[dict[str, Any]]:
    diff_lines = list(
        difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            fromfile=file_path,
            tofile=file_path,
            lineterm="",
        )
    )
    hunks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in diff_lines:
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("@@"):
            current = {
                "oldStart": 0,
                "oldLines": 0,
                "newStart": 0,
                "newLines": 0,
                "lines": [line],
            }
            hunks.append(current)
            continue
        if current is not None:
            current["lines"].append(line)
    return hunks
```

- [ ] **Step 7: Run primitive tests**

Run:

```bash
pytest tests/test_claude_file_tool_permissions.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/hagent/file_tools/state.py src/hagent/file_tools/paths.py src/hagent/file_tools/io.py src/hagent/file_tools/diff.py tests/test_claude_file_tool_permissions.py
git commit -m "feat(file-tools): add claude file primitives"
```

---

### Task 3: Implement the Claude Code `Read` Tool

**Files:**
- Create: `src/hagent/file_tools/tools.py`
- Modify: `src/hagent/file_tools/__init__.py`
- Test: `tests/test_claude_read_tool.py`

- [ ] **Step 1: Write failing Read tests**

Create `tests/test_claude_read_tool.py`:

```python
from pathlib import Path

from hagent.file_tools import create_claude_file_tools


def _tool(name: str, tmp_path: Path):
    tools = create_claude_file_tools(workspace_root=tmp_path, permissions=[])
    return next(tool for tool in tools if tool.name == name)


def test_read_tool_reads_numbered_text_and_records_state(tmp_path):
    file_path = tmp_path / "a.py"
    file_path.write_text("one\ntwo\n", encoding="utf-8")
    read = _tool("Read", tmp_path)

    result = read.invoke({"file_path": str(file_path)})

    assert "     1\tone" in result
    assert "     2\ttwo" in result
    state = read.metadata["hagent_file_state"]
    assert state.get(file_path).content == "one\ntwo\n"


def test_read_tool_supports_offset_and_limit(tmp_path):
    file_path = tmp_path / "a.py"
    file_path.write_text("one\ntwo\nthree\n", encoding="utf-8")
    read = _tool("Read", tmp_path)

    result = read.invoke({"file_path": str(file_path), "offset": 2, "limit": 1})

    assert "     2\ttwo" in result
    assert "one" not in result
    assert "three" not in result
    assert read.metadata["hagent_file_state"].get(file_path).is_partial_view is True


def test_read_tool_returns_unchanged_stub_for_duplicate_full_read(tmp_path):
    file_path = tmp_path / "a.py"
    file_path.write_text("one\n", encoding="utf-8")
    read = _tool("Read", tmp_path)

    first = read.invoke({"file_path": str(file_path)})
    second = read.invoke({"file_path": str(file_path)})

    assert "     1\tone" in first
    assert "File unchanged since last read" in second


def test_read_tool_rejects_directory(tmp_path):
    read = _tool("Read", tmp_path)
    result = read.invoke({"file_path": str(tmp_path)})
    assert "Error:" in result
    assert "is a directory" in result


def test_read_tool_reports_missing_file(tmp_path):
    read = _tool("Read", tmp_path)
    result = read.invoke({"file_path": str(tmp_path / "missing.py")})
    assert "File does not exist" in result
```

- [ ] **Step 2: Run Read tests to verify they fail**

Run:

```bash
pytest tests/test_claude_read_tool.py -v
```

Expected: FAIL because `Read` is still a stub.

- [ ] **Step 3: Implement `Read` in `tools.py`**

Create `src/hagent/file_tools/tools.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from deepagents import FilesystemPermission
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from hagent.file_tools.io import format_with_line_numbers, read_text_metadata
from hagent.file_tools.paths import ensure_allowed, expand_file_path
from hagent.file_tools.state import FileReadState

FILE_UNCHANGED_STUB = (
    "File unchanged since last read. The content from the earlier Read tool_result "
    "in this conversation is still current — refer to that instead of re-reading."
)


class ReadInput(BaseModel):
    file_path: str = Field(description="The absolute path to the file to read")
    offset: int | None = Field(default=1, description="The line number to start reading from")
    limit: int | None = Field(default=None, description="The number of lines to read")
    pages: str | None = Field(default=None, description="Page range for PDF files")


def create_read_tool(
    *,
    workspace_root: Path,
    permissions: list[FilesystemPermission],
    state: FileReadState,
) -> StructuredTool:
    def read_file(file_path: str, offset: int | None = 1, limit: int | None = None, pages: str | None = None) -> str:
        _ = pages
        try:
            full_path = expand_file_path(file_path, workspace_root)
            ensure_allowed(permissions, "read", full_path)
            if not full_path.exists():
                return f"File does not exist. Current working directory: {workspace_root}"
            if full_path.is_dir():
                return f"Error: {file_path} is a directory. Use Bash to list directory contents."

            meta = read_text_metadata(full_path)
            start_line = 1 if offset is None else offset
            line_offset = 0 if start_line == 0 else start_line - 1
            existing = state.get(full_path)
            if existing and not existing.is_partial_view and existing.offset == start_line and existing.limit == limit:
                if existing.timestamp_ms == meta.timestamp_ms:
                    return FILE_UNCHANGED_STUB

            lines = meta.content.splitlines(keepends=True)
            selected = lines[line_offset:] if limit is None else lines[line_offset : line_offset + limit]
            if line_offset >= len(lines) and lines:
                return f"<system-reminder>Warning: the file exists but is shorter than the provided offset ({start_line}). The file has {len(lines)} lines.</system-reminder>"

            content = "".join(selected)
            state.record_read(
                full_path,
                content=content,
                timestamp_ms=meta.timestamp_ms,
                offset=start_line,
                limit=limit,
            )
            if content == "":
                return "<system-reminder>Warning: the file exists but has empty contents</system-reminder>"
            return format_with_line_numbers(content, start_line)
        except PermissionError as exc:
            return f"Error: {exc}"
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            return f"Error: {exc}"

    tool = StructuredTool.from_function(
        name="Read",
        description="Read a file from the local filesystem.",
        func=read_file,
        args_schema=ReadInput,
    )
    tool.metadata = {"hagent_file_state": state}
    return tool
```

- [ ] **Step 4: Update the factory to use `create_read_tool`**

Replace `src/hagent/file_tools/__init__.py` with:

```python
from __future__ import annotations

from pathlib import Path

from deepagents import FilesystemPermission
from langchain_core.tools import StructuredTool

from hagent.file_tools.state import FileReadState
from hagent.file_tools.tools import create_read_tool


def create_claude_file_tools(
    *,
    workspace_root: Path,
    permissions: list[FilesystemPermission] | None = None,
) -> list[StructuredTool]:
    state = FileReadState()
    rules = permissions or []
    return [
        create_read_tool(workspace_root=workspace_root, permissions=rules, state=state),
        StructuredTool.from_function(name="Write", description="Write a file to the local filesystem.", func=lambda: "Write is not implemented yet."),
        StructuredTool.from_function(name="Edit", description="A tool for editing files.", func=lambda: "Edit is not implemented yet."),
    ]
```

Then set the same metadata on the temporary `Write` and `Edit` tools before returning:

```python
    write = StructuredTool.from_function(name="Write", description="Write a file to the local filesystem.", func=lambda: "Write is not implemented yet.")
    edit = StructuredTool.from_function(name="Edit", description="A tool for editing files.", func=lambda: "Edit is not implemented yet.")
    write.metadata = {"hagent_file_state": state}
    edit.metadata = {"hagent_file_state": state}
```

- [ ] **Step 5: Run Read tests**

Run:

```bash
pytest tests/test_claude_read_tool.py tests/test_claude_file_tools_registration.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/hagent/file_tools/__init__.py src/hagent/file_tools/tools.py tests/test_claude_read_tool.py
git commit -m "feat(file-tools): add claude read tool"
```

---

### Task 4: Implement the Claude Code `Write` Tool

**Files:**
- Modify: `src/hagent/file_tools/tools.py`
- Modify: `src/hagent/file_tools/__init__.py`
- Test: `tests/test_claude_write_tool.py`

- [ ] **Step 1: Write failing Write tests**

Create `tests/test_claude_write_tool.py`:

```python
from pathlib import Path

from hagent.file_tools import create_claude_file_tools


def _tools(tmp_path: Path):
    tools = create_claude_file_tools(workspace_root=tmp_path, permissions=[])
    return {tool.name: tool for tool in tools}


def test_write_creates_new_file_without_prior_read(tmp_path):
    tools = _tools(tmp_path)
    file_path = tmp_path / "new.py"

    result = tools["Write"].invoke({"file_path": str(file_path), "content": "print('hi')\n"})

    assert file_path.read_text(encoding="utf-8") == "print('hi')\n"
    assert "File created successfully at:" in result


def test_write_overwrites_existing_file_after_full_read(tmp_path):
    tools = _tools(tmp_path)
    file_path = tmp_path / "a.py"
    file_path.write_text("old\n", encoding="utf-8")

    tools["Read"].invoke({"file_path": str(file_path)})
    result = tools["Write"].invoke({"file_path": str(file_path), "content": "new\n"})

    assert file_path.read_text(encoding="utf-8") == "new\n"
    assert "has been updated successfully" in result
    assert tools["Read"].metadata["hagent_file_state"].get(file_path).content == "new\n"


def test_write_existing_file_requires_prior_read(tmp_path):
    tools = _tools(tmp_path)
    file_path = tmp_path / "a.py"
    file_path.write_text("old\n", encoding="utf-8")

    result = tools["Write"].invoke({"file_path": str(file_path), "content": "new\n"})

    assert "File has not been read yet" in result
    assert file_path.read_text(encoding="utf-8") == "old\n"


def test_write_rejects_stale_existing_file(tmp_path):
    tools = _tools(tmp_path)
    file_path = tmp_path / "a.py"
    file_path.write_text("old\n", encoding="utf-8")

    tools["Read"].invoke({"file_path": str(file_path)})
    file_path.write_text("user edit\n", encoding="utf-8")
    result = tools["Write"].invoke({"file_path": str(file_path), "content": "new\n"})

    assert "File has been modified since read" in result
    assert file_path.read_text(encoding="utf-8") == "user edit\n"
```

- [ ] **Step 2: Run Write tests to verify they fail**

Run:

```bash
pytest tests/test_claude_write_tool.py -v
```

Expected: FAIL because `Write` is still a stub.

- [ ] **Step 3: Add `WriteInput` and `create_write_tool`**

Append to `src/hagent/file_tools/tools.py`:

```python
from hagent.file_tools.diff import structured_patch
from hagent.file_tools.io import write_text_preserving_encoding


class WriteInput(BaseModel):
    file_path: str = Field(description="The absolute path to the file to write")
    content: str = Field(description="The content to write to the file")


def _assert_fresh_for_existing_file(state: FileReadState, file_path: Path, current_content: str, timestamp_ms: int) -> str | None:
    snapshot = state.get(file_path)
    if snapshot is None or snapshot.is_partial_view:
        return "File has not been read yet. Read it first before writing to it."
    if timestamp_ms > snapshot.timestamp_ms and current_content != snapshot.content:
        return "File has been modified since read, either by the user or by a linter. Read it again before attempting to write it."
    return None


def create_write_tool(
    *,
    workspace_root: Path,
    permissions: list[FilesystemPermission],
    state: FileReadState,
) -> StructuredTool:
    def write_file(file_path: str, content: str) -> str:
        try:
            full_path = expand_file_path(file_path, workspace_root)
            ensure_allowed(permissions, "write", full_path)
            old_content: str | None = None
            encoding = "utf-8"
            if full_path.exists():
                meta = read_text_metadata(full_path)
                old_content = meta.content
                encoding = meta.encoding
                stale_error = _assert_fresh_for_existing_file(state, full_path, meta.content, meta.timestamp_ms)
                if stale_error:
                    return stale_error

            write_text_preserving_encoding(full_path, content, encoding, "LF")
            timestamp_ms = full_path.stat().st_mtime_ns // 1_000_000
            state.record_write(full_path, content=content, timestamp_ms=timestamp_ms)
            if old_content is None:
                return f"File created successfully at: {file_path}"
            _ = structured_patch(file_path, old_content, content)
            return f"The file {file_path} has been updated successfully."
        except PermissionError as exc:
            return f"Error: {exc}"
        except (OSError, UnicodeDecodeError, UnicodeEncodeError, ValueError) as exc:
            return f"Error: {exc}"

    tool = StructuredTool.from_function(
        name="Write",
        description="Write a file to the local filesystem.",
        func=write_file,
        args_schema=WriteInput,
    )
    tool.metadata = {"hagent_file_state": state}
    return tool
```

- [ ] **Step 4: Update the factory to use `create_write_tool`**

Modify `src/hagent/file_tools/__init__.py` imports:

```python
from hagent.file_tools.tools import create_read_tool, create_write_tool
```

Replace the `Write` stub with:

```python
        create_write_tool(workspace_root=workspace_root, permissions=rules, state=state),
```

Keep `Edit` as the only remaining stub with shared metadata.

- [ ] **Step 5: Run Write tests**

Run:

```bash
pytest tests/test_claude_write_tool.py tests/test_claude_read_tool.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/hagent/file_tools/__init__.py src/hagent/file_tools/tools.py tests/test_claude_write_tool.py
git commit -m "feat(file-tools): add claude write tool"
```

---

### Task 5: Implement the Claude Code `Edit` Tool

**Files:**
- Modify: `src/hagent/file_tools/tools.py`
- Modify: `src/hagent/file_tools/__init__.py`
- Test: `tests/test_claude_edit_tool.py`

- [ ] **Step 1: Write failing Edit tests**

Create `tests/test_claude_edit_tool.py`:

```python
from pathlib import Path

from hagent.file_tools import create_claude_file_tools


def _tools(tmp_path: Path):
    tools = create_claude_file_tools(workspace_root=tmp_path, permissions=[])
    return {tool.name: tool for tool in tools}


def test_edit_requires_prior_full_read(tmp_path):
    tools = _tools(tmp_path)
    file_path = tmp_path / "a.py"
    file_path.write_text("old\n", encoding="utf-8")

    result = tools["Edit"].invoke({"file_path": str(file_path), "old_string": "old", "new_string": "new"})

    assert "File has not been read yet" in result
    assert file_path.read_text(encoding="utf-8") == "old\n"


def test_edit_rejects_partial_read(tmp_path):
    tools = _tools(tmp_path)
    file_path = tmp_path / "a.py"
    file_path.write_text("old\nsecond\n", encoding="utf-8")

    tools["Read"].invoke({"file_path": str(file_path), "offset": 1, "limit": 1})
    result = tools["Edit"].invoke({"file_path": str(file_path), "old_string": "old", "new_string": "new"})

    assert "File has not been read yet" in result


def test_edit_replaces_unique_string_after_read(tmp_path):
    tools = _tools(tmp_path)
    file_path = tmp_path / "a.py"
    file_path.write_text("old\n", encoding="utf-8")

    tools["Read"].invoke({"file_path": str(file_path)})
    result = tools["Edit"].invoke({"file_path": str(file_path), "old_string": "old", "new_string": "new"})

    assert file_path.read_text(encoding="utf-8") == "new\n"
    assert "has been updated successfully" in result


def test_edit_rejects_ambiguous_string_without_replace_all(tmp_path):
    tools = _tools(tmp_path)
    file_path = tmp_path / "a.py"
    file_path.write_text("x\nx\n", encoding="utf-8")

    tools["Read"].invoke({"file_path": str(file_path)})
    result = tools["Edit"].invoke({"file_path": str(file_path), "old_string": "x", "new_string": "y"})

    assert "Found 2 matches" in result
    assert file_path.read_text(encoding="utf-8") == "x\nx\n"


def test_edit_replace_all_replaces_every_occurrence(tmp_path):
    tools = _tools(tmp_path)
    file_path = tmp_path / "a.py"
    file_path.write_text("x\nx\n", encoding="utf-8")

    tools["Read"].invoke({"file_path": str(file_path)})
    result = tools["Edit"].invoke({"file_path": str(file_path), "old_string": "x", "new_string": "y", "replace_all": True})

    assert file_path.read_text(encoding="utf-8") == "y\ny\n"
    assert "All occurrences were successfully replaced" in result


def test_edit_rejects_ipynb(tmp_path):
    tools = _tools(tmp_path)
    file_path = tmp_path / "notebook.ipynb"
    file_path.write_text("{}", encoding="utf-8")

    tools["Read"].invoke({"file_path": str(file_path)})
    result = tools["Edit"].invoke({"file_path": str(file_path), "old_string": "{}", "new_string": "[]"})

    assert "File is a Jupyter Notebook" in result


def test_edit_empty_old_string_creates_missing_file(tmp_path):
    tools = _tools(tmp_path)
    file_path = tmp_path / "new.py"

    result = tools["Edit"].invoke({"file_path": str(file_path), "old_string": "", "new_string": "print('hi')\n"})

    assert file_path.read_text(encoding="utf-8") == "print('hi')\n"
    assert "has been updated successfully" in result
```

- [ ] **Step 2: Run Edit tests to verify they fail**

Run:

```bash
pytest tests/test_claude_edit_tool.py -v
```

Expected: FAIL because `Edit` is still a stub.

- [ ] **Step 3: Add `EditInput`, replacement validation, and `create_edit_tool`**

Append to `src/hagent/file_tools/tools.py`:

```python
class EditInput(BaseModel):
    file_path: str = Field(description="The absolute path to the file to modify")
    old_string: str = Field(description="The text to replace")
    new_string: str = Field(description="The text to replace it with")
    replace_all: bool = Field(default=False, description="Replace all occurrences of old_string")


def _replacement_error(content: str, old_string: str, replace_all: bool) -> str | None:
    matches = content.count(old_string)
    if matches == 0:
        return f"String to replace not found in file.\nString: {old_string}"
    if matches > 1 and not replace_all:
        return (
            f"Found {matches} matches of the string to replace, but replace_all is false. "
            "To replace all occurrences, set replace_all to true. To replace only one occurrence, "
            f"please provide more context to uniquely identify the instance.\nString: {old_string}"
        )
    return None


def create_edit_tool(
    *,
    workspace_root: Path,
    permissions: list[FilesystemPermission],
    state: FileReadState,
) -> StructuredTool:
    def edit_file(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        try:
            full_path = expand_file_path(file_path, workspace_root)
            ensure_allowed(permissions, "write", full_path)
            if old_string == new_string:
                return "No changes to make: old_string and new_string are exactly the same."
            if full_path.suffix == ".ipynb":
                return "File is a Jupyter Notebook. Use the NotebookEdit tool to edit this file."

            if not full_path.exists():
                if old_string == "":
                    write_text_preserving_encoding(full_path, new_string, "utf-8", "LF")
                    timestamp_ms = full_path.stat().st_mtime_ns // 1_000_000
                    state.record_write(full_path, content=new_string, timestamp_ms=timestamp_ms)
                    return f"The file {file_path} has been updated successfully."
                return f"File does not exist. Current working directory: {workspace_root}."

            meta = read_text_metadata(full_path)
            if old_string == "":
                if meta.content.strip() != "":
                    return "Cannot create new file - file already exists."
                write_text_preserving_encoding(full_path, new_string, meta.encoding, meta.line_endings)
                timestamp_ms = full_path.stat().st_mtime_ns // 1_000_000
                state.record_write(full_path, content=new_string, timestamp_ms=timestamp_ms)
                return f"The file {file_path} has been updated successfully."

            stale_error = _assert_fresh_for_existing_file(state, full_path, meta.content, meta.timestamp_ms)
            if stale_error:
                return stale_error

            replacement_error = _replacement_error(meta.content, old_string, replace_all)
            if replacement_error:
                return replacement_error

            updated = meta.content.replace(old_string, new_string) if replace_all else meta.content.replace(old_string, new_string, 1)
            _ = structured_patch(file_path, meta.content, updated)
            write_text_preserving_encoding(full_path, updated, meta.encoding, meta.line_endings)
            timestamp_ms = full_path.stat().st_mtime_ns // 1_000_000
            state.record_write(full_path, content=updated, timestamp_ms=timestamp_ms)
            if replace_all:
                return f"The file {file_path} has been updated. All occurrences were successfully replaced."
            return f"The file {file_path} has been updated successfully."
        except PermissionError as exc:
            return f"Error: {exc}"
        except (OSError, UnicodeDecodeError, UnicodeEncodeError, ValueError) as exc:
            return f"Error: {exc}"

    tool = StructuredTool.from_function(
        name="Edit",
        description="A tool for editing files",
        func=edit_file,
        args_schema=EditInput,
    )
    tool.metadata = {"hagent_file_state": state}
    return tool
```

- [ ] **Step 4: Update the factory to use `create_edit_tool`**

Modify `src/hagent/file_tools/__init__.py` imports:

```python
from hagent.file_tools.tools import create_edit_tool, create_read_tool, create_write_tool
```

Modify `src/hagent/file_tools/__init__.py` so `create_claude_file_tools(...)` returns:

```python
    return [
        create_read_tool(workspace_root=workspace_root, permissions=rules, state=state),
        create_write_tool(workspace_root=workspace_root, permissions=rules, state=state),
        create_edit_tool(workspace_root=workspace_root, permissions=rules, state=state),
    ]
```

- [ ] **Step 5: Run Edit tests**

Run:

```bash
pytest tests/test_claude_edit_tool.py tests/test_claude_write_tool.py tests/test_claude_read_tool.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/hagent/file_tools/__init__.py src/hagent/file_tools/tools.py tests/test_claude_edit_tool.py
git commit -m "feat(file-tools): add claude edit tool"
```

---

### Task 6: Enforce Hagent Default Permissions in the Custom Tools

**Files:**
- Modify: `tests/test_claude_read_tool.py`
- Modify: `tests/test_claude_write_tool.py`
- Modify: `tests/test_claude_edit_tool.py`
- Modify: `src/hagent/file_tools/tools.py`

- [ ] **Step 1: Add permission-denial tests**

Append to `tests/test_claude_write_tool.py`:

```python
from deepagents import FilesystemPermission


def test_write_respects_deny_permission(tmp_path):
    tools = create_claude_file_tools(
        workspace_root=tmp_path,
        permissions=[FilesystemPermission(operations=["write"], paths=[f"{tmp_path.as_posix()}/**"], mode="deny")],
    )
    write = next(tool for tool in tools if tool.name == "Write")

    result = write.invoke({"file_path": str(tmp_path / "blocked.py"), "content": "x\n"})

    assert "permission denied for write" in result
    assert not (tmp_path / "blocked.py").exists()
```

Append to `tests/test_claude_edit_tool.py`:

```python
from deepagents import FilesystemPermission


def test_edit_respects_deny_permission(tmp_path):
    file_path = tmp_path / "blocked.py"
    file_path.write_text("x\n", encoding="utf-8")
    tools = create_claude_file_tools(
        workspace_root=tmp_path,
        permissions=[FilesystemPermission(operations=["write"], paths=[f"{tmp_path.as_posix()}/**"], mode="deny")],
    )
    edit = next(tool for tool in tools if tool.name == "Edit")

    result = edit.invoke({"file_path": str(file_path), "old_string": "x", "new_string": "y"})

    assert "permission denied for write" in result
    assert file_path.read_text(encoding="utf-8") == "x\n"
```

Append to `tests/test_claude_read_tool.py`:

```python
from deepagents import FilesystemPermission


def test_read_respects_deny_permission(tmp_path):
    file_path = tmp_path / "blocked.py"
    file_path.write_text("x\n", encoding="utf-8")
    tools = create_claude_file_tools(
        workspace_root=tmp_path,
        permissions=[FilesystemPermission(operations=["read"], paths=[f"{tmp_path.as_posix()}/**"], mode="deny")],
    )
    read = next(tool for tool in tools if tool.name == "Read")

    result = read.invoke({"file_path": str(file_path)})

    assert "permission denied for read" in result
```

- [ ] **Step 2: Run permission tests**

Run:

```bash
pytest tests/test_claude_read_tool.py::test_read_respects_deny_permission tests/test_claude_write_tool.py::test_write_respects_deny_permission tests/test_claude_edit_tool.py::test_edit_respects_deny_permission -v
```

Expected: PASS because the tool implementations already call `ensure_allowed`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_claude_read_tool.py tests/test_claude_write_tool.py tests/test_claude_edit_tool.py
git commit -m "test(file-tools): cover custom tool permissions"
```

---

### Task 7: Update Prompt Tool Names and Decision Records

**Files:**
- Modify: `prompts/hagent_base.zh.md`
- Modify: `prompts/decisions.md`
- Test: `tests/test_core.py`

- [ ] **Step 1: Add prompt-name regression test**

Append to `tests/test_core.py`:

```python
def test_create_hagent_base_prompt_uses_claude_file_tool_names(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    create_hagent()

    prompt = captured["system_prompt"]
    assert "Read、Edit、Write" in prompt
    assert "read_file、edit_file、write_file" not in prompt
    assert "直接用 Write 工具写入" in prompt
```

- [ ] **Step 2: Run prompt test to verify it fails**

Run:

```bash
pytest tests/test_core.py::test_create_hagent_base_prompt_uses_claude_file_tool_names -v
```

Expected: FAIL because the prompt still names `read_file/edit_file/write_file`.

- [ ] **Step 3: Update base prompt tool names**

Modify `prompts/hagent_base.zh.md`:

```markdown
 - 优先用 Edit 编辑现有文件而不是用 Write 创建新文件。
```

```markdown
 - 当有合适的专用工具时，优先使用专用工具而不是 Bash（Read、Edit、Write）——仅在 shell-only 操作时保留 Bash。
```

```markdown
你拥有一个持久化的、基于文件的记忆系统，位于 `{{working_directory}}/.hagent/memory/`。该目录已经存在——直接用 Write 工具写入它（不要运行 mkdir 或检查它是否存在）。
```

- [ ] **Step 4: Update decision record**

Modify `prompts/decisions.md` so the tool mapping rows state:

```markdown
| # Using your tools | 50-53 | KEEP（含工具名 MODIFY） | §6 表行: "# Using your tools"。工具名映射：Read/Edit/Write 保持 Claude Code 工具名；Bash 保持为 Bash；TaskCreate→write_todos。其他文字完整保留。 |
```

Update the count summary to state:

```markdown
输出文件实际计数：Read=1, Edit=2, Write=3，Bash=2，write_todos=1。无残留 `read_file` / `edit_file` / `write_file` 字样。
```

- [ ] **Step 5: Run prompt validation**

Run:

```bash
pytest tests/test_core.py::test_create_hagent_base_prompt_uses_claude_file_tool_names -v
./scripts/check_base_prompt.sh
```

Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add prompts/hagent_base.zh.md prompts/decisions.md tests/test_core.py
git commit -m "docs(prompt): use claude file tool names"
```

---

### Task 8: Full Verification and Behavior Audit

**Files:**
- Modify only if verification exposes a failing behavior in files already introduced by this plan.

- [ ] **Step 1: Run focused file-tool tests**

Run:

```bash
pytest tests/test_claude_file_tools_registration.py tests/test_claude_file_tool_permissions.py tests/test_claude_read_tool.py tests/test_claude_write_tool.py tests/test_claude_edit_tool.py -v
```

Expected: PASS.

- [ ] **Step 2: Run core and prompt tests**

Run:

```bash
pytest tests/test_core.py -v
./scripts/check_base_prompt.sh
```

Expected: PASS.

- [ ] **Step 3: Run all Python tests**

Run:

```bash
pytest -v
```

Expected: PASS. If failures occur outside the touched files, inspect whether the custom tool registration changed tool-name assumptions before editing.

- [ ] **Step 4: Manual smoke test tool behavior without model calls**

Run:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from hagent.file_tools import create_claude_file_tools

root = Path('/tmp/hagent-file-tool-smoke')
root.mkdir(parents=True, exist_ok=True)
target = root / 'demo.py'
if target.exists():
    target.unlink()
tools = {tool.name: tool for tool in create_claude_file_tools(workspace_root=root, permissions=[])}
print(tools['Write'].invoke({'file_path': str(target), 'content': 'one\\n'}))
print(tools['Read'].invoke({'file_path': str(target)}))
print(tools['Edit'].invoke({'file_path': str(target), 'old_string': 'one', 'new_string': 'two'}))
print(target.read_text())
PY
```

Expected output includes:

```text
File created successfully at:
     1	one
The file /tmp/hagent-file-tool-smoke/demo.py has been updated successfully.
two
```

- [ ] **Step 5: Commit verification fixes**

If verification required code fixes, commit them:

```bash
git add src/hagent/file_tools tests prompts src/hagent/core.py
git commit -m "fix(file-tools): complete claude compatibility verification"
```

If no fixes were needed, do not create an empty commit.

---

## Self-Review

- Spec coverage: The plan covers tool names, exclusion of deepagents built-ins, shared read state, read-before-write/edit, stale-file rejection, create/update write semantics, exact replacement semantics, `replace_all`, `.ipynb` rejection, prompt names, and verification.
- Non-model-visible Claude Code internals: telemetry, feature flags, VSCode notifications, LSP notifications, and remote git diff fetching are intentionally represented as inert extension hooks because Hagent does not currently expose those subsystems. This preserves model-visible behavior and avoids introducing unused platform scaffolding.
- Placeholder scan: no incomplete task and no deferred implementation step.
- Type consistency: `FileReadState`, `ReadSnapshot`, `create_read_tool`, `create_write_tool`, `create_edit_tool`, and `create_claude_file_tools` are named consistently across tasks.
