from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

from hagent.subagents.builtin import BUILTIN_SUBAGENT_SPECS
from hagent.subagents.compiler import compile_subagent_runnable
from hagent.subagents.loader import load_markdown_agents
from hagent.subagents.types import SubagentSpec
from hagent.skills.materialize import SkillMaterializer
from hagent.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


def _parse_agents_paths_env(raw: str | None) -> list[Path]:
    """逗号分隔的目录列表（对齐 skills 的 HAGENT_SKILLS_PATHS）。空/None → []。"""
    if raw is None or not raw.strip():
        return []
    dirs: list[Path] = []
    for chunk in raw.split(","):
        item = chunk.strip()
        if item:
            dirs.append(Path(item).expanduser())
    return dirs


def _default_agents_dirs(workspace: Path, project_root: Path | None = None) -> list[Path]:
    workspace = Path(workspace)
    home = Path.home()
    # 后到的覆盖先到的：user → project（仓库） → workspace（会话工作目录）。
    # project_root 是 server 进程 CWD（仓库），与 LLM workspace（/tmp 或容器内）分离；
    # 不传时保持旧行为，不扫 CWD。
    dirs = [home / ".hagent" / "agents"]
    if project_root is not None:
        pr = Path(project_root)
        dirs += [pr / "agents", pr / ".hagent" / "agents"]
    dirs += [workspace / "agents", workspace / ".hagent" / "agents"]
    return dirs


def assemble_subagents(
    *,
    workspace: Path,
    project_root: Path | None = None,
    agents_paths: str | None = None,
    extra_subagents: Iterable[dict[str, Any]] | None = None,
    agents_dirs: Iterable[Path] | None = None,
    disable_builtin: bool = False,
) -> list[SubagentSpec]:
    """Merge built-in / markdown / extra_subagents, dedupe by name.

    Priority order (later wins): built-in → markdown → extra_subagents.

    Markdown discovery directory resolution (first non-None wins):
        agents_dirs (explicit) → agents_paths (env override) → defaults.

    Args:
        workspace: LLM-facing session working directory (在 sandbox 模式下是容器内
            路径 / host 模式是 /tmp 下的一次性目录)。用于计算默认 agents_dirs。
        project_root: server 进程的仓库目录（CWD），与 workspace 分离。传入后会把
            `<project_root>/agents` 与 `<project_root>/.hagent/agents` 纳入默认发现，
            让仓库里的 agent 文件被加载。None 时不扫仓库（保持旧行为）。
        agents_paths: 逗号分隔的目录列表（来自 HAGENT_AGENTS_PATHS）。非空时**替换**
            默认发现目录（对齐 skills 的 HAGENT_SKILLS_PATHS 语义）。
        extra_subagents: Iterable of raw spec dicts injected at the highest
            priority; missing required keys (name/description/system_prompt)
            log a warning and are skipped.
        agents_dirs: Iterable of directories to scan for markdown agent files.
            If None (default), falls back to agents_paths / defaults.
            Pass [] to explicitly skip all markdown discovery.
        disable_builtin: When True, skip the BUILTIN_SUBAGENT_SPECS layer entirely.
    """
    by_name: dict[str, SubagentSpec] = {}

    if not disable_builtin:
        for spec in BUILTIN_SUBAGENT_SPECS:
            by_name[spec["name"]] = dict(spec)  # type: ignore[assignment]

    if agents_dirs is not None:
        dirs = list(agents_dirs)
    elif _parse_agents_paths_env(agents_paths):
        dirs = _parse_agents_paths_env(agents_paths)
    else:
        dirs = _default_agents_dirs(workspace, project_root)
    for md_spec in load_markdown_agents(dirs):
        by_name[md_spec["name"]] = md_spec

    for raw in extra_subagents or []:
        if "name" not in raw or "description" not in raw or "system_prompt" not in raw:
            logger.warning("skipping malformed extra subagent: %s", raw)
            continue
        by_name[raw["name"]] = dict(raw)  # type: ignore[assignment]

    return list(by_name.values())


def compile_subagents(
    specs: Iterable[SubagentSpec],
    *,
    parent_model: str,
    retry_policy: Any | None = None,
    parent_tools: list[Any],
    skill_registry: SkillRegistry | None = None,
    materializer: SkillMaterializer | None = None,
    hook_runner: Any | None = None,
    hook_context: Any | None = None,
) -> dict[str, Any]:
    """Batch-compile SubagentSpecs into {name: runnable}."""
    runnables: dict[str, Any] = {}
    for spec in specs:
        runnables[spec["name"]] = compile_subagent_runnable(
            spec,
            parent_model=parent_model,
            retry_policy=retry_policy,
            parent_tools=parent_tools,
            skill_registry=skill_registry,
            materializer=materializer,
            hook_runner=hook_runner,
            hook_context=hook_context,
        )
    return runnables
