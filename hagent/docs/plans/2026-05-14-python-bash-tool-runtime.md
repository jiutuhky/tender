# Python Bash Tool Runtime Implementation Plan

> **存档说明**：本 plan 产出自已退役的 superpowers 工作流，仅作历史参考；新工作一律走仓根 tickets.md（Matt 契约）。

**Goal:** Build a Python implementation of Claude Code-style `Bash` as Hagent's primary shell tool, then hide Deep Agents' native `execute` from the model-visible tool list.

**Architecture:** Add a focused `hagent.bash_tool` package with schema, prompt, parser, permissions, shell provider, runtime, task registry, output store, and LangChain tool adapter. Integrate it in `create_hagent()` by injecting `Bash` and filtering `execute`, while keeping the existing backend `execute()` as compatibility code until a later cleanup.

**Tech Stack:** Python 3.11+, Pydantic, LangChain `StructuredTool`, `tree-sitter`, `tree-sitter-bash`, pytest, POSIX `bash`/`zsh`, `subprocess.Popen`, process groups.

---

## File Structure

Create:

- `src/hagent/bash_tool/__init__.py` — public exports for the Bash tool package.
- `src/hagent/bash_tool/schema.py` — Pydantic input/result/progress models and timeout/output-limit env parsing.
- `src/hagent/bash_tool/prompt.py` — model-facing `Bash` tool name and description.
- `src/hagent/bash_tool/parser.py` — `tree-sitter-bash` parser wrapper and conservative command analysis.
- `src/hagent/bash_tool/permissions.py` — permission rule parser, matcher, and default policy.
- `src/hagent/bash_tool/output.py` — output file allocation, inline preview, persisted result metadata.
- `src/hagent/bash_tool/tasks.py` — process-local background task registry.
- `src/hagent/bash_tool/shell_provider.py` — shell discovery, snapshot, quoting, command wrapping.
- `src/hagent/bash_tool/runtime.py` — foreground/background command execution runtime.
- `src/hagent/bash_tool/tool.py` — LangChain `StructuredTool` factory.
- `tests/bash_tool/__init__.py`
- `tests/bash_tool/test_schema.py`
- `tests/bash_tool/test_parser.py`
- `tests/bash_tool/test_permissions.py`
- `tests/bash_tool/test_output_tasks.py`
- `tests/bash_tool/test_shell_provider.py`
- `tests/bash_tool/test_runtime.py`
- `tests/bash_tool/test_tool.py`

Modify:

- `pyproject.toml` — add `pydantic`, `tree-sitter`, `tree-sitter-bash`.
- `src/hagent/config.py` — add `BashPermissionConfig` and include it in `HagentConfig`.
- `src/hagent/core.py` — create runtime/registry, inject `Bash`, filter native `execute`.
- `src/hagent/subagents.py` — replace model instruction references from `execute` to `Bash`.
- `prompts/hagent_base.zh.md` — replace shell instructions from `execute` to `Bash`.
- `prompts/decisions.md` — record the prompt wording change.
- `src/hagent/server/sse.py` — pass `Bash` tool call chunks and optional progress metadata through existing event paths.
- `tests/test_config.py` — test bash config defaults/env.
- `tests/test_core.py` — test `Bash` injection and `execute` filtering.
- `tests/test_subagents.py` — test subagent prompt no longer mentions execute.
- `tests/server/test_sse_adapter.py` — test `Bash` tool chunk behavior.

Implementation order is TDD-first: each task writes failing tests, runs them, implements the minimum, reruns focused tests, then commits.

---

### Task 1: Dependencies, Config, Schema, Prompt

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/hagent/config.py`
- Create: `src/hagent/bash_tool/__init__.py`
- Create: `src/hagent/bash_tool/schema.py`
- Create: `src/hagent/bash_tool/prompt.py`
- Test: `tests/bash_tool/test_schema.py`
- Modify test: `tests/test_config.py`

- [ ] **Step 1: Write failing schema tests**

Create `tests/bash_tool/test_schema.py`:

```python
import os

import pytest

from hagent.bash_tool.schema import (
    BashInput,
    BashResult,
    get_default_timeout_ms,
    get_max_output_length,
    get_max_timeout_ms,
)


def test_bash_input_accepts_claude_code_fields():
    data = BashInput(
        command="pytest -q",
        timeout=300000,
        description="Run Python tests",
        run_in_background=True,
        dangerouslyDisableSandbox=False,
    )

    assert data.command == "pytest -q"
    assert data.timeout == 300000
    assert data.description == "Run Python tests"
    assert data.run_in_background is True
    assert data.dangerouslyDisableSandbox is False


def test_bash_input_rejects_empty_command():
    with pytest.raises(ValueError, match="command must be a non-empty string"):
        BashInput(command="  ")


def test_timeout_env_defaults(monkeypatch):
    monkeypatch.delenv("BASH_DEFAULT_TIMEOUT_MS", raising=False)
    monkeypatch.delenv("BASH_MAX_TIMEOUT_MS", raising=False)
    monkeypatch.delenv("BASH_MAX_OUTPUT_LENGTH", raising=False)

    assert get_default_timeout_ms() == 120_000
    assert get_max_timeout_ms() == 600_000
    assert get_max_output_length() == 30_000


def test_timeout_env_overrides(monkeypatch):
    monkeypatch.setenv("BASH_DEFAULT_TIMEOUT_MS", "1500")
    monkeypatch.setenv("BASH_MAX_TIMEOUT_MS", "5000")
    monkeypatch.setenv("BASH_MAX_OUTPUT_LENGTH", "4096")

    assert get_default_timeout_ms() == 1500
    assert get_max_timeout_ms() == 5000
    assert get_max_output_length() == 4096


def test_max_timeout_is_at_least_default(monkeypatch):
    monkeypatch.setenv("BASH_DEFAULT_TIMEOUT_MS", "9000")
    monkeypatch.setenv("BASH_MAX_TIMEOUT_MS", "1000")

    assert get_max_timeout_ms() == 9000


def test_bash_result_defaults():
    result = BashResult(stdout="ok\n", exit_code=0)

    assert result.stdout == "ok\n"
    assert result.stderr == ""
    assert result.exit_code == 0
    assert result.interrupted is False
    assert result.truncated is False
    assert result.no_output_expected is False
```

- [ ] **Step 2: Write failing config tests**

Append to `tests/test_config.py`:

```python
from hagent.config import BashPermissionConfig, HagentConfig


def test_hagent_config_has_bash_permission_config(monkeypatch):
    monkeypatch.delenv("HAGENT_BASH_ALLOW", raising=False)
    monkeypatch.delenv("HAGENT_BASH_DENY", raising=False)
    monkeypatch.delenv("HAGENT_BASH_ASK", raising=False)

    cfg = HagentConfig.from_env()

    assert isinstance(cfg.bash_permissions, BashPermissionConfig)
    assert cfg.bash_permissions.allow_rules == ()
    assert cfg.bash_permissions.deny_rules == ()
    assert cfg.bash_permissions.ask_rules == ()


def test_bash_permission_config_reads_comma_separated_env(monkeypatch):
    monkeypatch.setenv("HAGENT_BASH_ALLOW", "Bash(pytest:*), Bash(git status)")
    monkeypatch.setenv("HAGENT_BASH_DENY", "Bash(rm *)")
    monkeypatch.setenv("HAGENT_BASH_ASK", "Bash(curl:*)")

    cfg = HagentConfig.from_env()

    assert cfg.bash_permissions.allow_rules == ("Bash(pytest:*)", "Bash(git status)")
    assert cfg.bash_permissions.deny_rules == ("Bash(rm *)",)
    assert cfg.bash_permissions.ask_rules == ("Bash(curl:*)",)
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_schema.py tests/test_config.py::test_hagent_config_has_bash_permission_config tests/test_config.py::test_bash_permission_config_reads_comma_separated_env -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hagent.bash_tool'` or `ImportError: cannot import name 'BashPermissionConfig'`.

- [ ] **Step 4: Add dependencies**

Modify `pyproject.toml` dependencies to include:

```toml
dependencies = [
    "deepagents>=0.5.4",
    "langchain-anthropic>=0.3",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "python-multipart>=0.0.20",
    "python-dotenv>=1.0",
    "langgraph-checkpoint-sqlite>=2.0",
    "pydantic>=2.0",
    "tree-sitter>=0.24",
    "tree-sitter-bash>=0.23",
]
```

- [ ] **Step 5: Create package exports**

Create `src/hagent/bash_tool/__init__.py`:

```python
from hagent.bash_tool.schema import BashInput, BashProgress, BashResult

__all__ = ["BashInput", "BashProgress", "BashResult"]
```

- [ ] **Step 6: Implement schema**

Create `src/hagent/bash_tool/schema.py`:

```python
from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_TIMEOUT_MS = 120_000
MAX_TIMEOUT_MS = 600_000
BASH_MAX_OUTPUT_DEFAULT = 30_000
BASH_MAX_OUTPUT_UPPER_LIMIT = 150_000


def _positive_int_env(name: str, default: int, *, upper_limit: int | None = None) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value <= 0:
        return default
    if upper_limit is not None:
        return min(value, upper_limit)
    return value


def get_default_timeout_ms() -> int:
    return _positive_int_env("BASH_DEFAULT_TIMEOUT_MS", DEFAULT_TIMEOUT_MS)


def get_max_timeout_ms() -> int:
    configured = _positive_int_env("BASH_MAX_TIMEOUT_MS", MAX_TIMEOUT_MS)
    return max(configured, get_default_timeout_ms())


def get_max_output_length() -> int:
    return _positive_int_env(
        "BASH_MAX_OUTPUT_LENGTH",
        BASH_MAX_OUTPUT_DEFAULT,
        upper_limit=BASH_MAX_OUTPUT_UPPER_LIMIT,
    )


class BashInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: str = Field(description="The command to execute")
    timeout: int | None = Field(default=None, description="Optional timeout in milliseconds")
    description: str | None = Field(default=None, description="Clear, concise description of what this command does")
    run_in_background: bool | None = Field(default=None, description="Run this command in the background")
    dangerouslyDisableSandbox: bool | None = Field(default=None, description="Compatibility flag; does not bypass local permissions")

    @field_validator("command")
    @classmethod
    def _command_is_non_empty(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            msg = "command must be a non-empty string"
            raise ValueError(msg)
        return value

    @field_validator("timeout")
    @classmethod
    def _timeout_is_positive_and_bounded(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value <= 0:
            msg = "timeout must be positive"
            raise ValueError(msg)
        max_timeout = get_max_timeout_ms()
        if value > max_timeout:
            msg = f"timeout {value}ms exceeds maximum allowed ({max_timeout}ms)"
            raise ValueError(msg)
        return value


class BashProgress(BaseModel):
    type: str = "bash_progress"
    output: str = ""
    full_output: str = ""
    elapsed_time_seconds: int = 0
    total_lines: int = 0
    total_bytes: int = 0
    task_id: str | None = None
    timeout_ms: int | None = None


class BashResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    interrupted: bool = False
    background_task_id: str | None = None
    backgrounded_by_user: bool | None = None
    assistant_auto_backgrounded: bool | None = None
    return_code_interpretation: str | None = None
    no_output_expected: bool = False
    persisted_output_path: str | None = None
    persisted_output_size: int | None = None
    truncated: bool = False

    def to_tool_text(self) -> str:
        parts: list[str] = []
        if self.stdout:
            parts.append(self.stdout.rstrip())
        if self.stderr:
            parts.append(self.stderr.rstrip())
        if self.background_task_id:
            parts.append(f"Command running in background with ID: {self.background_task_id}")
        if self.persisted_output_path:
            parts.append(f"Full output is stored at: {self.persisted_output_path}")
        if self.exit_code is not None and self.exit_code != 0:
            parts.append(f"Exit code: {self.exit_code}")
        if self.truncated:
            parts.append("Output was truncated due to size limits.")
        return "\n".join(part for part in parts if part) or ("Done" if self.no_output_expected else "<no output>")

    def to_progress_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)
```

- [ ] **Step 7: Implement prompt constants**

Create `src/hagent/bash_tool/prompt.py`:

```python
BASH_TOOL_NAME = "Bash"

BASH_TOOL_DESCRIPTION = """Executes a shell command.

Before executing, describe what the command does using the description parameter.
Use run_in_background when the command can continue without blocking the current response.
Use dedicated file tools for reading and searching files when possible; avoid cat, find, and grep for ordinary code exploration.
Timeouts are in milliseconds.
"""
```

- [ ] **Step 8: Add bash config**

Modify `src/hagent/config.py` by adding this helper and dataclass before `HagentConfig`:

```python
def _split_csv_env(name: str) -> tuple[str, ...]:
    raw = os.environ.get(name, "")
    return tuple(part.strip() for part in raw.split(",") if part.strip())


@dataclass(frozen=True)
class BashPermissionConfig:
    allow_rules: tuple[str, ...] = ()
    deny_rules: tuple[str, ...] = ()
    ask_rules: tuple[str, ...] = ()

    @classmethod
    def from_env(cls) -> "BashPermissionConfig":
        return cls(
            allow_rules=_split_csv_env("HAGENT_BASH_ALLOW"),
            deny_rules=_split_csv_env("HAGENT_BASH_DENY"),
            ask_rules=_split_csv_env("HAGENT_BASH_ASK"),
        )
```

Then replace `HagentConfig` with:

```python
@dataclass(frozen=True)
class HagentConfig:
    model: str
    langsmith_tracing: bool
    bash_permissions: BashPermissionConfig

    @classmethod
    def from_env(cls) -> "HagentConfig":
        return cls(
            model=os.environ.get("HAGENT_MODEL", DEFAULT_MODEL),
            langsmith_tracing=os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true",
            bash_permissions=BashPermissionConfig.from_env(),
        )
```

- [ ] **Step 9: Run focused tests**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_schema.py tests/test_config.py::test_hagent_config_has_bash_permission_config tests/test_config.py::test_bash_permission_config_reads_comma_separated_env -v
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml src/hagent/config.py src/hagent/bash_tool/__init__.py src/hagent/bash_tool/schema.py src/hagent/bash_tool/prompt.py tests/bash_tool/test_schema.py tests/test_config.py
git commit -m "feat(bash): add bash tool schema and config"
```

---

### Task 2: Tree-Sitter Bash Parser

**Files:**
- Create: `src/hagent/bash_tool/parser.py`
- Test: `tests/bash_tool/test_parser.py`

- [ ] **Step 1: Write failing parser tests**

Create `tests/bash_tool/test_parser.py`:

```python
from hagent.bash_tool.parser import CommandAnalysis, analyze_command


def test_analyze_simple_command_extracts_argv():
    result = analyze_command("git status --short")

    assert result.kind == "simple"
    assert [cmd.argv for cmd in result.commands] == [["git", "status", "--short"]]
    assert result.reason is None


def test_analyze_compound_and_extracts_two_commands():
    result = analyze_command("cd src && pytest -q")

    assert result.kind == "simple"
    assert [cmd.argv for cmd in result.commands] == [["cd", "src"], ["pytest", "-q"]]


def test_analyze_output_redirect_marks_redirect():
    result = analyze_command("echo hi > out.txt")

    assert result.kind == "simple"
    assert result.commands[0].redirects == [(">", "out.txt")]


def test_command_substitution_requires_approval():
    result = analyze_command("echo $(whoami)")

    assert result.kind == "ask"
    assert "command substitution" in result.reason


def test_subshell_requires_approval():
    result = analyze_command("(cd src && pytest)")

    assert result.kind == "ask"
    assert "subshell" in result.reason


def test_control_flow_requires_approval():
    result = analyze_command("for f in *.py; do echo $f; done")

    assert result.kind == "ask"
    assert "control flow" in result.reason


def test_malformed_command_requires_approval():
    result = analyze_command("echo 'unterminated")

    assert result.kind == "ask"
    assert "parse error" in result.reason
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_parser.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hagent.bash_tool.parser'`.

- [ ] **Step 3: Implement parser module**

Create `src/hagent/bash_tool/parser.py`:

```python
from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Literal

import tree_sitter_bash
from tree_sitter import Language, Parser


AnalysisKind = Literal["simple", "ask"]


@dataclass(frozen=True)
class ParsedCommand:
    text: str
    argv: list[str]
    redirects: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class CommandAnalysis:
    kind: AnalysisKind
    commands: list[ParsedCommand] = field(default_factory=list)
    reason: str | None = None


_LANGUAGE = Language(tree_sitter_bash.language())


def _parser() -> Parser:
    parser = Parser()
    parser.language = _LANGUAGE
    return parser


def _node_text(source: bytes, node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8")


def _has_error(node) -> bool:
    if node.type == "ERROR":
        return True
    return any(_has_error(child) for child in node.children)


def _reason_for_unsupported(node) -> str | None:
    unsupported = {
        "command_substitution": "command substitution requires approval",
        "process_substitution": "process substitution requires approval",
        "subshell": "subshell requires approval",
        "function_definition": "function definition requires approval",
        "for_statement": "control flow requires approval",
        "while_statement": "control flow requires approval",
        "if_statement": "control flow requires approval",
        "case_statement": "control flow requires approval",
    }
    if node.type in unsupported:
        return unsupported[node.type]
    for child in node.children:
        reason = _reason_for_unsupported(child)
        if reason:
            return reason
    return None


def _split_top_level_commands(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = ""
    segments: list[str] = []
    current: list[str] = []
    for token in lexer:
        if token in {"&&", "||", ";", "|"}:
            if current:
                segments.append(" ".join(current))
                current = []
        else:
            current.append(token)
    if current:
        segments.append(" ".join(current))
    return segments


def _extract_redirects(tokens: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    cleaned: list[str] = []
    redirects: list[tuple[str, str]] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in {">", ">>", "2>", "2>>", "<"}:
            target = tokens[i + 1] if i + 1 < len(tokens) else ""
            redirects.append((token, target))
            i += 2
            continue
        cleaned.append(token)
        i += 1
    return cleaned, redirects


def _parse_segment(segment: str) -> ParsedCommand:
    tokens = shlex.split(segment, posix=True)
    cleaned, redirects = _extract_redirects(tokens)
    return ParsedCommand(text=segment, argv=cleaned, redirects=redirects)


def analyze_command(command: str) -> CommandAnalysis:
    source = command.encode("utf-8")
    tree = _parser().parse(source)
    root = tree.root_node
    if _has_error(root):
        return CommandAnalysis(kind="ask", reason="parse error requires approval")
    reason = _reason_for_unsupported(root)
    if reason:
        return CommandAnalysis(kind="ask", reason=reason)
    try:
        segments = _split_top_level_commands(command)
        commands = [_parse_segment(segment) for segment in segments if segment.strip()]
    except ValueError as exc:
        return CommandAnalysis(kind="ask", reason=f"parse error requires approval: {exc}")
    if not commands:
        return CommandAnalysis(kind="ask", reason="empty command requires approval")
    return CommandAnalysis(kind="simple", commands=commands)
```

- [ ] **Step 4: Install dependencies locally**

Run:

```bash
source .venv/bin/activate && pip install -e ".[dev]"
```

Expected: installation succeeds and includes `tree-sitter` and `tree-sitter-bash`.

- [ ] **Step 5: Run focused parser tests**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_parser.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/hagent/bash_tool/parser.py tests/bash_tool/test_parser.py
git commit -m "feat(bash): add tree-sitter command analysis"
```

---

### Task 3: Permission Rules and Default Policy

**Files:**
- Create: `src/hagent/bash_tool/permissions.py`
- Test: `tests/bash_tool/test_permissions.py`

- [ ] **Step 1: Write failing permission tests**

Create `tests/bash_tool/test_permissions.py`:

```python
from hagent.bash_tool.parser import analyze_command
from hagent.bash_tool.permissions import BashPermissionConfig, PermissionDecision, check_bash_permission


def decide(command: str, config: BashPermissionConfig | None = None) -> PermissionDecision:
    return check_bash_permission(command, analyze_command(command), config or BashPermissionConfig())


def test_read_only_command_is_allowed():
    decision = decide("git status --short")

    assert decision.behavior == "allow"
    assert "read-only" in decision.reason


def test_unknown_write_command_asks():
    decision = decide("python generate.py")

    assert decision.behavior == "ask"
    assert "requires approval" in decision.reason


def test_deny_rule_beats_allow_rule():
    config = BashPermissionConfig(
        allow_rules=("Bash(rm:*)",),
        deny_rules=("Bash(rm *)",),
        ask_rules=(),
    )

    decision = decide("rm file.txt", config)

    assert decision.behavior == "deny"
    assert "matched deny rule" in decision.reason


def test_ask_rule_beats_allow_rule():
    config = BashPermissionConfig(
        allow_rules=("Bash(curl:*)",),
        deny_rules=(),
        ask_rules=("Bash(curl:*)",),
    )

    decision = decide("curl https://example.com", config)

    assert decision.behavior == "ask"
    assert "matched ask rule" in decision.reason


def test_prefix_allow_rule_allows_command():
    config = BashPermissionConfig(
        allow_rules=("Bash(pytest:*)",),
        deny_rules=(),
        ask_rules=(),
    )

    decision = decide("pytest tests/bash_tool -q", config)

    assert decision.behavior == "allow"
    assert "matched allow rule" in decision.reason


def test_exact_allow_rule_allows_command():
    config = BashPermissionConfig(
        allow_rules=("Bash(git status --short)",),
        deny_rules=(),
        ask_rules=(),
    )

    decision = decide("git status --short", config)

    assert decision.behavior == "allow"


def test_dangerous_root_removal_denied():
    decision = decide("rm -rf /")

    assert decision.behavior == "deny"
    assert "critical path" in decision.reason


def test_sudo_requires_approval():
    decision = decide("sudo ls")

    assert decision.behavior == "ask"
    assert "privilege escalation" in decision.reason


def test_output_redirect_to_system_path_denied():
    decision = decide("echo x > /etc/hagent-test")

    assert decision.behavior == "deny"
    assert "system path" in decision.reason


def test_parser_ask_result_stays_ask():
    decision = decide("echo $(whoami)")

    assert decision.behavior == "ask"
    assert "command substitution" in decision.reason
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_permissions.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hagent.bash_tool.permissions'`.

- [ ] **Step 3: Implement permissions**

Create `src/hagent/bash_tool/permissions.py`:

```python
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from hagent.bash_tool.parser import CommandAnalysis, ParsedCommand


Behavior = Literal["allow", "ask", "deny"]


@dataclass(frozen=True)
class BashPermissionConfig:
    allow_rules: tuple[str, ...] = ()
    deny_rules: tuple[str, ...] = ()
    ask_rules: tuple[str, ...] = ()
    workspace_root: Path | None = None


@dataclass(frozen=True)
class PermissionDecision:
    behavior: Behavior
    reason: str


@dataclass(frozen=True)
class ParsedRule:
    raw: str
    pattern: str
    kind: Literal["exact", "prefix", "wildcard"]


READ_ONLY_BASE_COMMANDS = {
    "pwd",
    "ls",
    "cat",
    "head",
    "tail",
    "wc",
    "stat",
    "file",
    "strings",
    "rg",
    "grep",
    "find",
    "git",
}

GIT_READ_ONLY_SUBCOMMANDS = {
    "status",
    "diff",
    "log",
    "show",
    "branch",
    "rev-parse",
    "ls-files",
}

PRIVILEGE_ESCALATION = {"sudo", "doas", "pkexec"}
SYSTEM_PATH_PREFIXES = ("/etc", "/usr", "/var", "/root", "/bin", "/sbin", "/lib", "/lib64")


def parse_rule(rule: str) -> ParsedRule:
    stripped = rule.strip()
    if not stripped.startswith("Bash(") or not stripped.endswith(")"):
        msg = f"invalid Bash permission rule: {rule}"
        raise ValueError(msg)
    pattern = stripped[len("Bash(") : -1].strip()
    if pattern.endswith(":*"):
        return ParsedRule(raw=rule, pattern=pattern[:-2], kind="prefix")
    if "*" in pattern or "?" in pattern:
        return ParsedRule(raw=rule, pattern=pattern, kind="wildcard")
    return ParsedRule(raw=rule, pattern=pattern, kind="exact")


def _matches_rule(rule: ParsedRule, command: str) -> bool:
    if rule.kind == "exact":
        return command == rule.pattern
    if rule.kind == "prefix":
        return command == rule.pattern or command.startswith(rule.pattern + " ")
    return fnmatch.fnmatchcase(command, rule.pattern)


def _first_matching(rules: tuple[str, ...], command: str) -> str | None:
    for raw in rules:
        if _matches_rule(parse_rule(raw), command):
            return raw
    return None


def _is_system_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in SYSTEM_PATH_PREFIXES)


def _check_dangerous(parsed: ParsedCommand) -> PermissionDecision | None:
    if not parsed.argv:
        return PermissionDecision("ask", "empty command requires approval")
    base = parsed.argv[0]
    if base in PRIVILEGE_ESCALATION:
        return PermissionDecision("ask", "privilege escalation command requires approval")
    if base == "rm" and any(arg == "/" for arg in parsed.argv[1:]):
        return PermissionDecision("deny", "removing a critical path is denied")
    for operator, target in parsed.redirects:
        if operator in {">", ">>", "2>", "2>>"} and _is_system_path(target):
            return PermissionDecision("deny", f"output redirection to system path is denied: {target}")
    return None


def _is_git_read_only(argv: list[str]) -> bool:
    if len(argv) < 2:
        return False
    return argv[1] in GIT_READ_ONLY_SUBCOMMANDS


def _is_read_only(parsed: ParsedCommand) -> bool:
    if not parsed.argv:
        return False
    base = parsed.argv[0]
    if parsed.redirects:
        return False
    if base == "git":
        return _is_git_read_only(parsed.argv)
    return base in READ_ONLY_BASE_COMMANDS


def check_bash_permission(
    command: str,
    analysis: CommandAnalysis,
    config: BashPermissionConfig,
) -> PermissionDecision:
    stripped = command.strip()
    deny_rule = _first_matching(config.deny_rules, stripped)
    if deny_rule:
        return PermissionDecision("deny", f"matched deny rule {deny_rule}")
    ask_rule = _first_matching(config.ask_rules, stripped)
    if ask_rule:
        return PermissionDecision("ask", f"matched ask rule {ask_rule}")
    allow_rule = _first_matching(config.allow_rules, stripped)
    if allow_rule:
        return PermissionDecision("allow", f"matched allow rule {allow_rule}")
    if analysis.kind == "ask":
        return PermissionDecision("ask", analysis.reason or "command requires approval")
    for parsed in analysis.commands:
        dangerous = _check_dangerous(parsed)
        if dangerous:
            return dangerous
    if all(_is_read_only(parsed) for parsed in analysis.commands):
        return PermissionDecision("allow", "read-only command is allowed")
    return PermissionDecision("ask", "command requires approval")
```

- [ ] **Step 4: Run focused permission tests**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_permissions.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/hagent/bash_tool/permissions.py tests/bash_tool/test_permissions.py
git commit -m "feat(bash): add permission policy"
```

---

### Task 4: Output Store and Task Registry

**Files:**
- Create: `src/hagent/bash_tool/output.py`
- Create: `src/hagent/bash_tool/tasks.py`
- Test: `tests/bash_tool/test_output_tasks.py`

- [ ] **Step 1: Write failing output/task tests**

Create `tests/bash_tool/test_output_tasks.py`:

```python
from pathlib import Path

from hagent.bash_tool.output import OutputStore
from hagent.bash_tool.tasks import ShellTask, TaskRegistry


def test_output_store_writes_and_previews(tmp_path):
    store = OutputStore(root=tmp_path, inline_limit=10)
    output = store.create("task-1")

    output.path.write_text("0123456789abcdef", encoding="utf-8")
    result = store.finalize(output)

    assert result.preview == "0123456789"
    assert result.truncated is True
    assert result.persisted_output_path == str(output.path)
    assert result.persisted_output_size == 16


def test_output_store_non_truncated_preview(tmp_path):
    store = OutputStore(root=tmp_path, inline_limit=100)
    output = store.create("task-2")

    output.path.write_text("hello", encoding="utf-8")
    result = store.finalize(output)

    assert result.preview == "hello"
    assert result.truncated is False


def test_task_registry_registers_and_updates(tmp_path):
    registry = TaskRegistry()
    task = ShellTask(
        task_id="task-1",
        command="sleep 1",
        description="Sleep briefly",
        pid=123,
        process_group_id=123,
        output_path=tmp_path / "out.log",
    )

    registry.register(task)
    registry.mark_completed("task-1", exit_code=0, interrupted=False)

    saved = registry.get("task-1")
    assert saved is not None
    assert saved.status == "completed"
    assert saved.exit_code == 0


def test_task_registry_lists_tasks(tmp_path):
    registry = TaskRegistry()
    registry.register(
        ShellTask(
            task_id="task-1",
            command="echo hi",
            description="Say hi",
            pid=1,
            process_group_id=1,
            output_path=tmp_path / "out.log",
        )
    )

    assert [task.task_id for task in registry.list()] == ["task-1"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_output_tasks.py -v
```

Expected: FAIL with missing `output` and `tasks` modules.

- [ ] **Step 3: Implement output store**

Create `src/hagent/bash_tool/output.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OutputFile:
    task_id: str
    path: Path


@dataclass(frozen=True)
class OutputPreview:
    preview: str
    truncated: bool
    persisted_output_path: str
    persisted_output_size: int


class OutputStore:
    def __init__(self, root: Path, inline_limit: int = 30_000) -> None:
        self.root = root
        self.inline_limit = inline_limit
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, task_id: str) -> OutputFile:
        path = self.root / f"{task_id}.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(mode=0o600, exist_ok=True)
        return OutputFile(task_id=task_id, path=path)

    def finalize(self, output: OutputFile) -> OutputPreview:
        data = output.path.read_text(encoding="utf-8", errors="replace")
        size = output.path.stat().st_size
        preview = data[: self.inline_limit]
        return OutputPreview(
            preview=preview,
            truncated=len(data) > self.inline_limit,
            persisted_output_path=str(output.path),
            persisted_output_size=size,
        )

    def tail(self, output: OutputFile, max_chars: int = 4000) -> str:
        data = output.path.read_text(encoding="utf-8", errors="replace")
        return data[-max_chars:]
```

- [ ] **Step 4: Implement task registry**

Create `src/hagent/bash_tool/tasks.py`:

```python
from __future__ import annotations

import os
import signal
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal


TaskStatus = Literal["running", "backgrounded", "completed", "failed", "killed"]


@dataclass(frozen=True)
class ShellTask:
    task_id: str
    command: str
    description: str
    pid: int
    process_group_id: int
    output_path: Path
    status: TaskStatus = "running"
    started_at: float = 0.0
    completed_at: float | None = None
    exit_code: int | None = None
    interrupted: bool = False

    def __post_init__(self) -> None:
        if self.started_at == 0.0:
            object.__setattr__(self, "started_at", time.time())


class TaskRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tasks: dict[str, ShellTask] = {}

    def register(self, task: ShellTask) -> None:
        with self._lock:
            self._tasks[task.task_id] = task

    def get(self, task_id: str) -> ShellTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list(self) -> list[ShellTask]:
        with self._lock:
            return list(self._tasks.values())

    def mark_backgrounded(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks[task_id]
            self._tasks[task_id] = replace(task, status="backgrounded")

    def mark_completed(self, task_id: str, *, exit_code: int, interrupted: bool) -> None:
        with self._lock:
            task = self._tasks[task_id]
            status: TaskStatus = "completed" if exit_code == 0 and not interrupted else "failed"
            if interrupted:
                status = "killed"
            self._tasks[task_id] = replace(
                task,
                status=status,
                completed_at=time.time(),
                exit_code=exit_code,
                interrupted=interrupted,
            )

    def kill(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            return False
        try:
            os.killpg(task.process_group_id, signal.SIGKILL)
        except ProcessLookupError:
            return False
        with self._lock:
            self._tasks[task_id] = replace(task, status="killed", completed_at=time.time(), interrupted=True)
        return True

    def kill_all_running(self) -> None:
        for task in self.list():
            if task.status in {"running", "backgrounded"}:
                self.kill(task.task_id)
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_output_tasks.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/hagent/bash_tool/output.py src/hagent/bash_tool/tasks.py tests/bash_tool/test_output_tasks.py
git commit -m "feat(bash): add output store and task registry"
```

---

### Task 5: Shell Provider

**Files:**
- Create: `src/hagent/bash_tool/shell_provider.py`
- Test: `tests/bash_tool/test_shell_provider.py`

- [ ] **Step 1: Write failing shell provider tests**

Create `tests/bash_tool/test_shell_provider.py`:

```python
from pathlib import Path

import pytest

from hagent.bash_tool.shell_provider import ShellProvider, quote_for_eval, resolve_shell


def test_quote_for_eval_preserves_spaces_and_quotes():
    quoted = quote_for_eval('printf "hello world"')

    assert quoted.startswith("'")
    assert quoted.endswith("'")
    assert "printf" in quoted


def test_resolve_shell_honors_explicit_env(monkeypatch, tmp_path):
    shell = tmp_path / "bash"
    shell.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    shell.chmod(0o755)
    monkeypatch.setenv("HAGENT_BASH_SHELL", str(shell))

    assert resolve_shell() == shell


def test_build_command_sources_snapshot_and_tracks_cwd(tmp_path):
    snapshot = tmp_path / "snapshot.sh"
    snapshot.write_text("export FROM_SNAPSHOT=1\n", encoding="utf-8")
    provider = ShellProvider(shell_path=Path("/bin/bash"), snapshot_path=snapshot)

    built = provider.build_command("echo hi", cwd_file=tmp_path / "cwd.txt")

    assert f"source {snapshot}" in built
    assert "eval " in built
    assert "pwd -P >|" in built
    assert "shopt -u extglob" in built


def test_build_command_can_omit_snapshot(tmp_path):
    provider = ShellProvider(shell_path=Path("/bin/bash"), snapshot_path=None)

    built = provider.build_command("echo hi", cwd_file=tmp_path / "cwd.txt")

    assert "source " not in built
    assert "eval " in built
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_shell_provider.py -v
```

Expected: FAIL with missing `shell_provider` module.

- [ ] **Step 3: Implement shell provider**

Create `src/hagent/bash_tool/shell_provider.py`:

```python
from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from shutil import which


def _is_executable(path: Path) -> bool:
    return path.exists() and os.access(path, os.X_OK)


def resolve_shell() -> Path:
    explicit = os.environ.get("HAGENT_BASH_SHELL")
    if explicit:
        path = Path(explicit)
        if _is_executable(path):
            return path
        msg = f"HAGENT_BASH_SHELL is not executable: {path}"
        raise RuntimeError(msg)

    env_shell = os.environ.get("SHELL")
    if env_shell and ("bash" in env_shell or "zsh" in env_shell):
        path = Path(env_shell)
        if _is_executable(path):
            return path

    candidates = [
        which("bash"),
        which("zsh"),
        "/bin/bash",
        "/usr/bin/bash",
        "/bin/zsh",
        "/usr/bin/zsh",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if _is_executable(path):
            return path

    msg = "No suitable bash or zsh shell found"
    raise RuntimeError(msg)


def quote_for_eval(command: str) -> str:
    return shlex.quote(command)


def disable_extglob_command(shell_path: Path) -> str:
    if "zsh" in shell_path.name:
        return "setopt NO_EXTENDED_GLOB 2>/dev/null || true"
    return "shopt -u extglob 2>/dev/null || true"


@dataclass(frozen=True)
class ShellProvider:
    shell_path: Path
    snapshot_path: Path | None = None

    @classmethod
    def create(cls) -> "ShellProvider":
        shell = resolve_shell()
        return cls(shell_path=shell, snapshot_path=create_shell_snapshot(shell))

    def build_command(self, command: str, *, cwd_file: Path, session_env_script: str | None = None) -> str:
        parts: list[str] = []
        if self.snapshot_path is not None:
            parts.append(f"source {shlex.quote(str(self.snapshot_path))} 2>/dev/null || true")
        if session_env_script:
            parts.append(session_env_script)
        parts.append(disable_extglob_command(self.shell_path))
        parts.append(f"eval {quote_for_eval(command)}")
        parts.append(f"pwd -P >| {shlex.quote(str(cwd_file))}")
        return " && ".join(parts)

    def spawn_args(self, command_string: str) -> list[str]:
        return ["-c", command_string] if self.snapshot_path else ["-c", "-l", command_string]


def create_shell_snapshot(shell_path: Path) -> Path | None:
    snapshot = Path(tempfile.gettempdir()) / f"hagent-shell-snapshot-{os.getpid()}.sh"
    command = "env | sed 's/'\"'\"'/\\'\"'\"'\"'\"'\\''\"'\"'/g' | awk -F= '{print \"export \" $1 \"=\\047\" substr($0, index($0,$2)) \"\\047\"}'"
    try:
        result = subprocess.run(
            [str(shell_path), "-lc", command],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    snapshot.write_text(result.stdout, encoding="utf-8")
    snapshot.chmod(0o600)
    return snapshot
```

- [ ] **Step 4: Run focused shell provider tests**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_shell_provider.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/hagent/bash_tool/shell_provider.py tests/bash_tool/test_shell_provider.py
git commit -m "feat(bash): add shell provider"
```

---

### Task 6: Runtime Foreground Execution

**Files:**
- Create: `src/hagent/bash_tool/runtime.py`
- Test: `tests/bash_tool/test_runtime.py`

- [ ] **Step 1: Write failing runtime tests**

Create `tests/bash_tool/test_runtime.py`:

```python
from pathlib import Path

from hagent.bash_tool.runtime import BashRuntime


def test_runtime_runs_bash_brace_expansion(tmp_path):
    runtime = BashRuntime(workspace=tmp_path)

    result = runtime.run("mkdir -p app/{api,core}")

    assert result.exit_code == 0
    assert (tmp_path / "app" / "api").is_dir()
    assert (tmp_path / "app" / "core").is_dir()


def test_runtime_tracks_cwd_between_commands(tmp_path):
    runtime = BashRuntime(workspace=tmp_path)
    (tmp_path / "sub").mkdir()

    first = runtime.run("cd sub")
    second = runtime.run("pwd")

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert str(tmp_path / "sub") in second.stdout


def test_runtime_merges_stderr_into_stdout_preview(tmp_path):
    runtime = BashRuntime(workspace=tmp_path)

    result = runtime.run("python -c 'import sys; print(\"out\"); print(\"err\", file=sys.stderr)'")

    assert result.exit_code == 0
    assert "out" in result.stdout
    assert "err" in result.stdout


def test_runtime_times_out_and_kills(tmp_path):
    runtime = BashRuntime(workspace=tmp_path)

    result = runtime.run("sleep 5", timeout_ms=200)

    assert result.exit_code != 0
    assert result.interrupted is True
    assert "timed out" in result.stderr


def test_runtime_persists_large_output(tmp_path):
    runtime = BashRuntime(workspace=tmp_path, inline_output_limit=10)

    result = runtime.run("printf 0123456789abcdef")

    assert result.truncated is True
    assert result.persisted_output_path is not None
    assert Path(result.persisted_output_path).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_runtime.py -v
```

Expected: FAIL with missing `runtime` module.

- [ ] **Step 3: Implement runtime foreground path**

Create `src/hagent/bash_tool/runtime.py`:

```python
from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from hagent.bash_tool.output import OutputStore
from hagent.bash_tool.schema import BashResult, get_default_timeout_ms, get_max_output_length
from hagent.bash_tool.shell_provider import ShellProvider
from hagent.bash_tool.tasks import ShellTask, TaskRegistry


class BashRuntime:
    def __init__(
        self,
        workspace: Path,
        *,
        provider: ShellProvider | None = None,
        registry: TaskRegistry | None = None,
        inline_output_limit: int | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.cwd = self.workspace
        self.provider = provider or ShellProvider.create()
        self.registry = registry or TaskRegistry()
        self.output_store = OutputStore(
            self.workspace / ".hagent" / "tool-results",
            inline_limit=inline_output_limit or get_max_output_length(),
        )

    def run(
        self,
        command: str,
        *,
        timeout_ms: int | None = None,
        description: str | None = None,
        run_in_background: bool = False,
    ) -> BashResult:
        if run_in_background:
            return self.start_background(command, description=description or command)
        task_id = f"local_bash_{uuid.uuid4().hex[:12]}"
        output = self.output_store.create(task_id)
        cwd_file = Path(tempfile.gettempdir()) / f"hagent-{task_id}-cwd"
        wrapped = self.provider.build_command(command, cwd_file=cwd_file)
        timeout_seconds = (timeout_ms or get_default_timeout_ms()) / 1000
        proc = subprocess.Popen(
            [str(self.provider.shell_path), *self.provider.spawn_args(wrapped)],
            cwd=str(self.cwd),
            stdin=subprocess.DEVNULL,
            stdout=output.path.open("ab", buffering=0),
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env={**os.environ, "SHELL": str(self.provider.shell_path), "GIT_EDITOR": "true", "CLAUDECODE": "1"},
        )
        interrupted = False
        stderr = ""
        try:
            exit_code = proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            interrupted = True
            exit_code = 124
            stderr = f"Command timed out after {int(timeout_seconds * 1000)}ms"
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
        if cwd_file.exists() and not interrupted:
            raw_cwd = cwd_file.read_text(encoding="utf-8", errors="replace").strip()
            if raw_cwd:
                self.cwd = Path(raw_cwd).resolve()
            cwd_file.unlink(missing_ok=True)
        preview = self.output_store.finalize(output)
        return BashResult(
            stdout=preview.preview,
            stderr=stderr,
            exit_code=exit_code,
            interrupted=interrupted,
            persisted_output_path=preview.persisted_output_path if preview.truncated else None,
            persisted_output_size=preview.persisted_output_size if preview.truncated else None,
            truncated=preview.truncated,
            no_output_expected=not preview.preview and exit_code == 0,
        )

    def start_background(self, command: str, *, description: str) -> BashResult:
        task_id = f"local_bash_{uuid.uuid4().hex[:12]}"
        output = self.output_store.create(task_id)
        cwd_file = Path(tempfile.gettempdir()) / f"hagent-{task_id}-cwd"
        wrapped = self.provider.build_command(command, cwd_file=cwd_file)
        out_handle = output.path.open("ab", buffering=0)
        proc = subprocess.Popen(
            [str(self.provider.shell_path), *self.provider.spawn_args(wrapped)],
            cwd=str(self.cwd),
            stdin=subprocess.DEVNULL,
            stdout=out_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env={**os.environ, "SHELL": str(self.provider.shell_path), "GIT_EDITOR": "true", "CLAUDECODE": "1"},
        )
        task = ShellTask(
            task_id=task_id,
            command=command,
            description=description,
            pid=proc.pid,
            process_group_id=proc.pid,
            output_path=output.path,
            status="backgrounded",
        )
        self.registry.register(task)
        return BashResult(
            stdout="",
            exit_code=0,
            background_task_id=task_id,
            persisted_output_path=str(output.path),
        )

    def cleanup(self) -> None:
        self.registry.kill_all_running()
```

- [ ] **Step 4: Run focused runtime tests**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_runtime.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/hagent/bash_tool/runtime.py tests/bash_tool/test_runtime.py
git commit -m "feat(bash): add local shell runtime"
```

---

### Task 7: Background Completion Tracking

**Files:**
- Modify: `src/hagent/bash_tool/runtime.py`
- Modify: `src/hagent/bash_tool/tasks.py`
- Modify test: `tests/bash_tool/test_runtime.py`

- [ ] **Step 1: Add failing background tests**

Append to `tests/bash_tool/test_runtime.py`:

```python
import time


def test_background_task_completes_and_output_is_readable(tmp_path):
    runtime = BashRuntime(workspace=tmp_path)

    result = runtime.run("printf background-ok", run_in_background=True, description="Print background output")

    assert result.background_task_id is not None
    task_id = result.background_task_id
    for _ in range(50):
        task = runtime.registry.get(task_id)
        if task and task.status == "completed":
            break
        time.sleep(0.05)

    task = runtime.registry.get(task_id)
    assert task is not None
    assert task.status == "completed"
    assert task.output_path.read_text(encoding="utf-8") == "background-ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_runtime.py::test_background_task_completes_and_output_is_readable -v
```

Expected: FAIL because background tasks remain `backgrounded`.

- [ ] **Step 3: Add background watcher**

Modify `src/hagent/bash_tool/runtime.py` imports:

```python
import threading
```

Add this method to `BashRuntime`:

```python
    def _watch_background(self, task_id: str, proc: subprocess.Popen, output_handle) -> None:
        try:
            exit_code = proc.wait()
            interrupted = exit_code in {137, 143}
            self.registry.mark_completed(task_id, exit_code=exit_code, interrupted=interrupted)
        finally:
            output_handle.close()
```

In `start_background()`, after `self.registry.register(task)`, add:

```python
        thread = threading.Thread(
            target=self._watch_background,
            args=(task_id, proc, out_handle),
            daemon=True,
        )
        thread.start()
```

- [ ] **Step 4: Run background test**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_runtime.py::test_background_task_completes_and_output_is_readable -v
```

Expected: PASS.

- [ ] **Step 5: Run all runtime tests**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_runtime.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/hagent/bash_tool/runtime.py tests/bash_tool/test_runtime.py
git commit -m "feat(bash): track background task completion"
```

---

### Task 8: LangChain Bash Tool Adapter

**Files:**
- Create: `src/hagent/bash_tool/tool.py`
- Test: `tests/bash_tool/test_tool.py`

- [ ] **Step 1: Write failing tool tests**

Create `tests/bash_tool/test_tool.py`:

```python
from pathlib import Path

from hagent.bash_tool.permissions import BashPermissionConfig
from hagent.bash_tool.runtime import BashRuntime
from hagent.bash_tool.tool import create_bash_tool


def test_create_bash_tool_name_and_schema(tmp_path):
    runtime = BashRuntime(workspace=tmp_path)
    tool = create_bash_tool(runtime=runtime, permission_config=BashPermissionConfig())

    assert tool.name == "Bash"
    schema = tool.args_schema.model_json_schema()
    assert "command" in schema["properties"]
    assert "run_in_background" in schema["properties"]
    assert "dangerouslyDisableSandbox" in schema["properties"]


def test_bash_tool_runs_allowed_read_only_command(tmp_path):
    runtime = BashRuntime(workspace=tmp_path)
    tool = create_bash_tool(runtime=runtime, permission_config=BashPermissionConfig())

    result = tool.invoke({"command": "pwd", "description": "Print working directory"})

    assert str(tmp_path) in result


def test_bash_tool_blocks_ask_command(tmp_path):
    runtime = BashRuntime(workspace=tmp_path)
    tool = create_bash_tool(runtime=runtime, permission_config=BashPermissionConfig())

    result = tool.invoke({"command": "python generate.py", "description": "Run generator"})

    assert "requires approval" in result


def test_bash_tool_uses_allow_rule(tmp_path):
    runtime = BashRuntime(workspace=tmp_path)
    tool = create_bash_tool(
        runtime=runtime,
        permission_config=BashPermissionConfig(allow_rules=("Bash(python:*)",)),
    )

    result = tool.invoke({"command": "python -c 'print(123)'", "description": "Print number"})

    assert "123" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_tool.py -v
```

Expected: FAIL with missing `tool` module.

- [ ] **Step 3: Implement tool adapter**

Create `src/hagent/bash_tool/tool.py`:

```python
from __future__ import annotations

from langchain_core.tools import StructuredTool

from hagent.bash_tool.parser import analyze_command
from hagent.bash_tool.permissions import BashPermissionConfig, check_bash_permission
from hagent.bash_tool.prompt import BASH_TOOL_DESCRIPTION, BASH_TOOL_NAME
from hagent.bash_tool.runtime import BashRuntime
from hagent.bash_tool.schema import BashInput


def create_bash_tool(
    *,
    runtime: BashRuntime,
    permission_config: BashPermissionConfig,
) -> StructuredTool:
    def _run(
        command: str,
        timeout: int | None = None,
        description: str | None = None,
        run_in_background: bool | None = None,
        dangerouslyDisableSandbox: bool | None = None,
    ) -> str:
        data = BashInput(
            command=command,
            timeout=timeout,
            description=description,
            run_in_background=run_in_background,
            dangerouslyDisableSandbox=dangerouslyDisableSandbox,
        )
        analysis = analyze_command(data.command)
        decision = check_bash_permission(data.command, analysis, permission_config)
        if decision.behavior == "deny":
            return f"Permission denied: {decision.reason}"
        if decision.behavior == "ask":
            return f"Permission required: {decision.reason}"
        result = runtime.run(
            data.command,
            timeout_ms=data.timeout,
            description=data.description,
            run_in_background=bool(data.run_in_background),
        )
        return result.to_tool_text()

    return StructuredTool.from_function(
        name=BASH_TOOL_NAME,
        description=BASH_TOOL_DESCRIPTION,
        func=_run,
        args_schema=BashInput,
        infer_schema=False,
    )
```

- [ ] **Step 4: Run focused tool tests**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool/test_tool.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/hagent/bash_tool/tool.py tests/bash_tool/test_tool.py
git commit -m "feat(bash): add langchain Bash tool"
```

---

### Task 9: Integrate Bash in create_hagent and Hide execute

**Files:**
- Modify: `src/hagent/core.py`
- Modify test: `tests/test_core.py`

- [ ] **Step 1: Add failing core tests**

Append to `tests/test_core.py`:

```python
def test_create_hagent_injects_bash_tool(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()

    tool_names = {tool.name for tool in captured["tools"]}
    assert "Bash" in tool_names


def test_create_hagent_filters_execute_tool_from_extra_tools(monkeypatch):
    captured: dict = {}

    class FakeExecuteTool:
        name = "execute"

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent(extra_tools=[FakeExecuteTool()])

    tool_names = {tool.name for tool in captured["tools"]}
    assert "execute" not in tool_names
    assert "Bash" in tool_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && pytest tests/test_core.py::test_create_hagent_injects_bash_tool tests/test_core.py::test_create_hagent_filters_execute_tool_from_extra_tools -v
```

Expected: FAIL because `Bash` is not injected.

- [ ] **Step 3: Add core helper functions**

Modify imports in `src/hagent/core.py`:

```python
from hagent.bash_tool.permissions import BashPermissionConfig
from hagent.bash_tool.runtime import BashRuntime
from hagent.bash_tool.tool import create_bash_tool
```

Add helper functions after `sanitize_anthropic_thinking_blocks_middleware`:

```python
def _tool_name(tool: Any) -> str | None:
    if hasattr(tool, "name"):
        return getattr(tool, "name")
    if isinstance(tool, dict):
        name = tool.get("name")
        return str(name) if name is not None else None
    return None


def _without_execute_tool(tools: list[Any]) -> list[Any]:
    return [tool for tool in tools if _tool_name(tool) != "execute"]
```

- [ ] **Step 4: Inject Bash tool**

In `create_hagent()`, after `working_directory = _backend_working_directory(backend)`, add:

```python
    bash_runtime = BashRuntime(workspace=working_directory)
    bash_tool = create_bash_tool(
        runtime=bash_runtime,
        permission_config=BashPermissionConfig(
            allow_rules=cfg.bash_permissions.allow_rules,
            deny_rules=cfg.bash_permissions.deny_rules,
            ask_rules=cfg.bash_permissions.ask_rules,
            workspace_root=working_directory,
        ),
    )
    model_tools = [bash_tool, *_without_execute_tool(list(extra_tools or []))]
```

Then change the `kwargs` entry from:

```python
        tools=list(extra_tools or []),
```

to:

```python
        tools=model_tools,
```

- [ ] **Step 5: Run focused core tests**

Run:

```bash
source .venv/bin/activate && pytest tests/test_core.py::test_create_hagent_injects_bash_tool tests/test_core.py::test_create_hagent_filters_execute_tool_from_extra_tools -v
```

Expected: PASS.

- [ ] **Step 6: Run all core tests**

Run:

```bash
source .venv/bin/activate && pytest tests/test_core.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/hagent/core.py tests/test_core.py
git commit -m "feat(core): inject Bash tool"
```

---

### Task 10: Prompt, Subagent, and SSE Updates

**Files:**
- Modify: `src/hagent/subagents.py`
- Modify: `prompts/hagent_base.zh.md`
- Modify: `prompts/decisions.md`
- Modify: `src/hagent/server/sse.py`
- Modify test: `tests/test_subagents.py`
- Modify test: `tests/server/test_sse_adapter.py`

- [ ] **Step 1: Add failing subagent test**

Append to `tests/test_subagents.py`:

```python
from hagent.subagents import BUILTIN_SUBAGENTS


def test_builtin_subagents_use_bash_not_execute():
    combined = "\n".join(agent["system_prompt"] for agent in BUILTIN_SUBAGENTS)

    assert "Bash" in combined
    assert "execute" not in combined
```

- [ ] **Step 2: Add failing SSE test for Bash chunks**

Append to `tests/server/test_sse_adapter.py`:

```python
def test_parse_bash_tool_call_args_chunks_without_repeated_name():
    class FakeToolCallStart:
        type = "AIMessageChunk"
        content = ""
        tool_call_chunks = [{"name": "Bash", "args": "", "id": "abc", "index": 0}]

    class FakeToolCallArgs:
        type = "AIMessageChunk"
        content = ""
        tool_call_chunks = [{"name": None, "args": '{"command":"pytest"}', "id": None, "index": 0}]

    tool_call_state = {}
    list(parse_lg_chunk(("messages", (FakeToolCallStart(), {})), tool_call_state=tool_call_state))

    out = list(parse_lg_chunk(("messages", (FakeToolCallArgs(), {})), tool_call_state=tool_call_state))

    assert out == [
        (
            "tool_call.started",
            {
                "call_id": "abc",
                "tool_name": "Bash",
                "args_chunk": '{"command":"pytest"}',
            },
        )
    ]
```

- [ ] **Step 3: Run tests to verify subagent fails and SSE passes or fails**

Run:

```bash
source .venv/bin/activate && pytest tests/test_subagents.py::test_builtin_subagents_use_bash_not_execute tests/server/test_sse_adapter.py::test_parse_bash_tool_call_args_chunks_without_repeated_name -v
```

Expected: subagent test FAIL because prompt still says `execute`; SSE may already PASS because adapter is tool-name agnostic.

- [ ] **Step 4: Update coder subagent prompt**

In `src/hagent/subagents.py`, replace the `CODER["system_prompt"]` string with:

```python
    "system_prompt": (
        "你是 Hagent 的 coder 子代理。在收到明确任务（要改的文件 + 期望行为）后："
        "先用 read_file 确认现状，必要时写测试，再用 edit_file / write_file 修改，"
        "最后用 Bash 跑测试或脚本确认。完成后报告：改了哪些文件、跑了什么验证、结果。"
    ),
```

- [ ] **Step 5: Update base prompt wording**

Run this search:

```bash
rg -n "execute|Execute" prompts/hagent_base.zh.md prompts/decisions.md
```

For every instruction that tells the model to use `execute` for shell commands, change it to `Bash`. Add a new entry to `prompts/decisions.md`:

```markdown
## 2026-05-14 Bash Tool Rename

- MODIFY: Shell execution instructions now refer to `Bash` instead of `execute`.
- Reason: Hagent implements a Claude Code-style Python Bash tool and hides Deep Agents' native `execute` from the model-visible tool list.
```

- [ ] **Step 6: Keep SSE adapter tool-name agnostic**

If the SSE test from Step 2 failed, inspect `src/hagent/server/sse.py` and ensure the chunk state stores `tool_name` exactly as received:

```python
                    if name:
                        saved["tool_name"] = name
```

No special-case code for `execute` or `Bash` should be added.

- [ ] **Step 7: Run prompt check if base prompt changed**

Run:

```bash
./scripts/check_base_prompt.sh
```

Expected: PASS.

- [ ] **Step 8: Run focused tests**

Run:

```bash
source .venv/bin/activate && pytest tests/test_subagents.py tests/server/test_sse_adapter.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/hagent/subagents.py src/hagent/server/sse.py prompts/hagent_base.zh.md prompts/decisions.md tests/test_subagents.py tests/server/test_sse_adapter.py
git commit -m "feat(bash): update prompts and streaming for Bash"
```

---

### Task 11: Full Verification and Documentation Check

**Files:**
- Modify: `README.md`
- No production code changes.

- [ ] **Step 1: Run Bash package tests**

Run:

```bash
source .venv/bin/activate && pytest tests/bash_tool -v
```

Expected: PASS.

- [ ] **Step 2: Run core and server adapter tests**

Run:

```bash
source .venv/bin/activate && pytest tests/test_core.py tests/test_config.py tests/test_subagents.py tests/server/test_sse_adapter.py -v
```

Expected: PASS.

- [ ] **Step 3: Run full Python test suite**

Run:

```bash
source .venv/bin/activate && pytest -v
```

Expected: PASS. If Docker-related or real-model tests are skipped by environment gating, record the skip summary in the final implementation report.

- [ ] **Step 4: Run a manual smoke command through runtime**

Run:

```bash
source .venv/bin/activate && python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from hagent.bash_tool.runtime import BashRuntime

with TemporaryDirectory() as d:
    rt = BashRuntime(Path(d))
    print(rt.run("mkdir -p app/{api,core} && find app -maxdepth 2 -type d | sort").to_tool_text())
PY
```

Expected output contains:

```text
app
app/api
app/core
```

- [ ] **Step 5: Confirm model-visible tool list behavior**

Run:

```bash
source .venv/bin/activate && pytest tests/test_core.py::test_create_hagent_injects_bash_tool tests/test_core.py::test_create_hagent_filters_execute_tool_from_extra_tools -v
```

Expected: PASS.

- [ ] **Step 6: Add README note and commit**

Add this section to `README.md`:

```markdown
### Shell Execution

Hagent exposes a Claude Code-style `Bash` tool for local shell execution. The Deep Agents native `execute` tool is hidden from the model-visible tool list.
```

Then run:

```bash
git add README.md
git commit -m "docs: document Bash shell tool"
```

Expected: commit succeeds.

---

## Self-Review

Spec coverage:

- Local POSIX host execution: Tasks 5 and 6.
- Claude Code-style `Bash` schema and prompt: Tasks 1 and 8.
- Disable native `execute`: Task 9.
- `tree-sitter-bash` parsing: Task 2.
- Permission rules and read-only policy: Task 3.
- Background tasks and persisted output: Tasks 4, 6, and 7.
- Prompt/subagent migration: Task 10.
- SSE compatibility: Task 10.
- Full verification: Task 11.

Placeholder scan:

- This plan contains no empty implementation steps and no vague implementation sections.
- Every code-changing task includes exact file paths, code blocks, commands, expected results, and commit commands.

Type consistency:

- `BashInput`, `BashResult`, `BashProgress` are defined in Task 1 and reused consistently.
- `CommandAnalysis` and `ParsedCommand` are defined in Task 2 and consumed by Task 3.
- `BashPermissionConfig` appears both in `hagent.config` and `hagent.bash_tool.permissions`; Task 9 explicitly maps from config to runtime permissions to avoid importing app config into low-level policy code.
- `TaskRegistry`, `ShellTask`, `OutputStore`, and `BashRuntime` names are consistent across Tasks 4-9.
