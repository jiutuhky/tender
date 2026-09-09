"""版面块 →(规范化 md, sidecar) 的装配器：纯函数，不碰网络不碰磁盘。

本模块是 PDF 入库管线唯一的测试缝，也是溯源锚点正确性的全部所在。

**行号一边追加一边记账**：`assemble_document` 只走一趟——追加一页 md 的同时
就把该页每个版面块占据的行号记进 sidecar。严禁「先拼 md、再回头把块文本匹配
回去」：模糊匹配正是本方案要绕开的东西。

md 文本取自服务端的 `markdown.text` 而非由 `block_content` 重拼。实测表明
PaddleOCR-VL 渲染 md 时会做块数据里不存在的加工——标题按层级给 `##` / `###`、
编号后补空格、表格 HTML 加样式属性——重拼必然丢失这些结构信息。块与 md 的对应
因此靠**顺序游标**建立：把 md 与块内容都压成「去空白、去 HTML 属性、去行首 #」
的比对流，逐块从游标处要求**精确前缀相等**。这是确定性的顺序消费，不是模糊匹配；
一旦某页对不上，该页照常出 md 但不产出任何 sidecar 条目——宁可让前端显示
「未能定位」，也不要稳稳地指到错误的地方。
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

SIDECAR_SCHEMA_VERSION = 1

#: `markdown_ignore_labels` 的默认集合。带这些标签的块不进 md，因而不占行号、
#: 不产出 sidecar 条目——版面块数量本就多于 md 段。
DEFAULT_IGNORE_LABELS = frozenset(
    {"number", "footnote", "header", "header_image", "footer", "footer_image", "aside_text"}
)

_TAG = re.compile(r"</?\s*([A-Za-z][\w-]*)")


@dataclass(frozen=True)
class OcrBlock:
    """一个版面块。

    ``group_id`` **只**取 `/restructure-pages` 给的 `global_group_id`——那是整份
    文档唯一的跨页合并键。绝不能退回页内的 `group_id`：它是页内序号，第 0 页与
    第 1 页的首块都叫 0，一合并就把毫不相干的块并成一条、把矩形撒到它根本不在的
    页上。没有 `global_group_id` 时留 None，装配器按页内身份处理（即不合并）。
    """

    label: str
    content: str
    bbox: tuple[float, float, float, float]
    group_id: int | None = None


@dataclass(frozen=True)
class OcrPage:
    """一页的解析结果。``index`` 是 0-based 文档页序，不是批次内页序。"""

    index: int
    width: int
    height: int
    markdown: str
    blocks: tuple[OcrBlock, ...] = ()
    failed: bool = False


@dataclass(frozen=True)
class AssembledDocument:
    markdown: str
    sidecar: dict[str, Any]


@dataclass
class _Group:
    """跨页合并块：正文落在首个非空块上，续页块只贡献本页矩形。"""

    label: str
    rects: list[dict[str, Any]] = field(default_factory=list)
    md_start: int | None = None
    md_end: int | None = None
    invalid: bool = False


def parse_layout_parsing_response(
    payload: dict[str, Any], *, page_offset: int = 0
) -> list[OcrPage]:
    """把一次 `/layout-parsing`（或 `/restructure-pages`）响应翻译成页列表。

    ``page_offset`` 是本批次首页在整份文档中的 0-based 页序——分批调用时用它把
    批次内页序还原为文档页序。
    """
    result = payload.get("result") or {}
    page_infos = ((result.get("dataInfo") or {}).get("pages")) or []
    pages: list[OcrPage] = []

    for offset, entry in enumerate(result.get("layoutParsingResults") or []):
        pruned = entry.get("prunedResult") or {}
        info = page_infos[offset] if offset < len(page_infos) else {}
        ignore_labels = _ignore_labels(pruned)
        blocks = tuple(
            OcrBlock(
                label=block.get("block_label") or "",
                content=block.get("block_content") or "",
                bbox=_bbox(block.get("block_bbox")),
                group_id=block.get("global_group_id"),
            )
            for block in (pruned.get("parsing_res_list") or [])
            if (block.get("block_label") or "") not in ignore_labels
        )
        pages.append(
            OcrPage(
                index=page_offset + offset,
                width=int(info.get("width") or pruned.get("width") or 0),
                height=int(info.get("height") or pruned.get("height") or 0),
                markdown=(entry.get("markdown") or {}).get("text") or "",
                blocks=blocks,
            )
        )
    return pages


def failed_page(index: int, *, width: int = 0, height: int = 0) -> OcrPage:
    """构造一个解析失败的页占位——供页级断点续跑在放弃某页后填坑。"""
    return OcrPage(index=index, width=width, height=height, markdown="", failed=True)


def assemble_document(
    pages: Sequence[OcrPage], *, origin_sha256: str | None = None,
    preview_sha256: str | None = None,
) -> AssembledDocument:
    """一趟走完：追加 md 的同时记账行号，产出 md 与 sidecar。"""
    ordered = sorted(pages, key=lambda page: page.index)
    md_lines: list[str] = []
    groups: dict[tuple[int, Any], _Group] = {}
    order: list[tuple[int, Any]] = []

    for page in ordered:
        # 跨页合并块的续页 md 只剩换行——不落任何行，免得堆出空段落
        page_markdown = "" if page.failed else page.markdown.strip("\n")
        if not page_markdown and not page.failed:
            _collect_rects(page, [None] * len(page.blocks), 0, groups, order)
            continue

        if md_lines:
            md_lines.append("")  # 页与页之间空行分隔
        page_start = len(md_lines) + 1  # 1-based：本页 md 的首行行号

        if page.failed:
            md_lines.append(f"> [第 {page.index + 1} 页原文解析失败，本页内容缺失]")
            continue

        md_lines.extend(page_markdown.split("\n"))

        _collect_rects(page, _align(page, page_markdown), page_start, groups, order)

    markdown = "\n".join(md_lines)
    blocks = [
        {
            "mdStart": group.md_start,
            "mdEnd": group.md_end,
            "label": group.label,
            "rects": group.rects,
        }
        for group in (groups[key] for key in order)
        if group.md_start is not None and not group.invalid
    ]
    return AssembledDocument(
        markdown=markdown,
        sidecar={
            "schema": 2 if origin_sha256 and preview_sha256 else SIDECAR_SCHEMA_VERSION,
            **({"coordinateSpace": "page-display-normalized",
                "originSha256": origin_sha256, "previewSha256": preview_sha256,
                "mdLineCount": len(md_lines)} if origin_sha256 and preview_sha256 else {}),
            "mdSha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
            "pages": [
                {"index": page.index, "width": page.width, "height": page.height}
                for page in ordered
            ],
            "blocks": blocks,
        },
    )


def _collect_rects(
    page: OcrPage,
    spans: Sequence[tuple[int, int] | None],
    page_start: int,
    groups: dict[tuple[int, Any], _Group],
    order: list[tuple[int, Any]],
) -> None:
    """把本页每个块的矩形并进它所属的组，并在首次拿到行号时定下行号。"""
    for block, span in zip(page.blocks, spans):
        key = _group_key(page, block)
        group = groups.get(key)
        if group is None:
            group = groups[key] = _Group(label=block.label)
            order.append(key)
        if (span is None and block.content.strip()) or not _valid_bbox(block.bbox, page.width, page.height):
            group.invalid = True
        group.rects.append(
            {"page": page.index, "bbox": _normalize(block.bbox, page.width, page.height)}
        )
        if span is not None and group.md_start is None:
            group.md_start = page_start + span[0]
            group.md_end = page_start + span[1]


# —— 对齐 ——


def _align(page: OcrPage, page_markdown: str) -> list[tuple[int, int] | None]:
    """返回每个块在本页 md 中占据的 (起始行, 结束行) 页内 0-based 偏移。

    整页要么全部对上，要么全部返回 None——半对半错的页比没有映射更危险。
    """
    squashed, offsets = _squash_with_offsets(page_markdown)
    spans: list[tuple[int, int] | None] = []
    cursor = 0

    for block in page.blocks:
        want = _squash(block.content)
        if not want:
            # 跨页合并块的续页：正文已归到首页，本页只贡献矩形
            spans.append(None)
            continue
        # 块之间可能夹着纯结构标记（如把 figure_title 裹起来的 <div>），跳过之
        cursor = _skip_structural(squashed, cursor, want)
        if squashed[cursor : cursor + len(want)] != want:
            return [None] * len(page.blocks)
        start_char = offsets[cursor]
        end_char = offsets[cursor + len(want) - 1]
        cursor += len(want)
        spans.append(
            (
                page_markdown.count("\n", 0, start_char),
                page_markdown.count("\n", 0, end_char),
            )
        )

    return spans


def _skip_structural(squashed: str, cursor: int, want: str) -> int:
    """跳过游标处纯结构性的标签记号——它们不属于任何块。

    实测到的场景：`figure_title` 会被渲染器裹进 `<div>…</div>`，于是下一个块
    （紧随其后的表格）前面多出一个闭合标签。只跳标签、绝不跳正文字符。
    """
    while cursor < len(squashed) and squashed[cursor] == "<":
        if squashed[cursor : cursor + len(want)] == want:
            break
        closing = squashed.find(">", cursor)
        if closing < 0:
            break
        cursor = closing + 1
    return cursor


def _squash_with_offsets(text: str) -> tuple[str, list[int]]:
    """压成比对流并保留每个字符回原文的下标。

    丢空白（渲染换行/缩进不承载内容）、丢 HTML 标签属性（PaddleOCR 给表格加了
    样式）、丢行首 `#`（标题层级由渲染器决定，块数据里没有）。
    """
    out: list[str] = []
    offsets: list[int] = []
    index = 0
    length = len(text)
    at_line_start = True

    while index < length:
        char = text[index]
        if char == "<":
            closing = text.find(">", index)
            if closing < 0:
                closing = length - 1
            match = _TAG.match(text, index)
            name = match.group(1) if match else ""
            normalized = f"</{name}>" if text.startswith("</", index) else f"<{name}>"
            out.extend(normalized)
            offsets.extend([index] * len(normalized))
            index = closing + 1
            at_line_start = False
            continue
        if char.isspace():
            at_line_start = at_line_start or char == "\n"
            index += 1
            continue
        if at_line_start and char == "#":
            while index < length and text[index] == "#":
                index += 1
            continue
        out.append(char)
        offsets.append(index)
        at_line_start = False
        index += 1

    return "".join(out), offsets


def _squash(text: str) -> str:
    return _squash_with_offsets(text)[0]


# —— 小工具 ——


def _group_key(page: OcrPage, block: OcrBlock) -> tuple[int, Any]:
    """无跨页合并键时按页内块身份成组，即「不合并」——绝不跨页并块。"""
    if block.group_id is None:
        return (page.index, id(block))
    return (-1, block.group_id)


def _normalize(
    bbox: tuple[float, float, float, float], width: int, height: int
) -> list[float]:
    if width <= 0 or height <= 0:
        return [0.0, 0.0, 0.0, 0.0]
    left, top, right, bottom = bbox
    return [
        _clamp(left / width),
        _clamp(top / height),
        _clamp(right / width),
        _clamp(bottom / height),
    ]


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def _bbox(raw: Iterable[Any] | None) -> tuple[float, float, float, float]:
    values = [float(value) for value in (raw or [])]
    while len(values) < 4:
        values.append(0.0)
    return (values[0], values[1], values[2], values[3])


def _ignore_labels(pruned: dict[str, Any]) -> frozenset[str]:
    settings = pruned.get("model_settings") or {}
    labels = settings.get("markdown_ignore_labels")
    return frozenset(labels) if labels else DEFAULT_IGNORE_LABELS


def _valid_bbox(bbox: tuple[float, ...], width: int, height: int) -> bool:
    """拒绝缺失、非有限和倒置的坐标；允许检测框在页缘轻微外扩。"""
    return (width > 0 and height > 0 and all(math.isfinite(v) for v in bbox)
            and bbox[0] < bbox[2] and bbox[1] < bbox[3]
            and bbox[2] > 0 and bbox[3] > 0 and bbox[0] < width and bbox[1] < height)
