"""PaddleOCR-VL HPS Gateway 客户端：分批调用 + 页级断点续跑。

为什么必须分批：请求体是 base64 JSON，整份塞进去体积不可接受；实测吞吐约
1 s/页，一份招标文件是分钟级任务。

**页级断点续跑**：一个批次整体失败时，先原样重试，仍失败则对半拆到单页重投——
坏页被隔离成一页，其余页照常产出。始终拿不到的页记为失败页，由装配器在 md 里
留占位、不产出 sidecar 条目；整份文档不作废。

``use_doc_preprocessor`` 恒为 ``False``：PaddleOCR-VL 的 unwarping 会让返回的
bbox 与原件错位，一旦置 true 全文高亮整体失效。**该参数不接受外部覆盖。**
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from typing import Callable, Sequence

import httpx

from hagent.ingest.env import int_env
from hagent.ingest.assembler import OcrPage, failed_page, parse_layout_parsing_response
from hagent.ingest.pdf import page_sizes, slice_pages

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_BATCH_PAGES = 10
DEFAULT_TIMEOUT_SECONDS = 600.0

#: 进度回调：(已完成页数, 总页数)
ProgressCallback = Callable[[int, int], None]


class OcrServiceError(RuntimeError):
    """OCR 服务不可用或返回了无法使用的响应。"""


@dataclass(frozen=True)
class _RawPage:
    """一页的原始服务响应；``entry is None`` 即该页解析失败。

    保留原始形状是因为 `/restructure-pages` 要吃回 `/layout-parsing` 的原样输出。
    """

    index: int
    entry: dict | None
    info: dict | None


@dataclass(frozen=True)
class OcrSettings:
    base_url: str = DEFAULT_BASE_URL
    batch_pages: int = DEFAULT_BATCH_PAGES
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    restructure: bool = True

    @classmethod
    def from_env(cls) -> "OcrSettings":
        return cls(
            base_url=os.environ.get("HAGENT_OCR_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            batch_pages=int_env("HAGENT_OCR_BATCH_PAGES", DEFAULT_BATCH_PAGES),
            timeout_seconds=float(
                os.environ.get("HAGENT_OCR_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
            ),
            restructure=os.environ.get("HAGENT_OCR_RESTRUCTURE", "1") != "0",
        )


class OcrClient:
    def __init__(self, settings: OcrSettings | None = None, *, client: httpx.Client | None = None):
        self._settings = settings or OcrSettings.from_env()
        self._client = client

    def parse_pdf(
        self, data: bytes, *, on_progress: ProgressCallback | None = None
    ) -> list[OcrPage]:
        """解析整份 PDF，返回按文档页序排好的页结果（含失败页占位）。"""
        total = len(page_sizes(data))
        raw: list[_RawPage] = []

        for start in range(0, total, self._settings.batch_pages):
            stop = min(start + self._settings.batch_pages, total)
            raw.extend(self._parse_range(data, start, stop))
            if on_progress is not None:
                on_progress(stop, total)

        return self._assemble_pages(self._restructure(raw))

    # —— 分批与重投 ——

    def _parse_range(self, data: bytes, start: int, stop: int) -> list["_RawPage"]:
        try:
            payload = self._layout_parsing(slice_pages(data, start, stop))
        except Exception as exc:  # noqa: BLE001 —— 网络/服务侧失败面很宽
            if stop - start <= 1:
                logger.warning("第 %d 页 OCR 失败，留占位继续: %s", start + 1, exc)
                return [_RawPage(index=start, entry=None, info=None)]
            middle = start + (stop - start) // 2
            logger.warning("第 %d–%d 页 OCR 批次失败，拆半重投: %s", start + 1, stop, exc)
            return [
                *self._parse_range(data, start, middle),
                *self._parse_range(data, middle, stop),
            ]

        result = payload.get("result") or {}
        entries = result.get("layoutParsingResults") or []
        infos = ((result.get("dataInfo") or {}).get("pages")) or []
        pages = [
            _RawPage(
                index=start + offset,
                entry=entry,
                info=infos[offset] if offset < len(infos) else None,
            )
            for offset, entry in enumerate(entries)
        ]
        # 服务少还了页时补占位，保证页序与页数始终对得上原件
        for index in range(start + len(pages), stop):
            logger.warning("第 %d 页 OCR 未返回结果，留占位继续", index + 1)
            pages.append(_RawPage(index=index, entry=None, info=None))
        return pages

    def _restructure(self, pages: list["_RawPage"]) -> list["_RawPage"]:
        """跨页合并：把被分页切开的表格/段落归成一个块（多矩形的来源）。

        失败不致命——退回未合并的逐页结果，切开的表格只是变成多个条目。
        """
        if not self._settings.restructure or not pages:
            return pages
        if any(page.entry is None for page in pages):
            # 合并按整份文档做，缺页会让页序错位——有失败页时不做合并
            return pages
        try:
            payload = self._post("/restructure-pages", {"pages": [p.entry for p in pages]})
        except Exception as exc:  # noqa: BLE001
            logger.warning("跨页合并失败，退回逐页结果: %s", exc)
            return pages
        merged = (payload.get("result") or {}).get("layoutParsingResults") or []
        if len(merged) != len(pages):
            logger.warning("跨页合并返回页数不符，退回逐页结果")
            return pages
        return [
            _RawPage(index=page.index, entry=entry, info=page.info)
            for page, entry in zip(pages, merged)
        ]

    @staticmethod
    def _assemble_pages(pages: Sequence["_RawPage"]) -> list[OcrPage]:
        result: list[OcrPage] = []
        for page in pages:
            if page.entry is None:
                result.append(failed_page(page.index))
                continue
            payload = {
                "result": {
                    "layoutParsingResults": [page.entry],
                    "dataInfo": {"pages": [page.info]} if page.info else {},
                }
            }
            result.extend(parse_layout_parsing_response(payload, page_offset=page.index))
        return result

    # —— HTTP ——

    def _layout_parsing(self, pdf_bytes: bytes) -> dict:
        return self._post(
            "/layout-parsing",
            {
                "file": base64.b64encode(pdf_bytes).decode("ascii"),
                "fileType": 0,
                # 不得改为 True：unwarping 会让 bbox 与原件错位
                "useDocPreprocessor": False,
            },
        )

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self._settings.base_url}{path}"
        if self._client is not None:
            response = self._client.post(url, json=body, timeout=self._settings.timeout_seconds)
        else:
            with httpx.Client(timeout=self._settings.timeout_seconds) as client:
                response = client.post(url, json=body)
        response.raise_for_status()
        payload = response.json()
        if payload.get("errorCode"):
            raise OcrServiceError(f"{path} 返回错误：{payload.get('errorMsg')}")
        return payload
