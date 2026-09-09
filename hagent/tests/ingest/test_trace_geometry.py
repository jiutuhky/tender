"""原文页面几何和映射版本的回归。"""
import io
import pytest
from pypdf import PdfWriter
from pypdf.generic import FloatObject, NameObject, RectangleObject
from hagent.ingest.pdf import build_preview, page_geometries
from hagent.ingest.pipeline import IngestPipeline
from hagent.ingest.assembler import OcrPage, OcrBlock, assemble_document


def pdf(rotation=0, crop=30, unit=2):
    writer = PdfWriter()
    page = writer.add_blank_page(width=700, height=500)
    page.cropbox = RectangleObject([crop, 40, 660, 460])
    page.rotate(rotation)
    page[NameObject("/UserUnit")] = FloatObject(unit)
    writer.add_blank_page(width=500, height=700)
    out = io.BytesIO(); writer.write(out)
    return out.getvalue()


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_preview_preserves_all_geometry(rotation):
    original = pdf(rotation)
    assert page_geometries(build_preview(original)) == page_geometries(original)


@pytest.mark.parametrize("changed", [pdf(90), pdf(crop=50), pdf(unit=1)])
def test_same_media_size_but_different_geometry_falls_back(monkeypatch, changed):
    original = pdf()
    monkeypatch.setattr("hagent.ingest.pipeline.build_preview", lambda _: changed)
    assert IngestPipeline._build_preview(original) == original


def test_unaligned_crosspage_member_does_not_attach_its_rect():
    first = OcrPage(0, 100, 100, "表格", (OcrBlock("table", "表格", (0, 0, 50, 50), 1),))
    bad = OcrPage(1, 100, 100, "无法对齐", (OcrBlock("table", "其他内容", (0, 0, 50, 50), 1),))
    result = assemble_document([first, bad], origin_sha256="a" * 64, preview_sha256="b" * 64)
    assert result.sidecar["schema"] == 2
    assert result.sidecar["blocks"] == []
    assert "无法对齐" in result.markdown


@pytest.mark.parametrize("bbox", [(0, 0, float("nan"), 2), (10, 0, 5, 10), (0, 0, 0, 0)])
def test_invalid_detection_never_becomes_a_highlight(bbox):
    result = assemble_document([OcrPage(0, 100, 100, "内容", (OcrBlock("text", "内容", bbox),))])
    assert not result.sidecar["blocks"]


def test_real_hps_crosspage_response_keeps_both_rectangles():
    import json
    from pathlib import Path
    from hagent.ingest.assembler import parse_layout_parsing_response
    payload = json.loads((Path(__file__).parent / "fixtures/hps_crosspage.json").read_text())
    result = assemble_document(parse_layout_parsing_response(payload), origin_sha256="a" * 64, preview_sha256="b" * 64)
    table = next(b for b in result.sidecar["blocks"] if b["label"] == "table")
    assert [r["page"] for r in table["rects"]] == [0, 1]
    assert all(r["bbox"][0] < r["bbox"][2] and r["bbox"][1] < r["bbox"][3] for r in table["rects"])
    assert "财务状况" in result.markdown
