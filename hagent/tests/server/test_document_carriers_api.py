"""REST adapter：预览版字节流与 sidecar JSON 两条读端点。

鉴权、404 与项目归属语义与既有矩阵读端点同构（`test_assets_api.py` 是 prior art）：
项目不存在 404、文档不存在 404、跨项目取不到；不 mock 服务内部。
"""

import json

import pytest
from fastapi.testclient import TestClient

from hagent.assets.model import Actor
from hagent.assets.service import get_asset_service
from hagent.ingest.blobs import BLOB_KIND_PREVIEW, BlobStore, set_blob_store
from hagent.ingest.paths import sidecar_path_for
from hagent.server.app import create_app
from hagent.server.project_workspace import get_project_workspace

SYSTEM = Actor(kind="system", ref="test")

MARKDOWN_PATH = "sources/招标文件.md"
PREVIEW_BYTES = b"%PDF-1.7\n% preview bytes\n"
SIDECAR = {
    "schema": 1,
    "mdSha256": "0" * 64,
    "pages": [{"index": 0, "width": 1191, "height": 1684}],
    "blocks": [
        {"mdStart": 1, "mdEnd": 1, "label": "table", "rects": [{"page": 0, "bbox": [0.1, 0.2, 0.5, 0.3]}]}
    ],
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    set_blob_store(BlobStore(tmp_path / "blobs"))
    yield TestClient(create_app())
    set_blob_store(None)


@pytest.fixture
def project(client):
    return client.post("/projects", json={"name": "溯源载体测试项目"}).json()["id"]


@pytest.fixture
def document(client, project):
    """一份走完入库的文档：md 与 sidecar 在 workspace，预览版在 blob 区。"""
    workspace = get_project_workspace()
    workspace.apply_changes(
        project,
        updated={
            MARKDOWN_PATH: "# 招标文件\n".encode("utf-8"),
            sidecar_path_for(MARKDOWN_PATH): json.dumps(SIDECAR, ensure_ascii=False).encode("utf-8"),
        },
        deleted=(),
    )
    workspace.commit(project, summary="ocr", kind="ocr_ingest", paths=[MARKDOWN_PATH])

    from hagent.ingest.blobs import get_blob_store

    preview_sha = get_blob_store().put(BLOB_KIND_PREVIEW, PREVIEW_BYTES)
    service = get_asset_service()
    record = service.register_workspace_document(
        project,
        path=MARKDOWN_PATH,
        doc_type="tender",
        workspace_root=workspace.path_for(project),
        actor=SYSTEM,
    )
    service.attach_document_blobs(
        project, record.id, origin_sha256="a" * 64, preview_sha256=preview_sha, actor=SYSTEM
    )
    return record.id


# —— 预览版字节流 ——


def test_preview_returns_pdf_bytes(client, project, document):
    r = client.get(f"/projects/{project}/documents/{document}/preview")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == PREVIEW_BYTES


def test_preview_404_when_document_has_no_pdf_original(client, project):
    """开发期 `.md` 语料与历史项目没有原件——前端据此降级到 md 预览，不是坏掉。"""
    workspace = get_project_workspace()
    workspace.apply_changes(project, updated={"sources/legacy.md": b"# legacy"}, deleted=())
    record = get_asset_service().register_workspace_document(
        project,
        path="sources/legacy.md",
        doc_type="tender",
        workspace_root=workspace.path_for(project),
        actor=SYSTEM,
    )
    assert client.get(f"/projects/{project}/documents/{record.id}/preview").status_code == 404


# —— sidecar ——


def test_sidecar_returns_schema_v1_payload(client, project, document):
    r = client.get(f"/projects/{project}/documents/{document}/sidecar")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/json"
    assert r.json() == SIDECAR


def test_sidecar_404_when_missing(client, project):
    """sidecar 缺失 → 前端顶部黄条「原文映射失效」，PDF 照常打开。"""
    workspace = get_project_workspace()
    workspace.apply_changes(project, updated={"sources/nosidecar.md": b"# x"}, deleted=())
    record = get_asset_service().register_workspace_document(
        project,
        path="sources/nosidecar.md",
        doc_type="tender",
        workspace_root=workspace.path_for(project),
        actor=SYSTEM,
    )
    assert client.get(f"/projects/{project}/documents/{record.id}/sidecar").status_code == 404


# —— 404 与归属 ——


@pytest.mark.parametrize("suffix", ["preview", "sidecar", "original"])
def test_unknown_project_or_document_is_404(client, project, document, suffix):
    assert client.get(f"/projects/nope/documents/{document}/{suffix}").status_code == 404
    assert client.get(f"/projects/{project}/documents/doc-nope/{suffix}").status_code == 404


@pytest.mark.parametrize("suffix", ["preview", "sidecar", "original"])
def test_document_of_another_project_is_404(client, project, document, suffix):
    other = client.post("/projects", json={"name": "另一个项目"}).json()["id"]
    assert client.get(f"/projects/{other}/documents/{document}/{suffix}").status_code == 404


@pytest.mark.parametrize("suffix", ["preview", "sidecar", "original"])
def test_requires_api_key(tmp_path, monkeypatch, suffix):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.setenv("HAGENT_API_KEY", "secret")
    guarded = TestClient(create_app())
    assert guarded.get(f"/projects/p/documents/d/{suffix}").status_code == 401


# —— 注册表暴露降级判据 ——


def test_document_listing_flags_preview_availability(client, project, document):
    documents = client.get(f"/projects/{project}/documents").json()["documents"]
    assert [d["has_preview"] for d in documents if d["id"] == document] == [True]


@pytest.mark.parametrize("suffix", ["preview", "original"])
def test_pdf_range_and_head(client, project, document, suffix):
    from hagent.ingest.blobs import BLOB_KIND_ORIGIN, get_blob_store
    # 原件夹具的固定寻址键只用于路由测试。
    original = get_blob_store().path_for(BLOB_KIND_ORIGIN, "a" * 64)
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(PREVIEW_BYTES)
    url = f"/projects/{project}/documents/{document}/{suffix}"
    head = client.head(url)
    assert head.status_code == 200 and not head.content
    assert head.headers["accept-ranges"] == "bytes"
    response = client.get(url, headers={"Range": "bytes=0-7", "If-Range": head.headers["etag"]})
    assert response.status_code == 206 and response.content == PREVIEW_BYTES[:8]
    assert response.headers["content-range"] == f"bytes 0-7/{len(PREVIEW_BYTES)}"
    assert client.get(url, headers={"Range": "bytes=99999-"}).status_code == 416
    assert client.get(url, headers={"Range": "invalid"}).status_code == 400
    assert client.get(url, headers={"Range": "bytes=0-7", "If-Range": '"old"'}).status_code == 200


def test_sidecar_rejects_mismatched_version(client, project, document):
    workspace = get_project_workspace()
    bad = {**SIDECAR, "schema": 2}
    workspace.apply_changes(project, updated={sidecar_path_for(MARKDOWN_PATH): json.dumps(bad).encode()}, deleted=())
    assert client.get(f"/projects/{project}/documents/{document}/sidecar").status_code == 409


def test_blob_binding_cannot_replace_original(client, project, document):
    from hagent.assets.errors import AssetError
    service = get_asset_service()
    old = service.get_document(project, document)
    with pytest.raises(AssetError, match="固定原件"):
        service.attach_document_blobs(project, document, origin_sha256="b" * 64, preview_sha256=old.preview_sha256, actor=SYSTEM)
    assert service.get_document(project, document).origin_sha256 == old.origin_sha256


@pytest.mark.parametrize("path", [MARKDOWN_PATH, sidecar_path_for(MARKDOWN_PATH)])
def test_registered_source_cannot_be_replaced_by_upload(client, project, document, path):
    before = get_project_workspace().read_file(project, path)
    response = client.post(f"/projects/{project}/files", data={"path": path}, files={"file": ("x.md", b"changed")})
    assert response.status_code == 409
    assert get_project_workspace().read_file(project, path) == before
