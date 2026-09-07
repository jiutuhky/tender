"""容量准入覆盖项目轮换、资源账本、失败保护和并发等待。"""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hagent.sandbox.ledger import AdmissionLedger
from hagent.sandbox.pool import PoolExhausted, SandboxPool


def make_pool(**kwargs):
    def factory():
        sb = MagicMock()
        sb.manifest = SimpleNamespace(paused=False, last_used_at=0)
        return sb
    return SandboxPool(sandbox_factory=factory, min_size=0, acquire_timeout=0, **kwargs)


@pytest.mark.parametrize('restore', [False, True])
def test_fifth_project_reclaims_oldest_idle_project_and_preserves_active(restore):
    pool = make_pool(max_size=4, restore_factory=lambda snap, pid: MagicMock())
    old = [pool.acquire(project_id=str(i)) for i in range(4)]
    # 旧环境无需等待五分钟暂停，run-hold 是正在执行任务的保护依据。
    pool.set_active_run_fn(lambda pid: pid == '0')
    pool.set_activity_fns(touch_fn=None, last_activity_fn=lambda pid: float(pid))
    persisted = []
    pool.set_persist_fn(lambda lease: persisted.append(lease.project_id) or True)
    try:
        new = (pool.acquire_restored(project_id='new', snapshot_id='snap')
               if restore else pool.acquire(project_id='new'))
        assert persisted == ['1']
        assert new.sandbox is not old[1].sandbox
        old[0].sandbox.close.assert_not_called()
        old[1].sandbox.close.assert_called_once()
        assert pool.stats()['size'] == 4
    finally:
        pool.shutdown()


@pytest.mark.parametrize('blocked_by', ['active', 'snapshot_failure', 'unknown_run', 'locked'])
def test_pressure_preserves_unavailable_or_unpersisted_project(blocked_by):
    pool = make_pool(max_size=1)
    old = pool.acquire(project_id='old')
    def has_active_run(pid):
        if blocked_by == 'unknown_run':
            raise RuntimeError('状态查询失败')
        return blocked_by == 'active'
    pool.set_active_run_fn(has_active_run)
    @contextmanager
    def try_guard(pid):
        yield blocked_by != 'locked'
    pool.set_project_try_guard_fn(try_guard)
    persist = MagicMock(return_value=False)
    pool.set_persist_fn(persist)
    try:
        with pytest.raises(PoolExhausted):
            pool.acquire(project_id='new')
        old.sandbox.close.assert_not_called()
        assert pool.stats()['size'] == 1
        if blocked_by != 'snapshot_failure':
            persist.assert_not_called()
        else:
            persist.assert_called_once()
    finally:
        pool.shutdown()


def test_host_memory_pressure_reclaims_even_when_pool_has_free_slots():
    ledger = AdmissionLedger(host_memory_mib=4096, host_cpus=4)
    pool = make_pool(max_size=4, ledger=ledger, quota_mem_mib=2048)
    old = pool.acquire(project_id='old')
    pool.set_persist_fn(lambda lease: True)
    try:
        pool.acquire(project_id='new')
        old.sandbox.close.assert_called_once()
        assert ledger.mem_in_use_mib == 2048
        assert pool.stats()['size'] == 1
    finally:
        pool.shutdown()
    assert ledger.mem_in_use_mib == 0


def test_waiter_can_use_capacity_freed_by_destroying_release():
    pool = make_pool(max_size=1)
    pool._acquire_timeout = 1
    old = pool.acquire(project_id='old')
    waiting = Event()
    original = pool._reclaim_capacity
    def reclaim(**kwargs):
        waiting.set()
        return original(**kwargs)
    pool._reclaim_capacity = reclaim
    try:
        with ThreadPoolExecutor() as executor:
            pending = executor.submit(pool.acquire, project_id='new')
            assert waiting.wait(1)
            pool.release(old)
            assert pending.result(timeout=2).project_id == 'new'
    finally:
        pool.shutdown()


def test_concurrent_admission_never_exceeds_capacity_or_snapshots_twice():
    pool = make_pool(max_size=1)
    pool._acquire_timeout = 0.2
    old = pool.acquire(project_id='old')
    persisted = []
    pool.set_active_run_fn(lambda pid: pid != 'old')
    pool.set_persist_fn(lambda lease: persisted.append(lease.project_id) or True)
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(pool.acquire, project_id=f'new{i}') for i in range(4)]
            successes = []
            for future in futures:
                try:
                    successes.append(future.result(timeout=2))
                except PoolExhausted:
                    pass
        assert len(successes) == 1
        assert persisted == ['old']
        old.sandbox.close.assert_called_once()
        assert pool.stats()['size'] == 1
    finally:
        pool.shutdown()


def test_factory_failure_returns_both_pool_and_host_reservations():
    ledger = AdmissionLedger(host_memory_mib=4096, host_cpus=4)
    pool = make_pool(max_size=1, ledger=ledger)
    pool._factory = MagicMock(side_effect=RuntimeError('创建失败'))
    with pytest.raises(RuntimeError, match='创建失败'):
        pool.acquire(project_id='new')
    assert pool.stats()['size'] == 0
    assert ledger.mem_in_use_mib == 0


def test_pressure_never_bypasses_existing_project_coordination():
    from threading import RLock

    pool = make_pool(max_size=1)
    old = pool.acquire(project_id='old')
    lock = RLock()
    pool.set_project_guard_fn(lambda pid: lock)
    persist = MagicMock(return_value=True)
    pool.set_persist_fn(persist)
    try:
        with pytest.raises(PoolExhausted):
            pool.acquire(project_id='new')
        persist.assert_not_called()
        old.sandbox.close.assert_not_called()
    finally:
        pool.shutdown()
