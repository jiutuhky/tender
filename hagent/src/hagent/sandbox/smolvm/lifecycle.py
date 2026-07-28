"""SmolVM VM 生命周期 — VMConfig 装配、启动重试、幂等 stop、adopt 收养。

SDK 调用点全部收敛在此模块(spec §9:升级 smolvm 版本时只审此文件与 image.py)。
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import time
from contextlib import suppress
from typing import Callable

from smolvm import (
    FirecrackerAPIError,
    HostError,
    ImageError,
    NetworkError,
    OperationTimeoutError,
    SmolVM,
    SmolVMError,
    SmolVMManager,
    VMAlreadyExistsError,
    VMNotFoundError,
)
from smolvm.types import VMState

from hagent.sandbox.manifest import SandboxManifest
from hagent.sandbox.smolvm.image import ensure_boot_image

logger = logging.getLogger(__name__)

DEFAULT_VCPUS = 2
DEFAULT_MEMORY_MIB = 2048
DEFAULT_BOOT_TIMEOUT_SECONDS = 30.0
DEFAULT_READY_TIMEOUT_SECONDS = 60.0
DEFAULT_WORKSPACE_DIR = "/workspace"
# 启动失败重试次数(总尝试 = 1 + MAX_START_RETRIES);每次重试前完整 delete()
MAX_START_RETRIES = 2
# 探针刻意零引号:vsock agent 的 shell="raw" 分词语义不做假设
READINESS_PROBE_CMD = "python3 --version"
READINESS_PROBE_TIMEOUT_SECONDS = 10

_VM_ID_SANITIZE = re.compile(r"[^a-z0-9]")


class SmolVMSandboxError(RuntimeError):
    """smolvm provider 异常基类。"""


class SandboxStartError(SmolVMSandboxError):
    """VM 启动重试耗尽。"""


class SandboxAdoptError(SmolVMSandboxError):
    """收养失败:VM 不存在 / 非 RUNNING / 探针不过。"""


class SandboxRestoreError(SmolVMSandboxError):
    """快照恢复失败:快照缺失/已消费 / restore 后 readiness 不过。"""


def delete_snapshot_quiet(
    snapshot_id: str, *, manager_factory: Callable[[], object] = SmolVMManager
) -> None:
    """best-effort 删除快照(恢复后已消费的旧快照 / session 删除的遗留)。

    失败只告警不抛:restored VM 活跃期间 SDK 本就拒删,遗留快照
    由下一次清理点(stop/persist/session 删除)或运维兜底。
    """
    try:
        with manager_factory() as manager:  # type: ignore[attr-defined]
            manager.delete_snapshot(snapshot_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("快照 %s 清理失败(遗留待后续清理): %s", snapshot_id, exc)


# SDK 异常 → 面向运营的中文描述(最具体类型优先;测试表驱动锁定)
_SDK_ERROR_LABELS: tuple[tuple[type[SmolVMError], str], ...] = (
    (HostError, "宿主环境不可用(KVM/firecracker/依赖)"),
    (ImageError, "镜像构建或加载失败"),
    (NetworkError, "VM 网络装配失败(TAP/nftables/IP)"),
    (FirecrackerAPIError, "Firecracker API 错误"),
    (OperationTimeoutError, "操作超时"),
    (VMAlreadyExistsError, "vm_id 已存在(残留未清理)"),
    (VMNotFoundError, "VM 不存在"),
    (SmolVMError, "SmolVM 错误"),
)


def describe_sdk_error(exc: BaseException) -> str:
    """把 SDK 异常翻译成带类别前缀的描述,保留原始信息。"""
    for exc_type, label in _SDK_ERROR_LABELS:
        if isinstance(exc, exc_type):
            return f"{label}: {exc}"
    return f"未知错误: {exc}"


def generate_vm_id(project_id: str | None) -> str:
    """对账键 ``hagent-<pid8>-<rand6>``：pid8 定位项目，rand6 防复用。"""
    pid = _VM_ID_SANITIZE.sub("", (project_id or "").lower())[:8] or secrets.token_hex(4)
    return f"hagent-{pid}-{secrets.token_hex(3)}"


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


def _allowed_domains_env() -> list[str] | None:
    """HAGENT_SMOLVM_ALLOWED_DOMAINS(Task C4,spec D14):逗号分隔主机名。

    返回 None 表示不启用(SDK 默认全放行,与 docker provider 对齐);
    空串/纯逗号视同不启用——手滑设空不得变成全断网(fail-closed 只在
    显式给出域名时生效)。局限见 spec F6:IP 在创建时钉死,CDN 轮换会误伤。

    非法条目(带路径/凭据/query 的 URL)在此 fail-fast 并给出带变量名的可读
    错误——否则 SDK 内 ``InternetSettings`` 抛的是 pydantic ValidationError
    (ValueError,非 SmolVMError),会穿透 ``start()`` 的 retry,以一坨原始报错
    砸掉每次 VM 创建(smolvm 是 server 默认 provider)。SDK 接受裸主机名 URL
    (抽 hostname),仅拒带非根路径/凭据的 URL。
    """
    raw = os.environ.get("HAGENT_SMOLVM_ALLOWED_DOMAINS", "")
    domains = [d.strip() for d in raw.split(",") if d.strip()]
    if not domains:
        return None
    try:
        from smolvm.types import InternetSettings

        InternetSettings(allowed_domains=domains)  # 委托 SDK 校验(单一真相源)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"HAGENT_SMOLVM_ALLOWED_DOMAINS 含非法条目(须主机名,不可带路径/凭据): {exc}"
        ) from exc
    return domains


class SmolVMLifecycle:
    """单个 microVM 的生命周期所有者。

    ``smolvm_cls`` / ``ensure_image`` 可注入,单元测试全 mock、不碰真 SDK。
    """

    def __init__(
        self,
        *,
        project_id: str | None = None,
        vcpus: int | None = None,
        memory_mib: int | None = None,
        boot_timeout: float = DEFAULT_BOOT_TIMEOUT_SECONDS,
        ready_timeout: float = DEFAULT_READY_TIMEOUT_SECONDS,
        smolvm_cls: type[SmolVM] | object = SmolVM,
        ensure_image: Callable[[], object] = ensure_boot_image,
        manager_factory: Callable[[], object] = SmolVMManager,
    ) -> None:
        self._project_id = project_id
        self._vcpus = vcpus if vcpus is not None else _int_env("HAGENT_SMOLVM_VCPUS", DEFAULT_VCPUS)
        self._memory_mib = (
            memory_mib if memory_mib is not None else _int_env("HAGENT_SMOLVM_MEMORY_MIB", DEFAULT_MEMORY_MIB)
        )
        self._boot_timeout = boot_timeout
        self._ready_timeout = ready_timeout
        self._smolvm_cls = smolvm_cls
        self._ensure_image = ensure_image
        self._manager_factory = manager_factory
        self._vm: SmolVM | None = None
        # 本 VM 由哪个快照恢复而来:快照一次性语义(SDK restored 标记),
        # VM 拆除即消费完毕,须清理防泄漏
        self._restored_from: str | None = None
        self.vm_id: str = generate_vm_id(project_id)

    @property
    def vm(self) -> SmolVM | None:
        return self._vm

    # —— 启动 ————————————————————————————————————————————————

    def start(self) -> SandboxManifest:
        """镜像 → from_image → start → wait_for_ready → 探针;失败全清理重试 ≤ MAX_START_RETRIES。"""
        image = self._ensure_image()
        last_exc: BaseException | None = None
        # 出口白名单(Task C4):dict 形态交 SDK 规范化(InternetSettings 校验
        # 裸主机名/拒 URL);不启用时完全不传参,保持 SDK 默认全放行
        extra_kwargs: dict = {}
        allowed_domains = _allowed_domains_env()
        if allowed_domains is not None:
            extra_kwargs["internet_settings"] = {"allowed_domains": allowed_domains}
        for attempt in range(1 + MAX_START_RETRIES):
            # 每次尝试换新 rand6:上一轮 delete 不彻底时避免 VMAlreadyExistsError
            vm_id = self.vm_id if attempt == 0 else generate_vm_id(self._project_id)
            vm: SmolVM | None = None
            try:
                vm = self._smolvm_cls.from_image(
                    image,
                    vm_id=vm_id,
                    vcpus=self._vcpus,
                    memory_mb=self._memory_mib,
                    **extra_kwargs,
                )
                vm.start(self._boot_timeout)
                vm.wait_for_ready(self._ready_timeout)
                self._probe(vm)
            except (SmolVMError, RuntimeError) as exc:
                last_exc = exc
                logger.warning(
                    "smolvm 启动尝试 %d/%d 失败(vm_id=%s): %s",
                    attempt + 1,
                    1 + MAX_START_RETRIES,
                    vm_id,
                    describe_sdk_error(exc),
                )
                if vm is not None:
                    self._cleanup_failed(vm)
                continue
            self._vm = vm
            self.vm_id = vm_id
            return self._manifest(image)
        raise SandboxStartError(
            f"smolvm 启动失败(重试 {MAX_START_RETRIES} 次耗尽): {describe_sdk_error(last_exc)}"
        ) from last_exc

    def _probe(self, vm: SmolVM) -> None:
        result = vm.run(READINESS_PROBE_CMD, timeout=READINESS_PROBE_TIMEOUT_SECONDS, shell="raw")
        if result.exit_code != 0:
            raise SmolVMError(
                f"readiness 探针失败(exit={result.exit_code}): {result.stderr.strip()}"
            )

    @staticmethod
    def _cleanup_failed(vm: SmolVM) -> None:
        """失败尝试全清理:delete 释放 TAP/IP/磁盘租约(F3),close 收连接。"""
        with suppress(Exception):
            vm.delete()
        with suppress(Exception):
            vm.close()

    def _manifest(self, image: object) -> SandboxManifest:
        return SandboxManifest(
            sandbox_id=self.vm_id,
            kind="smolvm",
            image_tag=getattr(image, "name", "hagent-sandbox"),
            runtime="firecracker",
            container_id=self.vm_id,
            workspace_dir=DEFAULT_WORKSPACE_DIR,
        )

    # —— 收养(启动对账 / reaper 用)—————————————————————————————

    def adopt(self, vm_id: str) -> SandboxManifest:
        """重连已存在的 VM 并校验活性;任何一步不过抛 SandboxAdoptError(清场归 reconciler)。"""
        try:
            vm = self._smolvm_cls.from_id(vm_id)
        except SmolVMError as exc:
            raise SandboxAdoptError(f"收养 {vm_id} 失败: {describe_sdk_error(exc)}") from exc
        try:
            vm.refresh()
            if vm.status == VMState.PAUSED:
                # 池 GC 暂停后 server 重启的常见形态:先解冻再探针
                vm.resume()
            if vm.status != VMState.RUNNING:
                raise SandboxAdoptError(f"收养 {vm_id} 失败: VM 状态为 {vm.status},非 RUNNING")
            # 重连句柄的 vsock 通道未必立刻就绪(L3 实测:负载下握手比探针慢,
            # 「control channel did not become ready」);探针前先等通道
            vm.wait_for_ready(self._ready_timeout)
            self._probe(vm)
        except SandboxAdoptError:
            raise
        except SmolVMError as exc:
            raise SandboxAdoptError(f"收养 {vm_id} 探针失败: {describe_sdk_error(exc)}") from exc
        self._vm = vm
        self.vm_id = vm_id
        return SandboxManifest(
            sandbox_id=vm_id,
            kind="smolvm",
            image_tag="adopted",
            runtime="firecracker",
            container_id=vm_id,
            workspace_dir=DEFAULT_WORKSPACE_DIR,
            created_at=time.time(),
        )

    # —— DISK 快照持久化(Task C2,spec D13)———————————————————————————

    def persist_to_snapshot(self) -> str:
        """DISK 快照(存盘不存内存)+ 全拆 VM,释放内存/TAP/IP 租约。

        快照先行:失败时 VM 保持完好,调用方退回普通驱逐路径。
        快照在 VM 删除后独立存活(SDK 不级联删除);若本 VM 自身由
        快照恢复而来,旧快照已被取代,顺手清理。
        """
        vm = self._vm
        if vm is None:
            raise SmolVMSandboxError("VM 未运行,无法快照")
        try:
            # SDK 仅对 RUNNING VM 在 DISK snapshot 前执行 guest filesystem sync；
            # idle 链路此时通常已 PAUSED，若直接 snapshot 会跳过刷盘并丢失
            # agent 通过 shell 自装的环境增量。
            if vm.status == VMState.PAUSED:
                vm.resume()
            info = vm.snapshot(snapshot_type="disk")
        except SmolVMError as exc:
            raise SmolVMSandboxError(f"DISK 快照失败: {describe_sdk_error(exc)}") from exc
        snapshot_id = str(info.snapshot_id)
        superseded = self._restored_from
        self._restored_from = None
        self._vm = None
        self._teardown(vm)
        if superseded is not None:
            delete_snapshot_quiet(superseded, manager_factory=self._manager_factory)
        return snapshot_id

    def restore_from_snapshot(self, snapshot_id: str) -> SandboxManifest:
        """从 DISK 快照重建(全新 boot、回原 vm_id);readiness 不过即全清理抛错。"""
        try:
            vm = self._smolvm_cls.from_snapshot(snapshot_id, resume_vm=True)
        except SmolVMError as exc:
            raise SandboxRestoreError(
                f"快照 {snapshot_id} 恢复失败: {describe_sdk_error(exc)}"
            ) from exc
        try:
            # DISK restore 是全新 boot(非 resume),与 start 同理须等通道再探针(F15)
            vm.wait_for_ready(self._ready_timeout)
            self._probe(vm)
        except (SmolVMError, RuntimeError) as exc:
            self._cleanup_failed(vm)
            # SDK restore 一旦把 VM 启起来就 mark_snapshot_restored(一次性,再 restore
            # 须 force,hagent 从不传)。此时快照已消费且不可复用——VM 已删,删快照防
            # 磁盘泄漏(delete_snapshot 的"restored VM 活跃"守卫因 VM 已删而放行)
            delete_snapshot_quiet(snapshot_id, manager_factory=self._manager_factory)
            raise SandboxRestoreError(
                f"快照 {snapshot_id} 恢复后 readiness 未过: {describe_sdk_error(exc)}"
            ) from exc
        self._vm = vm
        self.vm_id = getattr(vm, "vm_id", self.vm_id)
        self._restored_from = snapshot_id
        return SandboxManifest(
            sandbox_id=self.vm_id,
            kind="smolvm",
            image_tag="restored",
            runtime="firecracker",
            container_id=self.vm_id,
            workspace_dir=DEFAULT_WORKSPACE_DIR,
            created_at=time.time(),
        )

    # —— 停止 / 暂停 ————————————————————————————————————————————

    def _teardown(self, vm: SmolVM) -> None:
        """stop → delete → close;单步失败不阻断后续(F3:delete 才释放租约)。"""
        with suppress(Exception):
            vm.stop()
        try:
            vm.delete()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] delete 失败(残留交给 reaper): %s", self.vm_id, describe_sdk_error(exc))
        with suppress(Exception):
            vm.close()

    def stop(self) -> None:
        """全拆,幂等;由快照恢复而来的 VM 拆除后顺手清理已消费的源快照。"""
        vm = self._vm
        if vm is None:
            return
        self._vm = None
        self._teardown(vm)
        if self._restored_from is not None:
            consumed = self._restored_from
            self._restored_from = None
            delete_snapshot_quiet(consumed, manager_factory=self._manager_factory)

    def pause(self) -> None:
        if self._vm is None:
            return
        try:
            self._vm.pause()
        except SmolVMError as exc:
            logger.warning("[%s] pause 失败: %s", self.vm_id, describe_sdk_error(exc))

    def resume(self) -> None:
        if self._vm is None:
            return
        try:
            self._vm.resume()
        except SmolVMError as exc:
            logger.warning("[%s] resume 失败: %s", self.vm_id, describe_sdk_error(exc))
