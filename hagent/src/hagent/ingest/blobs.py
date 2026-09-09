"""按 sha256 内容寻址的二进制存储——**存在 project workspace 之外**。

原件与预览版不进 git：workspace 的策略是「全量回写 + 排除名单」，agent 每跑一轮
就可能把几百 MB 二进制再提交一次，仓会在几轮内爆掉。原件是不可变输入，本就不需
要版本化——内容寻址天然满足去重与幂等。仓内只留 md 与 sidecar 这类可 diff 的文本。
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

DEFAULT_BLOB_ROOT = "/tmp/hagent/blobs"

#: 原件（用户上传的 PDF，提供下载）与预览版（重压缩后下发浏览器）分开寻址
BLOB_KIND_ORIGIN = "origin"
BLOB_KIND_PREVIEW = "preview"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BlobStore:
    """``{root}/<kind>/<前两位>/<sha256>`` 的扁平内容寻址目录。"""

    def __init__(self, root: Path | str):
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def path_for(self, kind: str, digest: str) -> Path:
        return self._root / kind / digest[:2] / digest

    def put(self, kind: str, data: bytes) -> str:
        """写入并返回 sha256；同内容重复写入是空操作。"""
        digest = sha256_hex(data)
        target = self.path_for(kind, digest)
        if target.exists():
            return digest
        target.parent.mkdir(parents=True, exist_ok=True)
        # 先写临时文件再改名：并发/中断下不会留下半截 blob
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".partial", delete=False) as f:
            staging = Path(f.name)
            try:
                f.write(data)
                f.flush()
                staging.replace(target)
            finally:
                staging.unlink(missing_ok=True)
        return digest

    def get(self, kind: str, digest: str) -> bytes:
        return self.path_for(kind, digest).read_bytes()

    def exists(self, kind: str, digest: str) -> bool:
        return self.path_for(kind, digest).is_file()


_BLOB_STORE: BlobStore | None = None


def set_blob_store(store: BlobStore | None) -> None:
    global _BLOB_STORE
    _BLOB_STORE = store


def get_blob_store() -> BlobStore:
    global _BLOB_STORE
    if _BLOB_STORE is None:
        _BLOB_STORE = BlobStore(os.environ.get("HAGENT_BLOB_ROOT", DEFAULT_BLOB_ROOT))
    return _BLOB_STORE
