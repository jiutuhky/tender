"""发布物化双轨（票 06）：publish 成功后把矩阵物化为旧路径兼容 JSON（spec §8）。

只读导出投影：从对象库当前版拼装 `bid_response_matrix_<slug>_<ts>/final/<matrix_type>.json`，
不回读、不参与校验，重发布即覆盖。受 `HAGENT_PUBLISH_PROJECTION` 开关控制
（票 08 前端切 REST 读后默认关闭，显式置 1/true/yes/on 才物化——排障/回退旧读路径用）。
失败语义由调用方（service.publish_gated）兜住：best-effort，异常只记 WARNING，
不影响已完成的 publish 事务。

前端经 `git ls-files` 列举 workspace（server 的 ProjectWorkspace.list_files），而
sandbox 模式的 checkpoint 只提交 guest 变更——host 侧写出的投影文件必须由本模块
自行提交（workspace 非 git 仓库时跳过，CLI host 模式可能如此）。刻意不 import
ProjectWorkspace：hagent.server 包会连带加载 app.py（其经 mcp.py 依赖本包，成环），
提交约定（add --all + Kind trailer）与其保持镜像。
"""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from hagent.assets.model import ALLOWED_SECTIONS, MATRIX_TYPES, DocumentRecord, MatrixItem, MatrixLifecycle
from hagent.assets.store import DOCUMENTS_FETCH_LIMIT, deep_merge, now_iso
from hagent.assets.validators import META_SKELETONS

if TYPE_CHECKING:
    from hagent.assets.service import AssetService

PROJECTION_ENV = "HAGENT_PUBLISH_PROJECTION"
_ENABLED_VALUES = {"1", "true", "yes", "on"}

# 与 revision 快照同一 schema 版本口径（service.publish 的 snapshot）
SCHEMA_VERSION = "1.0"

# 标记文件：识别本模块创建的运行目录（重发布覆盖复用，不误认旧 skill 遗留目录）
MARKER_FILENAME = ".prose_projection.json"

# 偏离表 = 条目应答状态投影（spec §3，无独立实体）
DEVIATION_STATUSES = ("positive_deviation", "negative_deviation")

_PUBLISHED_STATES = (MatrixLifecycle.PUBLISHED, MatrixLifecycle.PUBLISHED_DRAFTING)

# 目录时间戳后缀：与前端 runDirSortKey 的 `_(\d{8}_\d{6})$` 约定一致
_RUN_DIR_TS_RE = re.compile(r"_(\d{8}_\d{6})$")

_SLUG_SANITIZE_RE = re.compile(r"[^\w-]+")
_SLUG_MAX_LEN = 60


class _PublishedMatrix(NamedTuple):
    """单个已发布矩阵的导出素材（当前版 envelope + 条目行）。"""

    meta: dict
    items: list[MatrixItem]


def projection_enabled() -> bool:
    """物化开关（票 08 收口后默认关）；关闭时 materialize 零文件写入。"""
    return os.environ.get(PROJECTION_ENV, "").strip().lower() in _ENABLED_VALUES


def _section_path(section: str) -> tuple[str, ...]:
    # unresolved_items 在旧 final JSON 里挂 validation 下（spec §3）
    if section == "unresolved_items":
        return ("validation", "unresolved_items")
    return tuple(section.split("."))


def _ensure_bucket(body: dict, path: tuple[str, ...]) -> list:
    node = body
    for key in path[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            child = {}
            node[key] = child
        node = child
    bucket = node.get(path[-1])
    if not isinstance(bucket, list):
        bucket = []
        node[path[-1]] = bucket
    return bucket


def build_matrix_document(
    matrix_type: str,
    *,
    meta: dict,
    items: list[MatrixItem],
    documents: list[DocumentRecord],
    generated_at: str,
) -> dict:
    """按旧 final JSON 契约拼装单矩阵文档（对拍 frontend/lib/hagent/matrix.ts）。

    meta 深合并进 META_SKELETONS 骨架（缺省字段以 null/空列表呈现，schema 稳定），
    区段行按 dot-path 嵌回原位置；envelope 的 schema_version / matrix_type /
    generated_at / source_documents 由服务端接管，覆盖 meta 中的同名杂散键。
    """
    body = deep_merge(copy.deepcopy(META_SKELETONS[matrix_type]), meta)
    for section in ALLOWED_SECTIONS[matrix_type]:
        _ensure_bucket(body, _section_path(section))
    for item in items:
        _ensure_bucket(body, _section_path(item.section)).append(item.payload)
    return {
        **body,
        "schema_version": SCHEMA_VERSION,
        "matrix_type": matrix_type,
        "generated_at": generated_at,
        "source_documents": [
            {
                "document_id": document.id,
                "path": document.path,
                "sha256": document.sha256,
                "doc_type": document.doc_type,
            }
            for document in documents
        ],
    }


def _slugify(value: str) -> str:
    slug = _SLUG_SANITIZE_RE.sub("-", value).strip("-")
    return slug[:_SLUG_MAX_LEN] or "project"


def _project_slug(metas: dict[str, dict], project_id: str) -> str:
    """目录 slug：优先矩阵 envelope 的 project_id（稳定 slug 或招标编号），
    次选 project_name，兜底 hagent project id。"""
    for matrix_type in MATRIX_TYPES:
        meta = metas.get(matrix_type) or {}
        for key in ("project_id", "project_name"):
            value = meta.get(key)
            if isinstance(value, str) and value.strip():
                return _slugify(value)
    return _slugify(project_id)


def _run_dir_sort_key(name: str) -> str:
    match = _RUN_DIR_TS_RE.search(name)
    return match.group(1) if match else name


def _resolve_run_dir(root: Path, project_id: str, metas: dict[str, dict]) -> Path:
    """复用既有投影目录（重发布即覆盖），没有才按 <slug>_<ts> 新建并落标记文件。

    复用条件是「带标记且全局最新」：前端 latestRunDir 只认时间戳最新的目录，
    若有更新时间戳的无标记目录（旧 skill 遗留/外部还原）遮蔽了投影目录，
    继续写旧目录会让前端永远读到陈旧数据——此时改为新建（当前时间戳排最前）自愈。
    """
    candidates = [
        path for path in root.glob("bid_response_matrix_*") if path.is_dir()
    ]
    if candidates:
        latest = max(candidates, key=lambda path: _run_dir_sort_key(path.name))
        if (latest / MARKER_FILENAME).is_file():
            return latest
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = root / f"bid_response_matrix_{_project_slug(metas, project_id)}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    marker = {"project_id": project_id, "created_at": now_iso()}
    (run_dir / MARKER_FILENAME).write_text(
        json.dumps(marker, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return run_dir


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=check, capture_output=True, text=True
    )


def _commit_projection(root: Path, run_dir_name: str, matrix_types: list[str]) -> None:
    """把投影文件提交进 workspace git（消息格式镜像 ProjectWorkspace.commit）。

    并发防线是 git 自身的 index.lock：与 checkpoint 撞车时本次提交失败，
    由调用方按 best-effort 记 WARNING，文件本身已落地、下次发布补提交。
    """
    if not (root / ".git").is_dir():
        return
    _git(root, "add", "--all", "--", run_dir_name)
    staged = _git(root, "diff", "--cached", "--quiet", "--", run_dir_name, check=False)
    if staged.returncode == 0:
        return
    summary = f"projection: 应答矩阵发布物化（{', '.join(matrix_types)}）"
    _git(root, "commit", "-m", f"{summary}\n\nKind: projection")


def materialize_published_matrices(
    service: AssetService, project_id: str, *, workspace_root: Path | str
) -> Path | None:
    """把项目所有已发布矩阵物化到旧路径（每次发布全量重写，幂等自愈）。

    返回运行目录；开关关闭或尚无已发布矩阵时返回 None（零文件写入）。
    """
    if not projection_enabled():
        return None
    published: dict[str, _PublishedMatrix] = {}
    for matrix_type in MATRIX_TYPES:
        info = service.get_matrix_info(project_id, matrix_type)
        if info.state not in _PUBLISHED_STATES:
            continue
        items, _ = service.query_items(project_id, matrix_type, stage="current")
        published[matrix_type] = _PublishedMatrix(meta=info.meta, items=items)
    if not published:
        return None
    documents, _ = service.list_documents(
        project_id, limit=DOCUMENTS_FETCH_LIMIT, offset=0
    )

    root = Path(workspace_root)
    metas = {matrix_type: matrix.meta for matrix_type, matrix in published.items()}
    run_dir = _resolve_run_dir(root, project_id, metas)
    final_dir = run_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    generated_at = now_iso()
    for matrix_type, matrix in published.items():
        document = build_matrix_document(
            matrix_type,
            meta=matrix.meta,
            items=matrix.items,
            documents=documents,
            generated_at=generated_at,
        )
        (final_dir / f"{matrix_type}.json").write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    _commit_projection(root, run_dir.name, sorted(published))
    return run_dir


def export_deviation_table(service: AssetService, project_id: str, matrix: str) -> list[dict]:
    """偏离表导出：当前版 items 按应答状态（正/负偏离）过滤的只读投影。

    文件格式由后续票定义；本票只固定数据口径与接口，调用方拿行级投影自行渲染。
    """
    rows: list[dict] = []
    for status in DEVIATION_STATUSES:
        items, _ = service.query_items(
            project_id, matrix, stage="current", section="items", response_status=status
        )
        rows.extend(
            {
                "matrix_type": item.matrix_type,
                "item_id": item.item_id,
                "response_status": item.response_status,
                "response_note": item.response_note,
                "confirmed": item.confirmed,
                "payload": item.payload,
            }
            for item in items
        )
    return rows
