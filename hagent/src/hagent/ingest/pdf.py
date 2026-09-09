"""PDF 侧的确定性操作：页数、逐页尺寸、批次切片、预览版重压缩。

预览版的硬约束：**页数与逐页页面尺寸必须与原件逐页一致**。归一化 bbox 是按
「该页的页面尺寸」算出来的，预览版只要改了页面几何，全文高亮就整体错位。因此
这里只做「重编码页内图片流 + 压缩内容流」——页对象与它的 MediaBox 原样保留，
从不新建页、从不缩放页。
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)

#: 预览版内嵌图片的目标分辨率上限（长边像素）。A4 @150dpi ≈ 1754px。
PREVIEW_MAX_IMAGE_EDGE = 1754
PREVIEW_JPEG_QUALITY = 60


class PdfError(ValueError):
    """PDF 本身不可用（损坏、加密、非 PDF）。"""


@dataclass(frozen=True)
class PageSize:
    width: float
    height: float


def read_pdf(data: bytes) -> PdfReader:
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 —— pypdf 的解析异常型别不稳定
        raise PdfError(f"无法解析 PDF：{exc}") from exc
    if reader.is_encrypted:
        raise PdfError("PDF 已加密，无法解析")
    return reader


def page_count(data: bytes) -> int:
    return len(read_pdf(data).pages)


def page_sizes(data: bytes) -> list[PageSize]:
    """逐页页面尺寸（PDF 用户空间单位）——预览版与原件的比对基准。"""
    return [
        PageSize(width=float(page.mediabox.width), height=float(page.mediabox.height))
        for page in read_pdf(data).pages
    ]


@dataclass(frozen=True)
class PageGeometry:
    """保留页面裁切、固有旋转与用户单位，按文档页序比较。"""

    media_box: tuple[float, ...]
    crop_box: tuple[float, ...]
    rotation: int
    user_unit: float


def page_geometries(data: bytes) -> list[PageGeometry]:
    return [PageGeometry(tuple(float(v) for v in page.mediabox),
                         tuple(float(v) for v in page.cropbox),
                         int(page.rotation) % 360, float(page.user_unit))
            for page in read_pdf(data).pages]


def slice_pages(data: bytes, start: int, stop: int) -> bytes:
    """截出 ``[start, stop)`` 页另存为一份 PDF——OCR 分批的输入。"""
    reader = read_pdf(data)
    writer = PdfWriter()
    for index in range(start, min(stop, len(reader.pages))):
        writer.add_page(reader.pages[index])
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def build_preview(data: bytes) -> bytes:
    """由原件重压缩出预览版：页几何一律不动，只压图片流与内容流。

    单页压缩失败不影响其余页——该页原样保留，预览版只是大一点。
    """
    reader = read_pdf(data)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    for index, page in enumerate(writer.pages):
        for image in page.images:
            try:
                _shrink(image)
            except Exception as exc:  # noqa: BLE001 —— 图片编解码失败面很宽
                logger.debug("预览版第 %d 页图片压缩跳过: %s", index + 1, exc)
        try:
            page.compress_content_streams()
        except Exception as exc:  # noqa: BLE001
            logger.debug("预览版第 %d 页内容流压缩跳过: %s", index + 1, exc)

    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _shrink(image) -> None:
    """降采样并以 JPEG 重编码一张内嵌图片（就地替换，不改页面几何）。"""
    source = image.image
    if source is None:
        return
    longest = max(source.size)
    if longest > PREVIEW_MAX_IMAGE_EDGE:
        ratio = PREVIEW_MAX_IMAGE_EDGE / longest
        target = (max(1, int(source.width * ratio)), max(1, int(source.height * ratio)))
        source = source.resize(target)
    if source.mode not in ("RGB", "L"):
        source = source.convert("RGB")
    image.replace(source, quality=PREVIEW_JPEG_QUALITY)
