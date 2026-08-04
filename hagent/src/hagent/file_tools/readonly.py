"""OCR 原文的只读锁：agent 改不动 `sources/` 下的 md 与 sidecar。

`line_span` 是脆弱的中间坐标——它的正确性完全建立在「md 只读」之上。agent 改一个
字，全份文档的溯源锚点就静默错位；而「改完重建映射」意味着回头做模糊对齐，正是本
方案要绕开的东西。所以直接在工具层拒绝：agent 要订正 OCR 讹误就另写到
`structured/` 或 `deliverables/`，不动原文。

与 `permissions` 的分工：permissions 是 host 模式下的路径白/黑名单，sandbox 模式
下整体跳过；本锁按 **workspace 相对路径**判定，两种模式一致生效。
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

#: 受锁目录——上传原件的落地处，OCR 产物与它同目录
PROTECTED_ROOT = "sources"

#: 受锁后缀：规范化 md 与它的 sidecar
PROTECTED_SUFFIXES = (".md", ".sidecar.json")


class ReadOnlySourceError(PermissionError):
    """写入被原文只读锁拒绝。"""


def is_protected(file_path: str | Path, workspace_root: str | Path) -> bool:
    """判断某绝对路径是否落在受锁的 OCR 产物上。"""
    try:
        relative = Path(file_path).resolve().relative_to(Path(workspace_root).resolve())
    except ValueError:
        return False  # 不在 workspace 内的路径由 permissions 管，不归本锁
    parts = PurePosixPath(relative.as_posix())
    if not parts.parts or parts.parts[0] != PROTECTED_ROOT:
        return False
    name = parts.name.lower()
    return any(name.endswith(suffix) for suffix in PROTECTED_SUFFIXES)


def ensure_writable(file_path: str | Path, workspace_root: str | Path) -> None:
    if not is_protected(file_path, workspace_root):
        return
    name = Path(file_path).name
    raise ReadOnlySourceError(
        f"{name} 是 OCR 产出的招标文件原文（含溯源锚点），只读，不能修改。"
        f"若要订正识别讹误，请把订正结果写到 structured/ 或 deliverables/ 下，"
        f"不要改动 {PROTECTED_ROOT}/ 里的原文。"
    )
