"""票6:项目上传 + workspace 读取端点的 API 契约。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hagent.server.app import create_app
from hagent.server.routers.sessions import get_session_manager
from tests.server.helpers import create_project_session


def _make_app(monkeypatch, tmp_path):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    return TestClient(create_app())


def _create_project(client) -> str:
    r = client.post("/projects", json={"name": "测试项目"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _upload(client, pid: str, *, name: str, content: bytes, path: str | None = None):
    data = {} if path is None else {"path": path}
    return client.post(
        f"/projects/{pid}/files",
        files={"file": (name, content, "text/markdown")},
        data=data,
    )


def test_upload_defaults_into_sources_and_creates_upload_commit(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    pid = _create_project(client)

    r = _upload(client, pid, name="招标文件.md", content="# 招标\n".encode())

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["path"] == "sources/招标文件.md"
    assert body["size"] == len("# 招标\n".encode())
    assert body["revision"]
    host_file = tmp_path / "projects" / pid / "workspace" / "sources" / "招标文件.md"
    assert host_file.read_text(encoding="utf-8") == "# 招标\n"

    history = client.get(f"/projects/{pid}/workspace/history").json()
    latest = history[0]
    assert latest["sha"] == body["revision"]
    assert latest["kind"] == "upload"
    assert latest["summary"] == "upload: sources/招标文件.md"
    assert latest["run_id"] is None
    assert latest["session_id"] is None


def test_addendum_upload_appends_second_commit(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    pid = _create_project(client)
    assert _upload(client, pid, name="招标文件.md", content=b"v1").status_code == 200

    r = _upload(
        client,
        pid,
        name="澄清.md",
        content="第一号补遗".encode(),
        path="sources/补遗/澄清1.md",
    )

    assert r.status_code == 200, r.text
    assert r.json()["path"] == "sources/补遗/澄清1.md"
    history = client.get(f"/projects/{pid}/workspace/history").json()
    # 初始化 + 两次上传
    assert len(history) == 3
    assert [entry["kind"] for entry in history[:2]] == ["upload", "upload"]


def test_identical_reupload_is_commit_noop(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    pid = _create_project(client)
    first = _upload(client, pid, name="a.md", content=b"same")
    again = _upload(client, pid, name="a.md", content=b"same")

    assert first.json()["revision"]
    assert again.status_code == 200
    assert again.json()["revision"] is None
    assert len(client.get(f"/projects/{pid}/workspace/history").json()) == 2


@pytest.mark.parametrize(
    "path",
    [
        "deliverables/x.md",
        "../evil.md",
        "sources/../deliverables/x.md",
        "/etc/passwd",
        "sources/.git/config",
        "sources",
    ],
)
def test_upload_rejects_paths_outside_sources(tmp_path, monkeypatch, path):
    client = _make_app(monkeypatch, tmp_path)
    pid = _create_project(client)

    r = _upload(client, pid, name="x.md", content=b"x", path=path)

    assert r.status_code == 400, path


def test_upload_unknown_project_404(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    r = _upload(client, "nope", name="x.md", content=b"x")
    assert r.status_code == 404


def test_upload_without_lease_does_not_create_vm(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    pid = _create_project(client)

    r = _upload(client, pid, name="x.md", content=b"x")

    assert r.status_code == 200
    assert r.json()["sandbox_synced"] is False
    assert get_session_manager().get_project_sandbox(pid) is None


def test_workspace_files_listing_and_read(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    pid = _create_project(client)
    _upload(client, pid, name="招标文件.md", content="# 招标\n".encode())

    listing = client.get(f"/projects/{pid}/workspace/files")
    assert listing.status_code == 200
    entries = {entry["path"]: entry["size"] for entry in listing.json()}
    assert entries["sources/招标文件.md"] == len("# 招标\n".encode())
    assert ".gitignore" in entries

    read = client.get(f"/projects/{pid}/workspace/files/sources/招标文件.md")
    assert read.status_code == 200
    assert read.text == "# 招标\n"


def test_workspace_read_guards(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    pid = _create_project(client)

    assert client.get(f"/projects/{pid}/workspace/files/nope.md").status_code == 404
    assert (
        client.get(f"/projects/{pid}/workspace/files/.git/config").status_code == 400
    )
    # httpx 可能在客户端规范化 ".." 段,400(守卫命中)或 404(路径被折叠)皆为拒绝
    assert client.get(
        f"/projects/{pid}/workspace/files/../../etc/passwd"
    ).status_code in (400, 404)


def test_workspace_history_respects_limit(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    pid = _create_project(client)
    _upload(client, pid, name="a.md", content=b"a")
    _upload(client, pid, name="b.md", content=b"b")

    r = client.get(f"/projects/{pid}/workspace/history", params={"limit": 1})

    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["summary"] == "upload: sources/b.md"


def test_workspace_endpoints_unknown_project_404(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    assert client.get("/projects/nope/workspace/files").status_code == 404
    assert client.get("/projects/nope/workspace/files/a.md").status_code == 404
    assert client.get("/projects/nope/workspace/history").status_code == 404


def test_session_upload_endpoint_gone(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    sid = create_project_session(client).json()["session_id"]

    r = client.post(
        f"/sessions/{sid}/files",
        files={"file": ("x.md", b"x", "text/markdown")},
        data={"path": "x.md"},
    )

    assert r.status_code == 410


def test_project_files_endpoints_require_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.setenv("HAGENT_API_KEY", "secret-key")
    client = TestClient(create_app())
    auth = {"Authorization": "Bearer secret-key"}
    pid = client.post("/projects", json={"name": "鉴权项目"}, headers=auth).json()["id"]

    assert (
        client.post(
            f"/projects/{pid}/files", files={"file": ("x.md", b"x")}
        ).status_code
        == 401
    )
    assert client.get(f"/projects/{pid}/workspace/files").status_code == 401
    assert client.get(f"/projects/{pid}/workspace/history").status_code == 401

    r = client.post(
        f"/projects/{pid}/files", files={"file": ("x.md", b"x")}, headers=auth
    )
    assert r.status_code == 200
    assert client.get(f"/projects/{pid}/workspace/files", headers=auth).status_code == 200
