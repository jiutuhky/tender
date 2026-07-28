"""LangChain tool adapter for the Hagent Bash runtime."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from langchain_core.tools import StructuredTool

from hagent.bash_tool.permissions import BashPermissionConfig, evaluate_bash_permission
from hagent.bash_tool.prompt import BASH_TOOL_DESCRIPTION, BASH_TOOL_PARAMETERS, TOOL_NAME
from hagent.bash_tool.runtime import BashRuntime
from hagent.bash_tool.schema import BashInput, BashResult


def create_bash_tool(
    *,
    workspace_root: Path,
    runtime: BashRuntime | None = None,
    permissions: BashPermissionConfig | None = None,
) -> StructuredTool:
    bash_runtime = runtime or BashRuntime(workspace_root)
    if permissions is None:
        permission_config = BashPermissionConfig(workspace_root=workspace_root)
    elif permissions.workspace_root is None:
        permission_config = replace(permissions, workspace_root=workspace_root)
    else:
        permission_config = permissions

    def _run_bash(
        command: str,
        timeout: int | None = None,
        description: str | None = None,
        run_in_background: bool | None = None,
        dangerouslyDisableSandbox: bool | None = None,
    ) -> str:
        decision = evaluate_bash_permission(command, permission_config)
        if decision.action != "allow":
            return f"Bash permission {decision.action}: {decision.reason}"

        result = bash_runtime.execute(
            command,
            timeout_ms=timeout,
            run_in_background=bool(run_in_background),
            description=description,
        )
        return format_bash_result(result)

    return StructuredTool.from_function(
        func=_run_bash,
        name=TOOL_NAME,
        description=f"{BASH_TOOL_DESCRIPTION}\n\n{BASH_TOOL_PARAMETERS}",
        args_schema=BashInput,
    )


def format_bash_result(result: BashResult) -> str:
    parts: list[str] = []
    if result.background_task_id:
        parts.append(f"Background task: {result.background_task_id}")
    if result.stdout:
        parts.append(result.stdout)
    if result.stderr:
        parts.append(result.stderr)
    if result.persisted_output_path:
        parts.append(f"Full output: {result.persisted_output_path}")
    if result.exit_code is not None and result.exit_code != 0:
        parts.append(f"Exit code: {result.exit_code}")
    if result.no_output_expected and not parts:
        return "<no output>"
    return "\n".join(part.rstrip("\n") for part in parts if part) or "<no output>"
