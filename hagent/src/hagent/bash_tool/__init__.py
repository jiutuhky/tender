"""Claude Code-compatible Bash tool foundation."""

from hagent.bash_tool.output import OutputManager
from hagent.bash_tool.runtime import BashRuntime
from hagent.bash_tool.schema import BashInput, BashResult
from hagent.bash_tool.shell_provider import ShellProvider
from hagent.bash_tool.tasks import TaskRecord, TaskRegistry
from hagent.bash_tool.tool import create_bash_tool

__all__ = [
    "BashInput",
    "BashResult",
    "BashRuntime",
    "OutputManager",
    "ShellProvider",
    "TaskRecord",
    "TaskRegistry",
    "create_bash_tool",
]
