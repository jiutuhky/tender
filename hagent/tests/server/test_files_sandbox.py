"""Tests: file upload/download routes through sandbox in docker mode."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from deepagents.backends.protocol import FileDownloadResponse, FileUploadResponse


def _make_sandbox_mock(workspace_dir: str = "/workspace") -> MagicMock:
    sandbox = MagicMock()
    sandbox.workspace_dir = workspace_dir
    sandbox.upload_files.return_value = [
        FileUploadResponse(path=f"{workspace_dir}/x.txt", error=None)
    ]
    sandbox.download_files.return_value = [
        FileDownloadResponse(path=f"{workspace_dir}/x.txt", content=b"hello", error=None)
    ]
    return sandbox


def _make_app_with_mgr(monkeypatch, tmp_path, sandbox):
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "s.db"))
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path / "wsp"))

    from hagent.server.app import create_app
    from hagent.server.routers.sessions import set_session_manager
    from hagent.server.sessions import SessionStore

    app = create_app()
    store = SessionStore(tmp_path / "s.db")

    mgr = MagicMock()
    mgr.store = store
    mgr.get_sandbox.return_value = sandbox
    mgr.workspace_dir.side_effect = (
        lambda sid: str(tmp_path / "wsp" / "projects" / store.get(sid).project_id / "workspace")
    )

    set_session_manager(mgr)
    return app, store, mgr


@pytest.fixture
def sandbox_setup(monkeypatch, tmp_path):
    sandbox = _make_sandbox_mock()
    app, store, mgr = _make_app_with_mgr(monkeypatch, tmp_path, sandbox)
    yield app, store, sandbox
    # Reset singleton after test
    from hagent.server import routers as _r
    import hagent.server.routers.sessions as sess_mod
    sess_mod._MANAGER = None


def test_upload_returns_410_even_with_active_sandbox(sandbox_setup):
    # 票6:session 级上传废弃,沙箱在与不在均 410,且不触碰沙箱。
    app, store, sandbox = sandbox_setup
    state = store.create(project_id="project-1")

    client = TestClient(app)
    resp = client.post(
        f"/sessions/{state.id}/files",
        files={"file": ("x.txt", b"hello", "text/plain")},
        data={"path": "x.txt"},
    )
    assert resp.status_code == 410
    sandbox.upload_files.assert_not_called()


def test_download_routes_through_sandbox(sandbox_setup):
    app, store, sandbox = sandbox_setup
    state = store.create(project_id="project-1")

    client = TestClient(app)
    resp = client.get(f"/sessions/{state.id}/files/x.txt")
    assert resp.status_code == 200
    assert resp.content == b"hello"
    sandbox.download_files.assert_called_once()


def test_download_uses_project_workspace_when_sandbox_missing(monkeypatch, tmp_path):
    app, store, mgr = _make_app_with_mgr(monkeypatch, tmp_path, None)
    state = store.create(project_id="project-1")

    try:
        client = TestClient(app)
        resp = client.get(f"/sessions/{state.id}/files/x.txt")
        assert resp.status_code == 404
    finally:
        import hagent.server.routers.sessions as sess_mod
        sess_mod._MANAGER = None


def test_download_rejects_path_traversal(sandbox_setup):
    app, store, sandbox = sandbox_setup
    state = store.create(project_id="project-1")
    client = TestClient(app)
    resp = client.get(f"/sessions/{state.id}/files/../etc/secret")
    # FastAPI path: ".." segments may be normalized by httpx/Starlette before
    # reaching the route handler. Accept either 400 (guard fires) or 404 (route
    # match fails because Starlette stripped traversal). Both prevent escape.
    assert resp.status_code in (400, 404)
    sandbox.download_files.assert_not_called()


def test_host_mode_list_reads_project_workspace(monkeypatch, tmp_path):
    """Host-mode sessions (无活跃租约) 的文件列举仍走宿主项目工作区。"""
    sandbox = _make_sandbox_mock()
    app, store, mgr = _make_app_with_mgr(monkeypatch, tmp_path, sandbox)
    state = store.create(project_id="project-host")
    mgr.get_sandbox.return_value = None

    try:
        ws = Path(mgr.workspace_dir(state.id))
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "hello.txt").write_bytes(b"world")
        client = TestClient(app)
        resp = client.get(f"/sessions/{state.id}/files")
        assert resp.status_code == 200
        assert "hello.txt" in [item["path"] for item in resp.json()]
        # 没有活跃项目租约时不经过沙箱。
        sandbox.upload_files.assert_not_called()
    finally:
        import hagent.server.routers.sessions as sess_mod
        sess_mod._MANAGER = None
