"""Command parsing metadata for Bash permission checks.

The parser is intentionally encapsulated here so tree-sitter can replace the
fallback without changing the permission API.
"""

from __future__ import annotations

from dataclasses import dataclass
import shlex


_CONTROL_FLOW_WORDS = {
    "case",
    "do",
    "done",
    "elif",
    "else",
    "esac",
    "fi",
    "for",
    "function",
    "if",
    "select",
    "then",
    "until",
    "while",
}
_COMMAND_SEPARATORS = {"&&", "||", ";", "&", "|", "|&"}
_REDIRECT_OPERATORS = {">", ">>", "<", "<<", "<<<", "<>", ">|", "&>", "&>>", ">&"}
_COMPLEX_TOKENS = {"(", ")", "{", "}"}


@dataclass(frozen=True)
class ParsedCommand:
    simple_commands: list[tuple[str, tuple[str, ...]]]
    redirects: tuple[tuple[str, str], ...] = ()
    requires_approval: bool = False
    reason: str | None = None


def parse_bash_command(command: str) -> ParsedCommand:
    """Parse a Bash command into conservative metadata.

    This shlex fallback recognizes common simple and compound commands. Shell
    substitutions, subshells, control flow, and malformed input are treated as
    complex and require approval.
    """

    if "\n" in command or "\r" in command:
        return ParsedCommand(simple_commands=[], requires_approval=True, reason="complex")

    try:
        tokens = _tokenize(command)
    except ValueError:
        return ParsedCommand(simple_commands=[], requires_approval=True, reason="complex")

    if not tokens:
        return ParsedCommand(simple_commands=[])

    if _is_complex(command, tokens):
        return ParsedCommand(simple_commands=[], requires_approval=True, reason="complex")

    simple_commands: list[tuple[str, tuple[str, ...]]] = []
    redirects: list[tuple[str, str]] = []
    current: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        operator = _redirect_operator_at(tokens, index)
        if operator is not None:
            target_index = index + (2 if operator.startswith(tokens[index]) and operator != token else 1)
            if target_index >= len(tokens):
                return ParsedCommand(
                    simple_commands=[],
                    redirects=tuple(redirects),
                    requires_approval=True,
                    reason="complex",
                )
            redirects.append((operator, tokens[target_index]))
            index = target_index + 1
            continue

        if token in _COMMAND_SEPARATORS:
            if not current or index == len(tokens) - 1:
                return ParsedCommand(
                    simple_commands=[],
                    redirects=tuple(redirects),
                    requires_approval=True,
                    reason="complex",
                )
            _append_simple_command(simple_commands, current)
            current = []
            index += 1
            continue

        current.append(token)
        index += 1

    _append_simple_command(simple_commands, current)
    return ParsedCommand(simple_commands=simple_commands, redirects=tuple(redirects))


def _tokenize(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def _is_complex(command: str, tokens: list[str]) -> bool:
    if "$(" in command or "`" in command or "${" in command or "$((" in command:
        return True
    return any(token in _CONTROL_FLOW_WORDS or token in _COMPLEX_TOKENS for token in tokens)


def _redirect_operator_at(tokens: list[str], index: int) -> str | None:
    token = tokens[index]
    if token in _REDIRECT_OPERATORS:
        return token
    if token.isdigit() and index + 1 < len(tokens) and tokens[index + 1] in _REDIRECT_OPERATORS:
        return f"{token}{tokens[index + 1]}"
    return None


def _append_simple_command(
    simple_commands: list[tuple[str, tuple[str, ...]]], parts: list[str]
) -> None:
    if not parts:
        return
    command, *args = parts
    simple_commands.append((command, tuple(args)))
