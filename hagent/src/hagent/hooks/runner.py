"""HookRunner：事件触发入口 —— 匹配 → 去重 → once 过滤 → 并行执行 → 聚合。

对齐 CC executeHooks / getMatchingHooks：
- 命中 hook 全部并行执行（asyncio.gather，单个异常折算 non-blocking error）。
- 去重按类型专属 key（shell\\0command\\0if 等），同 key 保留**最后**一个
  （后合并的 scope 胜出）。
- SessionStart/Setup 过滤 http hook（CC 同款限制）。
- 聚合：permission 优先级 deny > ask > allow；blocked = 任一 blocking_error /
  preventContinuation；updatedInput 仅在无 deny 时透传（最后一个非空胜出）；
  exit 0 纯文本 stdout 仅对 UserPromptSubmit / SessionStart / Setup /
  SubagentStart 注入为上下文（对齐 CC 各事件 exit code 语义文案）。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from hagent.hooks.config import HookRegistration, LoadedHooks
from hagent.hooks.context import HookContext
from hagent.hooks.events import HookEvent, build_payload, match_query_for
from hagent.hooks.executor import execute_command_hook
from hagent.hooks.executor_http import execute_http_hook
from hagent.hooks.executor_llm import (
    ModelFactory,
    execute_agent_hook,
    execute_prompt_hook,
)
from hagent.hooks.matcher import matches_pattern
from hagent.hooks.results import HookExecutionResult
from hagent.hooks.schema import (
    AgentHookConfig,
    CommandHookConfig,
    HttpHookConfig,
    PromptHookConfig,
)

logger = logging.getLogger(__name__)

# exit 0 纯文本 stdout 会注入给模型的事件（CC hooksConfigManager 语义文案）
_STDOUT_CONTEXT_EVENTS = frozenset(
    {
        HookEvent.USER_PROMPT_SUBMIT,
        HookEvent.SESSION_START,
        HookEvent.SETUP,
        HookEvent.SUBAGENT_START,
    }
)


@dataclass
class HookAggregate:
    """一次事件触发的聚合裁决。"""

    blocked: bool = False
    block_reasons: list[str] = field(default_factory=list)
    prevent_continuation: bool = False
    stop_reason: str | None = None
    permission_decision: str | None = None  # deny > ask > allow
    permission_reason: str | None = None
    updated_input: dict[str, Any] | None = None
    contexts: list[str] = field(default_factory=list)  # additionalContext + stdout
    system_messages: list[str] = field(default_factory=list)
    initial_user_message: str | None = None
    updated_mcp_tool_output: Any | None = None
    non_blocking_errors: list[str] = field(default_factory=list)
    results: list[HookExecutionResult] = field(default_factory=list)

    @property
    def block_reason(self) -> str:
        return "\n".join(self.block_reasons)


_EMPTY_AGGREGATE = HookAggregate()

_PERMISSION_RANK = {"deny": 2, "ask": 1, "allow": 0}


class HookRunner:
    """per-session 的 hook 执行器（once 状态与配置快照都绑定 session 生命周期）。"""

    def __init__(
        self,
        settings: LoadedHooks,
        ctx: HookContext,
        *,
        agent_tools: Sequence[Any] | None = None,
        model_factory: ModelFactory | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self._settings = settings
        self._ctx = ctx
        self._agent_tools = list(agent_tools or [])
        self._model_factory = model_factory
        self._env = env
        self._once_fired: set[tuple[str, str, str]] = set()

    @property
    def ctx(self) -> HookContext:
        return self._ctx

    @property
    def settings(self) -> LoadedHooks:
        return self._settings

    def for_subagent(
        self, agent_id: str, agent_type: str, extra: LoadedHooks | None = None
    ) -> "HookRunner":
        """派生子代理 runner：合并 frontmatter hooks、ctx 带 agent 身份。

        once 状态独立（子代理生命周期）；agent 型工具集与 env 继承。
        """
        settings = self._settings if extra is None else self._settings.merged(extra)
        return HookRunner(
            settings,
            self._ctx.for_subagent(agent_id, agent_type),
            agent_tools=self._agent_tools,
            model_factory=self._model_factory,
            env=self._env,
        )

    def set_agent_tools(self, tools: Sequence[Any]) -> None:
        """agent 型 hook 的只读工具集（core 装配时注入）。"""
        self._agent_tools = list(tools)

    def has_hooks(self, *events: HookEvent) -> bool:
        return any(self._settings.has(e) for e in events)

    # ------------------------------------------------------------------
    # 执行
    # ------------------------------------------------------------------

    def _select(
        self, event: HookEvent, payload: Mapping[str, Any]
    ) -> list[HookRegistration]:
        regs = self._settings.for_event(event)
        if not regs:
            return []
        match_query = match_query_for(event, payload)
        if match_query is not None:
            regs = [r for r in regs if matches_pattern(match_query, r.matcher)]
        # 去重：同 key 保留最后（后合并 scope 胜出，对齐 CC new Map(entries)）
        deduped: dict[tuple[str, str, str], HookRegistration] = {}
        for reg in regs:
            deduped[reg.dedup_key] = reg
        selected = list(deduped.values())
        # SessionStart/Setup 不支持 http hook（CC hooks.ts:1850）
        if event in (HookEvent.SESSION_START, HookEvent.SETUP):
            kept = []
            for reg in selected:
                if reg.hook.type == "http":
                    logger.warning(
                        "跳过 http hook %s — %s 事件不支持 http hook",
                        reg.hook.url,  # type: ignore[union-attr]
                        event.value,
                    )
                    continue
                kept.append(reg)
            selected = kept
        # once 过滤
        ready = []
        for reg in selected:
            if reg.hook.once and reg.dedup_key in self._once_fired:
                continue
            ready.append(reg)
        return ready

    async def _execute_one(
        self,
        reg: HookRegistration,
        event: HookEvent,
        payload: Mapping[str, Any],
        payload_json: str,
    ) -> HookExecutionResult:
        hook = reg.hook
        if isinstance(hook, CommandHookConfig):
            return await execute_command_hook(
                hook, payload, self._ctx, event, env=self._env
            )
        if isinstance(hook, HttpHookConfig):
            return await execute_http_hook(
                hook,
                payload_json,
                event,
                env=self._env if self._env is not None else os.environ,
            )
        if isinstance(hook, PromptHookConfig):
            return await execute_prompt_hook(
                hook, payload_json, event, model_factory=self._model_factory
            )
        if isinstance(hook, AgentHookConfig):
            return await execute_agent_hook(
                hook,
                payload_json,
                event,
                tools=self._agent_tools,
                model_factory=self._model_factory,
            )
        return HookExecutionResult(
            outcome="non_blocking_error",
            error_message=f"未知 hook 类型: {hook.type}",
        )

    async def arun(
        self,
        event: HookEvent,
        fields: Mapping[str, Any],
        *,
        ctx_override: HookContext | None = None,
    ) -> HookAggregate:
        ctx = ctx_override or self._ctx
        if not self._settings.has(event):
            return _EMPTY_AGGREGATE
        payload = build_payload(event, ctx, fields)
        regs = self._select(event, payload)
        if not regs:
            return _EMPTY_AGGREGATE
        payload_json = json.dumps(payload, ensure_ascii=False)

        raw = await asyncio.gather(
            *(self._execute_one(r, event, payload, payload_json) for r in regs),
            return_exceptions=True,
        )
        for reg in regs:
            if reg.hook.once:
                self._once_fired.add(reg.dedup_key)

        results: list[HookExecutionResult] = []
        for reg, item in zip(regs, raw):
            if isinstance(item, BaseException):
                logger.exception("hook 执行异常（不阻断）", exc_info=item)
                results.append(
                    HookExecutionResult(
                        outcome="non_blocking_error",
                        error_message=f"hook 执行异常: {item}",
                    )
                )
            else:
                results.append(item)
        return self._aggregate(event, results)

    def run(
        self,
        event: HookEvent,
        fields: Mapping[str, Any],
        *,
        ctx_override: HookContext | None = None,
    ) -> HookAggregate:
        """同步桥：无运行中事件循环时 asyncio.run；有则丢独立线程执行。"""
        if not self._settings.has(event):
            return _EMPTY_AGGREGATE
        coro = self.arun(event, fields, ctx_override=ctx_override)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()

    # ------------------------------------------------------------------
    # 聚合
    # ------------------------------------------------------------------

    def _aggregate(
        self, event: HookEvent, results: list[HookExecutionResult]
    ) -> HookAggregate:
        agg = HookAggregate(results=results)
        for res in results:
            if res.prevent_continuation:
                agg.prevent_continuation = True
                if agg.stop_reason is None and res.stop_reason is not None:
                    agg.stop_reason = res.stop_reason
            if res.blocking_error:
                agg.block_reasons.append(res.blocking_error)
            if res.permission_behavior is not None:
                current = agg.permission_decision
                if (
                    current is None
                    or _PERMISSION_RANK[res.permission_behavior]
                    > _PERMISSION_RANK[current]
                ):
                    agg.permission_decision = res.permission_behavior
                    agg.permission_reason = (
                        res.permission_reason or res.blocking_error
                    )
            if res.updated_input is not None:
                agg.updated_input = res.updated_input
            if res.additional_context:
                agg.contexts.append(res.additional_context)
            if (
                res.plain_text
                and not res.suppress_output
                and event in _STDOUT_CONTEXT_EVENTS
            ):
                agg.contexts.append(res.plain_text)
            if res.system_message:
                agg.system_messages.append(res.system_message)
            if res.initial_user_message and agg.initial_user_message is None:
                agg.initial_user_message = res.initial_user_message
            if res.updated_mcp_tool_output is not None:
                agg.updated_mcp_tool_output = res.updated_mcp_tool_output
            if res.error_message:
                agg.non_blocking_errors.append(res.error_message)
        agg.blocked = bool(agg.block_reasons) or agg.prevent_continuation
        # deny 时 updatedInput 不透传（CC：updatedInput 仅 allow/ask/passthrough）
        if agg.permission_decision == "deny":
            agg.updated_input = None
        return agg
