"""Task B4 — 指标采样:/proc/<pid>/stat|statm 解析 → 事件表 metrics 行(降采样)。"""

from __future__ import annotations

from types import SimpleNamespace

from hagent.sandbox.smolvm.audit import SandboxAuditor, SandboxEventStore
from hagent.sandbox.smolvm.metrics import (
    SmolVMMetricsSampler,
    parse_proc_stat,
    parse_proc_statm,
)

# comm 字段带空格与括号是 /proc 解析的经典雷区:必须从最后一个 ')' 之后分列
STAT_LINE = (
    "12345 (fire cracker) S 1 12345 12345 0 -1 4194560 "
    "1234 0 0 0 250 150 0 0 20 0 2 0 8000000 123456789 5000 "
    "18446744073709551615 1 1 0 0 0 0 0 0 0 0 0 0 17 3 0 0 0 0 0"
)
STATM_LINE = "123456 51200 300 50 0 1000 0"


def test_parse_proc_stat_cpu_seconds():
    # utime=250 + stime=150 ticks @ 100Hz → 4.0s
    assert parse_proc_stat(STAT_LINE, clock_ticks=100) == 4.0


def test_parse_proc_statm_rss_bytes():
    # resident=51200 pages @ 4096B → 200 MiB
    assert parse_proc_statm(STATM_LINE, page_size=4096) == 51200 * 4096


class FakeSandboxWithPid:
    def __init__(self, pid, vm_id="hagent-s1-abc"):
        self.pid = pid
        self.manifest = SimpleNamespace(container_id=vm_id)


def _write_proc(proc_root, pid):
    d = proc_root / str(pid)
    d.mkdir(parents=True)
    (d / "stat").write_text(STAT_LINE)
    (d / "statm").write_text(STATM_LINE)


def _sampler(tmp_path, targets, **kwargs):
    store = SandboxEventStore(tmp_path / "events.db")
    sampler = SmolVMMetricsSampler(
        targets_fn=lambda: targets,
        auditor=SandboxAuditor(event_store=store),
        proc_root=tmp_path / "proc",
        clock_ticks=100,
        page_size=4096,
        min_write_interval_seconds=0.0,
        **kwargs,
    )
    return sampler, store


def test_sample_once_records_metrics_event(tmp_path):
    _write_proc(tmp_path / "proc", 12345)
    sandbox = FakeSandboxWithPid(12345)
    sampler, store = _sampler(tmp_path, [("project-1", sandbox)])
    sampler.sample_once()
    (row,) = store.list(event="metrics")
    assert row.project_id == "project-1"
    assert row.vm_id == "hagent-s1-abc"
    assert row.detail == {"pid": 12345, "cpu_seconds": 4.0, "rss_bytes": 51200 * 4096}


def test_sample_skips_dead_pid_without_raising(tmp_path):
    (tmp_path / "proc").mkdir()
    sandbox = FakeSandboxWithPid(99999)  # /proc/99999 不存在
    sampler, store = _sampler(tmp_path, [("s1", sandbox)])
    sampler.sample_once()
    assert store.list(event="metrics") == []


def test_sample_skips_sandbox_without_pid(tmp_path):
    class NoPid:
        manifest = SimpleNamespace(container_id="x")

    (tmp_path / "proc").mkdir()
    sampler, store = _sampler(tmp_path, [("s1", NoPid()), ("s2", FakeSandboxWithPid(None))])
    sampler.sample_once()
    assert store.list(event="metrics") == []


def test_downsampling_respects_min_write_interval(tmp_path):
    _write_proc(tmp_path / "proc", 12345)
    sandbox = FakeSandboxWithPid(12345)
    store = SandboxEventStore(tmp_path / "events.db")
    sampler = SmolVMMetricsSampler(
        targets_fn=lambda: [("s1", sandbox)],
        auditor=SandboxAuditor(event_store=store),
        proc_root=tmp_path / "proc",
        clock_ticks=100,
        page_size=4096,
        min_write_interval_seconds=3600.0,
    )
    sampler.sample_once()
    sampler.sample_once()
    sampler.sample_once()
    assert len(store.list(event="metrics")) == 1, "写入窗口内重复采样必须降采样"


def test_sample_targets_failure_does_not_raise(tmp_path):
    store = SandboxEventStore(tmp_path / "events.db")

    def exploding_targets():
        raise RuntimeError("manager gone")

    sampler = SmolVMMetricsSampler(
        targets_fn=exploding_targets,
        auditor=SandboxAuditor(event_store=store),
        proc_root=tmp_path / "proc",
    )
    sampler.sample_once()
    assert store.list() == []


def test_sandbox_pid_property():
    from hagent.sandbox.manifest import SandboxManifest
    from hagent.sandbox.smolvm.sandbox import HagentSmolVMSandbox
    from tests.sandbox.test_smolvm_sandbox_unit import FakeLifecycle, FakeVM

    vm = FakeVM()
    vm.info = SimpleNamespace(pid=4242)
    lifecycle = FakeLifecycle(vm)
    manifest = SandboxManifest(
        sandbox_id=lifecycle.vm_id,
        kind="smolvm",
        image_tag="t",
        runtime="firecracker",
        container_id=lifecycle.vm_id,
    )
    sandbox = HagentSmolVMSandbox(lifecycle=lifecycle, manifest=manifest)
    assert sandbox.pid == 4242
    sandbox.close()
    assert sandbox.pid is None


def test_supervisor_metrics_loop_runs_and_stops():
    import threading

    from hagent.sandbox.supervisor import SandboxSupervisor
    from tests.sandbox.test_supervisor import FakeReconciler

    sampled = threading.Event()

    class FakeSampler:
        def sample_once(self):
            sampled.set()

    sup = SandboxSupervisor(
        reconciler=FakeReconciler(),
        metrics_sampler=FakeSampler(),
        metrics_interval_seconds=0.02,
    )
    thread = sup.start_metrics_loop()
    assert thread is not None
    assert sampled.wait(timeout=2), "metrics 循环未跑起来"
    sup.shutdown()
    assert not thread.is_alive()


def test_supervisor_metrics_loop_noop_without_sampler():
    from hagent.sandbox.supervisor import SandboxSupervisor
    from tests.sandbox.test_supervisor import FakeReconciler

    sup = SandboxSupervisor(reconciler=FakeReconciler())
    assert sup.start_metrics_loop() is None
    sup.shutdown()
