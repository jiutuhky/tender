"""Permission evaluation for Bash commands."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from hagent.bash_tool.parser import ParsedCommand, parse_bash_command


_SAFE_COMMANDS = {"pwd", "ls", "rg", "grep", "find", "cat", "head", "tail", "wc", "stat", "file"}
_PRIVILEGE_COMMANDS = {"sudo", "su", "doas", "pkexec"}
_CRITICAL_PATHS = {"/", "/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/lib64", "/proc", "/root", "/sbin", "/sys", "/usr", "/var"}


@dataclass(frozen=True)
class BashPermissionConfig:
    allow_rules: tuple[str, ...] = ()
    ask_rules: tuple[str, ...] = ()
    deny_rules: tuple[str, ...] = ()
    workspace_root: Path | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "allow_rules", tuple(self.allow_rules))
        object.__setattr__(self, "ask_rules", tuple(self.ask_rules))
        object.__setattr__(self, "deny_rules", tuple(self.deny_rules))
        if self.workspace_root is not None:
            object.__setattr__(self, "workspace_root", Path(self.workspace_root).resolve())


@dataclass(frozen=True)
class BashPermissionDecision:
    action: str
    reason: str


def evaluate_bash_permission(
    command: str, config: BashPermissionConfig | None = None
) -> BashPermissionDecision:
    config = config or BashPermissionConfig()
    normalized = _normalize_command(command)
    parsed = parse_bash_command(command)

    if _matches_any(normalized, config.deny_rules):
        return BashPermissionDecision("deny", "matched deny rule")
    if _matches_any(normalized, config.ask_rules):
        return BashPermissionDecision("ask", "matched ask rule")
    if parsed.requires_approval:
        if _contains_recursive_removal_text(normalized):
            return BashPermissionDecision("ask", "recursive removal requires approval")
        return BashPermissionDecision("allow", "bypass permissions mode")
    if _uses_privilege_wrapper(parsed):
        return BashPermissionDecision("deny", "privilege escalation is denied")
    if _is_critical_removal(parsed):
        return BashPermissionDecision("deny", "critical-path deletion is denied")
    if _is_recursive_removal(parsed):
        return BashPermissionDecision("ask", "recursive removal requires approval")
    if _is_destructive_find_operation(parsed):
        return BashPermissionDecision("ask", "destructive find operation requires approval")
    if _is_safe_read_only(parsed):
        return BashPermissionDecision("allow", "safe read-only command")
    if _matches_any(normalized, config.allow_rules) and _is_single_simple_command(parsed):
        return BashPermissionDecision("allow", "matched allow rule")
    return BashPermissionDecision("allow", "bypass permissions mode")


def _normalize_command(command: str) -> str:
    return " ".join(command.strip().split())


def _matches_any(command: str, rules: tuple[str, ...]) -> bool:
    return any(_matches_rule(command, rule) for rule in rules)


def _matches_rule(command: str, rule: str) -> bool:
    pattern = _extract_rule_pattern(rule)
    if pattern is None:
        return False
    if pattern.endswith(":*"):
        prefix = pattern[:-2]
        return command == prefix or command.startswith(f"{prefix} ")
    if "*" in pattern:
        return fnmatchcase(command, pattern)
    return command == pattern


def _extract_rule_pattern(rule: str) -> str | None:
    rule = rule.strip()
    if not rule.startswith("Bash(") or not rule.endswith(")"):
        return None
    return rule[len("Bash(") : -1].strip()


def _uses_privilege_wrapper(parsed: ParsedCommand) -> bool:
    return any(command in _PRIVILEGE_COMMANDS for command, _ in parsed.simple_commands)


def _is_critical_removal(parsed: ParsedCommand) -> bool:
    for command, args in parsed.simple_commands:
        if command != "rm":
            continue
        if any(arg in {"-rf", "-fr", "-r", "-R"} for arg in args):
            targets = [arg for arg in args if not arg.startswith("-")]
            if any(_is_critical_path(target) for target in targets):
                return True
    return False


def _is_critical_path(target: str) -> bool:
    try:
        path = Path(target).expanduser()
    except RuntimeError:
        return False
    return path.is_absolute() and str(path) in _CRITICAL_PATHS


def _is_safe_read_only(parsed: ParsedCommand) -> bool:
    if not parsed.simple_commands or parsed.redirects:
        return False
    return all(_is_safe_simple_command(command, args) for command, args in parsed.simple_commands)


def _is_single_simple_command(parsed: ParsedCommand) -> bool:
    return len(parsed.simple_commands) == 1 and not parsed.redirects


def _is_safe_simple_command(command: str, args: tuple[str, ...]) -> bool:
    if command == "git":
        if not args or args[0] not in {"status", "diff"}:
            return False
        if args[0] == "diff":
            return not any(_is_git_diff_write_option(arg) for arg in args[1:])
        return True
    if command == "find":
        return not any(_is_find_write_option(arg) for arg in args)
    if command == "rg":
        return not any(_is_rg_unsafe_option(arg) for arg in args)
    return command in _SAFE_COMMANDS


def _is_git_diff_write_option(arg: str) -> bool:
    return arg == "--output" or arg.startswith("--output=")


def _is_find_write_option(arg: str) -> bool:
    return arg in {"-delete", "-exec", "-execdir", "-fls", "-ok", "-okdir"} or arg.startswith("-fprint")


def _is_rg_unsafe_option(arg: str) -> bool:
    return arg == "--pre" or arg.startswith("--pre=")


def _is_recursive_removal(parsed: ParsedCommand) -> bool:
    return any(command == "rm" and _rm_args_include_recursive(args) for command, args in parsed.simple_commands)


def _rm_args_include_recursive(args: tuple[str, ...]) -> bool:
    return any(_rm_arg_is_recursive(arg) for arg in args)


def _rm_arg_is_recursive(arg: str) -> bool:
    return arg == "--recursive" or (arg.startswith("-") and not arg.startswith("--") and any(flag in arg for flag in ("r", "R")))


def _contains_recursive_removal_text(command: str) -> bool:
    parts = command.replace("\r", " ").replace("\n", " ").split()
    for index, part in enumerate(parts):
        if part != "rm":
            continue
        for arg in parts[index + 1 :]:
            if arg in {"&&", "||", ";", "|", "|&", "&"}:
                break
            if _rm_arg_is_recursive(arg):
                return True
    return False


def _is_destructive_find_operation(parsed: ParsedCommand) -> bool:
    return any(command == "find" and "-delete" in args for command, args in parsed.simple_commands)
