"""Execution layer for the Grep / Glob tools.

Grep/Glob run real commands (`rg` for content search, `python3` for glob) rather
than going through ``FileTransport`` (which only does read/write/exists). The
``CommandExecutor`` abstraction routes those commands to the right place:

- host mode  -> ``subprocess.run`` in the workspace directory
- sandbox mode -> ``sandbox.execute`` inside the container

This mirrors the host/sandbox branch the file API router already uses
(``server/routers/files.py`` -> ``sandbox.execute``).
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

GREP_TIMEOUT_S = 30
GLOB_TIMEOUT_S = 30


class CommandNotFound(RuntimeError):
    """Raised by the host executor when the requested binary is not on PATH."""


@dataclass(frozen=True)
class ExecResult:
    output: str  # combined stdout + stderr (matches sandbox ExecuteResponse.output)
    exit_code: int


class CommandExecutor(Protocol):
    """Runs an argv in the workspace and returns combined output + exit code."""

    @property
    def python_cmd(self) -> str: ...

    def run_argv(self, argv: list[str], timeout_s: int) -> ExecResult: ...


class HostCommandExecutor:
    """Runs commands on the host, in ``workspace_root``."""

    def __init__(self, workspace_root: str | Path) -> None:
        self._cwd = str(Path(workspace_root))

    @property
    def python_cmd(self) -> str:
        # Prefer the running interpreter so a venv without `python3` on PATH works.
        return sys.executable or "python3"

    def run_argv(self, argv: list[str], timeout_s: int) -> ExecResult:
        try:
            proc = subprocess.run(
                argv,
                cwd=self._cwd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except FileNotFoundError as exc:
            raise CommandNotFound(argv[0]) from exc
        except subprocess.TimeoutExpired:
            return ExecResult(output=f"Error: command timed out after {timeout_s}s", exit_code=124)
        return ExecResult(output=(proc.stdout or "") + (proc.stderr or ""), exit_code=proc.returncode)


class SandboxCommandExecutor:
    """Runs commands inside a sandbox container via ``sandbox.execute``."""

    def __init__(self, sandbox: Any) -> None:
        self._sandbox = sandbox

    @property
    def python_cmd(self) -> str:
        return "python3"  # provided by the hagent-base image (python:3.12-slim)

    def run_argv(self, argv: list[str], timeout_s: int) -> ExecResult:
        command = shlex.join(argv)
        resp = self._sandbox.execute(command, timeout=timeout_s)
        exit_code = resp.exit_code if resp.exit_code is not None else -1
        return ExecResult(output=resp.output or "", exit_code=exit_code)


def build_rg_argv(
    pattern: str,
    *,
    path: str | None,
    glob: str | None,
    type_: str | None,
    output_mode: str,
    case_insensitive: bool,
    line_numbers: bool,
    after: int | None,
    before: int | None,
    context: int | None,
    multiline: bool,
) -> list[str]:
    """Build a ripgrep argv from CC-aligned Grep parameters."""
    argv = ["rg", "--color=never"]

    if output_mode == "files_with_matches":
        argv.append("-l")
    elif output_mode == "count":
        argv.append("-c")
    else:  # content
        if line_numbers:
            argv.append("-n")
        if context is not None:
            argv += ["-C", str(context)]
        else:
            if after is not None:
                argv += ["-A", str(after)]
            if before is not None:
                argv += ["-B", str(before)]

    if case_insensitive:
        argv.append("-i")
    if multiline:
        argv += ["-U", "--multiline-dotall"]
    if glob:
        argv += ["-g", glob]
    if type_:
        argv += ["-t", type_]

    argv += ["-e", pattern]
    if path:
        argv.append(path)
    return argv


# ---- Python fallback (host only, when ripgrep is not installed) -------------

def python_grep_fallback(
    pattern: str,
    *,
    search_root: Path,
    glob: str | None,
    output_mode: str,
    case_insensitive: bool,
    line_numbers: bool,
    multiline: bool,
) -> tuple[str, int]:
    """A pure-Python regex search used when `rg` is unavailable on the host.

    Returns (output, exit_code) using the same exit-code convention as rg:
    0 = matches found, 1 = no matches, 2 = error.
    """
    import bisect
    import fnmatch
    import os
    import re

    flags = 0
    if case_insensitive:
        flags |= re.IGNORECASE
    if multiline:
        flags |= re.DOTALL
    try:
        regex = re.compile(pattern, flags)
    except re.error as exc:
        return (f"regex error: {exc}", 2)

    def _glob_match(name: str, rel_posix: str) -> bool:
        # Approximate ripgrep's `-g` (gitignore-style) glob in pure Python:
        # a pattern without `/` matches the basename at any depth; a leading
        # `**/` means "any number of directories"; otherwise match the path.
        if not glob:
            return True
        g = glob[3:] if glob.startswith("**/") else glob
        if "/" in g:
            return fnmatch.fnmatch(rel_posix, glob) or fnmatch.fnmatch(rel_posix, g)
        return fnmatch.fnmatch(name, g)

    files: list[Path] = []
    if search_root.is_file():
        files = [search_root]
    else:
        for dirpath, _dirs, filenames in os.walk(search_root):
            for name in filenames:
                fp = Path(dirpath) / name
                try:
                    rel_posix = fp.relative_to(search_root).as_posix()
                except ValueError:
                    rel_posix = name
                if not _glob_match(name, rel_posix):
                    continue
                files.append(fp)

    def _line_starts(text: str) -> list[int]:
        starts = [0]
        for i, ch in enumerate(text):
            if ch == "\n":
                starts.append(i + 1)
        return starts

    content_lines: list[str] = []
    file_matches: dict[str, int] = {}
    for fp in files:
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if multiline:
            matches = list(regex.finditer(text))
            if not matches:
                continue
            file_matches[str(fp)] = len(matches)
            if output_mode == "content":
                lines = text.splitlines()
                starts = _line_starts(text)
                emitted: set[int] = set()
                for m in matches:
                    # Emit every line spanned by the match (1-indexed).
                    lo = bisect.bisect_right(starts, m.start()) - 1
                    hi = bisect.bisect_right(starts, max(m.end() - 1, m.start())) - 1
                    for ln in range(lo, hi + 1):
                        if ln in emitted or ln >= len(lines):
                            continue
                        emitted.add(ln)
                        body = lines[ln]
                        content_lines.append(f"{fp}:{ln + 1}:{body}" if line_numbers else f"{fp}:{body}")
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                file_matches[str(fp)] = file_matches.get(str(fp), 0) + 1
                if output_mode == "content":
                    content_lines.append(f"{fp}:{i}:{line}" if line_numbers else f"{fp}:{line}")

    if not file_matches:
        return ("", 1)

    if output_mode == "files_with_matches":
        return ("\n".join(sorted(file_matches)), 0)
    if output_mode == "count":
        return ("\n".join(f"{p}:{c}" for p, c in sorted(file_matches.items())), 0)
    return ("\n".join(content_lines), 0)


# ---- Glob script (runs in host or sandbox via the executor) -----------------

GLOB_SCRIPT = r"""
import sys
from pathlib import Path

root = Path(sys.argv[1])
pattern = sys.argv[2]
matches = []
try:
    for p in root.glob(pattern):
        if p.is_file():
            try:
                mtime = p.stat().st_mtime
            except OSError:
                mtime = 0.0
            matches.append((mtime, str(p)))
except (ValueError, OSError) as exc:
    sys.stderr.write("glob error: %s" % exc)
    sys.exit(2)
matches.sort(key=lambda x: x[0], reverse=True)
for _, path in matches:
    print(path)
"""
