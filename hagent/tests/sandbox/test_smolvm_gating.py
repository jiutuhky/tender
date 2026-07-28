"""Task A1 — smolvm 依赖锁定与 pytest 门控。"""

from __future__ import annotations

import os
from importlib.metadata import version

import pytest


def test_smolvm_marker_registered(request):
    markers = request.config.getini("markers")
    assert any(m.startswith("smolvm") for m in markers), "pytest marker 'smolvm' 未注册"


def test_smolvm_dependency_locked():
    # spec D1:0.0.x API 演进剧烈,锁死版本;升级须显式任务
    assert version("smolvm") == "0.0.25"


@pytest.mark.smolvm
def test_smolvm_gate_sentinel():
    # 若门控失效(默认套件跑进了 smolvm 标记),此断言立即暴露
    assert os.environ.get("HAGENT_TEST_SMOLVM") == "1"
