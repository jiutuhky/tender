# Hagent Skills Support Implementation Plan

> **存档说明**：本 plan 产出自已退役的 superpowers 工作流，仅作历史参考；新工作一律走仓根 tickets.md（Matt 契约）。

**Goal:** Add Claude Code-aligned Skills support to Hagent: discover `SKILL.md` folders, expose a model-callable `Skill` tool, inject a concise skills catalog, and preload declared skills for subagents.

**Architecture:** Build a focused `hagent.skills` package that owns skill source discovery, frontmatter parsing, registry lookup, argument substitution, prompt expansion, and the `Skill` LangChain tool. Wire the registry and tool into `create_hagent()`, use a Hagent-specific skills middleware instead of DeepAgents' default prompt text so the model sees `Read`/`Skill` rather than hidden `read_file`, and carry subagent `skills` frontmatter through loader/compiler so subagents can start with selected skill content.

**Tech Stack:** Python 3.11+, Pydantic v2, PyYAML, LangChain `StructuredTool`, DeepAgents middleware API, pytest.

---

## Required Context

- DeepAgents official docs in `deepagents/skills.mdx` define Agent Skills as `skills/<name>/SKILL.md` folders with YAML frontmatter and progressive disclosure. The SDK only loads directories explicitly passed via `skills`, later sources override earlier sources, `SKILL.md` files over 10 MB are skipped, and subagent skill state is isolated.
- DeepAgents CLI docs in `deepagents/cli/memory-and-skills.mdx` and `deepagents/data-locations.mdx` discover skills from `~/.deepagents/<agent>/skills/`, `~/.agents/skills/`, `.deepagents/skills/`, `.agents/skills/`, and experimental Claude locations `~/.claude/skills/` / `.claude/skills/`.
- Installed `deepagents==0.6.1` implements `SkillsMiddleware` in `.venv/lib/python3.12/site-packages/deepagents/middleware/skills.py`. It loads metadata into private state, injects a "Skills System" prompt, and tells the model to call `read_file(path, limit=1000)`. Hagent hides DeepAgents `read_file`, so using this middleware unmodified would produce bad model instructions.
- Claude Code source in `/home/hankeyang/workplace/claude-code-main/src/skills/loadSkillsDir.ts` treats the directory name as the invocation name, supports `allowed-tools`, `argument-hint`, `arguments`, `when_to_use`, `version`, `model`, `disable-model-invocation`, `user-invocable`, `context: fork`, `agent`, `paths`, and shell-style `$ARGUMENTS` substitution.
- Claude Code source in `/home/hankeyang/workplace/claude-code-main/src/tools/SkillTool/SkillTool.ts` exposes a model-facing `Skill` tool with input `{ skill, args? }`. When a matching skill applies, the model is instructed to invoke `Skill` before answering. The skill body is expanded into the conversation with `Base directory for this skill: <dir>`.
- Claude Code source in `/home/hankeyang/workplace/claude-code-main/src/tools/AgentTool/runAgent.ts` preloads skills listed in an agent definition's `skills` frontmatter into the subagent's initial context.
- Hagent currently registers Claude-style `Read`, `Write`, `Edit`, `Bash`, `TaskCreate`, `TaskGet`, `TaskUpdate`, `TaskList`, and `Agent` tools in `src/hagent/core.py`, disables DeepAgents `read_file` / `write_file` / `edit_file` / `execute` / `write_todos`, and passes `subagents=None` to DeepAgents because Hagent compiles its own subagents.
- Hagent currently ignores subagent frontmatter key `skills` in `src/hagent/subagents/loader.py`. That must change for Claude Code parity.

## Scope

This plan implements the local, file-based Claude Code skill path:

- Supported: `skills/<name>/SKILL.md`, automatic discovery from DeepAgents/shared/Claude user and project locations, source precedence with last source winning, metadata catalog injection, model-facing `Skill` tool, direct CLI `--skill`, server message `/skill:<name>`, subagent frontmatter `skills`, `$ARGUMENTS` substitution, `$0` / `$1`, named arguments, `${CLAUDE_SKILL_DIR}`, `${HAGENT_SKILL_DIR}`, `${CLAUDE_SESSION_ID}`, `allowed-tools` metadata in tool results, `disable-model-invocation`, and `user-invocable`.
- Not included in this first Hagent implementation: Claude Code plugin skills, bundled skills, MCP skill resources, remote canonical skill search, frontmatter hooks, inline shell execution inside skill markdown, permission UI for `Skill(...)`, and `paths`-based dynamic activation. The parser preserves these fields so later work can use them without changing saved skill files.

## File Structure

Create:

- `src/hagent/skills/__init__.py` — public exports for the skills package.
- `src/hagent/skills/models.py` — Pydantic models for `SkillMetadata`, `SkillFrontmatter`, `SkillInvocation`, and `SkillInvocationResult`.
- `src/hagent/skills/arguments.py` — Claude Code-compatible shell-ish argument parsing and substitution.
- `src/hagent/skills/loader.py` — scan skill directories, parse `SKILL.md`, enforce size/path rules, dedupe by skill name with later sources winning.
- `src/hagent/skills/sources.py` — compute Hagent default skill source list from user home and workspace.
- `src/hagent/skills/registry.py` — immutable registry and lookup helpers used by middleware, tools, CLI, and subagent compilation.
- `src/hagent/skills/middleware.py` — Hagent model prompt middleware that lists available skills and instructs use of `Skill`.
- `src/hagent/skills/tool.py` — LangChain `StructuredTool` factory for `Skill`.

Modify:

- `src/hagent/core.py` — create a skill registry, register the `Skill` tool, add `HagentSkillsMiddleware`, pass the registry to subagent compilation, and attach `_hagent_skill_registry` to the agent.
- `src/hagent/config.py` — add `HAGENT_AGENT_NAME` and `HAGENT_SKILLS_PATHS` handling.
- `src/hagent/subagents/types.py` — add `skills: NotRequired[list[str]]`.
- `src/hagent/subagents/loader.py` — stop ignoring `skills`; parse it into the spec.
- `src/hagent/subagents/compiler.py` — accept `skill_registry` and append preloaded skill content to subagent prompts.
- `src/hagent/server/routers/messages.py` — expand `/skill:<name> [args]` messages before invoking the agent.
- `src/hagent/cli.py` — add `hagent demo --skill <name>` and expand the skill prompt before `invoke`.
- `prompts/hagent_base.zh.md` — add a concise `# Skills` section that matches Hagent's `Skill` tool.
- `prompts/decisions.md` — record the prompt change and why DeepAgents' default `read_file` wording is not used.

Test:

- `tests/test_skills_arguments.py`
- `tests/test_skills_loader.py`
- `tests/test_skills_sources.py`
- `tests/test_skills_registry.py`
- `tests/test_skill_tool.py`
- `tests/test_skills_middleware.py`
- `tests/test_skills_registration.py`
- `tests/test_subagents_loader.py`
- `tests/test_subagents_compiler.py`
- `tests/test_cli.py`
- `tests/server/test_messages_api.py`
- `tests/test_core.py`

---

### Task 1: Skill Models

**Files:**
- Create: `src/hagent/skills/__init__.py`
- Create: `src/hagent/skills/models.py`
- Test: `tests/test_skills_loader.py`

- [ ] **Step 1: Write failing model/loader-facing tests**

Create `tests/test_skills_loader.py` with the first model-level expectations:

```python
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from hagent.skills.loader import load_skills_from_sources
from hagent.skills.models import SkillInvocation, SkillMetadata


def _write_skill(root: Path, name: str, frontmatter: dict, body: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False)
    path = skill_dir / "SKILL.md"
    path.write_text(f"---\n{fm}---\n{body}", encoding="utf-8")
    return path


def test_skill_metadata_uses_directory_name_as_invocation_name(tmp_path: Path) -> None:
    path = _write_skill(
        tmp_path,
        "code-review",
        {
            "name": "Code Review",
            "description": "Review code changes for correctness.",
            "allowed-tools": "Read Grep Bash(pytest:*)",
            "argument-hint": "[scope]",
            "arguments": "scope focus",
            "when_to_use": "Use when asked to review diffs.",
            "version": "1.2.3",
            "model": "inherit",
            "disable-model-invocation": False,
            "user-invocable": True,
            "context": "fork",
            "agent": "Plan",
            "paths": "src/** tests/**",
        },
        "# Code Review\nFollow this review workflow.",
    )

    registry = load_skills_from_sources([(tmp_path, "Project Claude")])
    skill = registry.require("code-review")

    assert skill.name == "code-review"
    assert skill.display_name == "Code Review"
    assert skill.description == "Review code changes for correctness."
    assert skill.allowed_tools == ["Read", "Grep", "Bash(pytest:*)"]
    assert skill.argument_hint == "[scope]"
    assert skill.argument_names == ["scope", "focus"]
    assert skill.when_to_use == "Use when asked to review diffs."
    assert skill.version == "1.2.3"
    assert skill.model is None
    assert skill.disable_model_invocation is False
    assert skill.user_invocable is True
    assert skill.execution_context == "fork"
    assert skill.agent == "Plan"
    assert skill.paths == ["src/**", "tests/**"]
    assert skill.skill_file == path.resolve()
    assert skill.base_dir == path.parent.resolve()
    assert skill.source_label == "Project Claude"


def test_skill_invocation_rejects_empty_skill_name() -> None:
    with pytest.raises(ValidationError):
        SkillInvocation(skill=" ")


def test_skill_metadata_rejects_unknown_extra_fields(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        SkillMetadata(
            name="x",
            description="x",
            skill_file=tmp_path / "x" / "SKILL.md",
            base_dir=tmp_path / "x",
            source_label="Test",
            unexpected=True,
        )
```

- [ ] **Step 2: Run the tests and verify the expected failure**

Run:

```bash
pytest tests/test_skills_loader.py::test_skill_metadata_uses_directory_name_as_invocation_name -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hagent.skills'`.

- [ ] **Step 3: Create public package exports**

Create `src/hagent/skills/__init__.py`:

```python
from hagent.skills.loader import load_skills_from_sources
from hagent.skills.models import SkillInvocation, SkillInvocationResult, SkillMetadata
from hagent.skills.registry import SkillRegistry
from hagent.skills.tool import create_skill_tool

__all__ = [
    "SkillInvocation",
    "SkillInvocationResult",
    "SkillMetadata",
    "SkillRegistry",
    "create_skill_tool",
    "load_skills_from_sources",
]
```

- [ ] **Step 4: Implement skill models**

Create `src/hagent/skills/models.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SkillMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    skill_file: Path
    base_dir: Path
    source_label: str
    display_name: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    argument_hint: str | None = None
    argument_names: list[str] = Field(default_factory=list)
    when_to_use: str | None = None
    version: str | None = None
    model: str | None = None
    disable_model_invocation: bool = False
    user_invocable: bool = True
    execution_context: Literal["fork"] | None = None
    agent: str | None = None
    paths: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    license: str | None = None
    compatibility: str | None = None

    @field_validator("name", "description", "source_label")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "value must not be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("display_name", "argument_hint", "when_to_use", "version", "model", "agent", "license", "compatibility")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class SkillInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: str
    args: str | None = None

    @field_validator("skill")
    @classmethod
    def _normalize_skill(cls, value: str) -> str:
        stripped = value.strip()
        if stripped.startswith("/"):
            stripped = stripped[1:]
        if not stripped:
            msg = "skill must not be empty"
            raise ValueError(msg)
        return stripped


class SkillInvocationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    commandName: str
    status: Literal["inline"] = "inline"
    content: str | None = None
    allowedTools: list[str] | None = None
    model: str | None = None
    error: str | None = None


def stringify_metadata(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}
```

- [ ] **Step 5: Run model tests and observe the next missing module**

Run:

```bash
pytest tests/test_skills_loader.py::test_skill_invocation_rejects_empty_skill_name tests/test_skills_loader.py::test_skill_metadata_rejects_unknown_extra_fields -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hagent.skills.loader'` for import collection, while the model code is ready for the loader task.

- [ ] **Step 6: Commit**

```bash
git add src/hagent/skills/__init__.py src/hagent/skills/models.py tests/test_skills_loader.py
git commit -m "feat(skills): add skill metadata models"
```

---

### Task 2: Claude-Compatible Argument Substitution

**Files:**
- Create: `src/hagent/skills/arguments.py`
- Test: `tests/test_skills_arguments.py`

- [ ] **Step 1: Write failing argument tests**

Create `tests/test_skills_arguments.py`:

```python
from hagent.skills.arguments import parse_argument_names, parse_arguments, substitute_arguments


def test_parse_arguments_handles_shell_quotes() -> None:
    assert parse_arguments('src "hello world" $HOME') == ["src", "hello world", "$HOME"]


def test_parse_argument_names_accepts_string_and_list() -> None:
    assert parse_argument_names("scope focus 123") == ["scope", "focus"]
    assert parse_argument_names(["scope", "", "2", "focus"]) == ["scope", "focus"]


def test_substitute_arguments_replaces_claude_code_placeholders() -> None:
    content = "all=$ARGUMENTS first=$ARGUMENTS[0] second=$1 named=$scope"
    rendered = substitute_arguments(
        content,
        'src "unit tests"',
        argument_names=["scope", "focus"],
    )
    assert rendered == 'all=src "unit tests" first=src second=unit tests named=src'


def test_substitute_arguments_appends_when_no_placeholder() -> None:
    assert substitute_arguments("Review carefully.", "src") == "Review carefully.\n\nARGUMENTS: src"


def test_substitute_arguments_leaves_content_when_args_missing() -> None:
    assert substitute_arguments("Review $ARGUMENTS.") == "Review $ARGUMENTS."
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_skills_arguments.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hagent.skills.arguments'`.

- [ ] **Step 3: Implement argument helpers**

Create `src/hagent/skills/arguments.py`:

```python
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

    for index, name in enumerate(argument_names):
        content = re.sub(rf"\${re.escape(name)}(?![\[\w])", parsed_args[index] if index < len(parsed_args) else "", content)

    content = re.sub(
        r"\$ARGUMENTS\[(\d+)\]",
        lambda match: parsed_args[int(match.group(1))] if int(match.group(1)) < len(parsed_args) else "",
        content,
    )
    content = re.sub(
        r"\$(\d+)(?!\w)",
        lambda match: parsed_args[int(match.group(1))] if int(match.group(1)) < len(parsed_args) else "",
        content,
    )
    content = content.replace("$ARGUMENTS", args)

    if content == original and append_if_no_placeholder and args:
        return f"{content}\n\nARGUMENTS: {args}"
    return content
```

- [ ] **Step 4: Run argument tests**

Run:

```bash
pytest tests/test_skills_arguments.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/hagent/skills/arguments.py tests/test_skills_arguments.py
git commit -m "feat(skills): add Claude-style argument substitution"
```

---

### Task 3: Skill Loader and Registry

**Files:**
- Create: `src/hagent/skills/loader.py`
- Create: `src/hagent/skills/registry.py`
- Modify: `src/hagent/skills/__init__.py`
- Test: `tests/test_skills_loader.py`
- Test: `tests/test_skills_registry.py`

- [ ] **Step 1: Extend loader tests**

Append to `tests/test_skills_loader.py`:

```python
def test_loader_uses_later_source_for_duplicate_skill_names(tmp_path: Path) -> None:
    user = tmp_path / "user"
    project = tmp_path / "project"
    _write_skill(user, "review", {"description": "User review skill."}, "# Review\nUser copy.")
    _write_skill(project, "review", {"description": "Project review skill."}, "# Review\nProject copy.")

    registry = load_skills_from_sources([(user, "User Claude"), (project, "Project Claude")])

    skill = registry.require("review")
    assert skill.description == "Project review skill."
    assert skill.source_label == "Project Claude"
    assert skill.skill_file == (project / "review" / "SKILL.md").resolve()


def test_loader_extracts_description_from_markdown_when_frontmatter_missing(tmp_path: Path) -> None:
    _write_skill(tmp_path, "summarize", {}, "# Summarize\nSummarize long notes into decisions.")

    skill = load_skills_from_sources([(tmp_path, "Project Claude")]).require("summarize")

    assert skill.description == "Summarize long notes into decisions."


def test_loader_skips_files_without_skill_md(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("not a skill", encoding="utf-8")
    (tmp_path / "empty").mkdir()

    registry = load_skills_from_sources([(tmp_path, "Project Claude")])

    assert registry.list() == []


def test_loader_skips_oversized_skill_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import hagent.skills.loader as loader

    monkeypatch.setattr(loader, "MAX_SKILL_FILE_SIZE", 10)
    _write_skill(tmp_path, "large", {"description": "Too large."}, "01234567890")

    registry = load_skills_from_sources([(tmp_path, "Project Claude")])

    assert registry.list() == []
```

Create `tests/test_skills_registry.py`:

```python
from pathlib import Path

from hagent.skills.models import SkillMetadata
from hagent.skills.registry import SkillRegistry


def _skill(name: str, tmp_path: Path) -> SkillMetadata:
    base = tmp_path / name
    return SkillMetadata(
        name=name,
        description=f"{name} description",
        skill_file=base / "SKILL.md",
        base_dir=base,
        source_label="Test",
    )


def test_registry_lists_skills_sorted_by_name(tmp_path: Path) -> None:
    registry = SkillRegistry([_skill("zeta", tmp_path), _skill("alpha", tmp_path)])

    assert [skill.name for skill in registry.list()] == ["alpha", "zeta"]


def test_registry_lookup_accepts_leading_slash(tmp_path: Path) -> None:
    registry = SkillRegistry([_skill("review", tmp_path)])

    assert registry.get("/review").name == "review"
    assert registry.require("review").name == "review"


def test_registry_require_raises_clear_key_error(tmp_path: Path) -> None:
    registry = SkillRegistry([_skill("review", tmp_path)])

    try:
        registry.require("missing")
    except KeyError as exc:
        assert str(exc) == "\"Unknown skill: missing\""
    else:
        raise AssertionError("require must raise for missing skills")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_skills_loader.py tests/test_skills_registry.py -v
```

Expected: FAIL with missing `hagent.skills.loader` and `hagent.skills.registry`.

- [ ] **Step 3: Implement registry**

Create `src/hagent/skills/registry.py`:

```python
from __future__ import annotations

from collections.abc import Iterable

from hagent.skills.models import SkillMetadata


class SkillRegistry:
    def __init__(self, skills: Iterable[SkillMetadata] = ()) -> None:
        self._by_name = {skill.name: skill for skill in skills}

    def list(self) -> list[SkillMetadata]:
        return [self._by_name[name] for name in sorted(self._by_name)]

    def get(self, name: str) -> SkillMetadata | None:
        normalized = name.strip()
        if normalized.startswith("/"):
            normalized = normalized[1:]
        return self._by_name.get(normalized)

    def require(self, name: str) -> SkillMetadata:
        skill = self.get(name)
        if skill is None:
            normalized = name.strip()
            if normalized.startswith("/"):
                normalized = normalized[1:]
            msg = f"Unknown skill: {normalized}"
            raise KeyError(msg)
        return skill

    def __bool__(self) -> bool:
        return bool(self._by_name)
```

- [ ] **Step 4: Implement loader**

Create `src/hagent/skills/loader.py`:

```python
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

from hagent.skills.arguments import parse_argument_names
from hagent.skills.models import SkillMetadata, stringify_metadata
from hagent.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)

MAX_SKILL_FILE_SIZE = 10 * 1024 * 1024
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)

SkillSource = tuple[Path, str]


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _split_words(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip(",") for part in value.split() if part.strip(",")]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def _extract_frontmatter(text: str, path: Path) -> tuple[dict[str, Any], str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        loaded = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as err:
        logger.warning("invalid skill frontmatter in %s: %s", path, err)
        return {}, match.group(2)
    if not isinstance(loaded, dict):
        logger.warning("skill frontmatter in %s is not a mapping", path)
        return {}, match.group(2)
    return loaded, match.group(2)


def _extract_description(markdown: str, fallback_name: str) -> str:
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        return line
    return f"Skill {fallback_name}"


def _parse_skill(path: Path, source_label: str) -> SkillMetadata | None:
    try:
        if path.stat().st_size > MAX_SKILL_FILE_SIZE:
            logger.warning("skipping oversized skill file %s", path)
            return None
        text = path.read_text(encoding="utf-8-sig")
    except OSError as err:
        logger.warning("failed to read skill file %s: %s", path, err)
        return None

    frontmatter, body = _extract_frontmatter(text, path)
    skill_name = path.parent.name
    raw_description = frontmatter.get("description")
    description = str(raw_description).strip() if raw_description is not None else _extract_description(body, skill_name)
    model = frontmatter.get("model")
    model_value = None if model in (None, "inherit") else str(model)
    execution_context = "fork" if frontmatter.get("context") == "fork" else None

    return SkillMetadata(
        name=skill_name,
        display_name=str(frontmatter["name"]).strip() if frontmatter.get("name") is not None else None,
        description=description,
        skill_file=path.resolve(),
        base_dir=path.parent.resolve(),
        source_label=source_label,
        allowed_tools=_split_words(frontmatter.get("allowed-tools")),
        argument_hint=str(frontmatter["argument-hint"]).strip() if frontmatter.get("argument-hint") is not None else None,
        argument_names=parse_argument_names(frontmatter.get("arguments")),
        when_to_use=str(frontmatter["when_to_use"]).strip() if frontmatter.get("when_to_use") is not None else None,
        version=str(frontmatter["version"]).strip() if frontmatter.get("version") is not None else None,
        model=model_value,
        disable_model_invocation=_parse_bool(frontmatter.get("disable-model-invocation"), default=False),
        user_invocable=_parse_bool(frontmatter.get("user-invocable"), default=True),
        execution_context=execution_context,
        agent=str(frontmatter["agent"]).strip() if frontmatter.get("agent") is not None else None,
        paths=_split_words(frontmatter.get("paths")),
        metadata=stringify_metadata(frontmatter.get("metadata")),
        license=str(frontmatter["license"]).strip() if frontmatter.get("license") is not None else None,
        compatibility=str(frontmatter["compatibility"]).strip() if frontmatter.get("compatibility") is not None else None,
    )


def load_skills_from_sources(sources: Iterable[SkillSource]) -> SkillRegistry:
    by_name: dict[str, SkillMetadata] = {}
    for source_root, source_label in sources:
        root = Path(source_root).expanduser()
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir(), key=lambda p: p.name):
            if not entry.is_dir() and not entry.is_symlink():
                continue
            skill_file = entry / "SKILL.md"
            if not skill_file.is_file():
                continue
            skill = _parse_skill(skill_file, source_label)
            if skill is not None:
                by_name[skill.name] = skill
    return SkillRegistry(by_name.values())
```

- [ ] **Step 5: Run loader and registry tests**

Run:

```bash
pytest tests/test_skills_loader.py tests/test_skills_registry.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/hagent/skills/loader.py src/hagent/skills/registry.py src/hagent/skills/__init__.py tests/test_skills_loader.py tests/test_skills_registry.py
git commit -m "feat(skills): load local skill directories"
```

---

### Task 4: Default Skill Sources

**Files:**
- Create: `src/hagent/skills/sources.py`
- Modify: `src/hagent/config.py`
- Test: `tests/test_skills_sources.py`

- [ ] **Step 1: Write failing source tests**

Create `tests/test_skills_sources.py`:

```python
from pathlib import Path

from hagent.skills.sources import default_skill_sources, parse_skill_source_env


def test_parse_skill_source_env_uses_paths_and_labels(tmp_path: Path) -> None:
    one = tmp_path / "one"
    two = tmp_path / "two"

    assert parse_skill_source_env(f"{one}:One Skills,{two}:Two Skills") == [
        (one, "One Skills"),
        (two, "Two Skills"),
    ]


def test_default_skill_sources_order_lowest_to_highest(tmp_path: Path) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "repo"

    sources = default_skill_sources(workspace=workspace, home=home, agent_name="hagent")

    assert sources == [
        (home / ".deepagents" / "hagent" / "skills", "User DeepAgents"),
        (home / ".agents" / "skills", "User Agents"),
        (home / ".claude" / "skills", "User Claude"),
        (workspace / ".deepagents" / "skills", "Project DeepAgents"),
        (workspace / ".agents" / "skills", "Project Agents"),
        (workspace / ".claude" / "skills", "Project Claude"),
    ]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_skills_sources.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hagent.skills.sources'`.

- [ ] **Step 3: Add config constants**

Modify `src/hagent/config.py` near existing defaults:

```python
DEFAULT_AGENT_NAME = "hagent"
```

Modify `HagentConfig`:

```python
@dataclass(frozen=True)
class HagentConfig:
    model: str
    langsmith_tracing: bool
    bash_permissions: BashPermissionConfig = field(
        default_factory=lambda: BashPermissionConfig(allow_rules=DEFAULT_BASH_ALLOW_RULES)
    )
    max_tokens: int | None = None
    agent_name: str = DEFAULT_AGENT_NAME
    skills_paths: str | None = None
```

Modify `from_env`:

```python
    @classmethod
    def from_env(cls) -> "HagentConfig":
        return cls(
            model=os.environ.get("HAGENT_MODEL", DEFAULT_MODEL),
            langsmith_tracing=os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true",
            max_tokens=_positive_int_from_env("HAGENT_MAX_TOKENS"),
            agent_name=os.environ.get("HAGENT_AGENT_NAME", DEFAULT_AGENT_NAME),
            skills_paths=os.environ.get("HAGENT_SKILLS_PATHS") or None,
        )
```

- [ ] **Step 4: Implement source discovery**

Create `src/hagent/skills/sources.py`:

```python
from __future__ import annotations

from pathlib import Path

SkillSource = tuple[Path, str]


def parse_skill_source_env(raw: str | None) -> list[SkillSource]:
    if raw is None or not raw.strip():
        return []
    sources: list[SkillSource] = []
    for chunk in raw.split(","):
        item = chunk.strip()
        if not item:
            continue
        if ":" in item:
            path_text, label = item.rsplit(":", 1)
            sources.append((Path(path_text).expanduser(), label.strip() or "Custom"))
        else:
            sources.append((Path(item).expanduser(), "Custom"))
    return sources


def default_skill_sources(*, workspace: Path, home: Path | None = None, agent_name: str = "hagent") -> list[SkillSource]:
    user_home = Path.home() if home is None else home
    root = workspace.resolve()
    return [
        (user_home / ".deepagents" / agent_name / "skills", "User DeepAgents"),
        (user_home / ".agents" / "skills", "User Agents"),
        (user_home / ".claude" / "skills", "User Claude"),
        (root / ".deepagents" / "skills", "Project DeepAgents"),
        (root / ".agents" / "skills", "Project Agents"),
        (root / ".claude" / "skills", "Project Claude"),
    ]


def resolve_skill_sources(*, workspace: Path, agent_name: str, env_value: str | None) -> list[SkillSource]:
    explicit = parse_skill_source_env(env_value)
    if explicit:
        return explicit
    return default_skill_sources(workspace=workspace, agent_name=agent_name)
```

- [ ] **Step 5: Run source tests**

Run:

```bash
pytest tests/test_skills_sources.py -v
```

Expected: PASS.

- [ ] **Step 6: Run config smoke tests**

Run:

```bash
pytest tests/test_core.py::test_create_hagent_returns_runnable -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/hagent/config.py src/hagent/skills/sources.py tests/test_skills_sources.py
git commit -m "feat(skills): discover default skill sources"
```

---

### Task 5: Skill Tool

**Files:**
- Create: `src/hagent/skills/tool.py`
- Test: `tests/test_skill_tool.py`

- [ ] **Step 1: Write failing Skill tool tests**

Create `tests/test_skill_tool.py`:

```python
from pathlib import Path

from hagent.skills.loader import load_skills_from_sources
from hagent.skills.tool import create_skill_tool, render_skill_prompt


def _skill(root: Path, name: str, body: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: Test skill.\narguments: scope focus\nallowed-tools: Read Bash(pytest:*)\n---\n"
        + body,
        encoding="utf-8",
    )


def test_render_skill_prompt_adds_base_directory_and_substitutes_args(tmp_path: Path) -> None:
    _skill(tmp_path, "review", "Review $scope with $focus in ${CLAUDE_SKILL_DIR}.")
    registry = load_skills_from_sources([(tmp_path, "Project Claude")])
    skill = registry.require("review")

    rendered = render_skill_prompt(skill, 'src "unit tests"', session_id="session-1")

    assert rendered.startswith(f"Base directory for this skill: {skill.base_dir}\n\n")
    assert f"Review src with unit tests in {skill.base_dir}." in rendered


def test_skill_tool_returns_expanded_content(tmp_path: Path) -> None:
    _skill(tmp_path, "review", "Review $ARGUMENTS.")
    registry = load_skills_from_sources([(tmp_path, "Project Claude")])
    tool = create_skill_tool(registry, session_id="session-1")

    result = tool.invoke({"skill": "review", "args": "src"})

    assert result["success"] is True
    assert result["commandName"] == "review"
    assert result["allowedTools"] == ["Read", "Bash(pytest:*)"]
    assert "Review src." in result["content"]


def test_skill_tool_rejects_unknown_skill(tmp_path: Path) -> None:
    tool = create_skill_tool(load_skills_from_sources([(tmp_path, "Project Claude")]))

    result = tool.invoke({"skill": "missing"})

    assert result == {
        "success": False,
        "commandName": "missing",
        "status": "inline",
        "error": "Unknown skill: missing",
    }


def test_skill_tool_respects_disable_model_invocation(tmp_path: Path) -> None:
    skill_dir = tmp_path / "secret"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: Secret skill.\ndisable-model-invocation: true\n---\n# Secret",
        encoding="utf-8",
    )
    tool = create_skill_tool(load_skills_from_sources([(tmp_path, "Project Claude")]))

    result = tool.invoke({"skill": "secret"})

    assert result == {
        "success": False,
        "commandName": "secret",
        "status": "inline",
        "error": "Skill secret cannot be used with Skill tool due to disable-model-invocation",
    }
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_skill_tool.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hagent.skills.tool'`.

- [ ] **Step 3: Implement Skill tool**

Create `src/hagent/skills/tool.py`:

```python
from __future__ import annotations

import os

from langchain_core.tools import StructuredTool

from hagent.skills.arguments import substitute_arguments
from hagent.skills.models import SkillInvocation, SkillInvocationResult, SkillMetadata
from hagent.skills.registry import SkillRegistry

TOOL_NAME = "Skill"


def render_skill_prompt(skill: SkillMetadata, args: str | None = None, *, session_id: str | None = None) -> str:
    text = skill.skill_file.read_text(encoding="utf-8-sig")
    if text.startswith("---"):
        parts = text.split("---", 2)
        body = parts[2].lstrip() if len(parts) == 3 else text
    else:
        body = text
    rendered = f"Base directory for this skill: {skill.base_dir}\n\n{body}"
    rendered = substitute_arguments(rendered, args, argument_names=skill.argument_names)
    rendered = rendered.replace("${CLAUDE_SKILL_DIR}", str(skill.base_dir))
    rendered = rendered.replace("${HAGENT_SKILL_DIR}", str(skill.base_dir))
    rendered = rendered.replace("${CLAUDE_SESSION_ID}", session_id or os.environ.get("HAGENT_SESSION_ID", ""))
    return rendered


def create_skill_tool(registry: SkillRegistry, *, session_id: str | None = None) -> StructuredTool:
    def _invoke(skill: str, args: str | None = None) -> dict:
        invocation = SkillInvocation(skill=skill, args=args)
        found = registry.get(invocation.skill)
        if found is None:
            return SkillInvocationResult(
                success=False,
                commandName=invocation.skill,
                error=f"Unknown skill: {invocation.skill}",
            ).model_dump(exclude_none=True)
        if found.disable_model_invocation:
            return SkillInvocationResult(
                success=False,
                commandName=found.name,
                error=f"Skill {found.name} cannot be used with Skill tool due to disable-model-invocation",
            ).model_dump(exclude_none=True)
        content = render_skill_prompt(found, invocation.args, session_id=session_id)
        return SkillInvocationResult(
            success=True,
            commandName=found.name,
            content=content,
            allowedTools=found.allowed_tools or None,
            model=found.model,
        ).model_dump(exclude_none=True)

    return StructuredTool.from_function(
        func=_invoke,
        name=TOOL_NAME,
        description=(
            "Execute a skill within the main conversation. Use this before answering "
            "when the user's request matches an available skill."
        ),
        args_schema=SkillInvocation,
    )
```

- [ ] **Step 4: Run Skill tool tests**

Run:

```bash
pytest tests/test_skill_tool.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/hagent/skills/tool.py tests/test_skill_tool.py
git commit -m "feat(skills): add Skill tool"
```

---

### Task 6: Skills Middleware Catalog

**Files:**
- Create: `src/hagent/skills/middleware.py`
- Test: `tests/test_skills_middleware.py`

- [ ] **Step 1: Write failing middleware tests**

Create `tests/test_skills_middleware.py`:

```python
from pathlib import Path

from hagent.skills.loader import load_skills_from_sources
from hagent.skills.middleware import format_skills_catalog


def _skill(root: Path, name: str, description: str, when_to_use: str | None = None) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    when_line = f"when_to_use: {when_to_use}\n" if when_to_use else ""
    (skill_dir / "SKILL.md").write_text(
        f"---\ndescription: {description}\n{when_line}---\n# {name}\n",
        encoding="utf-8",
    )


def test_format_skills_catalog_lists_name_description_and_path(tmp_path: Path) -> None:
    _skill(tmp_path, "review", "Review code.", "Use for diffs.")
    registry = load_skills_from_sources([(tmp_path, "Project Claude")])

    catalog = format_skills_catalog(registry)

    assert "## Skills" in catalog
    assert "- review: Review code. - Use for diffs." in catalog
    assert "When a skill matches the user's request, invoke `Skill` before answering." in catalog
    assert str((tmp_path / "review" / "SKILL.md").resolve()) in catalog


def test_format_skills_catalog_empty_registry_is_short() -> None:
    registry = load_skills_from_sources([])

    assert format_skills_catalog(registry) == ""
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_skills_middleware.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'hagent.skills.middleware'`.

- [ ] **Step 3: Implement skills middleware**

Create `src/hagent/skills/middleware.py`:

```python
from __future__ import annotations

from typing import Any

from langchain.agents.middleware import AgentMiddleware

from hagent.skills.registry import SkillRegistry

MAX_LISTING_DESC_CHARS = 250


def _description(skill: Any) -> str:
    text = skill.description
    if skill.when_to_use:
        text = f"{text} - {skill.when_to_use}"
    if len(text) > MAX_LISTING_DESC_CHARS:
        return text[: MAX_LISTING_DESC_CHARS - 1] + "…"
    return text


def format_skills_catalog(registry: SkillRegistry) -> str:
    skills = registry.list()
    if not skills:
        return ""
    lines = [
        "## Skills",
        "",
        "Available skills are listed below. When a skill matches the user's request, invoke `Skill` before answering.",
        "Do not mention a skill without invoking it. If a skill has already been loaded in the current turn, follow its instructions directly.",
        "",
    ]
    for skill in skills:
        hidden = " (hidden from user slash invocation)" if not skill.user_invocable else ""
        lines.append(f"- {skill.name}: {_description(skill)}{hidden}")
        lines.append(f"  -> `Skill` name: `{skill.name}`")
        lines.append(f"  -> Source: {skill.source_label}; file: `{skill.skill_file}`")
    return "\n".join(lines)


class HagentSkillsMiddleware(AgentMiddleware):
    name = "HagentSkills"

    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        catalog = format_skills_catalog(self.registry)
        if not catalog:
            return handler(request)
        system_message = request.system_message
        if system_message is None:
            return handler(request.override(system_message=catalog))
        content = getattr(system_message, "content", "")
        updated = system_message.model_copy(update={"content": f"{content}\n\n{catalog}"})
        return handler(request.override(system_message=updated))

    async def awrap_model_call(self, request: Any, handler: Any) -> Any:
        catalog = format_skills_catalog(self.registry)
        if not catalog:
            return await handler(request)
        system_message = request.system_message
        if system_message is None:
            return await handler(request.override(system_message=catalog))
        content = getattr(system_message, "content", "")
        updated = system_message.model_copy(update={"content": f"{content}\n\n{catalog}"})
        return await handler(request.override(system_message=updated))
```

- [ ] **Step 4: Run middleware tests**

Run:

```bash
pytest tests/test_skills_middleware.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/hagent/skills/middleware.py tests/test_skills_middleware.py
git commit -m "feat(skills): add model skills catalog"
```

---

### Task 7: Wire Skills Into `create_hagent`

**Files:**
- Modify: `src/hagent/core.py`
- Test: `tests/test_skills_registration.py`
- Test: `tests/test_core.py`

- [ ] **Step 1: Write failing registration tests**

Create `tests/test_skills_registration.py`:

```python
from pathlib import Path

from deepagents.backends import FilesystemBackend

from hagent.config import HagentConfig
from hagent.core import create_hagent


def _write_skill(root: Path, name: str) -> None:
    skill_dir = root / ".claude" / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\ndescription: {name} skill.\n---\n# {name}\n",
        encoding="utf-8",
    )


def test_create_hagent_registers_skill_tool_and_middleware(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return type("FakeAgent", (), {})()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    _write_skill(tmp_path, "review")

    create_hagent(
        config=HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False),
        backend=FilesystemBackend(root_dir=tmp_path, virtual_mode=False),
        agents_dirs=[],
        disable_builtin_agents=True,
    )

    assert "Skill" in {tool.name for tool in captured["tools"]}
    assert any(type(middleware).__name__ == "HagentSkillsMiddleware" for middleware in captured["middleware"])
    assert "skills" not in captured


def test_create_hagent_attaches_skill_registry(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "hagent.core._create_deep_agent",
        lambda **_kwargs: type("FakeAgent", (), {})(),
    )
    _write_skill(tmp_path, "review")

    agent = create_hagent(
        config=HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False),
        backend=FilesystemBackend(root_dir=tmp_path, virtual_mode=False),
        agents_dirs=[],
        disable_builtin_agents=True,
    )

    registry = getattr(agent, "_hagent_skill_registry")
    assert registry.require("review").name == "review"
```

- [ ] **Step 2: Run registration tests and verify failure**

Run:

```bash
pytest tests/test_skills_registration.py -v
```

Expected: FAIL because `Skill` is not registered.

- [ ] **Step 3: Import skills helpers in core**

Modify `src/hagent/core.py` imports:

```python
from hagent.skills import create_skill_tool
from hagent.skills.loader import load_skills_from_sources
from hagent.skills.middleware import HagentSkillsMiddleware
from hagent.skills.sources import resolve_skill_sources
```

- [ ] **Step 4: Build registry and add tool/middleware**

Modify `create_hagent()` after `working_directory = requested_workspace`:

```python
    skill_sources = resolve_skill_sources(
        workspace=working_directory,
        agent_name=cfg.agent_name,
        env_value=cfg.skills_paths,
    )
    skill_registry = load_skills_from_sources(skill_sources)
    skill_tool = create_skill_tool(skill_registry, session_id=task_list_id)
```

Modify parent tools:

```python
    parent_tools: list[Any] = [bash_tool, *file_tools, *task_tools]
    if skill_registry:
        parent_tools.append(skill_tool)
    parent_tools.extend(list(extra_tools or []))
```

Modify middleware assembly:

```python
    middleware: list[Any] = [sanitize_anthropic_thinking_blocks_middleware]
    if skill_registry:
        middleware.insert(0, HagentSkillsMiddleware(skill_registry))
```

Modify `kwargs`:

```python
        middleware=middleware,
```

Do not pass DeepAgents `skills=` in `kwargs`.

Attach the registry near the existing task store attachment:

```python
    try:
        setattr(agent, "_hagent_skill_registry", skill_registry)
    except Exception:
        pass
```

- [ ] **Step 5: Run registration and core tests**

Run:

```bash
pytest tests/test_skills_registration.py tests/test_core.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/hagent/core.py tests/test_skills_registration.py
git commit -m "feat(skills): register Skill tool in Hagent"
```

---

### Task 8: Subagent Skill Preloading

**Files:**
- Modify: `src/hagent/subagents/types.py`
- Modify: `src/hagent/subagents/loader.py`
- Modify: `src/hagent/subagents/compiler.py`
- Modify: `src/hagent/core.py`
- Test: `tests/test_subagents_loader.py`
- Test: `tests/test_subagents_compiler.py`

- [ ] **Step 1: Update loader tests for `skills`**

Modify `tests/test_subagents_loader.py::test_unsupported_fields_are_logged_and_ignored` so `skills` is no longer expected to be ignored:

```python
    for key in ("permissionMode", "maxTurns", "mcpServers", "hooks", "memory", "isolation", "background"):
        assert key not in specs[0]
        assert key in caplog.text
    assert specs[0]["skills"] == ["a"]
```

Add a focused test:

```python
def test_load_with_skills(tmp_path):
    _write(
        tmp_path / "planner.md",
        {"name": "planner", "description": "规划代理", "skills": ["writing-plans", "review"]},
        "规划代理 system prompt。",
    )
    specs = load_markdown_agents([tmp_path])
    assert specs[0]["skills"] == ["writing-plans", "review"]
```

- [ ] **Step 2: Add compiler preload test**

Append to `tests/test_subagents_compiler.py`:

```python
from hagent.skills.models import SkillMetadata
from hagent.skills.registry import SkillRegistry


def test_compile_preloads_declared_skills(monkeypatch, tmp_path):
    captured = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.subagents.compiler.create_agent", fake_create_agent)
    monkeypatch.setattr("hagent.subagents.compiler.resolve_model", lambda m: m)

    skill_dir = tmp_path / "review"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: Review code.\n---\n# Review\nRead the diff.",
        encoding="utf-8",
    )
    registry = SkillRegistry([
        SkillMetadata(
            name="review",
            description="Review code.",
            skill_file=skill_dir / "SKILL.md",
            base_dir=skill_dir,
            source_label="Test",
        )
    ])

    compile_subagent_runnable(
        {"name": "x", "description": "y", "system_prompt": "base", "tools": ["*"], "skills": ["review"]},
        parent_model="anthropic:claude-sonnet-4-6",
        parent_tools=[_tool("Read")],
        skill_registry=registry,
    )

    assert "base" in captured["system_prompt"]
    assert "Preloaded skill: review" in captured["system_prompt"]
    assert "Base directory for this skill:" in captured["system_prompt"]
    assert "Read the diff." in captured["system_prompt"]
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
pytest tests/test_subagents_loader.py::test_load_with_skills tests/test_subagents_compiler.py::test_compile_preloads_declared_skills -v
```

Expected: FAIL because `skills` is ignored and `compile_subagent_runnable()` has no `skill_registry` parameter.

- [ ] **Step 4: Update subagent type**

Modify `src/hagent/subagents/types.py`:

```python
    skills: NotRequired[list[str]]
```

- [ ] **Step 5: Parse `skills` in subagent loader**

Modify `_IGNORED_FRONTMATTER_KEYS` in `src/hagent/subagents/loader.py` by removing `"skills"`.

Modify `_RECOGNIZED_FRONTMATTER_KEYS`:

```python
    {"name", "description", "tools", "disallowedTools", "model", "color", "skills"}
```

Add parsing after `tools`:

```python
    skills = fm.get("skills")
    if isinstance(skills, list):
        spec["skills"] = [str(s) for s in skills]
```

- [ ] **Step 6: Preload skills in compiler**

Modify `src/hagent/subagents/compiler.py` imports:

```python
from hagent.skills.registry import SkillRegistry
from hagent.skills.tool import render_skill_prompt
```

Add helper:

```python
def _with_preloaded_skills(system_prompt: str, spec: SubagentSpec, skill_registry: SkillRegistry | None) -> str:
    if skill_registry is None:
        return system_prompt
    names = spec.get("skills") or []
    if not names:
        return system_prompt
    sections = [system_prompt]
    for name in names:
        skill = skill_registry.get(name)
        if skill is None:
            logger.warning("subagent %s references unknown skill %s; skipped", spec.get("name", "<unnamed>"), name)
            continue
        sections.append(f"## Preloaded skill: {skill.name}\n\n{render_skill_prompt(skill, None)}")
    return "\n\n".join(sections)
```

Modify signature:

```python
def compile_subagent_runnable(
    spec: SubagentSpec,
    *,
    parent_model: str,
    parent_tools: list[Any],
    skill_registry: SkillRegistry | None = None,
) -> Any:
```

Modify `create_agent` call:

```python
        system_prompt=_with_preloaded_skills(spec["system_prompt"], spec, skill_registry),
```

Modify `compile_subagents()` in `src/hagent/subagents/registry.py` to accept and pass `skill_registry`:

```python
def compile_subagents(
    specs: list[SubagentSpec],
    *,
    parent_model: str,
    parent_tools: list[Any],
    skill_registry: SkillRegistry | None = None,
) -> dict[str, Any]:
    return {
        spec["name"]: compile_subagent_runnable(
            spec,
            parent_model=parent_model,
            parent_tools=parent_tools,
            skill_registry=skill_registry,
        )
        for spec in specs
    }
```

Add `SkillRegistry` import to `src/hagent/subagents/registry.py`.

- [ ] **Step 7: Pass registry from core**

Modify `src/hagent/core.py`:

```python
        runnables = compile_subagents(
            specs,
            parent_model=cfg.model,
            parent_tools=parent_tools,
            skill_registry=skill_registry,
        )
```

- [ ] **Step 8: Run subagent tests**

Run:

```bash
pytest tests/test_subagents_loader.py tests/test_subagents_compiler.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/hagent/subagents/types.py src/hagent/subagents/loader.py src/hagent/subagents/compiler.py src/hagent/subagents/registry.py src/hagent/core.py tests/test_subagents_loader.py tests/test_subagents_compiler.py
git commit -m "feat(skills): preload skills for subagents"
```

---

### Task 9: CLI and Server Direct Skill Invocation

**Files:**
- Modify: `src/hagent/cli.py`
- Modify: `src/hagent/server/routers/messages.py`
- Test: `tests/test_cli.py`
- Test: `tests/server/test_messages_api.py`

- [ ] **Step 1: Write CLI tests**

Create or append `tests/test_cli.py`:

```python
from hagent.cli import _build_skill_message


def test_build_skill_message_expands_skill_and_args() -> None:
    message = _build_skill_message("review", "src tests")

    assert message == 'Use the `Skill` tool with skill: "review" and args: "src tests".'


def test_build_skill_message_without_args() -> None:
    message = _build_skill_message("review", None)

    assert message == 'Use the `Skill` tool with skill: "review".'
```

- [ ] **Step 2: Add server helper tests**

Append to `tests/server/test_messages_api.py`:

```python
from hagent.server.routers.messages import _expand_skill_message


def test_expand_skill_message_converts_skill_prefix() -> None:
    assert _expand_skill_message("/skill:review src tests") == 'Use the `Skill` tool with skill: "review" and args: "src tests".'


def test_expand_skill_message_leaves_normal_message_alone() -> None:
    assert _expand_skill_message("review this code") == "review this code"
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
pytest tests/test_cli.py tests/server/test_messages_api.py::test_expand_skill_message_converts_skill_prefix tests/server/test_messages_api.py::test_expand_skill_message_leaves_normal_message_alone -v
```

Expected: FAIL because helpers are missing.

- [ ] **Step 4: Add CLI `--skill`**

Modify `src/hagent/cli.py` parser:

```python
    demo.add_argument("--skill", default=None, help="Invoke a skill by name before handling the message")
    demo.add_argument("--skill-args", default=None, help="Arguments passed to --skill")
```

Add helper:

```python
def _build_skill_message(skill: str, args: str | None) -> str:
    normalized = skill.strip().lstrip("/")
    if args:
        return f'Use the `Skill` tool with skill: "{normalized}" and args: "{args}".'
    return f'Use the `Skill` tool with skill: "{normalized}".'
```

Modify `run_demo` signature and body:

```python
def run_demo(message: str, max_steps: int | None, skill: str | None = None, skill_args: str | None = None) -> int:
    from hagent.core import create_hagent

    agent = create_hagent()
    if skill:
        message = f"{_build_skill_message(skill, skill_args)}\n\nUser request: {message}"
```

Modify `main` call:

```python
        return run_demo(args.message, args.max_steps, args.skill, args.skill_args)
```

- [ ] **Step 5: Add server `/skill:` expansion**

Modify `src/hagent/server/routers/messages.py`:

```python
def _build_skill_message(skill: str, args: str | None) -> str:
    normalized = skill.strip().lstrip("/")
    if args:
        return f'Use the `Skill` tool with skill: "{normalized}" and args: "{args}".'
    return f'Use the `Skill` tool with skill: "{normalized}".'


def _expand_skill_message(content: str) -> str:
    stripped = content.strip()
    if not stripped.startswith("/skill:"):
        return content
    rest = stripped[len("/skill:") :].strip()
    if not rest:
        return content
    if " " in rest:
        skill, args = rest.split(" ", 1)
        return _build_skill_message(skill, args.strip() or None)
    return _build_skill_message(rest, None)
```

Modify `post_message`:

```python
    expanded_content = _expand_skill_message(body.content)
    return StreamingResponse(
        _stream_agent_events(agent, expanded_content, thread_id=sid),
        media_type="text/event-stream",
    )
```

- [ ] **Step 6: Run CLI/server tests**

Run:

```bash
pytest tests/test_cli.py tests/server/test_messages_api.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/hagent/cli.py src/hagent/server/routers/messages.py tests/test_cli.py tests/server/test_messages_api.py
git commit -m "feat(skills): add direct skill invocation entrypoints"
```

---

### Task 10: Prompt and Decisions Update

**Files:**
- Modify: `prompts/hagent_base.zh.md`
- Modify: `prompts/decisions.md`
- Test: `tests/test_core.py`

- [ ] **Step 1: Add prompt regression test**

Append to `tests/test_core.py`:

```python
def test_create_hagent_base_prompt_mentions_skill_tool(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()

    system_prompt = captured["system_prompt"]
    assert "`Skill`" in system_prompt
    assert "/<skill-name>" in system_prompt
    assert "read_file" not in system_prompt
```

- [ ] **Step 2: Run prompt test and verify failure**

Run:

```bash
pytest tests/test_core.py::test_create_hagent_base_prompt_mentions_skill_tool -v
```

Expected: FAIL because the base prompt does not mention `Skill`.

- [ ] **Step 3: Update base prompt**

Insert after the `# 使用 subagent` section in `prompts/hagent_base.zh.md`:

```markdown
# Skills

可用 skills 会以精简目录注入到系统提示中。它们是按需加载的专业工作流和上下文，不是始终要遵循的全局规则。

当用户请求与某个 skill 的描述匹配，或用户引用 `/<skill-name>`、`/skill:<skill-name>` 这类 slash skill 时，先调用 `Skill` 工具加载该 skill，再基于加载到的说明继续工作。不要只提到某个 skill 而不调用它。看到当前回合已经加载过的 skill 内容时，直接遵循内容，不要重复调用。

Skill 内容可能包含支持文件路径、脚本、模板或参考资料。优先使用 Hagent 可见工具名：`Read`、`Write`、`Edit`、`Bash`、`Agent`、`TaskCreate`、`TaskUpdate`、`TaskList`、`TaskGet`、`Skill`。不要调用 deepagents 内部工具名 `read_file` / `write_file` / `edit_file`。
```

- [ ] **Step 4: Update decisions**

Append to `prompts/decisions.md`:

```markdown
## 2026-05-15 skills 段落补充

在 `# 使用 subagent` 后新增 `# Skills` 段。原因：Hagent 现在暴露 Claude Code 风格 `Skill` 工具，并且技能目录由 Hagent 自管；不能直接使用 DeepAgents `SkillsMiddleware` 默认提示中的 `read_file(path, limit=1000)` 文案，因为 Hagent 对模型隐藏了 deepagents 内部 `read_file` / `write_file` / `edit_file` 工具。

- 模型应在匹配 skill 或用户引用 slash skill 时先调用 `Skill`。
- prompt 明确列出当前 Hagent 可见工具名，避免模型退回 deepagents 内部工具名。
- 该段不替代动态 skills catalog；动态 catalog 由 `HagentSkillsMiddleware` 注入。
```

- [ ] **Step 5: Run prompt check**

Run:

```bash
./scripts/check_base_prompt.sh
```

Expected: PASS.

- [ ] **Step 6: Run prompt regression test**

Run:

```bash
pytest tests/test_core.py::test_create_hagent_base_prompt_mentions_skill_tool -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add prompts/hagent_base.zh.md prompts/decisions.md tests/test_core.py
git commit -m "docs(prompt): teach Hagent to use skills"
```

---

### Task 11: End-to-End Verification

**Files:**
- Test: `tests/test_skills_registration.py`
- Test: `tests/test_skill_tool.py`
- Test: `tests/test_skills_middleware.py`
- Test: `tests/test_subagents_loader.py`
- Test: `tests/test_subagents_compiler.py`
- Test: full Python suite

- [ ] **Step 1: Run focused skills suite**

Run:

```bash
pytest tests/test_skills_arguments.py tests/test_skills_loader.py tests/test_skills_sources.py tests/test_skills_registry.py tests/test_skill_tool.py tests/test_skills_middleware.py tests/test_skills_registration.py -v
```

Expected: PASS.

- [ ] **Step 2: Run affected integration tests**

Run:

```bash
pytest tests/test_core.py tests/test_subagents_loader.py tests/test_subagents_compiler.py tests/test_claude_file_tools_registration.py tests/server/test_messages_api.py -v
```

Expected: PASS.

- [ ] **Step 3: Run all tests**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 4: Manual smoke with a local skill**

Create a local skill for manual validation with `apply_patch`:

```diff
*** Begin Patch
*** Add File: .claude/skills/hagent-smoke/SKILL.md
+---
+description: Use for Hagent skills smoke testing.
+allowed-tools: Read
+---
+
+# Hagent Smoke
+
+Reply with the exact phrase: Hagent skill smoke loaded.
*** End Patch
```

Run:

```bash
hagent demo --skill hagent-smoke "run the smoke skill" --max-steps 8
```

Expected final answer contains:

```text
Hagent skill smoke loaded.
```

- [ ] **Step 5: Remove manual smoke skill**

Use `apply_patch` to delete the manual smoke file:

```diff
*** Begin Patch
*** Delete File: .claude/skills/hagent-smoke/SKILL.md
*** End Patch
```

Then remove the empty directory:

```bash
rmdir .claude/skills/hagent-smoke
```

Expected: `.claude/skills/hagent-smoke` no longer exists, or `rmdir` reports the directory is already absent.

- [ ] **Step 6: Commit verification-only changes if any**

If Task 11 produced no code changes, do not create a commit. If test fixes were made during this task, inspect the changed files and commit only those fixes:

```bash
git status --short
git add src/hagent/skills tests
git commit -m "test(skills): verify skills integration"
```

---

## Self-Review

**Spec coverage:** The plan covers DeepAgents skill directory format, source layering, progressive disclosure, Claude Code `Skill` tool invocation, Claude Code argument substitution, Hagent tool-name alignment, subagent `skills` preload behavior, CLI direct invocation, server direct invocation, prompt changes, and verification.

**Intentional exclusions:** Plugin skills, bundled skills, MCP skill resources, remote skill search, hooks, inline shell execution in markdown, permission UI, and `paths` dynamic activation are out of first-version scope and the loader preserves the relevant fields where useful.

**Placeholder scan:** No task relies on unspecified implementation text; every code-changing step includes concrete code or exact replacement text.

**Type consistency:** `SkillMetadata`, `SkillInvocation`, `SkillInvocationResult`, `SkillRegistry`, `create_skill_tool`, `render_skill_prompt`, `HagentSkillsMiddleware`, and `resolve_skill_sources` names are consistent across tasks.
