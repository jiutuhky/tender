"""prose MCP 工具面 agent 侧接入（票 04）：CLI host / stdio 链路。

覆盖验收：create_hagent 组装线注入 15 个 prose_* 工具、subagent 继承同一
工具面、stdio 子进程共享 SQLite 且 run 归属（actor_ref）闭环、四路并发
提交不同矩阵草稿无相互干扰、sandbox 模式下工具仍在宿主执行、
工具面唯一性（无绕过 MCP 的原生资产写工具）。
"""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

from deepagents.backends import FilesystemBackend

from hagent.config import HagentConfig
from hagent.mcp_tools import (
    load_prose_mcp_tools,
    prose_http_connection,
    prose_mcp_disabled,
    prose_stdio_connection,
)
from tests.prose_mcp import (
    EXPECTED_PROSE_TOOLS,
    content_json as _content_json,
    make_prose_workspace,
)

PROJECT = "p-mcp-wiring"


@pytest.fixture
def prose_env(tmp_path, monkeypatch):
    """stdio 子进程与测试进程共享的 DB / workspace 约定。"""
    paths = make_prose_workspace(tmp_path, PROJECT)
    monkeypatch.setenv("HAGENT_SESSIONS_DB", str(paths["db_path"]))
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(paths["workspace_root"]))
    return paths


def _cfg() -> HagentConfig:
    return HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False)


def _audit_rows(db_path) -> list[tuple]:
    return sqlite3.connect(db_path).execute(
        "SELECT actor_kind, actor_ref, action FROM asset_events ORDER BY id"
    ).fetchall()


# —— 连接构造 ——


def test_stdio_connection_shape_and_env(prose_env, monkeypatch):
    monkeypatch.setenv("HAGENT_SKILLS_PATHS", "/opt/skills")
    conn = prose_stdio_connection(actor_ref="cli-demo")
    assert conn["transport"] == "stdio"
    assert conn["args"] == ["-m", "hagent.assets.mcp"]
    assert conn["env"]["HAGENT_SESSIONS_DB"] == str(prose_env["db_path"])
    assert conn["env"]["HAGENT_WORKSPACE_ROOT"] == str(prose_env["workspace_root"])
    assert conn["env"]["HAGENT_SKILLS_PATHS"] == "/opt/skills"
    assert conn["env"]["HAGENT_MCP_ACTOR_REF"] == "cli-demo"
    # 不整体继承宿主 env：收窄泄漏面（如 API key 不进子进程）
    assert "ANTHROPIC_API_KEY" not in conn["env"]


def test_http_connection_url_chain(monkeypatch):
    assert prose_http_connection()["url"] == "http://127.0.0.1:8000/mcp"
    monkeypatch.setenv("HAGENT_MCP_URL", "http://127.0.0.1:9001/mcp")
    conn = prose_http_connection(actor_ref="session:s1")
    assert conn["transport"] == "streamable_http"
    assert conn["url"] == "http://127.0.0.1:9001/mcp"
    assert conn["headers"] == {"X-Hagent-Actor-Ref": "session:s1"}
    assert prose_http_connection(url="http://127.0.0.1:7000/mcp")["url"] == (
        "http://127.0.0.1:7000/mcp"
    )


def test_prose_mcp_disabled_env(monkeypatch):
    monkeypatch.delenv("HAGENT_MCP_DISABLED", raising=False)
    assert prose_mcp_disabled() is False
    monkeypatch.setenv("HAGENT_MCP_DISABLED", "1")
    assert prose_mcp_disabled() is True


# —— create_hagent 组装线 ——


def test_create_hagent_wires_prose_tools_and_subagents_inherit(prose_env, tmp_path):
    captured: dict = {}
    inherited: dict = {}

    from hagent.subagents import compile_subagents as real_compile

    def spy_compile(specs, **kwargs):
        inherited["parent_tools"] = list(kwargs["parent_tools"])
        return real_compile(specs, **kwargs)

    with patch("hagent.core._create_deep_agent", side_effect=lambda **kw: captured.update(kw) or MagicMock()), \
         patch("hagent.core.compile_subagents", side_effect=spy_compile):
        from hagent.core import create_hagent

        create_hagent(
            config=_cfg(),
            backend=FilesystemBackend(root_dir=tmp_path, virtual_mode=False),
            mcp_connection=prose_stdio_connection(actor_ref="t-wire"),
        )

    tool_names = {t.name for t in captured["tools"]}
    assert EXPECTED_PROSE_TOOLS.issubset(tool_names)
    # subagent（extraction worker）默认继承全部 parent_tools（票 04 验收）
    inherited_names = {t.name for t in inherited["parent_tools"]}
    assert EXPECTED_PROSE_TOOLS.issubset(inherited_names)
    # sync 桥就位：graph 同步执行路径（server threadpool / CLI invoke）可调
    prose_tools = [t for t in captured["tools"] if t.name in EXPECTED_PROSE_TOOLS]
    assert all(t.func is not None and t.coroutine is not None for t in prose_tools)


def test_create_hagent_without_connection_has_no_prose_tools(tmp_path):
    captured: dict = {}
    with patch("hagent.core._create_deep_agent", side_effect=lambda **kw: captured.update(kw) or MagicMock()):
        from hagent.core import create_hagent

        create_hagent(
            config=_cfg(),
            backend=FilesystemBackend(root_dir=tmp_path, virtual_mode=False),
        )
    assert not {t.name for t in captured["tools"]} & EXPECTED_PROSE_TOOLS


def test_sandbox_mode_keeps_prose_tools_on_host(prose_env, tmp_path):
    """sandbox 切线只影响 bash/file/grep；MCP 工具连接从宿主进程发起。"""
    captured: dict = {}
    sandbox = MagicMock()
    sandbox.workspace_dir = str(tmp_path / "workspace")
    sandbox._container = MagicMock(id="cidcid")
    sandbox.kind.value = "docker"

    with patch("hagent.core._create_deep_agent", side_effect=lambda **kw: captured.update(kw) or MagicMock()):
        from hagent.core import create_hagent

        create_hagent(
            config=_cfg(),
            sandbox=sandbox,
            mcp_connection=prose_stdio_connection(actor_ref="t-sandbox"),
        )

    prose_tools = [t for t in captured["tools"] if t.name in EXPECTED_PROSE_TOOLS]
    assert len(prose_tools) == len(EXPECTED_PROSE_TOOLS)
    # 宿主执行：调用一个只读工具，走 stdio 子进程（与 sandbox 无关）
    status = _content_json(
        next(t for t in prose_tools if t.name == "prose_get_matrix_status").invoke(
            {"project_id": PROJECT}
        )
    )
    assert {m["matrix_type"] for m in status["matrices"]} == {
        "basic_info",
        "business",
        "technical",
        "scoring",
    }


def test_no_native_asset_write_bypass(prose_env, tmp_path):
    """工具面唯一性：资产读写只有 prose_*，无绕过 MCP 的原生工具。"""
    captured: dict = {}
    with patch("hagent.core._create_deep_agent", side_effect=lambda **kw: captured.update(kw) or MagicMock()):
        from hagent.core import create_hagent

        create_hagent(
            config=_cfg(),
            backend=FilesystemBackend(root_dir=tmp_path, virtual_mode=False),
            mcp_connection=prose_stdio_connection(),
        )
    asset_like = {
        t.name
        for t in captured["tools"]
        if t.name.startswith("prose_")
        or any(key in t.name.lower() for key in ("matrix", "document", "asset"))
    }
    assert asset_like == EXPECTED_PROSE_TOOLS


# —— stdio 链路真调用 ——


def test_stdio_tool_call_roundtrip_and_actor_ref(prose_env):
    tools = {t.name: t for t in load_prose_mcp_tools(prose_stdio_connection(actor_ref="cli-demo"))}
    assert set(tools) == EXPECTED_PROSE_TOOLS

    doc = _content_json(
        tools["prose_register_document"].invoke(
            {"project_id": PROJECT, "path": "docs/tender.md", "doc_type": "tender"}
        )
    )
    assert doc["created"] is True

    # 子进程共享 SQLite：宿主进程直接读到写入结果，且 run 归属闭环
    rows = _audit_rows(prose_env["db_path"])
    assert rows == [("agent", "cli-demo", "register_document")]


def test_four_way_concurrent_submits_no_interference(prose_env):
    """四路并发（模拟 4 个 extraction worker）向不同矩阵提交草稿互不串扰。"""
    tools = {t.name: t for t in load_prose_mcp_tools(prose_stdio_connection(actor_ref="t-conc"))}
    plans = {
        "basic_info": ("timeline", [{"milestone": "投标截止", "time": "2026-08-01"}]),
        "business": ("items", [{"id": "BIZ-001", "title": "商务一"}, {"id": "BIZ-002", "title": "商务二"}]),
        "technical": ("items", [{"id": "TECH-001", "title": "技术一"}]),
        "scoring": ("items", [{"id": "SCORE-001", "title": "评分一"}, {"id": "SCORE-002", "title": "评分二"}]),
    }

    def worker(matrix: str) -> dict:
        section, records = plans[matrix]
        _content_json(
            tools["prose_start_matrix_draft"].invoke(
                {"project_id": PROJECT, "matrix_type": matrix}
            )
        )
        submitted = _content_json(
            tools["prose_submit_matrix_records"].invoke(
                {
                    "project_id": PROJECT,
                    "matrix": matrix,
                    "section": section,
                    "records": records,
                }
            )
        )
        return submitted

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(zip(plans, pool.map(worker, plans)))

    for matrix, (section, records) in plans.items():
        assert results[matrix]["count"] == len(records), matrix
        query = _content_json(
            tools["prose_query_matrix_items"].invoke(
                {"project_id": PROJECT, "matrix": matrix}
            )
        )
        assert query["total_count"] == len(records), matrix
        assert {i["section"] for i in query["items"]} == {section}, matrix


# —— CLI demo 接线 ——


def test_run_demo_wires_stdio_connection(prose_env, monkeypatch):
    captured: dict = {}

    def fake_create_hagent(**kwargs):
        captured.update(kwargs)
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [{"role": "assistant", "content": "好"}]}
        return agent

    monkeypatch.setattr("hagent.core.create_hagent", fake_create_hagent)
    from hagent.cli import run_demo

    assert run_demo("你好", max_steps=None) == 0
    conn = captured["mcp_connection"]
    assert conn["transport"] == "stdio"
    assert conn["env"]["HAGENT_MCP_ACTOR_REF"] == "cli-demo"


def test_run_demo_respects_mcp_disabled(prose_env, monkeypatch):
    captured: dict = {}

    def fake_create_hagent(**kwargs):
        captured.update(kwargs)
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [{"role": "assistant", "content": "好"}]}
        return agent

    monkeypatch.setattr("hagent.core.create_hagent", fake_create_hagent)
    monkeypatch.setenv("HAGENT_MCP_DISABLED", "1")
    from hagent.cli import run_demo

    assert run_demo("你好", max_steps=None) == 0
    assert captured["mcp_connection"] is None
