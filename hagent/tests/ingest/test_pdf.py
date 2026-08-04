"""预览版重压缩：页几何绝不能动。

`归一化 bbox × 页面尺寸` 是高亮的落点公式——预览版一旦改了页数或任何一页的
页面尺寸，全文高亮整体错位，而且**错得看不出来**。所以逐页尺寸是硬断言。

扫描件路径（整页位图）单独覆盖：真实招标文件里电子版与扫描件混杂，压缩收益也
几乎全来自这条路径。手边只有电子版真件（`data/` 下那份），故这里用合成的整页
位图 PDF 代替真扫描件。
"""

from __future__ import annotations

import io

import pytest
from PIL import Image
from pypdf import PdfWriter

from hagent.ingest.pdf import PdfError, build_preview, page_count, page_sizes, slice_pages


def digital_pdf(sizes: list[tuple[float, float]]) -> bytes:
    writer = PdfWriter()
    for width, height in sizes:
        writer.add_blank_page(width=width, height=height)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def scanned_pdf(pixel_sizes: list[tuple[int, int]]) -> bytes:
    """整页位图的 PDF——模拟扫描件：每页一张无损存储的噪声图。

    噪声图是刻意的：它压不动，能证明体积下降来自降采样与 JPEG 重编码，
    而不是「本来就有富余的无损压缩空间」。
    """
    import random

    random.seed(11)
    images = []
    for width, height in pixel_sizes:
        image = Image.new("RGB", (width, height))
        image.putdata(
            [
                (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                for _ in range(width * height)
            ]
        )
        images.append(image)
    buffer = io.BytesIO()
    images[0].save(
        buffer, format="PDF", save_all=True, append_images=images[1:], resolution=150.0
    )
    return buffer.getvalue()


A4 = (595.32, 841.92)
LETTER = (612.0, 792.0)
SCAN_A4_150DPI = (1240, 1754)
SCAN_LETTER_150DPI = (1275, 1650)


# —— 基础 ——


def test_rejects_non_pdf():
    with pytest.raises(PdfError):
        page_count(b"not a pdf")


def test_slice_pages_takes_a_half_open_range():
    data = digital_pdf([A4] * 5)
    assert page_count(slice_pages(data, 1, 4)) == 3
    assert page_count(slice_pages(data, 3, 99)) == 2


def test_slice_pages_preserves_page_size():
    data = digital_pdf([A4, LETTER, A4])
    assert page_sizes(slice_pages(data, 1, 3)) == page_sizes(data)[1:3]


# —— 预览版的硬约束 ——


def test_preview_preserves_page_count_and_size_for_mixed_page_sizes():
    data = digital_pdf([A4, LETTER, (200.0, 300.0)])
    preview = build_preview(data)
    assert page_count(preview) == page_count(data)
    assert page_sizes(preview) == page_sizes(data)


def test_preview_preserves_geometry_for_scanned_pages():
    data = scanned_pdf([SCAN_A4_150DPI, SCAN_LETTER_150DPI])
    preview = build_preview(data)
    assert page_sizes(preview) == page_sizes(data)


def test_preview_shrinks_scanned_pages():
    """扫描件的压缩收益必须真的发生——否则预览版就是原件，WASM 堆吃不消。"""
    data = scanned_pdf([SCAN_A4_150DPI, SCAN_A4_150DPI])
    assert len(build_preview(data)) < len(data)


def test_preview_of_empty_document_is_rejected_upstream():
    assert page_count(digital_pdf([])) == 0
