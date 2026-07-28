"""Task C5 — NodeClient 多机接缝(仅接口):pool 的沙箱供给抽象为节点客户端。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hagent.sandbox.node import LOCAL_NODE_ID, LocalNodeClient, NodeClient
from hagent.sandbox.pool import SandboxPool


def test_local_node_client_conforms_to_protocol():
    client = LocalNodeClient(lambda: MagicMock())
    assert isinstance(client, NodeClient)
    assert client.node_id == LOCAL_NODE_ID


def test_local_node_client_custom_node_id():
    client = LocalNodeClient(lambda: MagicMock(), node_id="node-a")
    assert client.node_id == "node-a"


def test_local_node_client_creates_via_factory():
    sentinel = MagicMock()
    client = LocalNodeClient(lambda: sentinel)
    assert client.create_sandbox() is sentinel


def test_pool_accepts_node_client():
    sentinel = MagicMock()
    pool = SandboxPool(
        node_client=LocalNodeClient(lambda: sentinel, node_id="node-b"),
        min_size=0,
        max_size=2,
    )
    assert pool.node_id == "node-b"
    lease = pool.acquire(project_id="s1")
    assert lease.sandbox is sentinel
    pool.release(lease)
    pool.shutdown()


def test_pool_with_plain_factory_reports_local_node():
    pool = SandboxPool(sandbox_factory=lambda: MagicMock(), min_size=0, max_size=2)
    assert pool.node_id == LOCAL_NODE_ID
    pool.shutdown()


def test_pool_requires_factory_or_node_client():
    with pytest.raises(ValueError):
        SandboxPool(min_size=0, max_size=2)
