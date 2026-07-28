"""matcher 表驱动测试，对齐 CC hooks.ts matchesPattern。"""

from __future__ import annotations

import pytest

from hagent.hooks.matcher import matches_pattern


@pytest.mark.parametrize(
    ("query", "matcher", "expected"),
    [
        # 空 / * 全匹配
        ("Bash", None, True),
        ("Bash", "", True),
        ("Bash", "*", True),
        # 简单串精确匹配（大小写敏感）
        ("Bash", "Bash", True),
        ("Bash", "bash", False),
        ("Bash", "Bas", False),
        # | 分割精确匹配（段落 trim）
        ("Write", "Write|Edit", True),
        ("Edit", "Write|Edit", True),
        ("Read", "Write|Edit", False),
        # 含空格即出简单串路径 → 按正则 "Write| Edit" 处理，"Edit" 不命中（CC 同款）
        ("Edit", "Write| Edit", False),
        # 正则（JS regex.test = 任意位置匹配）
        ("mcp__github__create_issue", "mcp__.*", True),
        ("Bash", "^(Write|Edit)$", False),
        ("Write", "^(Write|Edit)$", True),
        ("NotebookEdit", "Edit", False),  # 简单串走精确而非子串
        ("NotebookEdit", ".*Edit", True),
        ("Bash", "^Bas", True),  # search 语义：前缀正则可命中
        # 非法正则 → False（CC 行为：log 后返回 false）
        ("Bash", "([", False),
    ],
)
def test_matches_pattern(query: str, matcher: str | None, expected: bool):
    assert matches_pattern(query, matcher) is expected
