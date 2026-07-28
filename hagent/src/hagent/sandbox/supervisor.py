"""SandboxSupervisor — 通用治理骨架:启动对账 + 周期 reaper(spec §4.1)。

provider 无关:持一个 Reconciler 协议对象,plan → apply 逐动作执行,
单动作失败不阻断本轮;同一对象连续失败达阈值升 ERROR 日志(不静默重试,
containerd #3971 教训:只靠启动清扫不够,reaper 周期兜底)。
"""

from __future__ import annotations

import logging
import threading
from contextlib import suppress
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

DEFAULT_REAPER_INTERVAL_SECONDS = 60.0
FAILURE_ESCALATE_THRESHOLD = 3
DEFAULT_HEALTH_INTERVAL_SECONDS = 15.0
HEALTH_FAIL_THRESHOLD = 3
DEFAULT_METRICS_INTERVAL_SECONDS = 10.0


@runtime_checkable
class Reconciler(Protocol):
    """对账实现协议(smolvm 侧实现见 sandbox/smolvm/reconciler.py)。"""

    def plan(self) -> list:  # list[ReconcileAction]
        ...

    def apply(self, action) -> None: ...

    def reap_errors(self) -> None: ...


@runtime_checkable
class HealthChecker(Protocol):
    """健康巡检协议(smolvm 侧实现见 sandbox/smolvm/health.py)。

    杀重建哲学(spec D10):病 VM 不修复,``on_unhealthy`` 负责
    清残留 → session 标 orphaned → 记事件;重建延迟到首条新消息。
    """

    def targets(self) -> list[tuple[str, object]]:  # [(session_id, sandbox)]
        ...

    def check(self, sandbox) -> bool: ...

    def on_unhealthy(self, session_id: str, sandbox) -> None: ...


@runtime_checkable
class MetricsSampler(Protocol):
    """指标采样协议(smolvm 侧实现见 sandbox/smolvm/metrics.py)。"""

    def sample_once(self) -> None: ...


class SandboxSupervisor:
    def __init__(
        self,
        *,
        reconciler: Reconciler,
        interval_seconds: float = DEFAULT_REAPER_INTERVAL_SECONDS,
        health_checker: HealthChecker | None = None,
        health_interval_seconds: float = DEFAULT_HEALTH_INTERVAL_SECONDS,
        metrics_sampler: MetricsSampler | None = None,
        metrics_interval_seconds: float = DEFAULT_METRICS_INTERVAL_SECONDS,
    ) -> None:
        self._reconciler = reconciler
        self._interval = interval_seconds
        self._failures: dict[str, int] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._health_checker = health_checker
        self._health_interval = health_interval_seconds
        self._health_failures: dict[str, int] = {}
        self._health_thread: threading.Thread | None = None
        self._metrics_sampler = metrics_sampler
        self._metrics_interval = metrics_interval_seconds
        self._metrics_thread: threading.Thread | None = None

    # —— 单轮对账 ——————————————————————————————————————————————

    def _run_once(self) -> None:
        try:
            actions = self._reconciler.plan()
        except Exception:  # noqa: BLE001
            logger.exception("对账 plan() 失败,本轮跳过")
            return
        for action in actions:
            key = f"{getattr(action, 'kind', '?')}:{getattr(action, 'vm_id', None) or getattr(action, 'session_id', None)}"
            try:
                self._reconciler.apply(action)
                self._failures.pop(key, None)
            except Exception as exc:  # noqa: BLE001
                count = self._failures.get(key, 0) + 1
                self._failures[key] = count
                if count >= FAILURE_ESCALATE_THRESHOLD:
                    logger.error("清理动作连续 %d 次失败: %s — %s", count, key, exc)
                else:
                    logger.warning("清理动作失败(%d/%d): %s — %s", count, FAILURE_ESCALATE_THRESHOLD, key, exc)
        with suppress(Exception):
            self._reconciler.reap_errors()

    def startup_reclaim(self) -> None:
        """启动期同步跑一轮对账矩阵(收养/清场/标 orphaned)。"""
        self._run_once()

    # —— 周期 reaper ————————————————————————————————————————————

    def start_reaper(self) -> threading.Thread:
        def loop() -> None:
            while not self._stop.wait(self._interval):
                try:
                    self._run_once()
                except Exception:  # noqa: BLE001
                    logger.exception("reaper 轮次异常")

        thread = threading.Thread(target=loop, daemon=True, name="hagent-sandbox-reaper")
        self._thread = thread
        thread.start()
        return thread

    # —— 健康巡检(Task B2)————————————————————————————————————————

    def _health_once(self) -> None:
        checker = self._health_checker
        if checker is None:
            return
        try:
            targets = checker.targets()
        except Exception:  # noqa: BLE001
            logger.exception("健康巡检 targets() 失败,本轮跳过")
            return
        seen: set[str] = set()
        for session_id, sandbox in targets:
            seen.add(session_id)
            try:
                healthy = checker.check(sandbox)
            except Exception as exc:  # noqa: BLE001
                logger.warning("session %s 探活异常(计失败): %s", session_id, exc)
                healthy = False
            if healthy:
                self._health_failures.pop(session_id, None)
                continue
            count = self._health_failures.get(session_id, 0) + 1
            self._health_failures[session_id] = count
            logger.warning("session %s 探活失败(%d/%d)", session_id, count, HEALTH_FAIL_THRESHOLD)
            if count < HEALTH_FAIL_THRESHOLD:
                continue
            # 达阈值即处置;计数清零——处置失败下一轮重新累计,不背旧账
            self._health_failures.pop(session_id, None)
            try:
                checker.on_unhealthy(session_id, sandbox)
            except Exception as exc:  # noqa: BLE001
                logger.warning("session %s 杀重建处置失败(下一轮重试): %s", session_id, exc)
        # 目标消失(session 关闭 / VM 已重建)剪计数,防新 VM 背旧账
        for session_id in list(self._health_failures):
            if session_id not in seen:
                self._health_failures.pop(session_id, None)

    def start_health_loop(self) -> threading.Thread | None:
        if self._health_checker is None:
            return None

        def loop() -> None:
            while not self._stop.wait(self._health_interval):
                try:
                    self._health_once()
                except Exception:  # noqa: BLE001
                    logger.exception("health 轮次异常")

        thread = threading.Thread(target=loop, daemon=True, name="hagent-sandbox-health")
        self._health_thread = thread
        thread.start()
        return thread

    # —— 指标采样(Task B4)————————————————————————————————————————

    def start_metrics_loop(self) -> threading.Thread | None:
        sampler = self._metrics_sampler
        if sampler is None:
            return None

        def loop() -> None:
            while not self._stop.wait(self._metrics_interval):
                try:
                    sampler.sample_once()
                except Exception:  # noqa: BLE001
                    logger.exception("metrics 轮次异常")

        thread = threading.Thread(target=loop, daemon=True, name="hagent-sandbox-metrics")
        self._metrics_thread = thread
        thread.start()
        return thread

    def loop_status(self) -> dict:
        """三循环存活快照(ops 监控用):线程 is_alive。"""

        def alive(thread: threading.Thread | None) -> bool:
            return bool(thread is not None and thread.is_alive())

        return {
            "reaper": alive(self._thread),
            "health": alive(self._health_thread),
            "metrics": alive(self._metrics_thread),
        }

    def shutdown(self) -> None:
        """停 reaper / health / metrics 线程;幂等。"""
        self._stop.set()
        for thread in (self._thread, self._health_thread, self._metrics_thread):
            if thread is not None and thread.is_alive():
                thread.join(timeout=5)
        self._thread = None
        self._health_thread = None
        self._metrics_thread = None
