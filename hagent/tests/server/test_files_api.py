from tests.server.helpers import create_project_session
import os

from fastapi.testclient import TestClient

from hagent.server.app import create_app


def _make_app(monkeypatch, tmp_path):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    return TestClient(create_app())


def test_list_files_empty(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    sid = create_project_session(client).json()["session_id"]
    r = client.get(f"/sessions/{sid}/files")
    assert r.status_code == 200
    paths = {item["path"] for item in r.json()}
    assert {"sources", "structured", "deliverables", "tmp", ".gitignore"} <= paths
    assert ".git" not in paths


def test_download_existing_file(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    sid = create_project_session(client).json()["session_id"]
    # 手动写一个文件到 workspace
    project_id = client.get(f"/sessions/{sid}").json()["project_id"]
    ws = str(tmp_path / "projects" / project_id / "workspace")
    with open(os.path.join(ws, "hello.txt"), "w") as f:
        f.write("hi there")
    r = client.get(f"/sessions/{sid}/files/hello.txt")
    assert r.status_code == 200
    assert r.text == "hi there"


def test_download_nonexistent_404(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    sid = create_project_session(client).json()["session_id"]
    r = client.get(f"/sessions/{sid}/files/nope.txt")
    assert r.status_code == 404


def test_path_traversal_blocked(tmp_path, monkeypatch):
    client = _make_app(monkeypatch, tmp_path)
    sid = create_project_session(client).json()["session_id"]
    r = client.get(f"/sessions/{sid}/files/../../etc/passwd")
    assert r.status_code in (400, 404)


def test_path_prefix_match_blocked(tmp_path, monkeypatch):
    # 防御 startswith 误判：若 workspace 为 /tmp/.../UUID/workspace
    # 一个攻击 path 不能逃到一个名字以 "workspace" 开头的兄弟目录。
    client = _make_app(monkeypatch, tmp_path)
    sid = create_project_session(client).json()["session_id"]
    project_id = client.get(f"/sessions/{sid}").json()["project_id"]
    ws = str(tmp_path / "projects" / project_id / "workspace")
    # 在 workspace 的父目录下创建 workspace-evil 兄弟目录
    from pathlib import Path
    sibling = Path(ws).parent / "workspace-evil"
    sibling.mkdir(parents=True, exist_ok=True)
    (sibling / "secret.txt").write_text("nope")
    # 攻击路径：../workspace-evil/secret.txt — 应被拒
    r = client.get(f"/sessions/{sid}/files/../workspace-evil/secret.txt")
    assert r.status_code in (400, 404)


def test_upload_endpoint_deprecated_410(tmp_path, monkeypatch):
    # 票6:上传归属 project,session 级上传路径废弃(spec §4.4)。
    client = _make_app(monkeypatch, tmp_path)
    sid = create_project_session(client).json()["session_id"]
    files = {"file": ("greeting.txt", b"hello upload", "text/plain")}
    data = {"path": "greeting.txt"}
    r = client.post(f"/sessions/{sid}/files", files=files, data=data)
    assert r.status_code == 410
