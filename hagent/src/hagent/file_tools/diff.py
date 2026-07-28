from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any


_HUNK_HEADER_RE = re.compile(
    r"@@ -(?P<old_start>\d+)(?:,(?P<old_lines>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_lines>\d+))? @@"
)


def structured_patch(
    file_path: str | Path,
    old_content: str,
    new_content: str,
) -> list[dict[str, Any]]:
    diff_lines = list(
        difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=str(file_path),
            tofile=str(file_path),
        )
    )

    hunks: list[dict[str, Any]] = []
    current_hunk: dict[str, Any] | None = None
    for line in diff_lines:
        if line.startswith("--- ") or line.startswith("+++ "):
            continue
        if line.startswith("@@ "):
            match = _HUNK_HEADER_RE.match(line)
            if match is None:
                continue
            current_hunk = {
                "oldStart": int(match.group("old_start")),
                "oldLines": int(match.group("old_lines") or 1),
                "newStart": int(match.group("new_start")),
                "newLines": int(match.group("new_lines") or 1),
                "lines": [],
            }
            hunks.append(current_hunk)
            continue
        if current_hunk is not None:
            current_hunk["lines"].append(line)

    return hunks
