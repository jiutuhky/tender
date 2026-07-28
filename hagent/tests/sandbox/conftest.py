"""sandbox 测试共享配置 — smolvm 门控。"""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config, items):
    # smolvm 标记集中门控:HAGENT_TEST_SMOLVM=1 才真跑(需 KVM + firecracker)
    if os.environ.get("HAGENT_TEST_SMOLVM") == "1":
        return
    skip_smolvm = pytest.mark.skip(reason="HAGENT_TEST_SMOLVM!=1; skipping smolvm gated tests")
    for item in items:
        if "smolvm" in item.keywords:
            item.add_marker(skip_smolvm)
