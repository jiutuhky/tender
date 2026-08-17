"""SandboxPool — warm-pool acquire/release with idle GC.

Task A7 改造(spec D8):可选 AdmissionLedger 准入(占位→提交→释放)、
认领即异步补货至 min、补货连续失败熔断(Daytona #3289 教训)、
池空且额度足则冷启动。无 ledger 时行为与改造前一致(docker 路径零影响)。
"""

from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Callable

from hagent.sandbox.ledger import AdmissionLedger, CapacityExceeded, Reservation
from hagent.sandbox.node import LocalNodeClient, NodeClient
from hagent.sandbox.protocol import HagentSandboxProtocol

logger = logging.getLogger(__name__)

DEFAULT_QUOTA_MEM_MIB = 2048
DEFAULT_QUOTA_VCPUS = 2
REPLENISH_BREAKER_THRESHOLD = 3
REPLENISH_COOLDOWN_SECONDS = 300.0


class PoolExhausted(RuntimeError):
    """Raised when the pool is full and no warm sandbox is available within timeout."""


@dataclass
class SandboxLease:
    sandbox: HagentSandboxProtocol
    project_id: str
    leased_at: float = field(default_factory=time.time)


class SandboxPool:
    """Owns a small pool of HagentSandboxProtocol instances.

    Acquire returns a SandboxLease; release either tears the container down
    (default) or, if ``HAGENT_SANDBOX_REUSE=true``, wipes ``/workspace`` and
    returns the sandbox to the warm pool.

    传入 ``ledger`` 时启用容量准入:每个沙箱创建前占位、成功后提交、
    关闭/驱逐时归还;占位失败抛 ``CapacityExceeded``(路由层映射 503)。
    """

    def __init__(
        self,
        *,
        sandbox_factory: Callable[[], HagentSandboxProtocol] | None = None,
        project_sandbox_factory: Callable[[str], HagentSandboxProtocol] | None = None,
        node_client: NodeClient | None = None,
        min_size: int = 1,
        max_size: int = 4,
        acquire_timeout: float = 5.0,
        idle_pause_seconds: float = 300.0,
        idle_evict_seconds: float = 1800.0,
        max_lifetime_seconds: float | None = None,
        recycle_after_seconds: float | None = None,
        restore_factory: Callable[[str, str], HagentSandboxProtocol] | None = None,
        ledger: AdmissionLedger | None = None,
        quota_mem_mib: int = DEFAULT_QUOTA_MEM_MIB,
        quota_vcpus: int = DEFAULT_QUOTA_VCPUS,
        replenish_cooldown_seconds: float = REPLENISH_COOLDOWN_SECONDS,
    ) -> None:
        # 多机接缝(Task C5):供给线统一收敛为 NodeClient;裸工厂即本地节点
        if node_client is None:
            if sandbox_factory is None:
                raise ValueError("必须提供 sandbox_factory 或 node_client 之一")
            node_client = LocalNodeClient(sandbox_factory)
        self._node = node_client
        self._factory = node_client.create_sandbox
        self._project_factory = project_sandbox_factory
        self._min_size = min_size
        self._max_size = max_size
        self._acquire_timeout = acquire_timeout
        self._idle_pause_seconds = idle_pause_seconds
        self._idle_evict_seconds = idle_evict_seconds
        self._max_lifetime = max_lifetime_seconds
        self._recycle_after = recycle_after_seconds
        # —— 快照持久化(Task C2)——
        # persist_fn(lease) -> bool:True 表示 VM 已快照并拆除,池只做记账摘除;
        # restore_factory(snapshot_id, project_id) -> sandbox:快照恢复的工厂
        self._persist_fn: Callable[[SandboxLease], bool] | None = None
        self._lifecycle_fn: Callable[[str, str, HagentSandboxProtocol], None] | None = None
        self._activity_touch_fn: Callable[[str], None] | None = None
        self._last_activity_fn: Callable[[str], float | None] | None = None
        self._checkpoint_fn: (
            Callable[[str, HagentSandboxProtocol, str], None] | None
        ) = None
        # run-hold:project 有活跃 Run 时 GC 一律不降档(pause/persist/evict/
        # max_lifetime),由 manager 注入 RunStore 视图;未注入即无 hold
        self._active_run_fn: Callable[[str], bool] | None = None
        self._project_guard_fn: Callable[[str], AbstractContextManager] | None = None
        self._restore_factory = restore_factory
        self._idle: Queue = Queue()
        self._leased: dict[str, SandboxLease] = {}
        self._lock = threading.RLock()
        self._size = 0
        self._gc_stop: threading.Event | None = None
        # —— 准入账本 ——
        self._ledger = ledger
        self._quota_mem_mib = quota_mem_mib
        self._quota_vcpus = quota_vcpus
        self._reservations: dict[int, Reservation] = {}  # id(sandbox) → 占位
        # —— 补货熔断 ——
        self._replenish_failures = 0
        self._replenish_cooldown = replenish_cooldown_seconds
        self._breaker_open_until = 0.0
        self._replenish_active = False
        self._shutting_down = False

    @property
    def node_id(self) -> str:
        """本池的供给节点标识(session 落 node 列;单机恒 local)。"""
        return self._node.node_id

    # —— 项目绑定与活跃回写（provider 不支持时无影响）——————————

    def _bind_project(
        self, sandbox: HagentSandboxProtocol, project_id: str | None
    ) -> None:
        bind = getattr(sandbox, "bind_project", None)
        if callable(bind):
            try:
                bind(project_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("bind_project(%s) 失败(忽略): %s", project_id, exc)
        set_activity_callback = getattr(sandbox, "set_activity_callback", None)
        if callable(set_activity_callback):
            callback = None
            if project_id is not None and self._activity_touch_fn is not None:
                callback = lambda: self._activity_touch_fn(project_id)
            try:
                set_activity_callback(callback)
            except Exception as exc:  # noqa: BLE001
                logger.warning("project %s 活跃回调绑定失败(忽略): %s", project_id, exc)
        # 沙箱自发的生命周期变化(通道内 ensure_running 唤醒 → "resumed"、
        # pause → "paused")经此回到 manager,与 GC 触发的事件同一出口
        set_lifecycle_callback = getattr(sandbox, "set_lifecycle_callback", None)
        if callable(set_lifecycle_callback):
            lifecycle_callback = None
            if project_id is not None:
                lifecycle_callback = lambda kind: self._notify_lifecycle(
                    kind, project_id, sandbox
                )
            try:
                set_lifecycle_callback(lifecycle_callback)
            except Exception as exc:  # noqa: BLE001
                logger.warning("project %s 生命周期回调绑定失败(忽略): %s", project_id, exc)

    # —— 创建 / 销毁(统一走账本)———————————————————————————————

    def _create_sandbox(
        self, factory: Callable[[], HagentSandboxProtocol] | None = None
    ) -> HagentSandboxProtocol:
        """占位 → 工厂 → 提交;工厂失败回滚占位。调用方负责 size 记账。"""
        reservation: Reservation | None = None
        if self._ledger is not None:
            reservation = self._ledger.try_reserve(
                mem_mib=self._quota_mem_mib, vcpus=self._quota_vcpus
            )
        try:
            sandbox = (factory or self._factory)()
        except BaseException:
            if reservation is not None:
                self._ledger.release(reservation)
            raise
        if reservation is not None:
            self._ledger.commit(reservation)
            with self._lock:
                self._reservations[id(sandbox)] = reservation
        return sandbox

    def _teardown_sandbox(self, sandbox: HagentSandboxProtocol) -> None:
        """close + 归还额度;幂等,失败不抛。"""
        try:
            sandbox.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("sandbox close failed: %s", exc)
        finally:
            if self._ledger is not None:
                with self._lock:
                    reservation = self._reservations.pop(id(sandbox), None)
                if reservation is not None:
                    self._ledger.release(reservation)

    # —— 预热 / 补货 ——————————————————————————————————————————

    def prewarm(self) -> None:
        with self._lock:
            need = self._min_size - self._size
        for _ in range(max(0, need)):
            with self._lock:
                if self._size >= self._min_size:
                    break
                self._size += 1
            try:
                sandbox = self._create_sandbox()
            except BaseException:
                with self._lock:
                    self._size = max(0, self._size - 1)
                raise
            self._idle.put(sandbox)

    def _replenish_once(self) -> None:
        """补一只沙箱到 warm 池(idle < min 时);熔断打开期间 no-op。

        连续 ``REPLENISH_BREAKER_THRESHOLD`` 次工厂失败 → 打开熔断,
        冷却窗口后再试;容量不足(CapacityExceeded)不是 provider 故障,
        静默跳过、不计入熔断。
        """
        if self._shutting_down:
            return
        now = time.monotonic()
        if now < self._breaker_open_until:
            return
        with self._lock:
            if self._idle.qsize() >= self._min_size or self._size >= self._max_size:
                return
            self._size += 1
        try:
            sandbox = self._create_sandbox()
        except CapacityExceeded:
            with self._lock:
                self._size = max(0, self._size - 1)
            logger.info("补货跳过:宿主额度不足")
            return
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._size = max(0, self._size - 1)
                self._replenish_failures += 1
                failures = self._replenish_failures
            logger.warning("补货失败(连续 %d 次): %s", failures, exc)
            if failures >= REPLENISH_BREAKER_THRESHOLD:
                self._breaker_open_until = time.monotonic() + self._replenish_cooldown
                logger.error(
                    "补货熔断打开:连续 %d 败,冷却 %.0fs 后重试",
                    failures,
                    self._replenish_cooldown,
                )
            return
        with self._lock:
            self._replenish_failures = 0
        if self._shutting_down:
            self._teardown_sandbox(sandbox)
            with self._lock:
                self._size = max(0, self._size - 1)
            return
        self._idle.put(sandbox)

    def _maybe_replenish_async(self) -> None:
        """认领即补:后台线程补货,单飞防线程风暴。"""
        if self._min_size <= 0 or self._shutting_down:
            return
        if time.monotonic() < self._breaker_open_until:
            return
        with self._lock:
            if self._replenish_active:
                return
            if self._idle.qsize() >= self._min_size or self._size >= self._max_size:
                return
            self._replenish_active = True

        def worker() -> None:
            try:
                while not self._shutting_down:
                    before = self._idle.qsize()
                    self._replenish_once()
                    if self._idle.qsize() <= before:
                        break  # 没有进展(熔断/额度/已达标)即收工
            finally:
                with self._lock:
                    self._replenish_active = False

        threading.Thread(target=worker, daemon=True, name="hagent-sandbox-replenish").start()

    # —— acquire / release ————————————————————————————————————————

    def acquire(self, *, project_id: str) -> SandboxLease:
        sandbox: HagentSandboxProtocol | None = None
        if self._project_factory is None:
            try:
                sandbox = self._idle.get_nowait()
            except Empty:
                pass
        if sandbox is None:
            claimed_slot = False
            with self._lock:
                if self._size < self._max_size:
                    self._size += 1
                    claimed_slot = True
            if claimed_slot:
                try:
                    # 池空且额度足 → 冷启动;CapacityExceeded 原样上抛(503)
                    factory = (
                        (lambda: self._project_factory(project_id))
                        if self._project_factory is not None
                        else None
                    )
                    sandbox = self._create_sandbox(factory=factory)
                except BaseException:
                    with self._lock:
                        self._size = max(0, self._size - 1)
                    raise
        if sandbox is None:
            # Wait for someone to release
            deadline = time.monotonic() + self._acquire_timeout
            while time.monotonic() < deadline:
                try:
                    sandbox = self._idle.get(timeout=0.05)
                    break
                except Empty:
                    continue
            if sandbox is None:
                raise PoolExhausted(
                    f"sandbox pool exhausted (max={self._max_size}) after {self._acquire_timeout}s"
                )
        self._bind_project(sandbox, project_id)
        lease = SandboxLease(sandbox=sandbox, project_id=project_id)
        with self._lock:
            self._leased[project_id] = lease
        self._maybe_replenish_async()
        return lease

    def acquire_restored(self, *, project_id: str, snapshot_id: str) -> SandboxLease:
        """快照恢复(Task C2):占位 → restore_factory → 提交 → lease。

        恢复的 VM 同样吃内存,必须先过账本；本层将容量或恢复错误交给
        manager，由其把快照视为缓存未命中并尝试 warm/cold 供给。
        恢复本身不消费 warm 池、不触发补货——恢复与预热是两条独立供给线。
        """
        if self._restore_factory is None:
            raise RuntimeError("此池未配置 restore_factory,无法从快照恢复")
        claimed_slot = False
        with self._lock:
            if self._size < self._max_size:
                self._size += 1
                claimed_slot = True
        if not claimed_slot:
            raise PoolExhausted(f"sandbox pool exhausted (max={self._max_size})")
        try:
            sandbox = self._create_sandbox(
                factory=lambda: self._restore_factory(snapshot_id, project_id)
            )
        except BaseException:
            with self._lock:
                self._size = max(0, self._size - 1)
            raise
        self._bind_project(sandbox, project_id)
        lease = SandboxLease(sandbox=sandbox, project_id=project_id)
        with self._lock:
            self._leased[project_id] = lease
        return lease

    def set_persist_fn(self, persist_fn: Callable[[SandboxLease], bool] | None) -> None:
        """装配期注入：manager 持项目租约记账，池只认布尔结果。"""
        self._persist_fn = persist_fn

    def set_lifecycle_fn(
        self,
        lifecycle_fn: Callable[[str, str, HagentSandboxProtocol], None] | None,
    ) -> None:
        """接收池内 GC 产生的项目生命周期变更。"""
        self._lifecycle_fn = lifecycle_fn

    def set_activity_fns(
        self,
        *,
        touch_fn: Callable[[str], None] | None,
        last_activity_fn: Callable[[str], float | None] | None,
    ) -> None:
        """接入项目租约的活跃时间写入与读取。"""
        self._activity_touch_fn = touch_fn
        self._last_activity_fn = last_activity_fn

    def set_project_guard_fn(
        self,
        guard_fn: Callable[[str], AbstractContextManager] | None,
    ) -> None:
        """让池内项目生命周期副作用与 manager 共用协调边界。"""
        self._project_guard_fn = guard_fn

    def set_checkpoint_fn(
        self,
        checkpoint_fn: Callable[[str, HagentSandboxProtocol, str], None] | None,
    ) -> None:
        """注入生命周期动作前的项目工作区兜底 checkpoint。

        签名 ``(project_id, sandbox, reason)``;reason ∈ pause/persist/evict/
        release/drain/shutdown,供 run 终结记账写明原因。
        """
        self._checkpoint_fn = checkpoint_fn

    def set_active_run_fn(self, active_run_fn: Callable[[str], bool] | None) -> None:
        """注入「project 是否有活跃 Run」判定(run-hold 的数据源)。"""
        self._active_run_fn = active_run_fn

    def _has_active_run(self, project_id: str) -> bool:
        """run-hold 判定。判定函数异常按 **有活跃 Run** 处理(fail-safe:
        宁可晚一轮降档,也不能在 Run 中冻结/拆掉 VM)。"""
        if self._active_run_fn is None:
            return False
        try:
            return bool(self._active_run_fn(project_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "project %s 活跃 Run 判定失败,按 run-hold 处理: %s", project_id, exc
            )
            return True

    def _checkpoint_before_lifecycle(self, lease: SandboxLease, *, reason: str) -> None:
        if self._checkpoint_fn is None:
            return
        try:
            self._checkpoint_fn(lease.project_id, lease.sandbox, reason)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "project %s 生命周期(%s)前 checkpoint 失败(继续回收): %s",
                lease.project_id,
                reason,
                exc,
            )

    def _project_guard(self, project_id: str) -> AbstractContextManager:
        if self._project_guard_fn is None:
            return nullcontext()
        return self._project_guard_fn(project_id)

    def _is_current(self, lease: SandboxLease) -> bool:
        with self._lock:
            return self._leased.get(lease.project_id) is lease

    def _notify_lifecycle(
        self, kind: str, project_id: str, sandbox: HagentSandboxProtocol
    ) -> None:
        if self._lifecycle_fn is None:
            return
        try:
            self._lifecycle_fn(kind, project_id, sandbox)
        except Exception as exc:  # noqa: BLE001
            logger.warning("project %s 生命周期回调失败(%s): %s", project_id, kind, exc)

    def _try_persist(self, lease: SandboxLease) -> bool:
        """paused 超阈值时先试快照持久化;成功则只做记账摘除(VM 已拆)。"""
        with self._project_guard(lease.project_id):
            return self._try_persist_guarded(lease)

    def _try_persist_guarded(self, lease: SandboxLease) -> bool:
        assert self._persist_fn is not None
        if not self._is_current(lease):
            return True
        self._checkpoint_before_lifecycle(lease, reason="persist")
        try:
            persisted = bool(self._persist_fn(lease))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "project=%s 快照持久化失败,退回驱逐: %s", lease.project_id, exc
            )
            return False
        if not persisted:
            return False
        with self._lock:
            current = self._leased.get(lease.project_id)
            if current is lease:
                self._leased.pop(lease.project_id, None)
            elif current is None:
                return True
        if current is not lease:
            # 回调返回后同项目可能已恢复出新租约；只清理旧 VM 的容量记账，
            # 不得按 project_id 误删替代租约。
            logger.info("project %s 快照完成后已有替代租约，保留新租约", lease.project_id)
        # close 对已拆 VM 是幂等 no-op;走统一 teardown 归还账本额度
        self._teardown_sandbox(lease.sandbox)
        with self._lock:
            self._size = max(0, self._size - 1)
        return True

    def stats(self) -> dict:
        """只读池快照(ops 监控用):容量档位 + 在册数 + 补货熔断态。"""
        with self._lock:
            leased_ids = list(self._leased.keys())
            leased = len(leased_ids)
            size = self._size
            breaker_open = time.monotonic() < self._breaker_open_until
            replenish_failures = self._replenish_failures
        held = sum(1 for pid in leased_ids if self._has_active_run(pid))
        return {
            "size": size,
            "idle": self._idle.qsize(),
            "leased": leased,
            "held": held,
            "min_size": self._min_size,
            "max_size": self._max_size,
            "replenish_breaker_open": breaker_open,
            "replenish_failures": replenish_failures,
        }

    def live_vm_ids(self) -> set[str]:
        """池在册沙箱的 VM id(warm + leased)——supervisor 对账的保护集。"""
        ids: set[str] = set()
        with self._idle.mutex:
            idle_sandboxes = list(self._idle.queue)
        with self._lock:
            leased_sandboxes = [lease.sandbox for lease in self._leased.values()]
        for sandbox in (*idle_sandboxes, *leased_sandboxes):
            container_id = getattr(getattr(sandbox, "manifest", None), "container_id", None)
            if container_id:
                ids.add(container_id)
        return ids

    def register_external(
        self, sandbox: HagentSandboxProtocol, *, project_id: str
    ) -> SandboxLease:
        """把池外创建的沙箱(启动对账收养的 VM)纳入池的记账与治理。

        额度按新占位登记;账本已满时告警但照常收养——VM 实际存在,
        记账必须反映现实而非拒绝收养。
        """
        reservation: Reservation | None = None
        if self._ledger is not None:
            try:
                reservation = self._ledger.try_reserve(
                    mem_mib=self._quota_mem_mib, vcpus=self._quota_vcpus
                )
                self._ledger.commit(reservation)
            except CapacityExceeded:
                logger.warning(
                    "收养 project=%s 的 VM 时账本已满;按实收养,记账存在失真", project_id
                )
        self._bind_project(sandbox, project_id)
        lease = SandboxLease(sandbox=sandbox, project_id=project_id)
        with self._lock:
            self._size += 1
            if reservation is not None:
                self._reservations[id(sandbox)] = reservation
            self._leased[project_id] = lease
        return lease

    def evict(self, project_id: str) -> bool:
        """强制驱逐指定 project 的沙箱:不回 warm 池(即便 REUSE 开着),
        close + 归还额度。健康巡检杀重建(spec D10)的清残留入口。"""
        with self._lock:
            lease = self._leased.get(project_id)
        if lease is None:
            return False
        return self._evict_lease(lease)

    def _evict_lease(self, lease: SandboxLease) -> bool:
        """仅当租约仍是项目当前值时驱逐，避免 GC 误杀替代 VM。"""
        with self._project_guard(lease.project_id):
            return self._evict_lease_guarded(lease)

    def _evict_lease_guarded(self, lease: SandboxLease) -> bool:
        with self._lock:
            if self._leased.get(lease.project_id) is not lease:
                return False
        self._checkpoint_before_lifecycle(lease, reason="evict")
        with self._lock:
            if self._leased.get(lease.project_id) is not lease:
                return False
            self._leased.pop(lease.project_id, None)
        self._teardown_sandbox(lease.sandbox)
        with self._lock:
            self._size = max(0, self._size - 1)
        logger.info(
            "project %s sandbox %s 已驱逐",
            lease.project_id,
            getattr(lease.sandbox, "id", None),
        )
        self._notify_lifecycle("evicted", lease.project_id, lease.sandbox)
        return True

    def release(self, lease: SandboxLease) -> bool:
        with self._project_guard(lease.project_id):
            return self._release_guarded(lease)

    def _release_guarded(self, lease: SandboxLease) -> bool:
        with self._lock:
            if self._leased.get(lease.project_id) is not lease:
                # 已被并发路径摘除或替换时保持幂等，避免 size 双减或误删新租约。
                return False
        self._checkpoint_before_lifecycle(lease, reason="release")
        with self._lock:
            if self._leased.get(lease.project_id) is not lease:
                return False
            self._leased.pop(lease.project_id, None)
        if self._should_reuse():
            try:
                lease.sandbox.execute("rm -rf /workspace/* /workspace/.[!.]* 2>/dev/null || true")
                self._bind_project(lease.sandbox, None)
                self._idle.put(lease.sandbox)
                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning("reuse cleanup failed; tearing down: %s", exc)
        self._teardown_sandbox(lease.sandbox)
        with self._lock:
            self._size = max(0, self._size - 1)
        return True

    def drain(self) -> None:
        """graceful drain(Task B5):warm 池拆除,leased **pause 后保留**。

        与 shutdown 的区别:leased VM 不 close 不删——进程退出后 VM 照跑
        (F1),下次启动对账收养(D9:对话型产品重启不杀活跃会话)。
        """
        self._shutting_down = True
        self.stop_gc_loop()
        while True:
            try:
                sb = self._idle.get_nowait()
            except Empty:
                break
            self._teardown_sandbox(sb)
            with self._lock:
                self._size = max(0, self._size - 1)
        with self._lock:
            leases = list(self._leased.values())
        for lease in leases:
            try:
                self._checkpoint_before_lifecycle(lease, reason="drain")
                lease.sandbox.pause()
            except Exception as exc:  # noqa: BLE001
                logger.warning("drain pause 失败 project=%s: %s", lease.project_id, exc)

    def shutdown(self) -> None:
        self._shutting_down = True
        self.stop_gc_loop()
        while True:
            try:
                sb = self._idle.get_nowait()
            except Empty:
                break
            self._teardown_sandbox(sb)
        with self._lock:
            leases = list(self._leased.values())
            self._leased.clear()
        for lease in leases:
            self._checkpoint_before_lifecycle(lease, reason="shutdown")
            self._teardown_sandbox(lease.sandbox)
        with self._lock:
            self._size = 0

    def _recycle_pass(self, now: float) -> None:
        """warm idle 超龄回收(Task C1,防漂移):拆旧实例,补货线程回填至 min。

        只针对池内闲置实例——在租实例的寿命治理归 max_lifetime;
        created_at 缺失(非数值)的实例不回收,宁旧勿误杀。
        """
        assert self._recycle_after is not None
        recycled = 0
        # 逐只处理并即时放回幸存者:bounded by 起始 qsize(放回队尾不会本轮重检)。
        # 不一次性抽干——否则幸存暖 VM 在超龄实例 teardown(秒级)期间既不在 _idle
        # 也不在 live_vm_ids,并发 acquire 伪 503、reaper 保护集漏窗
        for _ in range(self._idle.qsize()):
            try:
                sandbox = self._idle.get_nowait()
            except Empty:
                break
            manifest = getattr(sandbox, "manifest", None)
            created_at = getattr(manifest, "created_at", None) if manifest is not None else None
            if isinstance(created_at, (int, float)) and now - created_at >= self._recycle_after:
                self._teardown_sandbox(sandbox)
                with self._lock:
                    self._size = max(0, self._size - 1)
                recycled += 1
            else:
                self._idle.put(sandbox)  # 立即放回,幸存者不脱离 _idle/live_vm_ids
        if recycled:
            logger.info(
                "recycle %d 只超龄 warm 沙箱(>= %.0fs),触发补货回填", recycled, self._recycle_after
            )
            self._maybe_replenish_async()

    def _gc_pass(self, *, now: float | None = None) -> None:
        if now is None:
            now = time.time()
        if self._recycle_after is not None:
            self._recycle_pass(now)
        with self._lock:
            leases = list(self._leased.values())
        for lease in leases:
            with self._project_guard(lease.project_id):
                if not self._is_current(lease):
                    continue
                # run-hold:活跃 Run 期间任何降档(pause/persist/evict/max_lifetime)
                # 都会让正在跑的工具打到冻结/消失的 VM,一律跳过,等 Run 结束
                if self._has_active_run(lease.project_id):
                    logger.debug("project %s run-hold: 跳过本轮 GC 降档", lease.project_id)
                    continue
                manifest = getattr(lease.sandbox, "manifest", None)
                # 绝对寿命上限与 idle 无关(但受 run-hold 约束),到期即驱逐。
                if self._max_lifetime is not None and manifest is not None:
                    age = now - getattr(manifest, "created_at", now)
                    if age >= self._max_lifetime:
                        logger.info(
                            "evicting sandbox project=%s: max_lifetime %.0fs 到期(age=%.0fs)",
                            lease.project_id,
                            self._max_lifetime,
                            age,
                        )
                        self._evict_lease_guarded(lease)
                        continue
                last_used = None
                if self._last_activity_fn is not None:
                    try:
                        last_used = self._last_activity_fn(lease.project_id)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("project %s 活跃时间读取失败: %s", lease.project_id, exc)
                if not self._is_current(lease):
                    continue
                if not isinstance(last_used, (int, float)):
                    last_used = (
                        getattr(manifest, "last_used_at", lease.leased_at)
                        if manifest is not None
                        else lease.leased_at
                    )
                idle = now - last_used
                paused = (
                    getattr(manifest, "paused", False)
                    if manifest is not None
                    else False
                )
                if idle >= self._idle_pause_seconds and not paused:
                    logger.info(
                        "pausing sandbox project=%s after %.1fs idle",
                        lease.project_id,
                        idle,
                    )
                    try:
                        self._checkpoint_before_lifecycle(lease, reason="pause")
                        lease.sandbox.pause()
                        if manifest is not None:
                            manifest.paused = True
                        self._notify_lifecycle("paused", lease.project_id, lease.sandbox)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("pause failed for project=%s: %s", lease.project_id, exc)
                elif paused and idle >= self._idle_evict_seconds:
                    # 优先快照持久化；不可用或失败时才退回破坏性驱逐。
                    if self._persist_fn is not None and self._try_persist_guarded(lease):
                        continue
                    logger.info(
                        "evicting sandbox project=%s after %.1fs idle",
                        lease.project_id,
                        idle,
                    )
                    self._evict_lease_guarded(lease)

    def start_gc_loop(self, *, interval_seconds: float = 60.0) -> threading.Thread:
        stop = threading.Event()
        self._gc_stop = stop

        def loop() -> None:
            while not stop.wait(interval_seconds):
                try:
                    self._gc_pass()
                except Exception:  # noqa: BLE001
                    logger.exception("idle_gc pass failed")

        thread = threading.Thread(target=loop, daemon=True, name="hagent-sandbox-gc")
        thread.start()
        return thread

    def stop_gc_loop(self) -> None:
        if self._gc_stop is not None:
            self._gc_stop.set()

    @staticmethod
    def _should_reuse() -> bool:
        return os.environ.get("HAGENT_SANDBOX_REUSE", "").lower() in {"1", "true", "yes"}
