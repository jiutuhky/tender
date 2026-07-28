import os
import subprocess
import sys

import pytest


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY 未设置，跳过真实模型 e2e 测试",
)
def test_cli_demo_simple_arithmetic(tmp_path, monkeypatch):
    # 用一个最小任务避免烧 token：让 agent 算 2+2 不需要工具
    monkeypatch.setenv("HAGENT_MODEL", "anthropic:claude-haiku-4-5")
    result = subprocess.run(
        [sys.executable, "-m", "hagent", "demo", "用 read_file 看一眼 /workspace 里有什么文件，没有就回复 empty。"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    print("STDOUT:", result.stdout[-500:])
    print("STDERR:", result.stderr[-500:])
    assert result.returncode == 0
    assert "final answer" in result.stdout.lower()
