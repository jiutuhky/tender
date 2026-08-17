"""Tests for the CC-aligned Grep / Glob tools (hagent.grep_tool).

Host-mode behavioral tests plus deterministic ripgrep-argv construction tests.
Behavioral assertions are written to hold whether or not `rg` is installed
(the tool transparently falls back to a pure-Python regex search on the host);
flag construction and rg-only features (-A/-B/-C context) are asserted
separately so they don't depend on a missing binary.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest

from hagent.grep_tool import create_grep_tools
from hagent.grep_tool.runner import build_rg_argv

HAS_RG = shutil.which("rg") is not None


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "a.py").write_text("import os\ndef foo():\n    log_Error('boom')\n")
    (tmp_path / "b.md").write_text("# Title\nfoo bar\nFOO BAR\n")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.py").write_text("foo = 1\n")
    return tmp_path


def _tools(tree: Path):
    return create_grep_tools(workspace_root=tree, sandbox=None, permissions=None)


# ---- Grep behavior ----------------------------------------------------------

def test_grep_files_with_matches_default(tree: Path) -> None:
    grep, _ = _tools(tree)
    out = grep.invoke({"pattern": "foo"})
    assert "a.py" in out and "b.md" in out and "c.py" in out


def test_grep_content_mode_with_line_numbers(tree: Path) -> None:
    grep, _ = _tools(tree)
    out = grep.invoke({"pattern": "foo", "output_mode": "content", "-n": True, "glob": "*.py"})
    assert "a.py:2:def foo():" in out
    assert "b.md" not in out  # filtered out by glob


def test_grep_count_mode_case_insensitive(tree: Path) -> None:
    grep, _ = _tools(tree)
    out = grep.invoke({"pattern": "foo", "output_mode": "count", "-i": True})
    # b.md has "foo bar" + "FOO BAR" => 2 with -i
    lines = {ln.rsplit(":", 1)[0].split("/")[-1]: int(ln.rsplit(":", 1)[1]) for ln in out.splitlines()}
    assert lines["b.md"] == 2


def test_grep_regex_pattern(tree: Path) -> None:
    grep, _ = _tools(tree)
    out = grep.invoke({"pattern": r"log.*Error", "output_mode": "content"})
    assert "log_Error" in out


def test_grep_no_matches(tree: Path) -> None:
    grep, _ = _tools(tree)
    assert grep.invoke({"pattern": "zzznotpresent"}) == "No matches found"


def test_grep_head_limit_truncates(tree: Path) -> None:
    grep, _ = _tools(tree)
    out = grep.invoke({"pattern": "foo", "head_limit": 1})
    body = out.split("\n")
    assert len([l for l in body if l and not l.startswith("…")]) == 1
    assert "truncated" in out


def test_grep_rejects_unknown_param(tree: Path) -> None:
    grep, _ = _tools(tree)
    assert grep.invoke({"pattern": "x", "bogus": 1}).startswith("Error: unexpected parameter")


def test_grep_requires_pattern(tree: Path) -> None:
    grep, _ = _tools(tree)
    assert grep.invoke({"path": "."}).startswith("Error")


def test_grep_permission_denied_returns_error(tree: Path) -> None:
    class DenyRead:
        operations = ("read",)
        paths = ("/etc/*",)
        mode = "deny"

    grep, _ = create_grep_tools(workspace_root=tree, sandbox=None, permissions=[DenyRead()])
    out = grep.invoke({"pattern": "x", "path": "/etc/passwd"})
    assert out.startswith("Error") and "permission denied" in out


def test_grep_recursive_glob_filter(tree: Path) -> None:
    # "**/*.py" must match at any depth (regression: the python fallback used to
    # fnmatch the basename only and never matched a slashed pattern).
    grep, _ = _tools(tree)
    out = grep.invoke({"pattern": "foo", "glob": "**/*.py"})
    assert any(line.endswith("a.py") for line in out.splitlines())
    assert any(line.endswith("sub/c.py") for line in out.splitlines())
    assert "b.md" not in out


def test_grep_multiline_content_returns_spanned_lines(tree: Path) -> None:
    # Pattern spans two lines of a.py: "def foo():" then "    log_Error('boom')".
    grep, _ = _tools(tree)
    out = grep.invoke(
        {"pattern": r"def foo.*Error", "output_mode": "content", "multiline": True}
    )
    assert "def foo():" in out
    assert "log_Error" in out


@pytest.mark.skipif(not HAS_RG, reason="ripgrep not installed; -C context is rg-only")
def test_grep_context_lines_rg_only(tree: Path) -> None:
    grep, _ = _tools(tree)
    out = grep.invoke({"pattern": "def foo", "output_mode": "content", "-C": 1})
    assert "import os" in out  # one line of context before the match


# ---- Glob behavior ----------------------------------------------------------

def test_glob_recursive(tree: Path) -> None:
    _, glob = _tools(tree)
    out = glob.invoke({"pattern": "**/*.py"})
    paths = set(out.splitlines())
    assert any(p.endswith("a.py") for p in paths)
    assert any(p.endswith("sub/c.py") for p in paths)


def test_glob_non_recursive_filter(tree: Path) -> None:
    _, glob = _tools(tree)
    out = glob.invoke({"pattern": "*.md"})
    assert out.endswith("b.md")
    assert "a.py" not in out


def test_glob_sorted_by_mtime_desc(tree: Path) -> None:
    _, glob = _tools(tree)
    # Make sub/c.py the most recently modified.
    time.sleep(0.01)
    (tree / "sub" / "c.py").write_text("foo = 2\n")
    out = glob.invoke({"pattern": "**/*.py"})
    first = out.splitlines()[0]
    assert first.endswith("c.py")


def test_glob_no_files(tree: Path) -> None:
    _, glob = _tools(tree)
    assert glob.invoke({"pattern": "*.rs"}) == "No files found"


def test_glob_rejects_unknown_param(tree: Path) -> None:
    _, glob = _tools(tree)
    assert glob.invoke({"pattern": "*", "bogus": 1}).startswith("Error: unexpected parameter")


# ---- Schema / argv construction ---------------------------------------------

def test_llm_visible_grep_properties_match_cc() -> None:
    from langchain_core.utils.function_calling import convert_to_openai_tool

    grep, glob = create_grep_tools(workspace_root=".", sandbox=None, permissions=None)
    props = list(convert_to_openai_tool(grep)["function"]["parameters"]["properties"].keys())
    assert props == [
        "pattern", "path", "glob", "type", "output_mode",
        "-i", "-n", "-A", "-B", "-C", "multiline", "head_limit",
    ]
    gprops = list(convert_to_openai_tool(glob)["function"]["parameters"]["properties"].keys())
    assert gprops == ["pattern", "path"]


def test_build_rg_argv_files_with_matches() -> None:
    argv = build_rg_argv(
        "foo", path="/w", glob="*.py", type_=None, output_mode="files_with_matches",
        case_insensitive=True, line_numbers=False, after=None, before=None, context=None,
        multiline=False,
    )
    assert argv[0] == "rg" and "-l" in argv and "-i" in argv
    assert "-g" in argv and "*.py" in argv
    assert argv[-1] == "/w"
    assert "-e" in argv and "foo" in argv


def test_build_rg_argv_content_context_and_multiline() -> None:
    argv = build_rg_argv(
        "x", path=None, glob=None, type_="py", output_mode="content",
        case_insensitive=False, line_numbers=True, after=2, before=1, context=None,
        multiline=True,
    )
    assert "-n" in argv
    assert "-A" in argv and "-B" in argv
    assert "-U" in argv and "--multiline-dotall" in argv
    assert "-t" in argv and "py" in argv


def test_build_rg_argv_count_mode() -> None:
    argv = build_rg_argv(
        "x", path=None, glob=None, type_=None, output_mode="count",
        case_insensitive=False, line_numbers=False, after=None, before=None, context=None,
        multiline=False,
    )
    assert "-c" in argv


def test_grep_passes_through_sandbox_unavailable_message(tmp_path: Path) -> None:
    """沙箱通道的契约文案原样透传,不加 "Error:" 前缀(保持模型可识别的 marker 形态)。"""
    from deepagents.backends.protocol import ExecuteResponse

    from hagent.sandbox.errors import SandboxUnavailableReason, execute_error_response

    class PausedSandbox:
        workspace_dir = str(tmp_path)

        def execute(self, command, timeout=None):
            return execute_error_response(SandboxUnavailableReason.PAUSED)

    grep_tool, glob_tool = create_grep_tools(tmp_path, sandbox=PausedSandbox())
    out = grep_tool.invoke({"pattern": "foo"})
    assert out.startswith("[sandbox_unavailable:paused]")
    out2 = glob_tool.invoke({"pattern": "*.md"})
    assert out2.startswith("[sandbox_unavailable:paused]")

    class FailingSandbox(PausedSandbox):
        def execute(self, command, timeout=None):
            return ExecuteResponse(output="rg: bad regex", exit_code=2, truncated=False)

    grep_tool, _ = create_grep_tools(tmp_path, sandbox=FailingSandbox())
    assert grep_tool.invoke({"pattern": "foo"}).startswith("Error: rg: bad regex")
