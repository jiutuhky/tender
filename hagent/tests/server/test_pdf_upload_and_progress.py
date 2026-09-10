"""上传口收 PDF：超限立即报错、原件不进仓、解析进度沿既有 SSE 通道上报。

OCR 是上传后的确定性前置异步任务——上传请求立即返回，消息流在起 agent 前把它
等完。这里替掉入库管线本身（它的行为由 `tests/ingest/test_pipeline.py` 覆盖），
只验时序与协议。
"""

from __future__ import annotations

import io
import threading

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from hagent.ingest.pipeline import IngestResult
from hagent.ingest.tasks import IngestRegistry, set_ingest_registry
from hagent.server.app import create_app
from hagent.server.project_workspace import get_project_workspace

PDF_NAME = "招标文件.pdf"


def make_pdf(pages: int = 3) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595.32, height=841.92)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class FakePipeline:
    """按外部信号收尾的假管线——让用例能观察「解析未完时 agent 不起跑」。"""

    release = threading.Event()
    started = threading.Event()
    done = threading.Event()
    error: Exception | None = None

    def ingest_pdf(self, project_id, *, data, pdf_path, on_progress=None):
        FakePipeline.started.set()
        for done in (1, 2, 3):
            if on_progress is not None:
                on_progress(done, 3)
        FakePipeline.release.wait(5)
        FakePipeline.done.set()
        if FakePipeline.error is not None:
            raise FakePipeline.error
        return IngestResult(
            document_id="doc-abc",
            markdown_path="sources/招标文件.md",
            sidecar_path="sources/招标文件.sidecar.json",
            origin_sha256="a" * 64,
            preview_sha256="b" * 64,
            page_count=3,
            failed_pages=(1,),
        )


class FakeAgent:
    """起跑即结束的假 agent——本文件只关心它「什么时候」起跑。"""

    ingest_done_at_start: bool | None = None

    def stream(self, *_args, **_kwargs):
        FakeAgent.ingest_done_at_start = FakePipeline.done.is_set()
        yield from ()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: FakeAgent(),
    )
    FakePipeline.release = threading.Event()
    FakePipeline.started = threading.Event()
    FakePipeline.done = threading.Event()
    FakePipeline.error = None
    FakeAgent.ingest_done_at_start = None
    set_ingest_registry(IngestRegistry(pipeline_factory=FakePipeline))
    yield TestClient(create_app())
    FakePipeline.release.set()
    set_ingest_registry(None)


@pytest.fixture
def project(client):
    return client.post("/projects", json={"name": "PDF 上传测试"}).json()["id"]


def upload(client, project, data=None, name=PDF_NAME):
    return client.post(
        f"/projects/{project}/files",
        files={"file": (name, data if data is not None else make_pdf(), "application/pdf")},
    )


# —— 准入 ——


def test_pdf_upload_is_accepted_and_reports_page_count(client, project):
    r = upload(client, project)
    assert r.status_code == 200, r.text
    assert r.json()["parsing"] == {"pages": 3}


def test_oversized_pdf_is_rejected_immediately(client, project, monkeypatch):
    monkeypatch.setenv("HAGENT_INGEST_MAX_BYTES", "10")
    r = upload(client, project)
    assert r.status_code == 400
    assert "体积" in r.json()["detail"]


def test_too_many_pages_is_rejected_immediately(client, project, monkeypatch):
    monkeypatch.setenv("HAGENT_INGEST_MAX_PAGES", "2")
    r = upload(client, project)
    assert r.status_code == 400
    assert "页" in r.json()["detail"]


def test_broken_pdf_is_rejected_immediately(client, project):
    r = upload(client, project, data=b"not a pdf at all")
    assert r.status_code == 400


# —— 原件不进仓 ——


def test_uploaded_pdf_never_enters_the_repo(client, project):
    upload(client, project)
    tracked = [f["path"] for f in client.get(f"/projects/{project}/workspace/files").json()]
    assert not [path for path in tracked if path.lower().endswith(".pdf")]

    pending = get_project_workspace().pending_changes(project)
    assert pending.updated == () and pending.deleted == ()


def test_markdown_upload_path_is_unchanged(client, project):
    """无 PDF 的开发期 `.md` 语料照旧直接落 sources/ 并形成提交。"""
    r = client.post(
        f"/projects/{project}/files",
        files={"file": ("语料.md", b"# hi", "text/markdown")},
    )
    assert r.status_code == 200
    assert r.json()["path"] == "sources/语料.md"
    assert r.json()["revision"]


# —— SSE 进度与起 agent 时序 ——


def read_events(client, session_id, content="/skill:noop"):
    frames: list[tuple[str, str]] = []
    with client.stream(
        "POST", f"/sessions/{session_id}/messages", json={"content": content}
    ) as response:
        assert response.status_code == 200
        buffer = ""
        for chunk in response.iter_text():
            buffer += chunk
            while "\n\n" in buffer:
                frame, buffer = buffer.split("\n\n", 1)
                event = next(
                    (line[len("event: ") :] for line in frame.splitlines() if line.startswith("event: ")),
                    "",
                )
                data = next(
                    (line[len("data: ") :] for line in frame.splitlines() if line.startswith("data: ")),
                    "",
                )
                frames.append((event, data))
                if event in ("done", "error"):
                    return frames
    return frames


def test_progress_is_reported_on_the_existing_message_stream(client, project):
    upload(client, project)
    session = client.post("/sessions", json={"project_id": project}).json()["session_id"]
    assert FakePipeline.started.wait(5)
    FakePipeline.release.set()

    events = read_events(client, session)
    progress = [data for event, data in events if event == "ingest.progress"]
    assert progress, [event for event, _ in events]
    assert "原文解析 3/3 页" in progress[-1]
    assert any(event == "ingest.completed" for event, _ in events)


def test_agent_does_not_start_before_markdown_and_sidecar_are_ready(client, project):
    """agent 的第一帧必须落在解析收尾之后——它读的 md 与 sidecar 那时才存在。"""
    upload(client, project)
    session = client.post("/sessions", json={"project_id": project}).json()["session_id"]
    assert FakePipeline.started.wait(5)

    # 解析仍在跑时就发消息；解析在消息处理途中才收尾
    threading.Timer(0.3, FakePipeline.release.set).start()
    assert not FakePipeline.done.is_set()

    events = read_events(client, session)

    assert FakeAgent.ingest_done_at_start is True
    names = [event for event, _ in events]
    assert names.index("run.started") < names.index("ingest.completed")
    # Run 在前置解析期间就可取消，模型仍须等 md 与 sidecar 就绪。
    assert FakeAgent.ingest_done_at_start is True


def test_ingest_failure_is_surfaced_and_does_not_block_the_agent(client, project):
    """失败页在 md 里已留占位，整份不作废——把失败如实报出来，agent 照常起跑。"""
    FakePipeline.error = RuntimeError("OCR 服务不可用")
    upload(client, project)
    session = client.post("/sessions", json={"project_id": project}).json()["session_id"]
    assert FakePipeline.started.wait(5)
    FakePipeline.release.set()

    events = read_events(client, session)
    failed = [data for event, data in events if event == "ingest.failed"]
    assert failed and "OCR 服务不可用" in failed[0]
    assert any(event == "run.started" for event, _ in events)


def test_second_message_does_not_wait_again(client, project):
    upload(client, project)
    session = client.post("/sessions", json={"project_id": project}).json()["session_id"]
    assert FakePipeline.started.wait(5)
    FakePipeline.release.set()

    read_events(client, session)
    again = read_events(client, session)
    assert not [event for event, _ in again if event.startswith("ingest.")]
