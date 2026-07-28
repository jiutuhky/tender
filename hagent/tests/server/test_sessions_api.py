from tests.server.helpers import create_project_session
from fastapi.testclient import TestClient

from hagent.server.app import create_app


def test_create_session_requires_project_and_returns_conversation_only_state(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    client = TestClient(create_app())

    assert client.post("/sessions", json={}).status_code == 422
    project = client.post("/projects", json={"name": "测试项目"}).json()
    response = client.post("/sessions", json={"project_id": project["id"]})

    assert response.status_code == 200, response.text
    assert set(response.json()) == {
        "id",
        "session_id",
        "status",
        "created_at",
        "last_active",
        "project_id",
    }


def test_create_session_returns_id_and_project(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)

    r = create_project_session(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "session_id" in body
    assert body["status"] == "active"


def test_list_includes_created(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)

    r = create_project_session(client)
    sid = r.json()["session_id"]

    r = client.get("/sessions")
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()]
    assert sid in ids


def test_list_filters_by_project_id(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)

    pid_a = client.post("/projects", json={"name": "项目A"}).json()["id"]
    pid_b = client.post("/projects", json={"name": "项目B"}).json()["id"]
    sid_a = client.post("/sessions", json={"project_id": pid_a}).json()["id"]
    sid_b = client.post("/sessions", json={"project_id": pid_b}).json()["id"]

    r = client.get("/sessions", params={"project_id": pid_a})
    assert r.status_code == 200
    assert [s["id"] for s in r.json()] == [sid_a]

    r = client.get("/sessions", params={"project_id": pid_b})
    assert [s["id"] for s in r.json()] == [sid_b]

    # 不带参数仍是全量列举
    ids = [s["id"] for s in client.get("/sessions").json()]
    assert {sid_a, sid_b} <= set(ids)


def test_get_session_state(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)
    r = create_project_session(client)
    sid = r.json()["session_id"]

    r = client.get(f"/sessions/{sid}")
    assert r.status_code == 200
    assert r.json()["id"] == sid


def test_get_missing_session_404(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)
    r = client.get("/sessions/nope")
    assert r.status_code == 404


def test_delete_marks_ended(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)
    r = create_project_session(client)
    sid = r.json()["session_id"]

    r = client.delete(f"/sessions/{sid}")
    assert r.status_code == 200

    r = client.get(f"/sessions/{sid}")
    assert r.json()["status"] == "ended"


def test_delete_closes_cached_agent(tmp_path, monkeypatch):
    closed = []

    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    monkeypatch.setattr(
        "hagent.server.routers.sessions.close_agent",
        lambda sid: closed.append(sid),
    )
    app = create_app()
    client = TestClient(app)
    sid = create_project_session(client).json()["session_id"]

    r = client.delete(f"/sessions/{sid}")

    assert r.status_code == 200
    assert closed == [sid]
