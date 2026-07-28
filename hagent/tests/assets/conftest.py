import pytest

from hagent.assets.model import Actor
from hagent.assets.service import AssetService
from hagent.assets.store import AssetStore


@pytest.fixture
def store(tmp_path):
    return AssetStore(tmp_path / "hagent.sqlite")


@pytest.fixture
def service(store):
    return AssetService(store)


@pytest.fixture
def agent_actor():
    return Actor(kind="agent", ref="run-001")


@pytest.fixture
def user_actor():
    return Actor(kind="user", ref="u-1")


def make_item(i: int, prefix: str = "TECH") -> dict:
    """按 technical items 形状构造一条最小合法记录。"""
    return {
        "id": f"{prefix}-{i:03d}",
        "category": "function",
        "title": f"需求条目 {i}",
        "requirement_text": f"第 {i} 条要求原文",
        "mandatory": False,
        "source_refs": [{"document_id": "doc-00000000", "line_span": [i, i + 1]}],
    }
