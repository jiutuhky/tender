"""上传后的确定性前置任务：PDF →(原件 blob, 预览版 blob, 规范化 md, sidecar)。

四件产物互相对得上才算完成：原件与预览版按 sha256 存在 workspace 之外，md 与
sidecar 落 `sources/` 进 git（文本可 diff 可审阅）。**md 与 sidecar 就绪后才起
agent**——OCR 是确定性 ETL，不该由 LLM 决定何时跑、跑几次。

页数与体积的硬上限在入口就判，超限**立即明确报错**而不是让用户等一个注定失败的
漫长解析。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING


from hagent.assets.model import Actor
from hagent.assets.service import AssetService, get_asset_service
from hagent.ingest.assembler import assemble_document
from hagent.ingest.env import int_env
from hagent.ingest.blobs import (
    BLOB_KIND_ORIGIN,
    BLOB_KIND_PREVIEW,
    BlobStore,
    get_blob_store,
    sha256_hex,
)
from hagent.ingest.ocr_client import OcrClient, ProgressCallback
from hagent.ingest.paths import markdown_path_for, sidecar_path_for
from hagent.ingest.pdf import PdfError, build_preview, page_count, page_geometries

if TYPE_CHECKING:  # 运行期不导入 hagent.server：那会绕回 routers 形成环
    from hagent.server.project_workspace import ProjectWorkspace

logger = logging.getLogger(__name__)

DEFAULT_MAX_PAGES = 800
DEFAULT_MAX_BYTES = 200 * 1024 * 1024

_SYSTEM = Actor(kind="system", ref="ingest")


class UploadRejected(ValueError):
    """上传在解析前就被拒（超限、非 PDF、损坏）——用户该立刻看到原因。"""


@dataclass(frozen=True)
class IngestResult:
    document_id: str
    markdown_path: str
    sidecar_path: str
    origin_sha256: str
    preview_sha256: str
    page_count: int
    failed_pages: tuple[int, ...]


@dataclass(frozen=True)
class IngestLimits:
    max_pages: int = DEFAULT_MAX_PAGES
    max_bytes: int = DEFAULT_MAX_BYTES

    @classmethod
    def from_env(cls) -> "IngestLimits":
        return cls(
            max_pages=int_env("HAGENT_INGEST_MAX_PAGES", DEFAULT_MAX_PAGES),
            max_bytes=int_env("HAGENT_INGEST_MAX_BYTES", DEFAULT_MAX_BYTES),
        )


def check_upload(data: bytes, filename: str, limits: IngestLimits | None = None) -> int:
    """解析前的准入检查，返回页数；不通过一律抛 `UploadRejected`。"""
    limits = limits or IngestLimits.from_env()
    if len(data) > limits.max_bytes:
        raise UploadRejected(
            f"文件体积 {len(data) / 1024 / 1024:.1f} MB 超过上限 "
            f"{limits.max_bytes / 1024 / 1024:.0f} MB：{filename}"
        )
    try:
        pages = page_count(data)
    except PdfError as exc:
        raise UploadRejected(str(exc)) from exc
    if pages > limits.max_pages:
        raise UploadRejected(f"文件共 {pages} 页，超过上限 {limits.max_pages} 页：{filename}")
    if pages == 0:
        raise UploadRejected(f"PDF 没有任何页：{filename}")
    return pages


class IngestPipeline:
    def __init__(
        self,
        *,
        ocr: OcrClient | None = None,
        blobs: BlobStore | None = None,
        workspace: "ProjectWorkspace | None" = None,
        service: AssetService | None = None,
        limits: IngestLimits | None = None,
    ):
        self._ocr = ocr or OcrClient()
        self._blobs = blobs or get_blob_store()
        if workspace is None:
            from hagent.server.project_workspace import get_project_workspace

            workspace = get_project_workspace()
        self._workspace = workspace
        self._service = service or get_asset_service()
        self._limits = limits or IngestLimits.from_env()

    def ingest_pdf(
        self,
        project_id: str,
        *,
        data: bytes,
        pdf_path: str,
        on_progress: ProgressCallback | None = None,
    ) -> IngestResult:
        """跑完一份 PDF 的入库；调用方在它返回之后才起 agent。"""
        total_pages = check_upload(data, pdf_path, self._limits)

        origin_sha = self._blobs.put(BLOB_KIND_ORIGIN, data)
        pages = self._ocr.parse_pdf(data, on_progress=on_progress)
        if not pages or all(page.failed for page in pages):
            raise UploadRejected("原文解析失败，未获得可用页面，请重试")
        preview_sha = self._blobs.put(BLOB_KIND_PREVIEW, self._build_preview(data))
        # 失败页仍保留显示比例，前端可正常预览原页。
        geometry = page_geometries(data)
        for i, page in enumerate(pages):
            if page.width <= 0 or page.height <= 0:
                g = geometry[page.index]
                w, h = g.crop_box[2] - g.crop_box[0], g.crop_box[3] - g.crop_box[1]
                if g.rotation in (90, 270):
                    w, h = h, w
                pages[i] = replace(page, width=max(1, round(w)), height=max(1, round(h)))
        assembled = assemble_document(pages, origin_sha256=origin_sha, preview_sha256=preview_sha)
        existing = self._service.find_document_by_sha(project_id, assembled.sidecar["mdSha256"])
        if existing is not None and (
            existing.origin_sha256 not in (None, origin_sha)
            or existing.preview_sha256 not in (None, preview_sha)
        ):
            raise UploadRejected("相同解析文本已关联其他原件，请保留原文档并创建新项目")
        markdown_path = existing.path if existing else markdown_path_for(pdf_path)
        # 同名重传产生新内容时另存版本，既有引用继续指向旧文件。
        try:
            previous = self._workspace.read_file(project_id, markdown_path)
        except FileNotFoundError:
            previous = None
        if previous is not None and previous != assembled.markdown.encode("utf-8"):
            markdown_path = markdown_path[:-3] + f".{origin_sha[:12]}.{assembled.sidecar['mdSha256'][:12]}.md"
        sidecar_path = sidecar_path_for(markdown_path)
        self._workspace.apply_changes(
            project_id,
            updated={
                markdown_path: assembled.markdown.encode("utf-8"),
                sidecar_path: (
                    json.dumps(assembled.sidecar, ensure_ascii=False, indent=1) + "\n"
                ).encode("utf-8"),
            },
            deleted=(),
        )
        self._workspace.commit(
            project_id,
            summary=f"ocr: {markdown_path}",
            kind="ocr_ingest",
            paths=[markdown_path, sidecar_path],
        )

        document = self._service.register_document(
            project_id,
            path=markdown_path,
            sha256=sha256_hex(assembled.markdown.encode("utf-8")),
            doc_type="tender",
            actor=_SYSTEM,
        )
        self._service.attach_document_blobs(
            project_id,
            document.id,
            origin_sha256=origin_sha,
            preview_sha256=preview_sha,
            actor=_SYSTEM,
        )

        return IngestResult(
            document_id=document.id,
            markdown_path=markdown_path,
            sidecar_path=sidecar_path,
            origin_sha256=origin_sha,
            preview_sha256=preview_sha,
            page_count=total_pages,
            failed_pages=tuple(page.index for page in pages if page.failed),
        )

    @staticmethod
    def _build_preview(data: bytes) -> bytes:
        """预览版必须与原件逐页同尺寸——不满足就退回原件当预览版。

        错位的高亮比大一点的下载危险得多。
        """
        try:
            preview = build_preview(data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("预览版生成失败，改用原件: %s", exc)
            return data
        if page_geometries(preview) != page_geometries(data):
            logger.warning("预览版页面几何与原件不符，改用原件")
            return data
        return preview
