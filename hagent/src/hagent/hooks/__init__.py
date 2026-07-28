"""Hagent hooks 子系统 — Claude Code hook 机制的 Python 移植。

对齐基准：docs/cc-recovered-main（CC 2.1.88），行为契约见
docs/specs/2026-07-06-hagent-hooks-design.md。
"""

from hagent.hooks.config import LoadedHooks, load_hook_settings
from hagent.hooks.context import HookContext
from hagent.hooks.events import HookEvent

__all__ = [
    "HookContext",
    "HookEvent",
    "LoadedHooks",
    "load_hook_settings",
]
