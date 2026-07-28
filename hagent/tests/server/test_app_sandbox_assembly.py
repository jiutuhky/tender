from __future__ import annotations

from tests.server.helpers import create_project_session

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def test_create_session_default_kind_none(monkeypatch, tmp_path):
    monkeypatch.setenv("HAGENT_API_KEY", "")
    monkeypatch.setenv("HAGENT_SESSIONS_DB", str(tmp_path / "s.db"))
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path / "wsp"))
    # server 默认已切 smolvm(spec D5),host 语义须显式声明
    monkeypatch.setenv("HAGENT_SANDBOX_KIND", "none")

    from hagent.server.app import create_app
    app = create_app()
    client = TestClient(app)
    resp = create_project_session(client)
    assert resp.status_code == 200
    data = resp.json()
    from hagent.server.routers.sessions import get_session_manager

    lease = get_session_manager().lease_store.get(data["project_id"])
    assert lease.sandbox_kind == "none"
    assert lease.sandbox_id is None


def test_create_session_with_docker_kind_populates_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("HAGENT_API_KEY", "")
    monkeypatch.setenv("HAGENT_SESSIONS_DB", str(tmp_path / "s.db"))
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path / "wsp"))

    sandbox = MagicMock()
    sandbox.id = "docker-abc"
    sandbox.workspace_dir = "/workspace"
    sandbox.manifest = MagicMock(container_id="abc", image_tag="hagent/sandbox:dev", runtime="runsc")
    sandbox.execute.return_value = MagicMock(exit_code=0, output="")
    sandbox.upload_files.return_value = [MagicMock(error=None)]

    # 让 HagentDockerSandbox.start() 返回 mock，跳过真实 docker
    with patch("hagent.server.app.HagentDockerSandbox") as cls:
        cls.start.return_value = sandbox
        from hagent.server.app import create_app
        app = create_app()
        client = TestClient(app)
        resp = create_project_session(client, {"sandbox_kind": "docker"})
        assert resp.status_code == 200
        data = resp.json()
        from hagent.server.routers.sessions import get_session_manager

        manager = get_session_manager()
        manager.ensure_sandbox(data["id"])
        lease = manager.lease_store.get(data["project_id"])
    assert lease.sandbox_kind == "docker"
    assert lease.sandbox_id == "abc"


def test_delete_session_invokes_manager(monkeypatch, tmp_path):
    """Verify DELETE /sessions/{sid} goes through SessionManager.delete_session()."""
    monkeypatch.setenv("HAGENT_API_KEY", "")
    monkeypatch.setenv("HAGENT_SESSIONS_DB", str(tmp_path / "s.db"))
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path / "wsp"))
    # server 默认已切 smolvm(spec D5),host 语义须显式声明
    monkeypatch.setenv("HAGENT_SANDBOX_KIND", "none")

    from hagent.server.app import create_app
    app = create_app()
    client = TestClient(app)
    create_resp = create_project_session(client)
    sid = create_resp.json()["id"]
    del_resp = client.delete(f"/sessions/{sid}")
    assert del_resp.status_code in (200, 204)
