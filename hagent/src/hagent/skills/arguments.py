from __future__ import annotations

import re
import shlex
from collections.abc import Sequence


def parse_arguments(args: str | None) -> list[str]:
    if args is None or not args.strip():
        return []
    try:
        return shlex.split(args, posix=True)
    except ValueError:
        return [part for part in re.split(r"\s+", args.strip()) if part]


def parse_argument_names(argument_names: str | Sequence[str] | None) -> list[str]:
    if argument_names is None:
        return []
    values = argument_names.split() if isinstance(argument_names, str) else list(argument_names)
    result: list[str] = []
    for value in values:
        name = str(value).strip()
        if name and not name.isdigit():
            result.append(name)
    return result


def substitute_arguments(
    content: str,
    args: str | None = None,
    *,
    append_if_no_placeholder: bool = True,
    argument_names: Sequence[str] = (),
) -> str:
    if args is None:
        return content

    parsed_args = parse_arguments(args)
    original = content
    substituted = False

    for index, name in enumerate(argument_names):
        pattern = rf"\${re.escape(name)}(?![\[\w])"

        def _replace_named(match: re.Match[str]) -> str:
            nonlocal substituted
            substituted = True
            return parsed_args[index] if index < len(parsed_args) else ""

        content, count = re.subn(pattern, _replace_named, content)
        substituted = substituted or count > 0

    def _replace_indexed(match: re.Match[str]) -> str:
        nonlocal substituted
        substituted = True
        position = int(match.group(1))
        return parsed_args[position] if position < len(parsed_args) else ""

    content, count = re.subn(r"\$ARGUMENTS\[(\d+)\]", _replace_indexed, content)
    substituted = substituted or count > 0
    content, count = re.subn(r"\$(\d+)(?!\w)", _replace_indexed, content)
    substituted = substituted or count > 0

    if "$ARGUMENTS" in content:
        substituted = True
        content = content.replace("$ARGUMENTS", args)

    if append_if_no_placeholder and not substituted and args:
        return f"{original}\n\nARGUMENTS: {args}"
    return content
