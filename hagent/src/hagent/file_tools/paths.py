from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Iterable


def _rule_operations(rule: Any) -> tuple[str, ...]:
    operations = getattr(rule, "operations", None)
    if operations is not None:
        return tuple(operations)

    command = getattr(rule, "command", None)
    if command is None:
        return ()
    if isinstance(command, str):
        return (command,)
    return tuple(command)


def _rule_paths(rule: Any) -> tuple[str, ...]:
    paths = getattr(rule, "paths", None)
    if paths is not None:
        return tuple(paths)

    pattern = getattr(rule, "pattern", None)
    if pattern is None:
        return ()
    if isinstance(pattern, str):
        return (pattern,)
    return tuple(pattern)


def expand_file_path(file_path: str | Path, workspace_root: str | Path) -> Path:
    path_text = str(file_path)
    if path_text.startswith("~"):
        raise ValueError("home-relative paths are not supported")

    path = Path(file_path)
    if not path.is_absolute():
        path = Path(workspace_root) / path
    return path.resolve()


def check_permission(
    rules: Iterable[Any] | None,
    operation: str,
    file_path: str | Path,
) -> str:
    if rules is None:
        return "allow"

    path_text = str(Path(file_path))
    for rule in rules:
        operations = _rule_operations(rule)
        paths = _rule_paths(rule)
        if operation not in operations:
            continue
        if any(fnmatch(path_text, pattern) for pattern in paths):
            return str(getattr(rule, "mode", "allow"))
    return "allow"


def ensure_allowed(
    rules: Iterable[Any] | None,
    operation: str,
    file_path: str | Path,
) -> None:
    mode = check_permission(rules, operation, file_path)
    if mode != "allow":
        raise PermissionError(f"permission denied for {operation}: {file_path}")
