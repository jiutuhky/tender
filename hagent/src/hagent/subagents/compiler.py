from __future__ import annotations

import logging
import uuid
from typing import Any

from deepagents._models import resolve_model
from langchain.agents import create_agent

from hagent.hooks.config import load_hooks_dict
from hagent.tool_error_guard import ToolErrorGuardMiddleware
from hagent.hooks.context import HookContext
from hagent.hooks.events import HookEvent
from hagent.hooks.middleware import HagentHooksMiddleware
from hagent.hooks.runner import HookRunner
from hagent.sanitize import sanitize_anthropic_thinking_blocks_middleware
from hagent.tool_call_repair import repair_invalid_tool_calls_middleware
from hagent.skills.materialize import SkillMaterializer
from hagent.skills.registry import SkillRegistry
from hagent.skills.tool import render_skill_prompt
from hagent.subagents.tools import resolve_subagent_tools
from hagent.subagents.types import SubagentSpec, resolve_model_alias

logger = logging.getLogger(__name__)


def _with_preloaded_skills(
    system_prompt: str,
    spec: SubagentSpec,
    skill_registry: SkillRegistry | None,
    materializer: SkillMaterializer | None = None,
) -> str:
    if skill_registry is None:
        return system_prompt
    skill_names = spec.get("skills") or []
    if not skill_names:
        return system_prompt

    sections = [system_prompt]
    for skill_name in skill_names:
        skill = skill_registry.get(skill_name)
        if skill is None:
            logger.warning(
                "subagent %s references unknown skill %s; skipped",
                spec.get("name", "<unnamed>"),
                skill_name,
            )
            continue
        if skill.disable_model_invocation:
            logger.warning(
                "subagent %s references disabled skill %s; skipped",
                spec.get("name", "<unnamed>"),
                skill_name,
            )
            continue
        base_dir = materializer.materialize(skill) if materializer is not None else None
        sections.append(
            f"## Preloaded skill: {skill.name}\n\n"
            f"{render_skill_prompt(skill, None, base_dir=base_dir)}"
        )
    return "\n\n".join(sections)


def _subagent_hooks_middleware(
    spec: SubagentSpec,
    hook_runner: HookRunner | None,
    hook_context: HookContext | None,
) -> HagentHooksMiddleware | None:
    """为子代理构建专属 hooks middleware（全局 settings + frontmatter hooks 合并）。

    对齐 CC：子代理内的工具调用触发 PreToolUse 等事件（payload 带
    agent_id/agent_type），子代理停止触发 SubagentStop（frontmatter 的
    Stop 在 load_hooks_dict 中自动转换为 SubagentStop）。

    已知差异：agent_id 在编译期生成、同一 session 内每个 runnable 固定，
    而 CC 是每次子代理调用生成新 id。
    """
    name = spec.get("name", "<unnamed>")
    fm_hooks = spec.get("hooks")
    extra = load_hooks_dict(fm_hooks, source=f"agent:{name}") if fm_hooks else None
    agent_id = f"{name}-{uuid.uuid4().hex[:8]}"
    if hook_runner is not None:
        if (extra is None or extra.empty) and hook_runner.settings.empty:
            return None
        sub_runner = hook_runner.for_subagent(agent_id, name, extra=extra)
    else:
        if extra is None or extra.empty:
            return None
        if hook_context is None:
            logger.warning(
                "subagent %s 声明了 frontmatter hooks 但缺少 HookContext，忽略",
                name,
            )
            return None
        sub_runner = HookRunner(extra, hook_context.for_subagent(agent_id, name))
    return HagentHooksMiddleware(sub_runner, stop_event=HookEvent.SUBAGENT_STOP)


def compile_subagent_runnable(
    spec: SubagentSpec,
    *,
    parent_model: str,
    parent_tools: list[Any],
    skill_registry: SkillRegistry | None = None,
    materializer: SkillMaterializer | None = None,
    hook_runner: HookRunner | None = None,
    hook_context: HookContext | None = None,
) -> Any:
    """Compile a SubagentSpec into a langchain runnable.

    Model resolution: spec.model is resolved via resolve_model_alias; when it's
    None / missing / "inherit", the parent_model is used. Runtime model override
    (per-Agent-tool-invocation) is not supported in this release.

    hook_runner/hook_context: 全局 hooks 子系统的 runner 与上下文。传入时为
    子代理图注入专属 HagentHooksMiddleware（PreToolUse 等 + SubagentStop）。
    """
    resolved_tools, unknown = resolve_subagent_tools(dict(spec), parent_tools)
    if unknown:
        logger.warning(
            "subagent %s references unknown tool(s) %s; dropped",
            spec.get("name", "<unnamed>"),
            unknown,
        )

    spec_model = spec.get("model") if isinstance(spec.get("model"), str) else None
    resolved_model = resolve_model_alias(spec_model)
    model = resolved_model if resolved_model is not None else parent_model
    agent_model = resolve_model(model)

    # 与主图(core.py)保持一致:hooks 在头部(最外层),清洗中间件贴近模型调用。
    # 子代理图不继承主图 middleware(deepagents/subagents.mdx),漏挂清洗层曾导致
    # DeepSeek-via-Anthropic 的坏 thinking 块在子代理回放历史时被 API 以
    # `messages[N].content: missing field 'thinking'` 拒绝。
    # repair 同理必挂:子代理走裸 create_agent,连 deepagents 默认的
    # PatchToolCallsMiddleware 都没有,invalid tool call 悬空曾直接把
    # 抽取子代理打死(2026-07-15 解析中断事故,tool_use 无配对 → 400)。
    middleware: list[Any] = [
        sanitize_anthropic_thinking_blocks_middleware,
        repair_invalid_tool_calls_middleware,
    ]
    hooks_mw = _subagent_hooks_middleware(spec, hook_runner, hook_context)
    if hooks_mw is not None:
        middleware.insert(0, hooks_mw)
    # 与主图一致:工具异常兜底在 hooks 内侧(子代理图不继承主图 middleware)
    middleware.insert(1 if hooks_mw is not None else 0, ToolErrorGuardMiddleware())
    kwargs: dict[str, Any] = {"middleware": middleware}

    return create_agent(
        model=agent_model,
        tools=list(resolved_tools),
        system_prompt=_with_preloaded_skills(
            spec["system_prompt"],
            spec,
            skill_registry,
            materializer,
        ),
        name=spec["name"],
        **kwargs,
    )
