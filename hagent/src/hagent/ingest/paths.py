"""入库产物的路径约定——读端点与写管线共用，避免两处各推一遍。

md 与 sidecar 同目录同名：前端拿到 `documents.path` 即可推出 sidecar 的位置。
"""

from __future__ import annotations

from pathlib import PurePosixPath

SIDECAR_SUFFIX = ".sidecar.json"


def markdown_path_for(pdf_path: str) -> str:
    return str(PurePosixPath(pdf_path).with_suffix(".md"))


def sidecar_path_for(markdown_path: str) -> str:
    stem = markdown_path[: -len(".md")] if markdown_path.endswith(".md") else markdown_path
    return stem + SIDECAR_SUFFIX
