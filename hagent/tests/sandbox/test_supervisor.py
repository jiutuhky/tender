"""Task A9 — SandboxSupervisor:startup_reclaim / reaper 失败计数告警 / shutdown 幂等。"""

from __future__ import annotations

import logging
import threading

from hagent.sandbox.supervisor import SandboxSupervisor
from hagent.sandbox.smolvm.reconciler import ReconcileAction


class FakeReconciler:
    def __init__(self):
        self.actions: list[ReconcileAction] = []
        self.applied: list[ReconcileAction] = []
        self.apply_error: Exception | None = None
        self.plan_calls = 0
        self.reap_calls = 0
        self.plan_event = threading.Event()

    def plan(self):
        self.plan_calls += 1
        self.plan_event.set()
        return list(self.actions)

    def apply(self, action):
        if self.apply_error is not None:
            raise self.apply_error
        self.applied.append(action)

    def reap_errors(self):
        self.reap_calls += 1


def test_startup_reclaim_plans_applies_and_reaps():
    rec = FakeReconciler()
    rec.actions = [ReconcileAction(kind="reclaim", vm_id="hagent-a-b")]
    sup = SandboxSupervisor(reconciler=rec)
    sup.startup_reclaim()
    assert rec.plan_calls == 1
    assert len(rec.applied) == 1
    assert rec.reap_calls == 1
    sup.shutdown()


def test_apply_failure_does_not_break_round_and_counts(caplog):
    rec = FakeReconciler()
    rec.actions = [ReconcileAction(kind="reclaim", vm_id="hagent-a-b")]
    rec.apply_error = RuntimeError("nft busy")
    sup = SandboxSupervisor(reconciler=rec)
    with caplog.at_level(logging.WARNING):
        sup.startup_reclaim()
        sup.startup_reclaim()
    assert rec.reap_calls == 2, "单动作失败不得阻断本轮 reap"
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "清理失败应有 WARNING"


def test_three_consecutive_failures_escalate_to_error_log(caplog):
    rec = FakeReconciler()
    rec.actions = [ReconcileAction(kind="reclaim", vm_id="hagent-a-b")]
    rec.apply_error = RuntimeError("still busy")
    sup = SandboxSupervisor(reconciler=rec)
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            sup.startup_reclaim()
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert errors, "同一对象连续 3 次清理失败必须升 ERROR(不静默重试)"
    sup.shutdown()


def test_success_resets_failure_counter(caplog):
    rec = FakeReconciler()
    rec.actions = [ReconcileAction(kind="reclaim", vm_id="hagent-a-b")]
    rec.apply_error = RuntimeError("busy")
    sup = SandboxSupervisor(reconciler=rec)
    sup.startup_reclaim()
    sup.startup_reclaim()
    rec.apply_error = None
    sup.startup_reclaim()  # 成功,计数清零
    rec.apply_error = RuntimeError("busy again")
    with caplog.at_level(logging.ERROR):
        sup.startup_reclaim()
    assert not [r for r in caplog.records if r.levelno == logging.ERROR]
    sup.shutdown()


def test_reaper_loop_runs_periodically_and_shutdown_stops():
    rec = FakeReconciler()
    sup = SandboxSupervisor(reconciler=rec, interval_seconds=0.02)
    sup.start_reaper()
    assert rec.plan_event.wait(timeout=2), "reaper 循环未跑起来"
    sup.shutdown()
    calls_after_shutdown = rec.plan_calls
    import time

    time.sleep(0.08)
    assert rec.plan_calls == calls_after_shutdown, "shutdown 后 reaper 必须停"


def test_shutdown_idempotent():
    rec = FakeReconciler()
    sup = SandboxSupervisor(reconciler=rec, interval_seconds=0.02)
    sup.start_reaper()
    sup.shutdown()
    sup.shutdown()  # 第二次不得抛


# ---------------------------------------------------------------------------
# Task B2:health_loop — 连续 3 败触发杀重建,成功清零,目标消失剪计数
# ---------------------------------------------------------------------------


class FakeHealthChecker:
    def __init__(self):
        self.sandboxes: dict[str, object] = {}
        self.healthy: dict[str, bool] = {}
        self.check_error: Exception | None = None
        self.unhealthy_calls: list[str] = []
        self.check_event = threading.Event()

    def targets(self):
        return list(self.sandboxes.items())

    def check(self, sandbox) -> bool:
        self.check_event.set()
        if self.check_error is not None:
            raise self.check_error
        for sid, sb in self.sandboxes.items():
            if sb is sandbox:
                return self.healthy.get(sid, True)
        return True

    def on_unhealthy(self, session_id, sandbox) -> None:
        self.unhealthy_calls.append(session_id)


def _health_supervisor(checker) -> SandboxSupervisor:
    return SandboxSupervisor(reconciler=FakeReconciler(), health_checker=checker)


def test_health_three_consecutive_failures_trigger_unhealthy():
    checker = FakeHealthChecker()
    checker.sandboxes["s1"] = object()
    checker.healthy["s1"] = False
    sup = _health_supervisor(checker)
    sup._health_once()
    sup._health_once()
    assert checker.unhealthy_calls == [], "未达 3 败不得触发杀重建"
    sup._health_once()
    assert checker.unhealthy_calls == ["s1"]
    # 触发后计数清零:再需 3 败才第二次触发
    sup._health_once()
    sup._health_once()
    assert checker.unhealthy_calls == ["s1"]
    sup._health_once()
    assert checker.unhealthy_calls == ["s1", "s1"]


def test_health_success_resets_failure_counter():
    checker = FakeHealthChecker()
    checker.sandboxes["s1"] = object()
    checker.healthy["s1"] = False
    sup = _health_supervisor(checker)
    sup._health_once()
    sup._health_once()
    checker.healthy["s1"] = True
    sup._health_once()  # 成功清零
    checker.healthy["s1"] = False
    sup._health_once()
    sup._health_once()
    assert checker.unhealthy_calls == []
    sup._health_once()
    assert checker.unhealthy_calls == ["s1"]


def test_health_check_exception_counts_as_failure():
    checker = FakeHealthChecker()
    checker.sandboxes["s1"] = object()
    checker.check_error = RuntimeError("probe blew up")
    sup = _health_supervisor(checker)
    for _ in range(3):
        sup._health_once()
    assert checker.unhealthy_calls == ["s1"]


def test_health_counter_pruned_when_target_disappears():
    checker = FakeHealthChecker()
    sandbox = object()
    checker.sandboxes["s1"] = sandbox
    checker.healthy["s1"] = False
    sup = _health_supervisor(checker)
    sup._health_once()
    sup._health_once()
    del checker.sandboxes["s1"]
    sup._health_once()  # 目标消失 → 剪计数
    checker.sandboxes["s1"] = sandbox  # 重建后回来
    sup._health_once()
    sup._health_once()
    assert checker.unhealthy_calls == [], "计数未剪:新 VM 背了旧账"


def test_on_unhealthy_failure_does_not_break_round(caplog):
    checker = FakeHealthChecker()
    checker.sandboxes["s1"] = object()
    checker.sandboxes["s2"] = object()
    checker.healthy["s1"] = False
    checker.healthy["s2"] = False
    original = checker.on_unhealthy

    def explode(session_id, sandbox):
        original(session_id, sandbox)
        if session_id == "s1":
            raise RuntimeError("teardown failed")

    checker.on_unhealthy = explode
    sup = _health_supervisor(checker)
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            sup._health_once()
    assert "s2" in checker.unhealthy_calls, "s1 处置失败不得阻断 s2"


def test_health_loop_runs_and_shutdown_stops():
    checker = FakeHealthChecker()
    checker.sandboxes["s1"] = object()
    sup = SandboxSupervisor(
        reconciler=FakeReconciler(), health_checker=checker, health_interval_seconds=0.02
    )
    thread = sup.start_health_loop()
    assert thread is not None
    assert checker.check_event.wait(timeout=2), "health 循环未跑起来"
    sup.shutdown()
    assert not thread.is_alive(), "shutdown 后 health 线程必须停"


def test_start_health_loop_without_checker_is_noop():
    sup = SandboxSupervisor(reconciler=FakeReconciler())
    assert sup.start_health_loop() is None
    sup.shutdown()
