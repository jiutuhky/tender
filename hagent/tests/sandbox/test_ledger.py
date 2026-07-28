"""Task A6 — AdmissionLedger:内存不超卖 / CPU 受控超卖 / 占位-提交-释放。"""

from __future__ import annotations

import threading

import pytest

from hagent.sandbox.ledger import AdmissionLedger, CapacityExceeded


def make_ledger(**kwargs) -> AdmissionLedger:
    kwargs.setdefault("host_memory_mib", 16384)
    kwargs.setdefault("host_cpus", 8)
    return AdmissionLedger(**kwargs)


class TestCapacity:
    def test_memory_capacity_applies_reserve_pct(self):
        # 16384 × (1 − 25%) = 12288
        ledger = make_ledger()
        assert ledger.mem_capacity_mib == 12288

    def test_cpu_capacity_applies_overcommit(self):
        # 8 × 2 = 16
        ledger = make_ledger()
        assert ledger.cpu_capacity == 16

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("HAGENT_SMOLVM_MEM_RESERVE_PCT", "50")
        monkeypatch.setenv("HAGENT_SMOLVM_CPU_OVERCOMMIT", "4")
        ledger = make_ledger()
        assert ledger.mem_capacity_mib == 8192
        assert ledger.cpu_capacity == 32

    def test_host_probe_injectable(self):
        ledger = AdmissionLedger(host_memory_mib=4096, host_cpus=2)
        assert ledger.mem_capacity_mib == 3072
        assert ledger.cpu_capacity == 4

    def test_default_probes_host(self):
        # 不注入时探测宿主(只验证 >0,不锁具体值)
        ledger = AdmissionLedger()
        assert ledger.mem_capacity_mib > 0
        assert ledger.cpu_capacity > 0


class TestReserveLifecycle:
    def test_reserve_then_commit_then_release(self):
        ledger = make_ledger()
        r = ledger.try_reserve(mem_mib=2048, vcpus=2)
        assert ledger.mem_in_use_mib == 2048
        assert ledger.cpu_in_use == 2
        ledger.commit(r)
        # commit 是状态转移,不改变占用量(创建中→运行中都满额计)
        assert ledger.mem_in_use_mib == 2048
        ledger.release(r)
        assert ledger.mem_in_use_mib == 0
        assert ledger.cpu_in_use == 0

    def test_release_uncommitted_reservation(self):
        # 创建失败路径:占位未 commit 直接 release
        ledger = make_ledger()
        r = ledger.try_reserve(mem_mib=2048, vcpus=2)
        ledger.release(r)
        assert ledger.mem_in_use_mib == 0

    def test_release_idempotent(self):
        ledger = make_ledger()
        r = ledger.try_reserve(mem_mib=2048, vcpus=2)
        ledger.release(r)
        ledger.release(r)
        assert ledger.mem_in_use_mib == 0

    def test_memory_exhaustion_raises(self):
        ledger = make_ledger()  # 12288 可用
        ledger.try_reserve(mem_mib=8192, vcpus=1)
        with pytest.raises(CapacityExceeded):
            ledger.try_reserve(mem_mib=8192, vcpus=1)

    def test_cpu_exhaustion_raises(self):
        ledger = make_ledger()  # cpu 容量 16
        ledger.try_reserve(mem_mib=64, vcpus=16)
        with pytest.raises(CapacityExceeded):
            ledger.try_reserve(mem_mib=64, vcpus=1)

    def test_exhaustion_message_mentions_dimension(self):
        ledger = make_ledger()
        ledger.try_reserve(mem_mib=12288, vcpus=1)
        with pytest.raises(CapacityExceeded, match="内存"):
            ledger.try_reserve(mem_mib=1, vcpus=1)

    def test_release_frees_capacity_for_next(self):
        ledger = make_ledger()
        r = ledger.try_reserve(mem_mib=12288, vcpus=2)
        ledger.release(r)
        ledger.try_reserve(mem_mib=12288, vcpus=2)


class TestConcurrency:
    def test_concurrent_reserve_never_overshoots(self):
        # 容量恰好 4 份(10923 × 0.75 ≈ 8192 = 4 × 2048);16 线程抢,成功数必须 == 4
        ledger = AdmissionLedger(host_memory_mib=10923, host_cpus=64)
        successes: list = []
        failures: list = []
        barrier = threading.Barrier(16)

        def worker():
            barrier.wait()
            try:
                successes.append(ledger.try_reserve(mem_mib=2048, vcpus=1))
            except CapacityExceeded:
                failures.append(1)

        threads = [threading.Thread(target=worker) for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert len(successes) == 4
        assert len(failures) == 12
        assert ledger.mem_in_use_mib == 4 * 2048
