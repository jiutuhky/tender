"""结构化资产管理面：对象库（store）+ 领域动作服务（service，唯一写入口）。

adapter（MCP / REST，票 03/07）只 import 本包公开面；对象表禁止旁路直写。
"""

from hagent.assets.errors import AssetError, ConflictError
from hagent.assets.model import (
    ALLOWED_SECTIONS,
    MATRIX_TYPES,
    RESPONSE_STATUSES,
    Actor,
    AssetEvent,
    DocumentRecord,
    MatrixInfo,
    MatrixItem,
    MatrixLifecycle,
    PublishResult,
    SubmitResult,
)
from hagent.assets.service import AssetService, get_asset_service, set_asset_service
from hagent.assets.store import AssetStore

__all__ = [
    "ALLOWED_SECTIONS",
    "MATRIX_TYPES",
    "RESPONSE_STATUSES",
    "Actor",
    "AssetError",
    "AssetEvent",
    "AssetService",
    "AssetStore",
    "ConflictError",
    "DocumentRecord",
    "MatrixInfo",
    "MatrixItem",
    "MatrixLifecycle",
    "PublishResult",
    "SubmitResult",
    "get_asset_service",
    "set_asset_service",
]
