from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hagent.sandbox.pool import PoolExhausted, SandboxLease, SandboxPool


def test_pool_indexes_runtime_lease_by_project():
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2)
    lease = pool.acquire(project_id="project-alpha")

    assert lease.project_id == "project-alpha"
    assert pool.evict("project-alpha") is True
    assert pool.stats()["leased"] == 0


def test_project_activity_store_drives_tool_touch_and_idle_gc():
    import time

    touched: list[str] = []
    now = time.time()

    class ActivitySandbox:
        def __init__(self):
            self.manifest = MagicMock(
                created_at=now,
                last_used_at=now - 3600,
                paused=False,
                container_id="hagent-projecta-a1b2c3",
            )
            self.pause = MagicMock()
            self.close = MagicMock()
            self._activity_callback = None

        def bind_project(self, project_id):
            self.project_id = project_id

        def set_activity_callback(self, callback):
            self._activity_callback = callback

        def simulate_tool_call(self):
            self._activity_callback()

    sandbox = ActivitySandbox()
    pool = SandboxPool(
        sandbox_factory=lambda: sandbox,
        min_size=0,
        max_size=1,
        idle_pause_seconds=300,
    )
    pool.set_activity_fns(
        touch_fn=touched.append,
        last_activity_fn=lambda project_id: now,
    )
    lease = pool.acquire(project_id="project-alpha")

    lease.sandbox.simulate_tool_call()
    pool._gc_pass(now=now + 1)

    assert touched == ["project-alpha"]
    sandbox.pause.assert_not_called()
    pool.release(lease)


def test_project_factory_receives_lease_owner_when_cold_starting():
    seen: list[str] = []

    def project_factory(project_id: str):
        seen.append(project_id)
        sandbox = MagicMock()
        sandbox.id = "smolvm-project"
        return sandbox

    pool = SandboxPool(
        sandbox_factory=lambda: MagicMock(),
        project_sandbox_factory=project_factory,
        min_size=0,
        max_size=2,
    )
    lease = pool.acquire(project_id="project-alpha")

    assert seen == ["project-alpha"]
    assert lease.project_id == "project-alpha"
    pool.release(lease)


def _make_sandbox_factory():
    counter = {"n": 0}

    def factory():
        counter["n"] += 1
        sb = MagicMock()
        sb.id = f"docker-sb{counter['n']}"
        sb._container = MagicMock(id=f"cid{counter['n']}")
        sb.kind.value = "docker"
        sb.close = MagicMock()
        return sb

    return factory, counter


def test_pool_prewarms_to_min_size():
    factory, counter = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=2, max_size=4)
    pool.prewarm()
    assert counter["n"] == 2
    pool.shutdown()


def test_acquire_returns_warm_sandbox_when_available():
    factory, counter = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=1, max_size=4)
    pool.prewarm()
    lease = pool.acquire(project_id="s1")
    assert lease.sandbox.id == "docker-sb1"
    pool.release(lease)
    pool.shutdown()


def test_acquire_creates_new_when_pool_empty():
    factory, counter = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2)
    lease = pool.acquire(project_id="s1")
    assert counter["n"] == 1
    pool.release(lease)
    pool.shutdown()


def test_acquire_raises_when_max_reached():
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=1, acquire_timeout=0.05)
    lease1 = pool.acquire(project_id="s1")
    with pytest.raises(PoolExhausted):
        pool.acquire(project_id="s2")
    pool.release(lease1)
    pool.shutdown()


def test_release_default_stops_and_removes(monkeypatch):
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2)
    lease = pool.acquire(project_id="s1")
    pool.release(lease)
    lease.sandbox.close.assert_called_once()
    pool.shutdown()


def test_release_reuses_when_reuse_env_set(monkeypatch):
    monkeypatch.setenv("HAGENT_SANDBOX_REUSE", "true")
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2)
    lease = pool.acquire(project_id="s1")
    sandbox = lease.sandbox
    sandbox.execute = MagicMock(return_value=MagicMock(exit_code=0))
    pool.release(lease)
    sandbox.execute.assert_called_once()
    cmd_arg = sandbox.execute.call_args[0][0]
    assert "rm -rf" in cmd_arg
    sandbox.close.assert_not_called()
    pool.shutdown()


import time


# ---------------------------------------------------------------------------
# Task A7:ledger 准入 + 认领即补 + 补货熔断
# ---------------------------------------------------------------------------


class FakeLedger:
    """记录调用的账本替身;capacity 控制 try_reserve 放行数。"""

    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.reserved: list = []
        self.committed: list = []
        self.released: list = []

    def try_reserve(self, *, mem_mib: int, vcpus: int):
        from hagent.sandbox.ledger import CapacityExceeded, Reservation

        if len(self.reserved) - len(self.released) >= self.capacity:
            raise CapacityExceeded("内存额度不足")
        r = Reservation(mem_mib=mem_mib, vcpus=vcpus)
        self.reserved.append(r)
        return r

    def commit(self, r):
        r.committed = True
        self.committed.append(r)

    def release(self, r):
        if r not in self.released:
            self.released.append(r)


def _wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_acquire_with_ledger_reserves_commits_and_release_frees():
    factory, _ = _make_sandbox_factory()
    ledger = FakeLedger()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2, ledger=ledger)
    lease = pool.acquire(project_id="s1")
    assert len(ledger.reserved) == 1
    assert len(ledger.committed) == 1
    assert ledger.reserved[0].mem_mib > 0
    pool.release(lease)
    assert len(ledger.released) == 1, "释放沙箱必须归还额度"
    pool.shutdown()


def test_acquire_capacity_exceeded_propagates_and_no_slot_leak():
    from hagent.sandbox.ledger import CapacityExceeded

    factory, counter = _make_sandbox_factory()
    ledger = FakeLedger(capacity=0)
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2, ledger=ledger)
    with pytest.raises(CapacityExceeded):
        pool.acquire(project_id="s1")
    assert counter["n"] == 0
    # 额度恢复后必须还能创建:size 未泄漏
    ledger.capacity = 1
    lease = pool.acquire(project_id="s2")
    assert lease is not None
    pool.shutdown()


def test_factory_failure_rolls_back_size_and_reservation():
    ledger = FakeLedger()
    calls = {"n": 0}

    def flaky_factory():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boot failed")
        sb = MagicMock()
        sb.manifest = MagicMock(last_used_at=time.time(), paused=False)
        return sb

    pool = SandboxPool(sandbox_factory=flaky_factory, min_size=0, max_size=1, ledger=ledger)
    with pytest.raises(RuntimeError):
        pool.acquire(project_id="s1")
    assert len(ledger.released) == 1, "工厂失败必须回滚占位"
    # size 已回滚:max=1 下仍可再创建
    lease = pool.acquire(project_id="s2")
    assert lease is not None
    pool.shutdown()


def test_claim_triggers_async_replenish_to_min():
    factory, counter = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=1, max_size=4)
    pool.prewarm()
    assert counter["n"] == 1
    pool.acquire(project_id="s1")
    # 认领即异步补货:idle 应回到 min
    assert _wait_until(lambda: counter["n"] == 2), "认领后未触发补货"
    pool.shutdown()


def test_replenish_breaker_opens_after_3_consecutive_failures():
    state = {"n": 0, "fail_from": 2}

    def factory():
        state["n"] += 1
        if state["n"] >= state["fail_from"]:
            raise RuntimeError("provider down")
        sb = MagicMock()
        sb.manifest = MagicMock(last_used_at=time.time(), paused=False)
        return sb

    pool = SandboxPool(
        sandbox_factory=factory,
        min_size=1,
        max_size=8,
        replenish_cooldown_seconds=9999.0,
    )
    pool.prewarm()  # n=1 成功
    lease = pool.acquire(project_id="s1")  # 认领唯一 warm,触发补货(开始失败)
    assert _wait_until(lambda: pool._replenish_failures >= 1)
    # 再触发两次补货(release 不回池 → close;再 acquire 走冷启动会失败,
    # 这里直接调内部补货入口,行为锁定在「连续 3 败熔断」)
    pool._replenish_once()
    pool._replenish_once()
    assert pool._replenish_failures >= 3
    n_before = state["n"]
    pool._replenish_once()  # 熔断打开:不再打工厂
    assert state["n"] == n_before, "熔断期间不得继续冲击工厂"
    pool.release(lease)
    pool.shutdown()


def test_replenish_breaker_recovers_after_cooldown():
    state = {"n": 0, "fail": True}

    def factory():
        state["n"] += 1
        if state["fail"]:
            raise RuntimeError("down")
        sb = MagicMock()
        sb.manifest = MagicMock(last_used_at=time.time(), paused=False)
        return sb

    pool = SandboxPool(
        sandbox_factory=factory,
        min_size=1,
        max_size=8,
        replenish_cooldown_seconds=0.05,
    )
    for _ in range(3):
        pool._replenish_once()
    assert pool._replenish_failures == 3
    state["fail"] = False
    time.sleep(0.08)  # 冷却窗口过后重试
    pool._replenish_once()
    assert pool._replenish_failures == 0, "冷却后成功补货应复位熔断"
    pool.shutdown()


def test_replenish_capacity_exceeded_does_not_trip_breaker():
    factory, _ = _make_sandbox_factory()
    ledger = FakeLedger(capacity=1)
    pool = SandboxPool(sandbox_factory=factory, min_size=1, max_size=4, ledger=ledger)
    lease = pool.acquire(project_id="s1")  # 用掉唯一额度
    pool._replenish_once()  # 额度不足:静默跳过
    assert pool._replenish_failures == 0, "容量不足不是 provider 故障,不应计入熔断"
    pool.release(lease)
    pool.shutdown()


def test_live_vm_ids_reports_idle_and_leased():
    # supervisor 对账的保护集:池在册(warm + leased)VM 的 container_id
    factory_state = {"n": 0}

    def factory():
        factory_state["n"] += 1
        sb = MagicMock()
        sb.manifest = MagicMock(
            container_id=f"hagent-pool-{factory_state['n']}",
            last_used_at=time.time(),
            paused=False,
        )
        return sb

    pool = SandboxPool(sandbox_factory=factory, min_size=2, max_size=4)
    pool.prewarm()
    lease = pool.acquire(project_id="s1")  # 从 warm 池认领一只
    ids = pool.live_vm_ids()
    assert "hagent-pool-1" in ids and "hagent-pool-2" in ids, f"got {ids}"
    pool.release(lease)
    pool.shutdown()


def test_register_external_accounts_and_release_frees():
    # 收养路径:池外沙箱纳入记账;release 走正常归还
    factory, _ = _make_sandbox_factory()
    ledger = FakeLedger()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2, ledger=ledger)
    sandbox = MagicMock()
    lease = pool.register_external(sandbox, project_id="adopted-1")
    assert len(ledger.reserved) == 1
    assert pool._size == 1
    pool.release(lease)
    assert len(ledger.released) == 1
    assert pool._size == 0
    pool.shutdown()


def test_register_external_over_capacity_still_adopts():
    factory, _ = _make_sandbox_factory()
    ledger = FakeLedger(capacity=0)
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2, ledger=ledger)
    lease = pool.register_external(MagicMock(), project_id="adopted-1")
    assert lease is not None, "账本满时收养照常(VM 实存,记账失真仅告警)"
    pool.shutdown()


def test_idle_gc_pauses_then_evicts():
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(
        sandbox_factory=factory,
        min_size=0,
        max_size=2,
        idle_pause_seconds=0.1,
        idle_evict_seconds=0.2,
    )
    lease = pool.acquire(project_id="s1")
    # Force last_used backwards
    lease.sandbox.manifest = MagicMock()
    lease.sandbox.manifest.last_used_at = time.time() - 1.0
    lease.sandbox.manifest.paused = False
    lease.sandbox.pause = MagicMock()
    pool._gc_pass(now=time.time())
    lease.sandbox.pause.assert_called_once()
    pool._gc_pass(now=time.time())  # second pass evicts
    lease.sandbox.close.assert_called_once()
    pool.shutdown()


# ---------------------------------------------------------------------------
# Task B1:认领/收养绑定 session(审计归属);回 warm 池解绑
# ---------------------------------------------------------------------------


def test_acquire_binds_session_and_reuse_release_unbinds(monkeypatch):
    monkeypatch.setenv("HAGENT_SANDBOX_REUSE", "true")
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2)
    lease = pool.acquire(project_id="s1")
    lease.sandbox.bind_project.assert_called_with("s1")
    lease.sandbox.execute = MagicMock(return_value=MagicMock(exit_code=0))
    pool.release(lease)  # 回 warm 池 → 解绑
    lease.sandbox.bind_project.assert_called_with(None)
    pool.shutdown()


def test_register_external_binds_session():
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2)
    sandbox = MagicMock()
    pool.register_external(sandbox, project_id="adopted-1")
    sandbox.bind_project.assert_called_with("adopted-1")
    pool.shutdown()


def test_acquire_tolerates_sandbox_without_bind_project():
    # docker 路径零影响:没有 bind_project 方法的沙箱照常工作
    counter = {"n": 0}

    class Plain:
        def close(self):
            pass

    def factory():
        counter["n"] += 1
        return Plain()

    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2)
    lease = pool.acquire(project_id="s1")
    assert lease.sandbox is not None
    pool.release(lease)
    pool.shutdown()


# ---------------------------------------------------------------------------
# Task B2:evict — 健康巡检杀重建的强制驱逐(不回 warm 池)
# ---------------------------------------------------------------------------


def test_evict_tears_down_and_frees_quota(monkeypatch):
    monkeypatch.setenv("HAGENT_SANDBOX_REUSE", "true")  # 即便 reuse 开着也不得回池
    factory, _ = _make_sandbox_factory()
    ledger = FakeLedger()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2, ledger=ledger)
    lease = pool.acquire(project_id="s1")
    assert pool.evict("s1") is True
    lease.sandbox.close.assert_called_once()
    assert len(ledger.released) == 1
    assert pool._size == 0
    assert pool.live_vm_ids() == set()
    pool.shutdown()


def test_evict_unknown_session_returns_false():
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2)
    assert pool.evict("nope") is False
    pool.shutdown()


# ---------------------------------------------------------------------------
# Task B3:max_lifetime 绝对寿命驱逐(与 idle 无关,活跃也到期)
# ---------------------------------------------------------------------------


def test_gc_evicts_on_max_lifetime_even_if_active(monkeypatch):
    monkeypatch.setenv("HAGENT_SANDBOX_REUSE", "true")  # 寿命到期必须真拆,不得回池
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(
        sandbox_factory=factory,
        min_size=0,
        max_size=2,
        idle_pause_seconds=3600,
        idle_evict_seconds=7200,
        max_lifetime_seconds=10,
    )
    lease = pool.acquire(project_id="s1")
    now = time.time()
    lease.sandbox.manifest = MagicMock(
        created_at=now - 11, last_used_at=now, paused=False  # 刚用过,但寿命已过
    )
    pool._gc_pass(now=now)
    lease.sandbox.close.assert_called_once()
    assert pool._size == 0
    pool.shutdown()


def test_gc_no_lifetime_eviction_by_default():
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2)
    lease = pool.acquire(project_id="s1")
    now = time.time()
    lease.sandbox.manifest = MagicMock(created_at=now - 999999, last_used_at=now, paused=False)
    pool._gc_pass(now=now)
    lease.sandbox.close.assert_not_called()
    pool.release(lease)
    pool.shutdown()


def test_gc_lifetime_not_reached_keeps_sandbox():
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2, max_lifetime_seconds=100)
    lease = pool.acquire(project_id="s1")
    now = time.time()
    lease.sandbox.manifest = MagicMock(created_at=now - 50, last_used_at=now, paused=False)
    pool._gc_pass(now=now)
    lease.sandbox.close.assert_not_called()
    pool.release(lease)
    pool.shutdown()


# ---------------------------------------------------------------------------
# Task C2:paused 超阈值 → 快照持久化(persist_fn)替代驱逐;快照恢复走
# acquire_restored(占位→restore_factory→提交)
# ---------------------------------------------------------------------------


def _paused_overdue_lease(pool, project_id="s1"):
    lease = pool.acquire(project_id=project_id)
    lease.sandbox.manifest = MagicMock()
    lease.sandbox.manifest.created_at = time.time()
    lease.sandbox.manifest.last_used_at = time.time() - 10.0
    lease.sandbox.manifest.paused = True
    return lease


def test_gc_persist_replaces_evict_when_fn_returns_true():
    factory, _ = _make_sandbox_factory()
    ledger = FakeLedger()
    lifecycle_events: list[str] = []
    pool = SandboxPool(
        sandbox_factory=factory,
        min_size=0,
        max_size=2,
        idle_pause_seconds=0.1,
        idle_evict_seconds=0.2,
        ledger=ledger,
    )
    pool.set_checkpoint_fn(
        lambda project_id, sandbox: lifecycle_events.append(
            f"checkpoint:{project_id}"
        )
    )
    pool.set_persist_fn(
        lambda lease: lifecycle_events.append(f"snapshot:{lease.project_id}") or True
    )
    lease = _paused_overdue_lease(pool)
    pool._gc_pass(now=time.time())
    assert lifecycle_events == ["checkpoint:s1", "snapshot:s1"]
    assert len(ledger.released) == 1, "持久化后必须归还内存额度(D13 的痛点)"
    assert pool._size == 0
    assert pool.live_vm_ids() == set(), "lease 必须摘除"
    pool.shutdown()


def test_persist_cleanup_keeps_replacement_lease_created_after_callback():
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(
        sandbox_factory=factory,
        min_size=0,
        max_size=2,
    )
    old_lease = pool.acquire(project_id="s1")
    replacement: dict[str, SandboxLease] = {}

    def persist(_lease):
        replacement["lease"] = pool.acquire(project_id="s1")
        return True

    pool.set_persist_fn(persist)

    assert pool._try_persist(old_lease) is True
    assert pool.stats() == {
        "size": 1,
        "idle": 0,
        "leased": 1,
        "min_size": 0,
        "max_size": 2,
        "replenish_breaker_open": False,
        "replenish_failures": 0,
    }
    assert pool.evict("s1") is True
    replacement["lease"].sandbox.close.assert_called_once()
    old_lease.sandbox.close.assert_called_once()
    pool.shutdown()


def test_gc_does_not_emit_evicted_for_stale_lease_removed_mid_pass():
    factory, _ = _make_sandbox_factory()
    lifecycle = MagicMock()
    pool = SandboxPool(
        sandbox_factory=factory,
        min_size=0,
        max_size=1,
        idle_pause_seconds=0.1,
        idle_evict_seconds=0.2,
    )
    lease = _paused_overdue_lease(pool)
    pool.set_lifecycle_fn(lifecycle)

    def remove_during_gc(_project_id):
        pool.release(lease)
        return lease.leased_at - 10

    pool.set_activity_fns(
        touch_fn=None,
        last_activity_fn=remove_during_gc,
    )

    pool._gc_pass(now=lease.leased_at)

    lifecycle.assert_not_called()
    assert pool.stats()["leased"] == 0
    pool.shutdown()


def test_gc_does_not_pause_or_notify_stale_lease_removed_mid_pass():
    factory, _ = _make_sandbox_factory()
    lifecycle = MagicMock()
    pool = SandboxPool(
        sandbox_factory=factory,
        min_size=0,
        max_size=1,
        idle_pause_seconds=0.1,
        idle_evict_seconds=20,
    )
    lease = pool.acquire(project_id="s1")
    lease.sandbox.manifest = MagicMock(
        created_at=lease.leased_at,
        last_used_at=lease.leased_at - 10,
        paused=False,
    )
    pool.set_lifecycle_fn(lifecycle)

    def remove_during_gc(_project_id):
        pool.release(lease)
        return lease.leased_at - 10

    pool.set_activity_fns(
        touch_fn=None,
        last_activity_fn=remove_during_gc,
    )

    pool._gc_pass(now=lease.leased_at)

    lease.sandbox.pause.assert_not_called()
    lifecycle.assert_not_called()
    pool.shutdown()


def test_gc_persist_false_falls_back_to_evict():
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(
        sandbox_factory=factory,
        min_size=0,
        max_size=2,
        idle_pause_seconds=0.1,
        idle_evict_seconds=0.2,
    )
    pool.set_persist_fn(lambda lease: False)
    lease = _paused_overdue_lease(pool)
    pool._gc_pass(now=time.time())
    lease.sandbox.close.assert_called_once()
    assert pool._size == 0
    pool.shutdown()


def test_gc_persist_exception_falls_back_to_evict():
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(
        sandbox_factory=factory,
        min_size=0,
        max_size=2,
        idle_pause_seconds=0.1,
        idle_evict_seconds=0.2,
    )
    pool.set_persist_fn(lambda lease: (_ for _ in ()).throw(RuntimeError("snapshot fail")))
    lease = _paused_overdue_lease(pool)
    pool._gc_pass(now=time.time())
    assert lease.sandbox.close.call_count == 1, "持久化失败必须退回驱逐,不能滞留"
    pool.shutdown()


def test_acquire_restored_reserves_then_builds_lease():
    ledger = FakeLedger()
    restored = MagicMock()
    calls: list = []

    def restore_factory(snapshot_id: str, project_id: str):
        calls.append((snapshot_id, project_id))
        return restored

    pool = SandboxPool(
        sandbox_factory=lambda: MagicMock(),
        min_size=0,
        max_size=2,
        ledger=ledger,
        restore_factory=restore_factory,
    )
    lease = pool.acquire_restored(project_id="s1", snapshot_id="snap-x-1")
    assert lease.sandbox is restored
    assert calls == [("snap-x-1", "s1")]
    assert len(ledger.committed) == 1, "恢复的 VM 同样吃内存,必须过账本"
    restored.bind_project.assert_called_with("s1")
    pool.release(lease)
    assert len(ledger.released) == 1
    pool.shutdown()


def test_acquire_restored_capacity_exceeded_propagates():
    from hagent.sandbox.ledger import CapacityExceeded

    pool = SandboxPool(
        sandbox_factory=lambda: MagicMock(),
        min_size=0,
        max_size=2,
        ledger=FakeLedger(capacity=0),
        restore_factory=lambda snapshot_id, project_id: MagicMock(),
    )
    with pytest.raises(CapacityExceeded):
        pool.acquire_restored(project_id="s1", snapshot_id="snap-x-1")
    assert pool._size == 0, "占位失败不得泄漏 size"
    pool.shutdown()


def test_acquire_restored_without_factory_raises():
    pool = SandboxPool(sandbox_factory=lambda: MagicMock(), min_size=0, max_size=2)
    with pytest.raises(RuntimeError, match="restore"):
        pool.acquire_restored(project_id="s1", snapshot_id="snap-x-1")
    pool.shutdown()


def test_acquire_restored_factory_failure_rolls_back():
    ledger = FakeLedger()

    def bad_factory(snapshot_id: str, project_id: str):
        raise RuntimeError("restore boom")

    pool = SandboxPool(
        sandbox_factory=lambda: MagicMock(),
        min_size=0,
        max_size=1,
        ledger=ledger,
        restore_factory=bad_factory,
    )
    with pytest.raises(RuntimeError, match="restore boom"):
        pool.acquire_restored(project_id="s1", snapshot_id="snap-x-1")
    assert len(ledger.released) == 1
    # size 已回滚:仍可正常创建
    lease = pool.acquire(project_id="s2")
    assert lease is not None
    pool.shutdown()


# ---------------------------------------------------------------------------
# Task C1:warm idle 定期 recycle(防漂移)——超龄的池内闲置实例拆旧补新
# ---------------------------------------------------------------------------


def _factory_with_manifest(created_at: float):
    counter = {"n": 0}

    def factory():
        counter["n"] += 1
        sb = MagicMock()
        sb.id = f"sb{counter['n']}"
        sb.manifest = MagicMock(
            container_id=f"hagent-recycle-{counter['n']}",
            created_at=created_at,
            last_used_at=time.time(),
            paused=False,
        )
        return sb

    return factory, counter


def test_gc_recycles_aged_warm_idle_and_replenishes():
    now = time.time()
    factory, counter = _factory_with_manifest(created_at=now - 100)
    ledger = FakeLedger()
    pool = SandboxPool(
        sandbox_factory=factory,
        min_size=1,
        max_size=4,
        recycle_after_seconds=10,
        ledger=ledger,
    )
    pool.prewarm()
    first = pool._idle.queue[0]
    pool._gc_pass(now=now)
    first.close.assert_called_once()
    assert len(ledger.released) == 1, "recycle 必须归还额度"
    # 补货线程回填至 min:新实例顶上
    assert _wait_until(lambda: pool._idle.qsize() == 1), "recycle 后未补货回 min"
    assert pool._idle.queue[0] is not first
    pool.shutdown()


def test_gc_keeps_young_warm_idle():
    now = time.time()
    factory, counter = _factory_with_manifest(created_at=now - 5)
    pool = SandboxPool(
        sandbox_factory=factory, min_size=1, max_size=4, recycle_after_seconds=10
    )
    pool.prewarm()
    first = pool._idle.queue[0]
    pool._gc_pass(now=now)
    first.close.assert_not_called()
    assert pool._idle.qsize() == 1 and pool._idle.queue[0] is first
    pool.shutdown()


def test_double_release_decrements_size_once(monkeypatch):
    """审查缺陷 F:同一 lease 被 GC 驱逐与 delete_session 各 release 一次时,
    release 必须幂等——只有真正摘到 lease 才拆除+减 size,否则 size 双减(docker
    池无 ledger 兜底会突破 max_size)。"""
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2)
    lease = pool.acquire(project_id="s1")
    assert pool._size == 1
    pool.release(lease)
    assert pool._size == 0
    lease.sandbox.close.assert_called_once()
    pool.release(lease)  # 二次 release 同一 lease:必须 no-op
    assert pool._size == 0, "二次 release 不得再减 size"
    lease.sandbox.close.assert_called_once(), "二次 release 不得再拆一次"
    pool.shutdown()


def test_double_release_reuse_no_double_enqueue(monkeypatch):
    monkeypatch.setenv("HAGENT_SANDBOX_REUSE", "true")
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2)
    lease = pool.acquire(project_id="s1")
    lease.sandbox.execute = MagicMock(return_value=MagicMock(exit_code=0))
    pool.release(lease)
    assert pool._idle.qsize() == 1
    pool.release(lease)  # 二次 release:不得把同一 VM 再入队(否则双租串写)
    assert pool._idle.qsize() == 1, "二次 release 不得重复入队同一 VM"
    pool.shutdown()


def test_gc_recycle_keeps_survivor_when_overdue_present():
    """审查缺陷 E:回收超龄实例期间,未超龄的幸存实例必须始终留在 _idle,
    不能被抽干到本地列表跨越 teardown(否则并发 acquire 伪 503 / 保护集漏窗)。"""
    now = time.time()
    made: list = []

    def factory():
        sb = MagicMock()
        sb.id = f"sb{len(made)}"
        # 头一只超龄、其余年轻
        age = 100 if not made else 1
        sb.manifest = MagicMock(
            container_id=f"hagent-{len(made)}",
            created_at=now - age,
            last_used_at=now,
            paused=False,
        )
        made.append(sb)
        return sb

    pool = SandboxPool(
        sandbox_factory=factory, min_size=2, max_size=4, recycle_after_seconds=10
    )
    pool.prewarm()
    overdue, young = made[0], made[1]
    pool._recycle_pass(now)
    overdue.close.assert_called_once()
    young.close.assert_not_called()
    remaining = list(pool._idle.queue)
    assert young in remaining and overdue not in remaining
    pool.shutdown()


def test_stats_reports_capacity_and_counts():
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=1, max_size=3)
    pool.prewarm()
    lease = pool.acquire(project_id="s1")
    st = pool.stats()
    assert st["leased"] == 1
    assert st["max_size"] == 3 and st["min_size"] == 1
    assert st["replenish_breaker_open"] is False
    assert "idle" in st and "size" in st
    pool.release(lease)
    pool.shutdown()


def test_gc_recycle_disabled_by_default():
    now = time.time()
    factory, counter = _factory_with_manifest(created_at=now - 999999)
    pool = SandboxPool(sandbox_factory=factory, min_size=1, max_size=4)
    pool.prewarm()
    first = pool._idle.queue[0]
    pool._gc_pass(now=now)
    first.close.assert_not_called()
    pool.shutdown()


def test_gc_recycle_does_not_touch_leased():
    """recycle 只针对 warm idle;在租实例的寿命治理归 max_lifetime。"""
    now = time.time()
    factory, counter = _factory_with_manifest(created_at=now - 100)
    pool = SandboxPool(
        sandbox_factory=factory, min_size=0, max_size=4, recycle_after_seconds=10
    )
    lease = pool.acquire(project_id="s1")
    lease.sandbox.manifest.last_used_at = now  # 活跃,不触发 idle 分支
    pool._gc_pass(now=now)
    lease.sandbox.close.assert_not_called()
    pool.release(lease)
    pool.shutdown()


# ---------------------------------------------------------------------------
# Task B5:pool.drain — warm 拆除、leased pause 保留(重启收养)
# ---------------------------------------------------------------------------


def test_drain_pauses_leased_without_teardown_and_clears_warm():
    factory, _ = _make_sandbox_factory()
    ledger = FakeLedger()
    pool = SandboxPool(sandbox_factory=factory, min_size=2, max_size=4, ledger=ledger)
    pool.prewarm()
    lease = pool.acquire(project_id="s1")  # 1 leased + 1 warm idle
    pool.drain()
    # leased:pause 且不 close(VM 存活待重启收养)
    lease.sandbox.pause.assert_called_once()
    lease.sandbox.close.assert_not_called()
    # warm idle:拆除并归还额度
    assert pool._idle.qsize() == 0
    assert len(ledger.released) == 1
    pool.shutdown()


def test_drain_pause_failure_does_not_block_others():
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=4)
    lease1 = pool.acquire(project_id="s1")
    lease2 = pool.acquire(project_id="s2")
    lease1.sandbox.pause.side_effect = RuntimeError("freeze failed")
    pool.drain()
    lease2.sandbox.pause.assert_called_once()
