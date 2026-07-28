from fastapi.testclient import TestClient

from hagent.server.app import create_app


def test_healthz_is_public():
    app = create_app()
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_protected_endpoint_requires_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("HAGENT_API_KEY", "secret-key")
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    app = create_app()
    client = TestClient(app)
    r = client.get("/sessions")
    assert r.status_code == 401


def test_protected_endpoint_accepts_bearer(monkeypatch, tmp_path):
    monkeypatch.setenv("HAGENT_API_KEY", "secret-key")
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    app = create_app()
    client = TestClient(app)
    r = client.get("/sessions", headers={"Authorization": "Bearer secret-key"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_protected_endpoint_rejects_wrong_bearer(monkeypatch, tmp_path):
    monkeypatch.setenv("HAGENT_API_KEY", "secret-key")
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    app = create_app()
    client = TestClient(app)
    r = client.get("/sessions", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_lowercase_bearer_scheme_accepted(monkeypatch, tmp_path):
    monkeypatch.setenv("HAGENT_API_KEY", "secret-key")
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    app = create_app()
    client = TestClient(app)
    r = client.get("/sessions", headers={"Authorization": "bearer secret-key"})
    assert r.status_code == 200


def test_no_scheme_returns_401(monkeypatch, tmp_path):
    monkeypatch.setenv("HAGENT_API_KEY", "secret-key")
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    app = create_app()
    client = TestClient(app)
    r = client.get("/sessions", headers={"Authorization": "secret-key"})
    assert r.status_code == 401
