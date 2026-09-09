"""入库管线的外部行为：准入、产物落点、仓内不留二进制。

OCR 服务在缝外——这里用一个按真实响应形状回放夹具的假客户端替掉网络那一跳，
装配逻辑本身由 `test_assembler.py` 直接覆盖。
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from pypdf import PdfWriter

from hagent.assets.service import AssetService
from hagent.assets.store import AssetStore
from hagent.ingest.assembler import OcrBlock, OcrPage, failed_page
from hagent.ingest.blobs import BLOB_KIND_ORIGIN, BLOB_KIND_PREVIEW, BlobStore
from hagent.ingest.pipeline import IngestLimits, IngestPipeline, UploadRejected, check_upload
from hagent.server.project_workspace import ProjectWorkspace

PROJECT = "proj-ingest"
PDF_PATH = "sources/招标文件.pdf"


def make_pdf(pages: int = 3, *, width: float = 595.32, height: float = 841.92) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=width, height=height)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class FakeOcr:
    """按页产出可预期结果的假 OCR；`fail_pages` 里的页模拟解析失败。"""

    def __init__(self, fail_pages: set[int] | None = None):
        self.fail_pages = fail_pages or set()
        self.progress: list[tuple[int, int]] = []

    def parse_pdf(self, data: bytes, *, on_progress=None) -> list[OcrPage]:
        from hagent.ingest.pdf import page_sizes

        total = len(page_sizes(data))
        pages = []
        for index in range(total):
            if index in self.fail_pages:
                pages.append(failed_page(index))
            else:
                text = f"第 {index + 1} 页正文"
                pages.append(
                    OcrPage(
                        index=index,
                        width=1191,
                        height=1684,
                        markdown=text,
                        blocks=(
                            OcrBlock(
                                label="text", content=text, bbox=(100, 200, 500, 400), group_id=index
                            ),
                        ),
                    )
                )
            if on_progress is not None:
                on_progress(index + 1, total)
                self.progress.append((index + 1, total))
        return pages


@pytest.fixture
def workspace(tmp_path) -> ProjectWorkspace:
    ws = ProjectWorkspace(tmp_path / "workspaces")
    ws.initialize(PROJECT)
    return ws


@pytest.fixture
def pipeline(tmp_path, workspace):
    return lambda ocr: IngestPipeline(
        ocr=ocr,
        blobs=BlobStore(tmp_path / "blobs"),
        workspace=workspace,
        service=AssetService(AssetStore(tmp_path / "assets.sqlite")),
    )


# —— 准入：超限立即报错 ——


def test_rejects_oversized_file_before_parsing():
    data = make_pdf(2)
    with pytest.raises(UploadRejected, match="体积"):
        check_upload(data, "x.pdf", IngestLimits(max_pages=100, max_bytes=len(data) - 1))


def test_rejects_too_many_pages_before_parsing():
    with pytest.raises(UploadRejected, match="页"):
        check_upload(make_pdf(5), "x.pdf", IngestLimits(max_pages=4))


def test_rejects_non_pdf_payload():
    with pytest.raises(UploadRejected):
        check_upload("这不是 PDF".encode("utf-8"), "x.pdf", IngestLimits())


def test_accepts_file_within_limits():
    assert check_upload(make_pdf(3), "x.pdf", IngestLimits(max_pages=3)) == 3


# —— 产物 ——


def test_ingest_writes_markdown_and_sidecar_only(pipeline, workspace):
    ocr = FakeOcr()
    result = pipeline(ocr).ingest_pdf(PROJECT, data=make_pdf(3), pdf_path=PDF_PATH)

    assert result.markdown_path == "sources/招标文件.md"
    assert result.sidecar_path == "sources/招标文件.sidecar.json"

    tracked = {file.path for file in workspace.list_files(PROJECT)}
    assert result.markdown_path in tracked and result.sidecar_path in tracked
    # 仓内不留任何二进制——原件与预览版都在 workspace 之外
    assert not [path for path in tracked if path.lower().endswith(".pdf")]


def test_ingest_leaves_no_pending_changes(pipeline, workspace):
    """产物已提交：解析后 `git status` 干净，画布与 checkpoint 不被脏工作区干扰。"""
    pipeline(FakeOcr()).ingest_pdf(PROJECT, data=make_pdf(2), pdf_path=PDF_PATH)
    pending = workspace.pending_changes(PROJECT)
    assert pending.updated == () and pending.deleted == ()


def test_sidecar_is_bound_schema_v2_and_matches_markdown(pipeline, workspace):
    import hashlib

    result = pipeline(FakeOcr()).ingest_pdf(PROJECT, data=make_pdf(2), pdf_path=PDF_PATH)
    markdown = workspace.read_file(PROJECT, result.markdown_path).decode("utf-8")
    sidecar = json.loads(workspace.read_file(PROJECT, result.sidecar_path))

    assert sidecar["schema"] == 2
    assert sidecar["originSha256"] == result.origin_sha256
    assert sidecar["previewSha256"] == result.preview_sha256
    assert sidecar["coordinateSpace"] == "page-display-normalized"
    assert sidecar["mdLineCount"] == len(markdown.splitlines())
    assert sidecar["mdSha256"] == hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    assert len(sidecar["pages"]) == 2


def test_original_and_preview_land_outside_the_workspace(tmp_path, pipeline, workspace):
    blobs = BlobStore(tmp_path / "blobs")
    ingest = IngestPipeline(
        ocr=FakeOcr(),
        blobs=blobs,
        workspace=workspace,
        service=AssetService(AssetStore(tmp_path / "assets.sqlite")),
    )
    result = ingest.ingest_pdf(PROJECT, data=make_pdf(2), pdf_path=PDF_PATH)

    assert blobs.exists(BLOB_KIND_ORIGIN, result.origin_sha256)
    assert blobs.exists(BLOB_KIND_PREVIEW, result.preview_sha256)
    workspace_root = workspace.path_for(PROJECT).resolve()
    for kind, digest in (
        (BLOB_KIND_ORIGIN, result.origin_sha256),
        (BLOB_KIND_PREVIEW, result.preview_sha256),
    ):
        assert not blobs.path_for(kind, digest).resolve().is_relative_to(workspace_root)


def test_preview_keeps_page_count_and_per_page_size(tmp_path, pipeline, workspace):
    """归一化 bbox 按逐页尺寸算——预览版改了页面几何，全文高亮就整体错位。"""
    from hagent.ingest.pdf import page_sizes

    blobs = BlobStore(tmp_path / "blobs")
    data = make_pdf(3)
    ingest = IngestPipeline(
        ocr=FakeOcr(),
        blobs=blobs,
        workspace=workspace,
        service=AssetService(AssetStore(tmp_path / "assets.sqlite")),
    )
    result = ingest.ingest_pdf(PROJECT, data=data, pdf_path=PDF_PATH)
    preview = blobs.get(BLOB_KIND_PREVIEW, result.preview_sha256)

    assert page_sizes(preview) == page_sizes(data)


# —— 部分页失败 ——


def test_partial_page_failure_does_not_void_the_document(pipeline, workspace):
    result = pipeline(FakeOcr(fail_pages={1})).ingest_pdf(
        PROJECT, data=make_pdf(3), pdf_path=PDF_PATH
    )

    assert result.failed_pages == (1,)
    markdown = workspace.read_file(PROJECT, result.markdown_path).decode("utf-8")
    assert "第 1 页正文" in markdown and "第 3 页正文" in markdown
    assert "第 2 页原文解析失败" in markdown

    sidecar = json.loads(workspace.read_file(PROJECT, result.sidecar_path))
    assert [rect["page"] for entry in sidecar["blocks"] for rect in entry["rects"]] == [0, 2]


# —— 进度 ——


def test_progress_is_reported_per_page(pipeline):
    ocr = FakeOcr()
    seen: list[tuple[int, int]] = []
    pipeline(ocr).ingest_pdf(
        PROJECT, data=make_pdf(3), pdf_path=PDF_PATH, on_progress=lambda d, t: seen.append((d, t))
    )
    assert seen == [(1, 3), (2, 3), (3, 3)]


# —— 注册 ——


def test_document_is_registered_with_blob_keys(tmp_path, workspace):
    service = AssetService(AssetStore(tmp_path / "assets.sqlite"))
    ingest = IngestPipeline(
        ocr=FakeOcr(),
        blobs=BlobStore(tmp_path / "blobs"),
        workspace=workspace,
        service=service,
    )
    result = ingest.ingest_pdf(PROJECT, data=make_pdf(2), pdf_path=PDF_PATH)

    record = service.get_document(PROJECT, result.document_id)
    assert record.path == result.markdown_path
    assert record.origin_sha256 == result.origin_sha256
    assert record.preview_sha256 == result.preview_sha256


def test_same_filename_keeps_registered_version(pipeline, workspace):
    runner = pipeline(FakeOcr())
    first = runner.ingest_pdf(PROJECT, data=make_pdf(2), pdf_path=PDF_PATH)
    before = workspace.read_file(PROJECT, first.markdown_path)
    second = runner.ingest_pdf(PROJECT, data=make_pdf(3), pdf_path=PDF_PATH)
    assert first.markdown_path != second.markdown_path
    assert workspace.read_file(PROJECT, first.markdown_path) == before
    assert runner._service.get_document(PROJECT, first.document_id).origin_sha256 == first.origin_sha256


def test_same_text_different_original_rejected_before_writing(pipeline, workspace):
    runner = pipeline(FakeOcr())
    first = runner.ingest_pdf(PROJECT, data=make_pdf(2), pdf_path=PDF_PATH)
    before = workspace.read_file(PROJECT, first.sidecar_path)
    with pytest.raises(UploadRejected, match="其他原件"):
        runner.ingest_pdf(PROJECT, data=make_pdf(2, width=500), pdf_path=PDF_PATH)
    assert workspace.read_file(PROJECT, first.sidecar_path) == before


def test_all_pages_failed_is_not_registered(pipeline, workspace):
    runner = pipeline(FakeOcr(fail_pages={0, 1}))
    with pytest.raises(UploadRejected, match="未获得可用页面"):
        runner.ingest_pdf(PROJECT, data=make_pdf(2), pdf_path=PDF_PATH)
    assert not [f for f in workspace.list_files(PROJECT) if f.path.startswith("sources/")]
    assert runner._service.list_documents(PROJECT)[1] == 0
