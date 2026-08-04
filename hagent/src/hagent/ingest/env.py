"""入库管线的环境变量读取——限额与批次大小共用一套「坏值退回默认」的口径。"""

from __future__ import annotations

import os


def int_env(name: str, default: int) -> int:
    """读一个正整数环境变量；缺失或不可解析时退回默认值，绝不因配置笔误崩掉启动。"""
    try:
        return max(1, int(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default
