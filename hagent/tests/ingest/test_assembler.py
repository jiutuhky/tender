"""装配器唯一测试缝：OCR 响应 →(md, sidecar) 的确定性产出。

不碰网络不碰磁盘——OCR 服务在缝外，真实响应样本进仓当夹具：

- ``single-page.json``：`.scratch/pdf-source-trace/reference/ocr-response-sample.json`
  的修复版。原样本为人工裁剪稿，`block_content` 与 `markdown.text` 都带
  「（截断）」标记因而自相矛盾；此处补全被截断的表格并补入 header /
  number / footer 三个被忽略标签的块（真实页面必有，原样本恰好没有）。
- ``multipage-crosspage.json``：真实招标文件第 21–24 页经 `/restructure-pages`
  的响应，含一张跨 4 页合并的表——合并块的正文落在首页，续页块内容为空
  但各自带本页 bbox，靠 `global_group_id` 归组。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hagent.ingest.assembler import (
    OcrBlock,
    OcrPage,
    assemble_document,
    parse_layout_parsing_response,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ocr"

IGNORED_LABELS = ("header", "footer", "number", "footnote")


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def single_page() -> list[OcrPage]:
    return parse_layout_parsing_response(load("single-page"), page_offset=0)


@pytest.fixture
def crosspage() -> list[OcrPage]:
    return parse_layout_parsing_response(load("multipage-crosspage"), page_offset=20)


# —— 解析 ——


def test_parse_maps_pages_with_offset_and_sizes(crosspage):
    """一次 /layout-parsing 只覆盖一个批次，页序由 page_offset 还原为文档页序。"""
    assert [page.index for page in crosspage] == [20, 21, 22, 23]
    assert {(page.width, page.height) for page in crosspage} == {(1191, 1684)}


def test_parse_reads_page_sizes_from_data_info(single_page):
    page = single_page[0]
    assert (page.index, page.width, page.height) == (0, 1190, 1684)


# —— md 拼装 ——


def test_markdown_is_page_markdown_joined(single_page):
    result = assemble_document(single_page)
    assert result.markdown == single_page[0].markdown


def test_ignored_label_blocks_occupy_no_line_and_no_sidecar_entry(single_page):
    """header / footer / number 不进 md，也就不占行号、不产出 sidecar 条目。"""
    result = assemble_document(single_page)

    for ignored in ("Confidential — Draft", "Procurement Agency"):
        assert ignored not in result.markdown
    assert not [b for b in result.sidecar["blocks"] if b["label"] in IGNORED_LABELS]

    # 首个未被忽略的块（doc_title）落在第 1 行——被忽略的 header 没有顶掉它
    first = result.sidecar["blocks"][0]
    assert (first["label"], first["mdStart"], first["mdEnd"]) == ("doc_title", 1, 1)


def test_line_accounting_points_at_the_real_lines(single_page):
    result = assemble_document(single_page)
    lines = result.markdown.split("\n")

    for entry in result.sidecar["blocks"]:
        span = "\n".join(lines[entry["mdStart"] - 1 : entry["mdEnd"]])
        assert span.strip(), f"{entry} 指向空行"

    table = next(b for b in result.sidecar["blocks"] if b["label"] == "table")
    assert "<table" in "\n".join(lines[table["mdStart"] - 1 : table["mdEnd"]])


# —— bbox 归一化 ——


def test_bbox_normalized_against_that_pages_size(single_page):
    result = assemble_document(single_page)
    entry = next(b for b in result.sidecar["blocks"] if b["label"] == "doc_title")
    rect = entry["rects"][0]

    assert rect["page"] == 0
    assert rect["bbox"] == pytest.approx([142 / 1190, 124 / 1684, 706 / 1190, 175 / 1684])
    assert all(0.0 <= value <= 1.0 for value in rect["bbox"])


def test_each_page_normalizes_against_its_own_size():
    """逐页尺寸不同时按各页 dataInfo.pages[i] 归一化，不共用首页尺寸。"""
    pages = [
        OcrPage(
            index=0,
            width=1000,
            height=2000,
            markdown="第一页",
            blocks=(OcrBlock(label="text", content="第一页", bbox=(100, 200, 500, 400), group_id=1),),
        ),
        OcrPage(
            index=1,
            width=2000,
            height=4000,
            markdown="第二页",
            blocks=(OcrBlock(label="text", content="第二页", bbox=(100, 200, 500, 400), group_id=2),),
        ),
    ]
    result = assemble_document(pages)

    first, second = result.sidecar["blocks"]
    assert first["rects"][0]["bbox"] == pytest.approx([0.1, 0.1, 0.5, 0.2])
    assert second["rects"][0]["bbox"] == pytest.approx([0.05, 0.05, 0.25, 0.1])


def test_sidecar_pages_record_every_page_size(crosspage):
    result = assemble_document(crosspage)
    assert result.sidecar["pages"] == [
        {"index": index, "width": 1191, "height": 1684} for index in (20, 21, 22, 23)
    ]


# —— 跨页合并 ——


def test_crosspage_merged_block_yields_one_entry_with_rects_per_page(crosspage):
    """合并表只占一段 md，却要在它铺过的每一页上都能高亮。"""
    result = assemble_document(crosspage)

    merged = max(
        (b for b in result.sidecar["blocks"] if b["label"] == "table"),
        key=lambda b: len(b["rects"]),
    )
    assert [rect["page"] for rect in merged["rects"]] == [20, 21, 22, 23]
    assert merged["mdStart"] == merged["mdEnd"]

    # 续页的空块不另起条目：4 页共 18 个块，其中 3 个是该合并块的续页
    assert len(result.sidecar["blocks"]) == 18 - 3


def test_page_local_group_ids_never_merge_across_pages():
    """未经 `/restructure-pages` 的响应里 `group_id` 是页内序号——各页首块都叫 0。

    把它当跨页合并键会把毫不相干的块并成一条、把矩形撒到它根本不在的页上，
    正是「稳稳地指到错误的地方」。这条路径在任一页解析失败时必被走到。
    """
    payload = {
        "result": {
            "layoutParsingResults": [
                {
                    "prunedResult": {
                        "parsing_res_list": [
                            {
                                "block_label": "text",
                                "block_content": f"第 {index + 1} 页正文",
                                "block_bbox": [0, 0, 50, 50],
                                "group_id": 0,  # 页内序号，三页全是 0；无 global_group_id
                            }
                        ]
                    },
                    "markdown": {"text": f"第 {index + 1} 页正文"},
                }
                for index in range(3)
            ],
            "dataInfo": {"pages": [{"width": 100, "height": 100}] * 3},
        }
    }
    result = assemble_document(parse_layout_parsing_response(payload, page_offset=0))

    assert len(result.sidecar["blocks"]) == 3
    assert [[rect["page"] for rect in b["rects"]] for b in result.sidecar["blocks"]] == [
        [0],
        [1],
        [2],
    ]


def test_crosspage_continuation_pages_contribute_no_markdown(crosspage):
    result = assemble_document(crosspage)
    assert "<table" in result.markdown
    # 续页 md 只有一个换行，不该在文档 md 里留下空段落堆积
    assert "\n\n\n\n" not in result.markdown


# —— 失败页 ——


def test_failed_page_leaves_a_placeholder_and_no_sidecar_entries():
    """部分页失败不让整份作废：失败页留可识别占位，其余页照常产出。"""
    pages = [
        OcrPage(index=0, width=100, height=100, markdown="第一页正文",
                blocks=(OcrBlock(label="text", content="第一页正文", bbox=(0, 0, 50, 50), group_id=1),)),
        OcrPage(index=1, width=100, height=100, markdown="", blocks=(), failed=True),
        OcrPage(index=2, width=100, height=100, markdown="第三页正文",
                blocks=(OcrBlock(label="text", content="第三页正文", bbox=(0, 0, 50, 50), group_id=3),)),
    ]
    result = assemble_document(pages)

    assert "第 2 页" in result.markdown and "解析失败" in result.markdown
    assert [b["rects"][0]["page"] for b in result.sidecar["blocks"]] == [0, 2]

    # 占位撑住行号：第三页的块行号在占位之后
    third = result.sidecar["blocks"][1]
    assert result.markdown.split("\n")[third["mdStart"] - 1] == "第三页正文"


# —— 保险丝与确定性 ——


def test_md_sha256_matches_the_markdown_it_ships_with(single_page, crosspage):
    for pages in (single_page, crosspage):
        result = assemble_document(pages)
        digest = hashlib.sha256(result.markdown.encode("utf-8")).hexdigest()
        assert result.sidecar["mdSha256"] == digest
    assert assemble_document(single_page).sidecar["schema"] == 1


def test_assembly_is_deterministic(crosspage):
    first = assemble_document(crosspage)
    second = assemble_document(crosspage)
    assert first.markdown == second.markdown
    assert first.sidecar == second.sidecar


def test_unalignable_page_keeps_markdown_but_drops_its_rects():
    """宁可「未能定位」也不要指错：块与 md 对不上的页照常出 md，但不产出条目。"""
    pages = [
        OcrPage(
            index=0,
            width=100,
            height=100,
            markdown="服务端给的正文与块对不上",
            blocks=(OcrBlock(label="text", content="完全不同的内容", bbox=(0, 0, 50, 50), group_id=1),),
        ),
        OcrPage(
            index=1,
            width=100,
            height=100,
            markdown="第二页正文",
            blocks=(OcrBlock(label="text", content="第二页正文", bbox=(0, 0, 50, 50), group_id=2),),
        ),
    ]
    result = assemble_document(pages)

    assert "服务端给的正文与块对不上" in result.markdown
    assert [b["rects"][0]["page"] for b in result.sidecar["blocks"]] == [1]
