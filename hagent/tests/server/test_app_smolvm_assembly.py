"""Task A10 — app 装配:smolvm pool + supervisor lifespan 顺序 + 503 语义。"""

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


def test_smolvm_effective_kind_wires_pool_and_supervisor(base_env, monkeypatch):
    calls: list[str] = []

    fake_pool = MagicMock()
    supervisor = MagicMock()
    supervisor.startup_reclaim.side_effect = lambda: calls.append("startup_reclaim")
    supervisor.start_reaper.side_effect = lambda: calls.append("start_reaper")
    supervisor.shutdown.side_effect = lambda: calls.append("supervisor.shutdown")

    import hagent.server.app as app_mod

    monkeypatch.setattr(app_mod, "preflight_sandbox_kind", lambda: SandboxKind.SMOLVM)
    monkeypatch.setattr(app_mod, "_ensure_smolvm_image", lambda: None)
    monkeypatch.setattr(app_mod, "_build_smolvm_pool", lambda auditor=None: fake_pool)
    monkeypatch.setattr(app_mod, "_build_smolvm_supervisor", lambda mgr, pool, auditor=None: supervisor)

    app = app_mod.create_app()
    with TestClient(app):
        assert calls[:2] == ["startup_reclaim", "start_reaper"], "启动序:先对账再起 reaper"
    assert "supervisor.shutdown" in calls
    # shutdown 顺序:supervisor 先于 pool;smolvm 路径走 drain(存量保留待收养)
    fake_pool.drain.assert_called_once()
    fake_pool.shutdown.assert_not_called()


def test_smolvm_default_kind_exposed_to_session_route(base_env, monkeypatch):
    import hagent.server.app as app_mod
    from hagent.server.routers.sessions import _default_sandbox_kind

    monkeypatch.setattr(app_mod, "preflight_sandbox_kind", lambda: SandboxKind.SMOLVM)
    monkeypatch.setattr(app_mod, "_ensure_smolvm_image", lambda: None)
    monkeypatch.setattr(app_mod, "_build_smolvm_pool", lambda auditor=None: MagicMock())
    monkeypatch.setattr(app_mod, "_build_smolvm_supervisor", lambda mgr, pool, auditor=None: MagicMock())
    app_mod.create_app()
    assert _default_sandbox_kind() == "smolvm"


def test_none_effective_kind_keeps_docker_pool_no_supervisor(base_env, monkeypatch):
    import hagent.server.app as app_mod

    monkeypatch.setattr(app_mod, "preflight_sandbox_kind", lambda: SandboxKind.NONE)
    built = {"smolvm": 0}
    monkeypatch.setattr(
        app_mod, "_build_smolvm_pool", lambda auditor=None: built.__setitem__("smolvm", built["smolvm"] + 1)
    )
    app = app_mod.create_app()
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"ok": True}
    assert built["smolvm"] == 0, "none 生效时不应装 smolvm pool"


def test_capacity_exceeded_maps_to_503_with_retry_after(base_env, monkeypatch):
    from hagent.sandbox.ledger import CapacityExceeded
    import hagent.server.app as app_mod

    monkeypatch.setenv("HAGENT_SANDBOX_KIND", "none")
    app = app_mod.create_app()
    client = TestClient(app)

    from hagent.server.routers.sessions import get_session_manager

    mgr = get_session_manager()
    monkeypatch.setattr(
        mgr._pool, "acquire", MagicMock(side_effect=CapacityExceeded("内存额度不足"))
    )
    created = create_project_session(client, {"sandbox_kind": "docker"})
    assert created.status_code == 200
    resp = client.post(
        f"/sessions/{created.json()['id']}/messages", json={"content": "测试"}
    )
    assert resp.status_code == 503
    assert "Retry-After" in resp.headers
    assert "内存额度不足" in resp.json()["detail"]


def test_pool_exhausted_maps_to_503(base_env, monkeypatch):
    from hagent.sandbox.pool import PoolExhausted
    import hagent.server.app as app_mod

    monkeypatch.setenv("HAGENT_SANDBOX_KIND", "none")
    app = app_mod.create_app()
    client = TestClient(app)

    from hagent.server.routers.sessions import get_session_manager

    mgr = get_session_manager()
    monkeypatch.setattr(
        mgr._pool, "acquire", MagicMock(side_effect=PoolExhausted("pool exhausted"))
    )
    created = create_project_session(client, {"sandbox_kind": "docker"})
    assert created.status_code == 200
    resp = client.post(
        f"/sessions/{created.json()['id']}/messages", json={"content": "测试"}
    )
    assert resp.status_code == 503
    assert "Retry-After" in resp.headers


def test_smolvm_pool_reads_max_lifetime_env(base_env, monkeypatch):
    import hagent.server.app as app_mod

    monkeypatch.setenv("HAGENT_SMOLVM_MAX_LIFETIME_SECONDS", "1234")
    pool = app_mod._build_smolvm_pool()
    assert pool._max_lifetime == 1234
    monkeypatch.delenv("HAGENT_SMOLVM_MAX_LIFETIME_SECONDS")
    pool = app_mod._build_smolvm_pool()
    assert pool._max_lifetime == 86400, "默认绝对寿命 86400s(spec §5)"


# ---------------------------------------------------------------------------
# Task C1:golden base 启动期烘焙 + GC 常开 + warm recycle 配置
# ---------------------------------------------------------------------------


def _smolvm_app(monkeypatch, *, fake_pool=None):
    import hagent.server.app as app_mod

    calls: list[str] = []
    pool = fake_pool if fake_pool is not None else MagicMock()
    pool.prewarm.side_effect = lambda: calls.append("prewarm")
    monkeypatch.setattr(app_mod, "preflight_sandbox_kind", lambda: SandboxKind.SMOLVM)
    monkeypatch.setattr(
        app_mod, "_ensure_smolvm_image", lambda: calls.append("ensure_image")
    )
    monkeypatch.setattr(app_mod, "_build_smolvm_pool", lambda auditor=None: pool)
    monkeypatch.setattr(
        app_mod, "_build_smolvm_supervisor", lambda mgr, pool, auditor=None: MagicMock()
    )
    return app_mod, pool, calls


def test_smolvm_builds_golden_image_at_startup(base_env, monkeypatch):
    app_mod, pool, calls = _smolvm_app(monkeypatch)
    app_mod.create_app()
    assert "ensure_image" in calls, "golden base 必须在启动期烘焙(首会话不付构建成本)"


def test_smolvm_image_built_before_prewarm(base_env, monkeypatch):
    monkeypatch.setenv("HAGENT_SANDBOX_PREWARM", "1")
    app_mod, pool, calls = _smolvm_app(monkeypatch)
    app_mod.create_app()
    assert calls.index("ensure_image") < calls.index("prewarm"), (
        f"镜像先于预热(prewarm 首 VM 不重复触发构建);got {calls}"
    )


def test_smolvm_gc_loop_runs_without_prewarm(base_env, monkeypatch):
    """idle 治理 / max_lifetime / recycle 都挂 GC 循环,不得依赖 PREWARM 开关。"""
    monkeypatch.delenv("HAGENT_SANDBOX_PREWARM", raising=False)
    app_mod, pool, calls = _smolvm_app(monkeypatch)
    app_mod.create_app()
    pool.start_gc_loop.assert_called_once()
    pool.prewarm.assert_not_called()


def test_none_kind_does_not_build_smolvm_image(base_env, monkeypatch):
    import hagent.server.app as app_mod

    built = {"n": 0}
    monkeypatch.setattr(app_mod, "preflight_sandbox_kind", lambda: SandboxKind.NONE)
    monkeypatch.setattr(
        app_mod, "_ensure_smolvm_image", lambda: built.__setitem__("n", built["n"] + 1)
    )
    app_mod.create_app()
    assert built["n"] == 0


# ---------------------------------------------------------------------------
# Task C2:快照持久化接线 — persist_fn 挂 manager;restore_factory 进 pool
# ---------------------------------------------------------------------------


def test_smolvm_pool_has_restore_factory(base_env, monkeypatch):
    import hagent.server.app as app_mod

    pool = app_mod._build_smolvm_pool()
    assert pool._restore_factory is not None, "快照恢复须经池的占位/记账通道"


def test_smolvm_wires_persist_fn_to_manager(base_env, monkeypatch):
    app_mod, pool, calls = _smolvm_app(monkeypatch)
    app_mod.create_app()
    pool.set_persist_fn.assert_called_once()
    from hagent.server.routers.sessions import get_session_manager

    fn = pool.set_persist_fn.call_args[0][0]
    assert fn == get_session_manager().persist_sandbox


def test_smolvm_persist_env_off_skips_wiring(base_env, monkeypatch):
    monkeypatch.setenv("HAGENT_SMOLVM_SNAPSHOT_PERSIST", "0")
    app_mod, pool, calls = _smolvm_app(monkeypatch)
    app_mod.create_app()
    pool.set_persist_fn.assert_not_called()


def test_smolvm_pool_reads_recycle_env(base_env, monkeypatch):
    import hagent.server.app as app_mod

    monkeypatch.setenv("HAGENT_SANDBOX_RECYCLE_SECONDS", "120")
    pool = app_mod._build_smolvm_pool()
    assert pool._recycle_after == 120
    monkeypatch.delenv("HAGENT_SANDBOX_RECYCLE_SECONDS")
    pool = app_mod._build_smolvm_pool()
    assert pool._recycle_after == 3600, "默认 1h recycle 一轮 warm 实例(防漂移)"
