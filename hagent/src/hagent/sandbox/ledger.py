"""AdmissionLedger — provider 无关的容量账本(spec D7)。

内存**不超卖**:可用 = 宿主内存 ×(1 − 预留%)− Σ(创建中占位 + 运行中);
Firecracker 不归还 guest 内存,按配额满额计。CPU 按超卖比放大。
不足时快速失败(CapacityExceeded → API 503),不排队。
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field

DEFAULT_MEM_RESERVE_PCT = 25
DEFAULT_CPU_OVERCOMMIT = 2


class CapacityExceeded(RuntimeError):
    """宿主容量不足,拒绝新 sandbox 准入。"""


@dataclass
class Reservation:
    """一份已占用的配额;committed 只是状态标记,占用量不变。"""

    mem_mib: int
    vcpus: int
    committed: bool = False
    _released: bool = field(default=False, repr=False)


def _probe_host_memory_mib() -> int:
    with open("/proc/meminfo", encoding="ascii") as f:
        for line in f:
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024
    raise RuntimeError("无法从 /proc/meminfo 读取 MemTotal")


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


class AdmissionLedger:
    """线程安全的占位-提交-释放账本。

    ``host_memory_mib`` / ``host_cpus`` 可注入(测试与容量压缩部署);
    预留比例与 CPU 超卖比走 env(HAGENT_SMOLVM_MEM_RESERVE_PCT /
    HAGENT_SMOLVM_CPU_OVERCOMMIT)。
    """

    def __init__(
        self,
        *,
        host_memory_mib: int | None = None,
        host_cpus: int | None = None,
    ) -> None:
        mem_total = host_memory_mib if host_memory_mib is not None else _probe_host_memory_mib()
        cpus = host_cpus if host_cpus is not None else (os.cpu_count() or 1)
        reserve_pct = _int_env("HAGENT_SMOLVM_MEM_RESERVE_PCT", DEFAULT_MEM_RESERVE_PCT)
        overcommit = _int_env("HAGENT_SMOLVM_CPU_OVERCOMMIT", DEFAULT_CPU_OVERCOMMIT)
        self._mem_capacity_mib = int(mem_total * (100 - reserve_pct) / 100)
        self._cpu_capacity = cpus * overcommit
        self._mem_in_use = 0
        self._cpu_in_use = 0
        self._lock = threading.Lock()

    # —— 容量视图 ——————————————————————————————————————————————

    @property
    def mem_capacity_mib(self) -> int:
        return self._mem_capacity_mib

    @property
    def cpu_capacity(self) -> int:
        return self._cpu_capacity

    @property
    def mem_in_use_mib(self) -> int:
        return self._mem_in_use

    @property
    def cpu_in_use(self) -> int:
        return self._cpu_in_use

    # —— 占位 / 提交 / 释放 ————————————————————————————————————————

    def try_reserve(self, *, mem_mib: int, vcpus: int) -> Reservation:
        with self._lock:
            if self._mem_in_use + mem_mib > self._mem_capacity_mib:
                raise CapacityExceeded(
                    f"内存额度不足: 需 {mem_mib}MiB,"
                    f"已用 {self._mem_in_use}/{self._mem_capacity_mib}MiB"
                )
            if self._cpu_in_use + vcpus > self._cpu_capacity:
                raise CapacityExceeded(
                    f"CPU 额度不足: 需 {vcpus} vCPU,已用 {self._cpu_in_use}/{self._cpu_capacity}"
                )
            self._mem_in_use += mem_mib
            self._cpu_in_use += vcpus
            return Reservation(mem_mib=mem_mib, vcpus=vcpus)

    def commit(self, reservation: Reservation) -> None:
        """创建成功后把占位标记为运行中(占用量不变,防重复释放的审计位)。"""
        reservation.committed = True

    def release(self, reservation: Reservation) -> None:
        """归还额度;幂等——释放/驱逐/创建失败路径都可安全调用。"""
        with self._lock:
            if reservation._released:
                return
            reservation._released = True
            self._mem_in_use = max(0, self._mem_in_use - reservation.mem_mib)
            self._cpu_in_use = max(0, self._cpu_in_use - reservation.vcpus)
