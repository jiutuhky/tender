"""hook settings 的发现、加载与合并。

发现顺序（优先级从低到高；匹配后去重时后加载的 scope 胜出）：
1. （可选，``HAGENT_HOOKS_READ_CLAUDE_SETTINGS`` 打开时）
   ``~/.claude/settings.json`` → ``<project_root>/.claude/settings.json``
2. ``~/.hagent/settings.json``（user）
3. ``<project_root>/.hagent/settings.json``（project）
4. ``<project_root>/.hagent/settings.local.json``（local）

``HAGENT_HOOKS_SETTINGS_PATHS``（逗号分隔文件路径）会**替换**默认发现列表
（对齐 HAGENT_SKILLS_PATHS / HAGENT_AGENTS_PATHS 范式）；
``HAGENT_HOOKS_DISABLED`` 为真值时返回空配置。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Union

from pydantic import ValidationError

from hagent.hooks.events import SUPPORTED_EVENTS, HookEvent, is_hook_event
from hagent.hooks.schema import (
    AgentHookConfig,
    CommandHookConfig,
    HooksSettings,
    HttpHookConfig,
    PromptHookConfig,
)

logger = logging.getLogger(__name__)

HookConfigType = Union[
    CommandHookConfig, PromptHookConfig, AgentHookConfig, HttpHookConfig
]

_TRUTHY = {"1", "true", "yes", "on"}


def _is_truthy(value: str | None) -> bool:
    return bool(value) and value.strip().lower() in _TRUTHY


@dataclass(frozen=True)
class HookRegistration:
    """一条已加载的 hook 配置（保留来源 scope 供去重与展示）。"""

    event: HookEvent
    matcher: str | None
    hook: HookConfigType
    source: str  # user / project / local / claude-user / claude-project / 自定义路径

    @property
    def dedup_key(self) -> tuple[str, str, str]:
        # 对齐 hooks.ts hookDedupKey：类型 + 类型专属 payload；hagent 无
        # plugin/skill 命名空间，source 不参与 key（后加载 scope 胜出）。
        return (self.event.value, self.hook.type, self.hook.dedup_payload)


@dataclass
class LoadedHooks:
    by_event: dict[HookEvent, list[HookRegistration]] = field(default_factory=dict)

    def has(self, event: HookEvent) -> bool:
        return bool(self.by_event.get(event))

    def for_event(self, event: HookEvent) -> list[HookRegistration]:
        return self.by_event.get(event, [])

    @property
    def empty(self) -> bool:
        return not any(self.by_event.values())

    def merged(self, other: "LoadedHooks") -> "LoadedHooks":
        """合并两份配置（other 追加在后 → 匹配后去重时 other 胜出）。"""
        result = LoadedHooks()
        for src in (self, other):
            for event, regs in src.by_event.items():
                result.by_event.setdefault(event, []).extend(regs)
        return result


def default_settings_paths(
    project_root: Path,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> list[tuple[Path, str]]:
    env = env if env is not None else os.environ
    home = home if home is not None else Path.home()
    paths: list[tuple[Path, str]] = []
    if _is_truthy(env.get("HAGENT_HOOKS_READ_CLAUDE_SETTINGS")):
        paths.append((home / ".claude" / "settings.json", "claude-user"))
        paths.append((project_root / ".claude" / "settings.json", "claude-project"))
    paths.append((home / ".hagent" / "settings.json", "user"))
    paths.append((project_root / ".hagent" / "settings.json", "project"))
    paths.append((project_root / ".hagent" / "settings.local.json", "local"))
    return paths


def _parse_settings_file(path: Path) -> HooksSettings | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("hook settings 文件读取/解析失败，跳过 %s: %s", path, exc)
        return None
    try:
        return HooksSettings.model_validate(raw)
    except ValidationError as exc:
        logger.warning("hook settings schema 校验失败，跳过 %s: %s", path, exc)
        return None


def _ingest_settings(
    loaded: LoadedHooks, settings: HooksSettings, source: str, origin: object
) -> None:
    for event_name, matchers in settings.hooks.items():
        if not is_hook_event(event_name):
            logger.warning(
                "%s: 未知 hook 事件 %r，跳过（合法事件见 HookEvent）",
                origin,
                event_name,
            )
            continue
        event = HookEvent(event_name)
        if event not in SUPPORTED_EVENTS:
            logger.warning(
                "%s: hook 事件 %s 已识别但 hagent 暂未支持触发，该配置不会执行",
                origin,
                event_name,
            )
        bucket = loaded.by_event.setdefault(event, [])
        for matcher_cfg in matchers:
            for hook in matcher_cfg.hooks:
                if hook.if_ is not None:
                    logger.warning(
                        "%s: hook `if` 条件暂不支持求值，按恒真处理: %r",
                        origin,
                        hook.if_,
                    )
                bucket.append(
                    HookRegistration(
                        event=event,
                        matcher=matcher_cfg.matcher,
                        hook=hook,
                        source=source,
                    )
                )


def load_hooks_dict(hooks: Mapping[str, object], source: str) -> LoadedHooks:
    """从内联 hooks dict（如 agent frontmatter）构建 LoadedHooks。

    对齐 CC registerFrontmatterHooks：agent 的 Stop hook 自动转换为
    SubagentStop（子代理触发的是 SubagentStop 而非 Stop）。
    """
    converted: dict[str, object] = dict(hooks)
    if "Stop" in converted:
        stop_matchers = converted.pop("Stop") or []
        existing = converted.get("SubagentStop") or []
        if isinstance(stop_matchers, list) and isinstance(existing, list):
            converted["SubagentStop"] = [*existing, *stop_matchers]
    loaded = LoadedHooks()
    try:
        settings = HooksSettings.model_validate({"hooks": converted})
    except ValidationError as exc:
        logger.warning("%s: frontmatter hooks 校验失败，忽略: %s", source, exc)
        return loaded
    _ingest_settings(loaded, settings, source, source)
    return loaded


def load_hook_settings(
    project_root: Path,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> LoadedHooks:
    env = env if env is not None else os.environ
    if _is_truthy(env.get("HAGENT_HOOKS_DISABLED")):
        return LoadedHooks()

    custom = env.get("HAGENT_HOOKS_SETTINGS_PATHS", "").strip()
    if custom:
        sources = [
            (Path(p.strip()), p.strip()) for p in custom.split(",") if p.strip()
        ]
    else:
        sources = default_settings_paths(project_root, env=env, home=home)

    loaded = LoadedHooks()
    for path, source in sources:
        if not path.is_file():
            continue
        settings = _parse_settings_file(path)
        if settings is None:
            continue
        _ingest_settings(loaded, settings, source, path)
    return loaded
