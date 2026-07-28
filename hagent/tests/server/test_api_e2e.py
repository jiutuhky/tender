from tests.server.helpers import create_project_session
import io

from fastapi.testclient import TestClient

from hagent.server.app import create_app


class FakeAgent:
    def stream(self, *_a, **_kw):
        class FakeAIChunk:
            type = "AIMessageChunk"
            content = "demo answer"
            tool_call_chunks = []

        yield ((), "messages", (FakeAIChunk(), {}))

    def get_state(self, _cfg):
        class S:
            values = {"messages": [], "todos": []}
        return S()


def test_full_session_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: FakeAgent(),
    )
    app = create_app()
    client = TestClient(app)

    # 1. health
    assert client.get("/healthz").json() == {"ok": True}

    # 2. create
    created = create_project_session(client).json()
    sid = created["session_id"]
    assert sid
    pid = client.get(f"/sessions/{sid}").json()["project_id"]

    # 3. upload(票6:上传归属 project,落 sources/)
    r = client.post(
        f"/projects/{pid}/files",
        files={"file": ("data.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert r.status_code == 200
    assert r.json()["path"] == "sources/data.csv"

    # 4. list files(canonical workspace 端点)
    r = client.get(f"/projects/{pid}/workspace/files")
    paths = [f["path"] for f in r.json()]
    assert "sources/data.csv" in paths

    # 5. POST message + 消费 SSE
    with client.stream(
        "POST", f"/sessions/{sid}/messages", json={"content": "process the csv"}
    ) as r:
        body = b"".join(r.iter_bytes())
        assert b"demo answer" in body
        assert b"event: done" in body

    # 6. todos
    r = client.get(f"/sessions/{sid}/todos")
    assert isinstance(r.json(), list)

    # 7. download(workspace 读取端点 + session 兼容读)
    r = client.get(f"/projects/{pid}/workspace/files/sources/data.csv")
    assert r.text == "a,b\n1,2\n"
    r = client.get(f"/sessions/{sid}/files/sources/data.csv")
    assert r.text == "a,b\n1,2\n"

    # 8. delete
    r = client.delete(f"/sessions/{sid}")
    assert r.status_code == 200
    assert client.get(f"/sessions/{sid}").json()["status"] == "ended"
