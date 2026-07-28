"""指标采样(spec §4.5 / D11):/proc/<pid>/stat|statm → 事件表 metrics 行。

无 cgroup 可读(F9),``/proc`` 采样够单机运营:CPU 取 utime+stime 累计秒,
RSS 取 statm resident 页数。写入按 VM 降采样(``min_write_interval_seconds``,
默认 60s 一行),采样频率(supervisor 循环 5–10s)与落库频率解耦。
best-effort:目标消失 / /proc 读失败一律跳过,不产生半行数据。
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Callable

from hagent.sandbox.smolvm.audit import SandboxAuditor

logger = logging.getLogger(__name__)

DEFAULT_MIN_WRITE_INTERVAL_SECONDS = 60.0


def parse_proc_stat(text: str, *, clock_ticks: int) -> float:
    """utime+stime(clock ticks)→ CPU 累计秒。

    comm 字段(第 2 列)可含空格与括号,必须从**最后一个** ``)`` 之后分列;
    其后第 12/13 列(0 起)才是 utime/stime。
    """
    rest = text[text.rindex(")") + 2 :].split()
    utime, stime = int(rest[11]), int(rest[12])
    return (utime + stime) / clock_ticks


def parse_proc_statm(text: str, *, page_size: int) -> int:
    """statm 第 2 列(resident 页数)→ RSS 字节。"""
    return int(text.split()[1]) * page_size


class SmolVMMetricsSampler:
    """supervisor metrics 循环的采样器;依赖全部可注入(测试 mock /proc)。"""

    def __init__(
        self,
        *,
        targets_fn: Callable[[], list[tuple[str, object]]],
        auditor: SandboxAuditor,
        proc_root: Path | str = "/proc",
        clock_ticks: int | None = None,
        page_size: int | None = None,
        min_write_interval_seconds: float = DEFAULT_MIN_WRITE_INTERVAL_SECONDS,
    ) -> None:
        self._targets_fn = targets_fn
        self._auditor = auditor
        self._proc_root = Path(proc_root)
        self._clock_ticks = clock_ticks or os.sysconf("SC_CLK_TCK")
        self._page_size = page_size or os.sysconf("SC_PAGE_SIZE")
        self._min_write_interval = min_write_interval_seconds
        self._last_written: dict[str, float] = {}  # vm_id → monotonic

    def sample_once(self) -> None:
        try:
            targets = self._targets_fn()
        except Exception as exc:  # noqa: BLE001
            logger.warning("metrics targets() 失败,本轮跳过: %s", exc)
            return
        now = time.monotonic()
        seen: set[str] = set()
        for project_id, sandbox in targets:
            pid = getattr(sandbox, "pid", None)
            vm_id = getattr(getattr(sandbox, "manifest", None), "container_id", None)
            if pid is None or vm_id is None:
                continue
            seen.add(vm_id)
            last = self._last_written.get(vm_id)
            if last is not None and (now - last) < self._min_write_interval:
                continue  # 降采样:写入窗口未到
            try:
                stat_text = (self._proc_root / str(pid) / "stat").read_text()
                statm_text = (self._proc_root / str(pid) / "statm").read_text()
                cpu_seconds = parse_proc_stat(stat_text, clock_ticks=self._clock_ticks)
                rss_bytes = parse_proc_statm(statm_text, page_size=self._page_size)
            except (OSError, ValueError, IndexError):
                continue  # pid 死/读竞态:健康巡检负责处置,这里只跳过
            self._auditor.record_event(
                event="metrics",
                project_id=project_id,
                vm_id=vm_id,
                detail={"pid": pid, "cpu_seconds": cpu_seconds, "rss_bytes": rss_bytes},
            )
            self._last_written[vm_id] = now
        # 目标消失即剪状态,防 vm_id 复用时沿用旧窗口
        for vm_id in list(self._last_written):
            if vm_id not in seen:
                self._last_written.pop(vm_id, None)
