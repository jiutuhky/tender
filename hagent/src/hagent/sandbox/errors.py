"""沙箱基础设施错误契约:provider 无关、面向模型的统一文案。

设计动机(事故 a49b1a3d):SDK 的运维提示("run 'smolvm sandbox start <vm_id>'")
被原样包进工具输出,模型照抄执行了宿主运维命令。此后所有"沙箱层不可用"类
错误都经本模块产出文案:

- 文案**唯一来源**是 ``MODEL_MESSAGES``,docker / smolvm 两个 provider 共用,
  不含 SDK 命令、vm_id、宿主路径;
- 每条以 ``[sandbox_unavailable:<reason>]`` 开头,系统提示词据此教模型区分
  「命令/文件本身的错误」与「环境不可用」;
- SDK 原文只进 ``detail``(日志/审计),绝不进模型可见文本。
"""

from __future__ import annotations

from enum import Enum

from deepagents.backends.protocol import ExecuteResponse

SANDBOX_UNAVAILABLE_MARKER = "sandbox_unavailable"
# 与 provider 既有约定对齐:基础设施失败 137,超时 124
SANDBOX_INFRA_EXIT_CODE = 137
SANDBOX_TIMEOUT_EXIT_CODE = 124


class SandboxUnavailableReason(str, Enum):
    PAUSED = "paused"
    STOPPED = "stopped"
    GONE = "gone"
    CONNECT_FAILED = "connect_failed"
    TIMEOUT = "timeout"


_COMMON_TAIL = "不要执行任何沙箱运维命令,也不要猜测宿主路径。"

MODEL_MESSAGES: dict[SandboxUnavailableReason, str] = {
    SandboxUnavailableReason.PAUSED: (
        f"[{SANDBOX_UNAVAILABLE_MARKER}:paused] 沙箱环境暂时不可用(正在唤醒)。"
        "这不是命令或文件本身的错误:请原样重试一次;若仍失败,停止当前操作并向用户说明。"
        + _COMMON_TAIL
    ),
    SandboxUnavailableReason.STOPPED: (
        f"[{SANDBOX_UNAVAILABLE_MARKER}:stopped] 沙箱环境当前不可用。"
        "请停止当前操作并向用户说明,等待环境恢复后重试。" + _COMMON_TAIL
    ),
    SandboxUnavailableReason.GONE: (
        f"[{SANDBOX_UNAVAILABLE_MARKER}:gone] 沙箱环境已被回收并将重建,本轮无法继续。"
        "请立即停止并告知用户重新发送请求。" + _COMMON_TAIL
    ),
    SandboxUnavailableReason.CONNECT_FAILED: (
        f"[{SANDBOX_UNAVAILABLE_MARKER}:connect_failed] 与沙箱环境的连接失败。"
        "这不是命令或文件本身的错误:请原样重试一次;若仍失败,停止当前操作并向用户说明。"
        + _COMMON_TAIL
    ),
    SandboxUnavailableReason.TIMEOUT: (
        f"[{SANDBOX_UNAVAILABLE_MARKER}:timeout] 命令在沙箱内执行超时。"
        "可缩小处理范围或延长 timeout 后重试。"
    ),
}


class SandboxUnavailable(RuntimeError):
    """沙箱层不可用。``str(exc)`` 即模型文案;``detail`` 只供日志/审计。"""

    def __init__(
        self,
        reason: SandboxUnavailableReason,
        *,
        detail: str | None = None,
    ) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(model_message(reason))

    def __str__(self) -> str:  # 显式:RuntimeError 默认 str 取 args[0],此处锁死
        return model_message(self.reason)


def model_message(reason: SandboxUnavailableReason) -> str:
    return MODEL_MESSAGES[reason]


def timeout_message(timeout_seconds: int | float | None) -> str:
    base = MODEL_MESSAGES[SandboxUnavailableReason.TIMEOUT]
    if timeout_seconds is None:
        return base
    return base.replace("执行超时。", f"执行超时({int(timeout_seconds)}s)。")


def is_infra_message(text: str | None) -> bool:
    """工具输出是否是本契约文案(通道层据此决定原样透传、不再加前缀)。"""
    return bool(text) and text.lstrip().startswith(f"[{SANDBOX_UNAVAILABLE_MARKER}:")


# —— 分类 ——————————————————————————————————————————————————————

_PAUSED_MARKERS = ("state: paused", "is paused", "current state: paused")
_STOPPED_MARKERS = (
    "state: stopped",
    "state: created",
    "is stopped",
    "is not running",
    "not running",
    "current state: stopped",
    "current state: created",
)
_CONNECT_MARKERS = (
    "vsock connect handshake failed",
    "control channel did not become ready",
    "connection refused",
    "connect to host",
    "handshake",
    "connection reset",
    "broken pipe",
    "no route to host",
    "network is unreachable",
    "timed out",
)


def classify_exception(exc: BaseException) -> SandboxUnavailableReason:
    """把 provider/SDK 异常归到契约类别。

    只在 provider 内部使用:smolvm 的 ``OperationTimeoutError`` 在调用点已单独
    映射为 TIMEOUT,这里按消息文本兜底分类;无法判断一律 CONNECT_FAILED(可重试
    一次,最保守)。
    """
    if isinstance(exc, SandboxUnavailable):
        return exc.reason
    name = type(exc).__name__
    message = str(exc).lower()
    if "timeout" in name.lower():
        return SandboxUnavailableReason.TIMEOUT
    if any(marker in message for marker in _PAUSED_MARKERS):
        return SandboxUnavailableReason.PAUSED
    if any(marker in message for marker in _STOPPED_MARKERS):
        return SandboxUnavailableReason.STOPPED
    if any(marker in message for marker in _CONNECT_MARKERS):
        return SandboxUnavailableReason.CONNECT_FAILED
    return SandboxUnavailableReason.CONNECT_FAILED


# —— 各通道的产出形态 ————————————————————————————————————————————


def execute_error_response(
    reason: SandboxUnavailableReason, *, timeout_seconds: int | float | None = None
) -> ExecuteResponse:
    """execute() 通道:契约文案 + 约定 exit_code。"""
    if reason is SandboxUnavailableReason.TIMEOUT:
        return ExecuteResponse(
            output=timeout_message(timeout_seconds),
            exit_code=SANDBOX_TIMEOUT_EXIT_CODE,
            truncated=False,
        )
    return ExecuteResponse(
        output=model_message(reason), exit_code=SANDBOX_INFRA_EXIT_CODE, truncated=False
    )


def transfer_error(reason: SandboxUnavailableReason) -> str:
    """upload/download 通道的 error 字段:机器可解析,``file_not_found`` 之外的
    基础设施类失败统一为 ``sandbox_unavailable:<reason>``。"""
    return f"{SANDBOX_UNAVAILABLE_MARKER}:{reason.value}"


FILE_NOT_FOUND_ERROR = "file_not_found"


def parse_transfer_error(error: str | None) -> SandboxUnavailableReason | None:
    """从 upload/download 的 error 字段解析契约类别;非契约错误返回 None。

    ``file_not_found`` 与 ``download_failed: ...`` / ``upload_failed: ...``(guest
    内脚本级失败,如目录/权限)都是业务错误,返回 None 交调用方按原语义处理;
    只有 provider 明确标成 ``sandbox_unavailable:<reason>`` 的才是基础设施失败。
    """
    if not error:
        return None
    prefix = f"{SANDBOX_UNAVAILABLE_MARKER}:"
    if not error.startswith(prefix):
        return None
    raw = error[len(prefix) :].strip()
    try:
        return SandboxUnavailableReason(raw)
    except ValueError:
        return SandboxUnavailableReason.CONNECT_FAILED
