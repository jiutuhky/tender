"""结构化资产服务的可行动错误：每个错误带 code 与下一步建议（hint）。"""

from __future__ import annotations


class AssetError(Exception):
    """服务层拒绝动作时抛出；message 说明原因，hint 给出下一步建议。"""

    def __init__(self, code: str, message: str, *, hint: str | None = None):
        self.code = code
        self.hint = hint
        super().__init__(f"{message}（建议：{hint}）" if hint else message)
        self.message = message


class ConflictError(AssetError):
    """乐观锁冲突：expected_version 与当前 version 不符。"""

    def __init__(self, message: str, *, current_version: int, hint: str | None = None):
        super().__init__("version_conflict", message, hint=hint)
        self.current_version = current_version
