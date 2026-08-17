"""Claude Code-aligned Grep / Glob tools.

These replace deepagents' built-in lowercase ``grep`` / ``glob`` scaffolding (which
is literal-string, not regex, and is not inherited by hagent's subagents). They are
registered into ``parent_tools`` in ``core.py`` so the main agent AND every subagent
share them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool

from hagent.file_tools.paths import ensure_allowed, expand_file_path
from hagent.grep_tool.prompt import (
    GLOB_TOOL_DESCRIPTION,
    GLOB_TOOL_NAME,
    GREP_TOOL_DESCRIPTION,
    GREP_TOOL_NAME,
)
from hagent.grep_tool.runner import (
    GLOB_SCRIPT,
    GLOB_TIMEOUT_S,
    GREP_TIMEOUT_S,
    CommandExecutor,
    CommandNotFound,
    HostCommandExecutor,
    SandboxCommandExecutor,
    build_rg_argv,
    python_grep_fallback,
)
from hagent.grep_tool.schema import (
    GLOB_ALLOWED_KEYS,
    GLOB_SCHEMA,
    GREP_ALLOWED_KEYS,
    GREP_SCHEMA,
)
from hagent.sandbox.errors import is_infra_message

__all__ = ["create_grep_tools"]


def _render_exec_failure(output: str, fallback: str) -> str:
    """非零退出的呈现:沙箱基础设施契约文案原样透传(不加 "Error:" 前缀,
    保持系统提示词教给模型的 ``[sandbox_unavailable:...]`` 识别形态);其它照旧。"""
    text = output.strip()
    if is_infra_message(text):
        return text
    return f"Error: {text or fallback}"


def _truncate(text: str, head_limit: int | None) -> str:
    if head_limit is None or head_limit <= 0:
        return text
    lines = text.splitlines()
    if len(lines) <= head_limit:
        return text
    kept = lines[:head_limit]
    return "\n".join(kept) + f"\n… (truncated to first {head_limit} of {len(lines)} lines)"


def create_grep_tools(
    workspace_root: str | Path,
    sandbox: Any | None = None,
    permissions: Any | None = None,
) -> list[StructuredTool]:
    """Build the Grep and Glob StructuredTools.

    In sandbox mode ``workspace_root`` is the container-visible path and
    ``permissions`` is None (the container is the trust boundary); commands run
    inside the container via ``sandbox.execute``. In host mode commands run in the
    host workspace and ``permissions`` gates the search path.
    """
    root = Path(workspace_root)
    executor: CommandExecutor
    if sandbox is not None:
        executor = SandboxCommandExecutor(sandbox)
    else:
        executor = HostCommandExecutor(root)

    def _resolve_search_path(raw_path: str | None) -> tuple[str | None, str | None]:
        """Return (path_to_pass_to_command, error). path_to_pass is absolute."""
        if raw_path is None:
            return (str(root), None)
        try:
            resolved = expand_file_path(raw_path, root)
            ensure_allowed(permissions, "read", resolved)
        except (PermissionError, ValueError) as exc:
            return (None, f"Error: {exc}")
        return (str(resolved), None)

    def _grep(**kwargs: Any) -> str:
        unknown = set(kwargs) - GREP_ALLOWED_KEYS
        if unknown:
            return f"Error: unexpected parameter(s): {', '.join(sorted(unknown))}"
        pattern = kwargs.get("pattern")
        if not pattern or not isinstance(pattern, str):
            return "Error: 'pattern' is required"
        output_mode = kwargs.get("output_mode", "files_with_matches")
        if output_mode not in ("content", "files_with_matches", "count"):
            return f"Error: invalid output_mode: {output_mode}"
        head_limit = kwargs.get("head_limit")

        search_path, err = _resolve_search_path(kwargs.get("path"))
        if err:
            return err

        argv = build_rg_argv(
            pattern,
            path=search_path,
            glob=kwargs.get("glob"),
            type_=kwargs.get("type"),
            output_mode=output_mode,
            case_insensitive=bool(kwargs.get("-i", False)),
            line_numbers=bool(kwargs.get("-n", False)),
            after=kwargs.get("-A"),
            before=kwargs.get("-B"),
            context=kwargs.get("-C"),
            multiline=bool(kwargs.get("multiline", False)),
        )
        try:
            result = executor.run_argv(argv, GREP_TIMEOUT_S)
        except CommandNotFound:
            if sandbox is not None:
                return "Error: ripgrep (rg) is not available in the sandbox"
            out, code = python_grep_fallback(
                pattern,
                search_root=Path(search_path) if search_path else root,
                glob=kwargs.get("glob"),
                output_mode=output_mode,
                case_insensitive=bool(kwargs.get("-i", False)),
                line_numbers=bool(kwargs.get("-n", False)),
                multiline=bool(kwargs.get("multiline", False)),
            )
            result_output, result_code = out, code
        else:
            result_output, result_code = result.output, result.exit_code

        if result_code == 1 and not result_output.strip():
            return "No matches found"
        if result_code not in (0, 1):
            return _render_exec_failure(result_output, "grep failed")
        if not result_output.strip():
            return "No matches found"
        return _truncate(result_output.rstrip("\n"), head_limit)

    def _glob(**kwargs: Any) -> str:
        unknown = set(kwargs) - GLOB_ALLOWED_KEYS
        if unknown:
            return f"Error: unexpected parameter(s): {', '.join(sorted(unknown))}"
        pattern = kwargs.get("pattern")
        if not pattern or not isinstance(pattern, str):
            return "Error: 'pattern' is required"

        search_path, err = _resolve_search_path(kwargs.get("path"))
        if err:
            return err

        argv = [executor.python_cmd, "-c", GLOB_SCRIPT, str(search_path), pattern]
        result = executor.run_argv(argv, GLOB_TIMEOUT_S)
        if result.exit_code != 0:
            return _render_exec_failure(result.output, "glob failed")
        if not result.output.strip():
            return "No files found"
        return result.output.rstrip("\n")

    grep_tool = StructuredTool.from_function(
        func=_grep,
        name=GREP_TOOL_NAME,
        description=GREP_TOOL_DESCRIPTION,
        args_schema=GREP_SCHEMA,
    )
    glob_tool = StructuredTool.from_function(
        func=_glob,
        name=GLOB_TOOL_NAME,
        description=GLOB_TOOL_DESCRIPTION,
        args_schema=GLOB_SCHEMA,
    )
    return [grep_tool, glob_tool]
