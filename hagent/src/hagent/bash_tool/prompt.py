"""Prompt constants for the Bash tool."""

TOOL_NAME = "Bash"

BASH_TOOL_DESCRIPTION = (
    "Executes a given bash command and returns its output. The working directory "
    "persists between commands, but shell state does not."
)

BASH_TOOL_PARAMETERS = """
Parameters:
- command: command to execute.
- timeout: optional timeout in milliseconds; max is read from Hagent timeout config.
- description: clear, concise active-voice description of what the command does.
- run_in_background: run in background when immediate result is not needed.
- dangerouslyDisableSandbox: compatibility field; does not bypass Hagent permission checks in local-host mode.
""".strip()
