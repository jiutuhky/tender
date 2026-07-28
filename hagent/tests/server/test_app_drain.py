"""Task B5 — graceful drain:拒新建 503 → 存量 pause → supervisor/pool 有序退出。"""

from __future__ import annotations

from tests.server.helpers import create_project_session

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from hagent.sandbox import SandboxKind


@pytest.fixture
def base_env(monkeypatch, tmp_path):
    monkeypatch.setenv("HAGENT_API_KEY", "")
    monkeypatch.setenv("HAGENT_SESSIONS_DB", str(tmp_path / "s.db"))
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path / "wsp"))


def test_post_sessions_503_when_draining(base_env, monkeypatch):
    import hagent.server.app as app_mod
    from hagent.server.routers import sessions as sessions_router

    monkeypatch.setenv("HAGENT_SANDBOX_KIND", "none")
    app = app_mod.create_app()
    client = TestClient(app)
    assert create_project_session(client).status_code == 200
    sessions_router.begin_drain()
    resp = create_project_session(client)
    assert resp.status_code == 503
    assert "Retry-After" in resp.headers
    sessions_router.set_draining(False)


def test_create_app_resets_drain_flag(base_env, monkeypatch):
    import hagent.server.app as app_mod
    from hagent.server.routers import sessions as sessions_router

    monkeypatch.setenv("HAGENT_SANDBOX_KIND", "none")
    sessions_router.begin_drain()
    app_mod.create_app()
    assert sessions_router.is_draining() is False, "新 app 装配必须复位 drain 旗标"


def test_smolvm_shutdown_drains_in_order(base_env, monkeypatch):
    """drain 时序:拒新建 → supervisor 停 → 存量 pause(pool.drain),不走 shutdown。"""
    import hagent.server.app as app_mod
    from hagent.server.routers import sessions as sessions_router

    calls: list[str] = []
    fake_pool = MagicMock()
    fake_pool.drain.side_effect = lambda: calls.append("pool.drain")
    fake_pool.shutdown.side_effect = lambda: calls.append("pool.shutdown")
    supervisor = MagicMock()
    supervisor.shutdown.side_effect = lambda: calls.append("supervisor.shutdown")

    monkeypatch.setattr(app_mod, "preflight_sandbox_kind", lambda: SandboxKind.SMOLVM)
    monkeypatch.setattr(app_mod, "_ensure_smolvm_image", lambda: None)
    monkeypatch.setattr(app_mod, "_build_smolvm_pool", lambda auditor=None: fake_pool)
    monkeypatch.setattr(
        app_mod, "_build_smolvm_supervisor", lambda mgr, pool, auditor=None: supervisor
    )
    app = app_mod.create_app()
    with TestClient(app):
        assert sessions_router.is_draining() is False
    assert sessions_router.is_draining() is True, "shutdown 起点即拒新建"
    assert calls == ["supervisor.shutdown", "pool.drain"], (
        "顺序:supervisor 先停(防巡检把 paused 误判病 VM),再 pause 存量;"
        f"got {calls}"
    )
    fake_pool.shutdown.assert_not_called()  # leased VM 保留待重启收养,不得拆除
    sessions_router.set_draining(False)


def test_none_kind_shutdown_keeps_teardown(base_env, monkeypatch):
    """docker/none 路径无收养机制,shutdown 维持全拆语义。"""
    import hagent.server.app as app_mod
    from hagent.server.routers import sessions as sessions_router

    monkeypatch.setattr(app_mod, "preflight_sandbox_kind", lambda: SandboxKind.NONE)
    app = app_mod.create_app()
    from hagent.server.routers.sessions import get_session_manager

    with TestClient(app):
        mgr = get_session_manager()
        mgr.shutdown = MagicMock(wraps=mgr.shutdown)
    mgr.shutdown.assert_called_once()
    sessions_router.set_draining(False)
