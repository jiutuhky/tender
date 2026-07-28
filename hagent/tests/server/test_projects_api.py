from fastapi.testclient import TestClient

from hagent.server.app import create_app
from hagent.server.project_workspace import ProjectWorkspace
from hagent.server.projects import get_project_store


def _client(tmp_path, monkeypatch, *, raise_server_exceptions: bool = True) -> TestClient:
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    return TestClient(create_app(), raise_server_exceptions=raise_server_exceptions)


def test_create_project_returns_fields(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.post("/projects", json={"name": "XX市政务云招标", "metadata": {"doc_name": "招标文件.md"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"]
    assert body["name"] == "XX市政务云招标"
    assert body["status"] == "active"
    assert body["created_at"] > 0
    assert body["metadata"] == {"doc_name": "招标文件.md"}
    assert body["latest_session"] is None
    workspaces = ProjectWorkspace(tmp_path)
    assert workspaces.path_for(body["id"]).is_dir()
    assert workspaces.head(body["id"])


def test_create_project_validates_name(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    assert client.post("/projects", json={"name": ""}).status_code == 422
    assert client.post("/projects", json={"name": "   "}).status_code == 422
    assert client.post("/projects", json={"name": "x" * 201}).status_code == 422
    # strip 后入库
    r = client.post("/projects", json={"name": "  项目A  "})
    assert r.status_code == 200
    assert r.json()["name"] == "项目A"


def test_create_project_rolls_back_when_workspace_initialization_fails(tmp_path, monkeypatch):
    def fail_initialization(self, project_id):
        raise OSError("磁盘不可用")

    monkeypatch.setattr(
        ProjectWorkspace,
        "initialize",
        fail_initialization,
    )
    client = _client(tmp_path, monkeypatch, raise_server_exceptions=False)

    r = client.post("/projects", json={"name": "项目A"})

    assert r.status_code == 500
    assert client.get("/projects").json() == []
    assert get_project_store().list(include_deleted=True) == []


def test_get_project_detail_and_404(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    pid = client.post("/projects", json={"name": "项目A"}).json()["id"]
    r = client.get(f"/projects/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "项目A"
    assert body["sessions"] == []
    assert client.get("/projects/nope").status_code == 404


def test_list_projects_orders_by_activity(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    a = client.post("/projects", json={"name": "项目A"}).json()["id"]
    b = client.post("/projects", json={"name": "项目B"}).json()["id"]
    assert [p["id"] for p in client.get("/projects").json()] == [b, a]
    client.patch(f"/projects/{a}", json={"status": "parsed"})
    assert [p["id"] for p in client.get("/projects").json()] == [a, b]


def test_patch_project(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    pid = client.post("/projects", json={"name": "旧名"}).json()["id"]
    r = client.patch(f"/projects/{pid}", json={"name": "新名", "status": "parsed", "metadata": {"k": 1}})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "新名"
    assert body["status"] == "parsed"
    assert body["metadata"] == {"k": 1}
    assert client.patch("/projects/nope", json={"name": "x"}).status_code == 404
    # 空 PATCH:200,状态不变
    r = client.patch(f"/projects/{pid}", json={})
    assert r.status_code == 200
    assert r.json()["name"] == "新名"


def test_delete_project_soft_deletes(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    pid = client.post("/projects", json={"name": "项目A"}).json()["id"]
    workspaces = ProjectWorkspace(tmp_path)
    workspace = workspaces.path_for(pid)
    (workspace / "deliverables" / "保留成果.md").write_text("成果内容", encoding="utf-8")
    workspaces.commit(
        pid,
        summary="chat_turn: 保存成果",
        run_id="run-1",
        session_id="session-1",
        kind="chat_turn",
    )
    r = client.delete(f"/projects/{pid}")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["ended_sessions"] == []
    assert all(p["id"] != pid for p in client.get("/projects").json())
    # 软删后仍可单查
    r = client.get(f"/projects/{pid}")
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"
    assert workspaces.read_file(pid, "deliverables/保留成果.md") == "成果内容".encode()
    assert workspaces.history(pid, limit=1)[0].run_id == "run-1"
    assert client.delete("/projects/nope").status_code == 404


def test_create_session_under_project(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    pid = client.post("/projects", json={"name": "项目A"}).json()["id"]

    r = client.post("/sessions", json={"project_id": pid})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    assert r.json()["project_id"] == pid

    # 项目列表带 latest_session;详情嵌入 session 行
    listed = client.get("/projects").json()
    row = next(p for p in listed if p["id"] == pid)
    assert row["latest_session"] == {"id": sid, "status": "active"}
    detail = client.get(f"/projects/{pid}").json()
    assert [s["id"] for s in detail["sessions"]] == [sid]
    assert detail["sessions"][0]["project_id"] == pid


def test_create_session_with_unknown_project_404(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.post("/sessions", json={"project_id": "nope"})
    assert r.status_code == 404


def test_create_session_with_deleted_project_404(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    pid = client.post("/projects", json={"name": "项目A"}).json()["id"]
    client.delete(f"/projects/{pid}")
    r = client.post("/sessions", json={"project_id": pid})
    assert r.status_code == 404


def test_create_session_without_project_is_rejected(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    pid = client.post("/projects", json={"name": "项目A"}).json()["id"]
    r = client.post("/sessions", json={})
    assert r.status_code == 422
    # 被拒绝的请求不影响项目 latest_session
    row = next(p for p in client.get("/projects").json() if p["id"] == pid)
    assert row["latest_session"] is None


def test_latest_session_flips_to_newer(tmp_path, monkeypatch):
    import time

    client = _client(tmp_path, monkeypatch)
    pid = client.post("/projects", json={"name": "项目A"}).json()["id"]
    client.post("/sessions", json={"project_id": pid})
    time.sleep(0.01)
    sid2 = client.post("/sessions", json={"project_id": pid}).json()["id"]
    row = next(p for p in client.get("/projects").json() if p["id"] == pid)
    assert row["latest_session"]["id"] == sid2


def test_delete_project_cascades_active_sessions(tmp_path, monkeypatch):
    closed: list[str] = []
    monkeypatch.setattr(
        "hagent.server.routers.sessions.close_agent",
        lambda sid: closed.append(sid),
    )
    client = _client(tmp_path, monkeypatch)
    pid = client.post("/projects", json={"name": "项目A"}).json()["id"]
    sid = client.post("/sessions", json={"project_id": pid}).json()["id"]
    # 已结束的 session 不重复结束
    ended_sid = client.post("/sessions", json={"project_id": pid}).json()["id"]
    client.delete(f"/sessions/{ended_sid}")

    r = client.delete(f"/projects/{pid}")
    assert r.status_code == 200
    assert r.json()["ended_sessions"] == [sid]
    assert client.get(f"/sessions/{sid}").json()["status"] == "ended"
    # close_agent 对 sid 只在项目级联中调用一次,ended_sid 在其自身 DELETE 时调用
    assert closed == [ended_sid, sid]


def test_projects_require_api_key_when_set(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.setenv("HAGENT_API_KEY", "secret")
    client = TestClient(create_app())
    assert client.get("/projects").status_code == 401
    r = client.get("/projects", headers={"Authorization": "Bearer secret"})
    assert r.status_code == 200
