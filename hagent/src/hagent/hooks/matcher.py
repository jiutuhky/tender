"""matcher 匹配逻辑，对齐 CC hooks.ts matchesPattern（:1346）。

规则：
1. matcher 为空或 ``*`` → 全匹配。
2. matcher 仅含 ``[a-zA-Z0-9_|]`` → 按 ``|`` 分割做精确匹配（单段亦精确）。
3. 否则按正则处理（JS ``regex.test`` = 任意位置匹配，对应 ``re.search``）；
   正则非法时记录日志并返回 False（CC 同款行为，不回退精确匹配）。

hagent 无 legacy 工具名，CC 的 normalizeLegacyToolName / getLegacyToolNames
按恒等处理。
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

logger = logging.getLogger(__name__)

_SIMPLE_PATTERN = re.compile(r"^[a-zA-Z0-9_|]+$")


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern[str] | None:
    try:
        return re.compile(pattern)
    except re.error:
        return None


def matches_pattern(match_query: str, matcher: str | None) -> bool:
    if not matcher or matcher == "*":
        return True
    if _SIMPLE_PATTERN.fullmatch(matcher):
        if "|" in matcher:
            return match_query in [p.strip() for p in matcher.split("|")]
        return match_query == matcher
    regex = _compile(matcher)
    if regex is None:
        logger.warning("hook matcher 正则非法，按不匹配处理: %r", matcher)
        return False
    return regex.search(match_query) is not None
