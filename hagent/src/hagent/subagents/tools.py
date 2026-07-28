from __future__ import annotations

from typing import Any, Sequence


def resolve_subagent_tools(
    spec: dict[str, Any],
    parent_tools: Sequence[Any],
) -> tuple[list[Any], list[str]]:
    requested = spec.get("tools")
    disallowed = set(spec.get("disallowed_tools") or [])

    name_to_tool = {t.name: t for t in parent_tools}
    unknown: list[str] = []

    if requested is None or requested == ["*"]:
        resolved = list(parent_tools)
    else:
        resolved = []
        seen: set[str] = set()
        for name in requested:
            if name in name_to_tool and name not in seen:
                resolved.append(name_to_tool[name])
                seen.add(name)
            elif name not in name_to_tool:
                unknown.append(name)

    if disallowed:
        resolved = [t for t in resolved if t.name not in disallowed]

    return resolved, unknown
