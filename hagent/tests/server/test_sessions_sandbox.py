"""L3 服务端集成：用真实 Docker 验证项目沙箱租约生命周期。

需要 Docker 守护进程并设置 HAGENT_TEST_DOCKER=1。端到端验证规范 §4.2：
创建会话时不启动容器，首次 ensure 才租用，删除项目后释放。
"""

from __future__ import annotations

from tests.server.helpers import create_project_session

import os

import pytest

pytestmark = pytest.mark.docker

if os.environ.get("HAGENT_TEST_DOCKER") != "1":
    pytest.skip(
        "HAGENT_TEST_DOCKER!=1; skipping server sandbox integration",
        allow_module_level=True,
    )


import docker as docker_sdk  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def app_with_real_sandbox(monkeypatch, tmp_path):
    """FastAPI app wired to a real SandboxPool (HAGENT_SANDBOX_PREWARM off)."""
    monkeypatch.setenv("HAGENT_API_KEY", "")
    monkeypatch.setenv("HAGENT_SESSIONS_DB", str(tmp_path / "s.db"))
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path / "wsp"))
    monkeypatch.delenv("HAGENT_SANDBOX_PREWARM", raising=False)

    from hagent.server.app import create_app
    from hagent.server.routers.sessions import set_session_manager

    app = create_app()
    yield app
    # Reset singleton so subsequent tests in this process pick up fresh state.
    try:
        from hagent.server.routers import sessions as sess_mod
        sess_mod._MANAGER = None
    except Exception:
        pass
    set_session_manager(None)  # type: ignore[arg-type]


def _list_hagent_containers(sandbox_id: str | None = None):
    client = docker_sdk.from_env()
    filters = {"label": "hagent.kind=docker"}
    if sandbox_id is not None:
        filters = {"label": f"hagent.sandbox_id={sandbox_id}"}
    return client.containers.list(all=True, filters=filters)


def test_create_docker_session_spawns_real_container(app_with_real_sandbox):
    app = app_with_real_sandbox
    client = TestClient(app)

    resp = create_project_session(client, {"sandbox_kind": "docker"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    from hagent.server.routers.sessions import get_session_manager

    manager = get_session_manager()
    assert manager.get_sandbox(data["id"]) is None
    manager.ensure_sandbox(data["id"])
    lease = manager.lease_store.get(data["project_id"])
    container_id = lease.sandbox_id
    assert container_id, "container_id should be populated after sandbox acquire"

    # docker ps should see the container with our label
    client_sdk = docker_sdk.from_env()
    container = client_sdk.containers.get(container_id)
    assert container.status in ("running", "created"), f"unexpected status: {container.status}"
    assert container.labels.get("hagent.kind") == "docker"

    # 清理：会话不拥有 VM，删除项目才释放租约。
    del_resp = client.delete(f"/projects/{data['project_id']}")
    assert del_resp.status_code in (200, 204)

    # Container should be gone (or marked exited and removed)
    matches = client_sdk.containers.list(
        all=True, filters={"id": container_id}
    )
    assert not matches, f"container {container_id} not cleaned up after DELETE"


def test_session_metadata_records_runtime_and_image_tag(app_with_real_sandbox):
    app = app_with_real_sandbox
    client = TestClient(app)

    resp = create_project_session(client, {"sandbox_kind": "docker"})
    assert resp.status_code == 200
    data = resp.json()
    try:
        # 项目租约应完整保存提供方元数据。
        from hagent.server.routers.sessions import get_session_manager
        mgr = get_session_manager()
        mgr.ensure_sandbox(data["id"])
        lease = mgr.lease_store.get(data["project_id"])
        assert lease.sandbox_kind == "docker"
        assert lease.sandbox_id
        assert "hagent/sandbox" in (lease.metadata_json or "")
        assert any(runtime in (lease.metadata_json or "") for runtime in ("runc", "runsc"))
    finally:
        client.delete(f"/projects/{data['project_id']}")
