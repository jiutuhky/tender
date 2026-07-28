"""Task A4 — SmolVMLifecycle:启动重试/清理、幂等 stop、adopt 校验、异常映射。全 mock SDK。"""

from __future__ import annotations

import re

import pytest
from smolvm import (
    FirecrackerAPIError,
    HostError,
    ImageError,
    NetworkError,
    OperationTimeoutError,
    SmolVMError,
    VMAlreadyExistsError,
    VMNotFoundError,
)
from smolvm.types import CommandResult, VMState

from hagent.sandbox.smolvm.lifecycle import (
    MAX_START_RETRIES,
    SandboxAdoptError,
    SandboxRestoreError,
    SandboxStartError,
    SmolVMLifecycle,
    SmolVMSandboxError,
    delete_snapshot_quiet,
    describe_sdk_error,
    generate_vm_id,
)

_OK = CommandResult(exit_code=0, stdout="Python 3.12.0\n", stderr="")
_FAIL = CommandResult(exit_code=1, stdout="", stderr="boom")


class FakeVM:
    """可脚本化的 SmolVM 替身;fail_plan 控制各阶段抛错。"""

    def __init__(self, vm_id: str, fail_plan: dict | None = None):
        self._vm_id = vm_id
        self.fail_plan = fail_plan or {}
        self.calls: list[str] = []
        self._status = self.fail_plan.get("status", VMState.RUNNING)

    @property
    def vm_id(self) -> str:
        return self._vm_id

    def _maybe_fail(self, stage: str) -> None:
        exc = self.fail_plan.get(stage)
        if exc is not None:
            raise exc

    def start(self, boot_timeout: float = 30.0):
        self.calls.append("start")
        self._maybe_fail("start")
        return self

    def wait_for_ready(self, timeout: float = 60.0):
        self.calls.append("wait_for_ready")
        self._maybe_fail("wait_for_ready")
        return self

    def run(self, command: str, timeout: int = 30, shell: str = "login") -> CommandResult:
        self.calls.append(f"run:{command}")
        self._maybe_fail("run")
        return self.fail_plan.get("run_result", _OK)

    def refresh(self):
        self.calls.append("refresh")
        self._maybe_fail("refresh")
        return self

    @property
    def status(self) -> VMState:
        # 对齐 facade:status 是缓存 property,adopt 前须 refresh()
        return self._status

    def pause(self):
        self.calls.append("pause")
        self._maybe_fail("pause")
        self._status = VMState.PAUSED
        return self

    def resume(self):
        self.calls.append("resume")
        self._maybe_fail("resume")
        self._status = VMState.RUNNING  # 对齐 facade:resume 后 info 刷成 RUNNING
        return self

    def stop(self, timeout: float = 3.0):
        self.calls.append("stop")
        self._maybe_fail("stop")
        return self

    def delete(self) -> None:
        self.calls.append("delete")
        self._maybe_fail("delete")

    def close(self) -> None:
        self.calls.append("close")
        self._maybe_fail("close")

    def snapshot(self, snapshot_id=None, *, snapshot_type="full", resume_source=False):
        self.calls.append(f"snapshot:{snapshot_type}")
        self._maybe_fail("snapshot")

        class Info:
            pass

        info = Info()
        info.snapshot_id = self.fail_plan.get("snapshot_id", f"snap-{self._vm_id}-1")
        return info


class FakeSmolVMClass:
    """SmolVM 类替身:from_image/from_id 工厂,按序派发 FakeVM。"""

    def __init__(self):
        self.from_image_calls: list[dict] = []
        self.from_id_calls: list[str] = []
        self.vms: list[FakeVM] = []
        # 每次 from_image 依序弹出一个 fail_plan;耗尽后成功
        self.fail_plans: list[dict] = []
        self.from_id_error: Exception | None = None
        self.adopt_vm: FakeVM | None = None
        self.from_snapshot_calls: list[dict] = []
        self.from_snapshot_error: Exception | None = None
        self.restore_vm: FakeVM | None = None

    def from_image(self, image, **kwargs) -> FakeVM:
        self.from_image_calls.append(kwargs)
        plan = self.fail_plans.pop(0) if self.fail_plans else {}
        if isinstance(plan.get("from_image"), Exception):
            raise plan["from_image"]
        vm = FakeVM(kwargs["vm_id"], plan)
        self.vms.append(vm)
        return vm

    def from_id(self, vm_id: str, **kwargs) -> FakeVM:
        self.from_id_calls.append(vm_id)
        if self.from_id_error is not None:
            raise self.from_id_error
        vm = self.adopt_vm or FakeVM(vm_id)
        self.vms.append(vm)
        return vm

    def from_snapshot(self, snapshot_id: str, **kwargs) -> FakeVM:
        self.from_snapshot_calls.append({"snapshot_id": snapshot_id, **kwargs})
        if self.from_snapshot_error is not None:
            raise self.from_snapshot_error
        vm = self.restore_vm or FakeVM("hagent-abcd1234-x1y2z3")
        self.vms.append(vm)
        return vm


_IMAGE = object()


@pytest.fixture
def sdk():
    return FakeSmolVMClass()


def make_lifecycle(sdk, **kwargs) -> SmolVMLifecycle:
    kwargs.setdefault("project_id", "abcd1234efgh")
    return SmolVMLifecycle(smolvm_cls=sdk, ensure_image=lambda: _IMAGE, **kwargs)


class TestVMId:
    def test_format(self):
        vm_id = generate_vm_id("abcd1234efgh5678")
        assert re.fullmatch(r"hagent-abcd1234-[a-z0-9]{6}", vm_id)

    def test_sanitizes_project_id(self):
        vm_id = generate_vm_id("AB_cd-12!34")
        assert re.fullmatch(r"hagent-abcd1234-[a-z0-9]{6}", vm_id)

    def test_unique_suffix(self):
        assert generate_vm_id("s1") != generate_vm_id("s1")

    def test_no_project_id_still_valid(self):
        assert re.fullmatch(r"hagent-[a-z0-9]{1,8}-[a-z0-9]{6}", generate_vm_id(None))


class TestStart:
    def test_success_returns_manifest(self, sdk):
        lc = make_lifecycle(sdk)
        manifest = lc.start()
        assert manifest.kind == "smolvm"
        assert manifest.runtime == "firecracker"
        assert manifest.workspace_dir == "/workspace"
        assert manifest.container_id == lc.vm_id
        assert manifest.container_id.startswith("hagent-abcd1234-")
        # 启动序:start → wait_for_ready → 探针
        vm = sdk.vms[0]
        assert vm.calls[0] == "start"
        assert vm.calls[1] == "wait_for_ready"
        assert vm.calls[2].startswith("run:")

    def test_quota_from_env(self, sdk, monkeypatch):
        monkeypatch.setenv("HAGENT_SMOLVM_VCPUS", "4")
        monkeypatch.setenv("HAGENT_SMOLVM_MEMORY_MIB", "1024")
        make_lifecycle(sdk).start()
        kwargs = sdk.from_image_calls[0]
        assert kwargs["vcpus"] == 4
        assert kwargs["memory_mb"] == 1024

    def test_quota_defaults(self, sdk):
        make_lifecycle(sdk).start()
        kwargs = sdk.from_image_calls[0]
        assert kwargs["vcpus"] == 2
        assert kwargs["memory_mb"] == 2048

    def test_retry_after_boot_failure_cleans_up(self, sdk):
        sdk.fail_plans = [{"start": NetworkError("tap busy")}]
        lc = make_lifecycle(sdk)
        manifest = lc.start()
        assert manifest is not None
        assert len(sdk.from_image_calls) == 2
        # 失败尝试必须全清理(delete),不留半启动 VM
        assert "delete" in sdk.vms[0].calls

    def test_retry_uses_fresh_vm_id(self, sdk):
        # delete 不彻底时旧 vm_id 会撞 VMAlreadyExistsError,每次尝试换后缀
        sdk.fail_plans = [{"start": NetworkError("tap busy")}]
        make_lifecycle(sdk).start()
        ids = [c["vm_id"] for c in sdk.from_image_calls]
        assert len(set(ids)) == 2

    def test_probe_nonzero_exit_counts_as_failure(self, sdk):
        sdk.fail_plans = [{"run_result": _FAIL}]
        make_lifecycle(sdk).start()
        assert len(sdk.from_image_calls) == 2
        assert "delete" in sdk.vms[0].calls

    def test_retries_exhausted_raises_start_error(self, sdk):
        sdk.fail_plans = [
            {"start": NetworkError("1")},
            {"wait_for_ready": OperationTimeoutError("wait_for_ready", 2.0)},
            {"run": SmolVMError("3")},
        ]
        with pytest.raises(SandboxStartError):
            make_lifecycle(sdk).start()
        assert len(sdk.from_image_calls) == 1 + MAX_START_RETRIES
        for vm in sdk.vms:
            assert "delete" in vm.calls, "每次失败尝试都必须清理"

    def test_cleanup_failure_does_not_mask_retry(self, sdk):
        sdk.fail_plans = [{"start": NetworkError("boot"), "delete": SmolVMError("del")}]
        manifest = make_lifecycle(sdk).start()
        assert manifest is not None
        assert len(sdk.from_image_calls) == 2


class TestStop:
    def test_stop_calls_full_teardown(self, sdk):
        lc = make_lifecycle(sdk)
        lc.start()
        lc.stop()
        vm = sdk.vms[0]
        assert vm.calls[-3:] == ["stop", "delete", "close"]

    def test_stop_idempotent(self, sdk):
        lc = make_lifecycle(sdk)
        lc.start()
        lc.stop()
        n_calls = len(sdk.vms[0].calls)
        lc.stop()
        assert len(sdk.vms[0].calls) == n_calls, "第二次 stop 应为 no-op"

    def test_stop_before_start_is_noop(self, sdk):
        make_lifecycle(sdk).stop()

    def test_stop_survives_sdk_errors(self, sdk):
        lc = make_lifecycle(sdk)
        lc.start()
        vm = sdk.vms[0]
        vm.fail_plan["stop"] = SmolVMError("stop fail")
        lc.stop()
        assert "delete" in vm.calls, "stop 抛错不应阻断 delete"
        assert "close" in vm.calls


class TestPauseResume:
    def test_delegates(self, sdk):
        lc = make_lifecycle(sdk)
        lc.start()
        lc.pause()
        lc.resume()
        vm = sdk.vms[0]
        assert "pause" in vm.calls
        assert "resume" in vm.calls

    def test_noop_without_vm(self, sdk):
        lc = make_lifecycle(sdk)
        lc.pause()
        lc.resume()


class TestAdopt:
    def test_adopt_running_vm(self, sdk):
        lc = make_lifecycle(sdk)
        manifest = lc.adopt("hagent-abcd1234-x1y2z3")
        assert manifest.container_id == "hagent-abcd1234-x1y2z3"
        assert lc.vm_id == "hagent-abcd1234-x1y2z3"
        vm = sdk.vms[0]
        assert any(c.startswith("run:") for c in vm.calls), "收养必须过探针"

    def test_adopt_missing_vm_raises(self, sdk):
        sdk.from_id_error = VMNotFoundError("gone")
        with pytest.raises(SandboxAdoptError):
            make_lifecycle(sdk).adopt("hagent-dead0000-aaaaaa")

    def test_adopt_not_running_raises(self, sdk):
        sdk.adopt_vm = FakeVM("hagent-s-a", {"status": VMState.STOPPED})
        with pytest.raises(SandboxAdoptError):
            make_lifecycle(sdk).adopt("hagent-s-a")

    def test_adopt_probe_failure_raises(self, sdk):
        sdk.adopt_vm = FakeVM("hagent-s-a", {"run": OperationTimeoutError("probe", 10.0)})
        with pytest.raises(SandboxAdoptError):
            make_lifecycle(sdk).adopt("hagent-s-a")

    def test_adopt_paused_vm_resumes_first(self, sdk):
        # 池 GC 暂停 → server 重启 → 收养须先 resume 再探针
        sdk.adopt_vm = FakeVM("hagent-s-a", {"status": VMState.PAUSED})
        manifest = make_lifecycle(sdk).adopt("hagent-s-a")
        assert manifest is not None
        vm = sdk.vms[0]
        assert "resume" in vm.calls
        assert vm.calls.index("resume") < [i for i, c in enumerate(vm.calls) if c.startswith("run:")][0]


class TestAllowedDomains:
    """Task C4 — HAGENT_SMOLVM_ALLOWED_DOMAINS → from_image(internet_settings=…)。

    SDK 语义(F6):域名在创建时宿主解析、IP 钉进 per-TAP nftables,
    fail-closed;不设置则完全不传参(SDK 默认全放行,与 docker 对齐 D14)。
    """

    def test_unset_env_omits_internet_settings(self, sdk, monkeypatch):
        monkeypatch.delenv("HAGENT_SMOLVM_ALLOWED_DOMAINS", raising=False)
        make_lifecycle(sdk).start()
        assert "internet_settings" not in sdk.from_image_calls[0]

    def test_env_passes_parsed_domain_list(self, sdk, monkeypatch):
        monkeypatch.setenv(
            "HAGENT_SMOLVM_ALLOWED_DOMAINS", "pypi.org, files.pythonhosted.org ,github.com"
        )
        make_lifecycle(sdk).start()
        assert sdk.from_image_calls[0]["internet_settings"] == {
            "allowed_domains": ["pypi.org", "files.pythonhosted.org", "github.com"]
        }

    def test_blank_env_treated_as_unset(self, sdk, monkeypatch):
        # 空串/纯逗号不得触发 fail-closed(否则手滑设空变成全断网)
        monkeypatch.setenv("HAGENT_SMOLVM_ALLOWED_DOMAINS", " , ")
        make_lifecycle(sdk).start()
        assert "internet_settings" not in sdk.from_image_calls[0]

    def test_invalid_domain_fails_fast_with_readable_error(self, sdk, monkeypatch):
        """审查缺陷 MEDIUM-3:非法条目(带路径的 URL)在 SDK 内抛 pydantic
        ValidationError(ValueError,不是 SmolVMError),会穿透 start 的 retry。
        须在 env 解析处 fail-fast,错误信息带变量名可诊断。"""
        from hagent.sandbox.smolvm.lifecycle import _allowed_domains_env

        monkeypatch.setenv("HAGENT_SMOLVM_ALLOWED_DOMAINS", "https://example.com/v1/path")
        with pytest.raises(ValueError, match="HAGENT_SMOLVM_ALLOWED_DOMAINS"):
            _allowed_domains_env()

    def test_bare_hostname_url_accepted(self, sdk, monkeypatch):
        # SDK 接受裸主机名 URL(抽 hostname),只拒带路径/凭据的;不得误拒
        from hagent.sandbox.smolvm.lifecycle import _allowed_domains_env

        monkeypatch.setenv("HAGENT_SMOLVM_ALLOWED_DOMAINS", "example.com, pypi.org")
        assert _allowed_domains_env() == ["example.com", "pypi.org"]


class FakeManager:
    """SmolVMManager 替身:只捕 delete_snapshot;上下文协议对齐真 SDK。"""

    def __init__(self, record: list[str], error: Exception | None = None):
        self._record = record
        self._error = error

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def delete_snapshot(self, snapshot_id: str) -> None:
        if self._error is not None:
            raise self._error
        self._record.append(snapshot_id)


class TestPersistRestore:
    """Task C2 — DISK 快照持久化:persist(快照+全拆)与 restore(重建+readiness)。"""

    def _lifecycle_with_manager(self, sdk, record: list[str], **kwargs) -> SmolVMLifecycle:
        return make_lifecycle(
            sdk, manager_factory=lambda: FakeManager(record), **kwargs
        )

    def test_persist_takes_disk_snapshot_then_full_teardown(self, sdk):
        lc = make_lifecycle(sdk)
        lc.start()
        snapshot_id = lc.persist_to_snapshot()
        vm = sdk.vms[0]
        assert snapshot_id == f"snap-{lc.vm_id}-1"
        assert "snapshot:disk" in vm.calls, "必须是 DISK 快照(存盘不存内存)"
        # 快照先于拆除;VM 全拆释放内存/TAP/IP 租约
        assert vm.calls.index("snapshot:disk") < vm.calls.index("delete")
        assert "close" in vm.calls
        assert lc.vm is None

    def test_persist_resumes_paused_vm_so_disk_snapshot_flushes_guest(self, sdk):
        lc = make_lifecycle(sdk)
        lc.start()
        lc.pause()

        lc.persist_to_snapshot()

        vm = sdk.vms[0]
        assert vm.calls.index("pause") < vm.calls.index("resume")
        assert vm.calls.index("resume") < vm.calls.index("snapshot:disk")

    def test_persist_without_vm_raises(self, sdk):
        with pytest.raises(SmolVMSandboxError):
            make_lifecycle(sdk).persist_to_snapshot()

    def test_persist_snapshot_failure_keeps_vm(self, sdk):
        # 快照失败时 VM 须保持完好——退回普通驱逐路径处置,不得半拆
        sdk.fail_plans = [{"snapshot": SmolVMError("no space")}]
        lc = make_lifecycle(sdk)
        lc.start()
        with pytest.raises(SmolVMSandboxError):
            lc.persist_to_snapshot()
        vm = sdk.vms[0]
        assert "delete" not in vm.calls
        assert lc.vm is vm

    def test_restore_boots_from_snapshot_with_readiness(self, sdk):
        lc = make_lifecycle(sdk)
        manifest = lc.restore_from_snapshot("snap-x-1")
        call = sdk.from_snapshot_calls[0]
        assert call["snapshot_id"] == "snap-x-1"
        assert call["resume_vm"] is True, "DISK 快照恢复即全新 boot,直接开机"
        vm = sdk.vms[0]
        ready_index = vm.calls.index("wait_for_ready")
        probe_index = next(i for i, c in enumerate(vm.calls) if c.startswith("run:"))
        assert ready_index < probe_index, "探针前必须等通道就绪(F15)"
        assert manifest.container_id == "hagent-abcd1234-x1y2z3"
        assert lc.vm_id == "hagent-abcd1234-x1y2z3"

    def test_restore_missing_snapshot_raises(self, sdk):
        sdk.from_snapshot_error = SmolVMError("Snapshot already restored")
        with pytest.raises(SandboxRestoreError):
            make_lifecycle(sdk).restore_from_snapshot("snap-x-1")

    def test_restore_readiness_failure_cleans_up(self, sdk):
        sdk.restore_vm = FakeVM(
            "hagent-abcd1234-x1y2z3",
            {"wait_for_ready": OperationTimeoutError("ready", 60.0)},
        )
        lc = make_lifecycle(sdk)
        with pytest.raises(SandboxRestoreError):
            lc.restore_from_snapshot("snap-x-1")
        vm = sdk.vms[0]
        assert "delete" in vm.calls and "close" in vm.calls, "恢复失败必须全清理"
        assert lc.vm is None

    def test_restore_readiness_failure_deletes_consumed_snapshot(self, sdk):
        """审查缺陷 B:SDK restore 启动 VM 即把快照标 restored(一次性),
        readiness 失败后 VM 被删但快照残留——必须在失败分支删快照,否则磁盘泄漏
        且该快照永远无法再 restore(须 force,hagent 从不传)。"""
        deleted: list[str] = []
        sdk.restore_vm = FakeVM(
            "hagent-abcd1234-x1y2z3",
            {"wait_for_ready": OperationTimeoutError("ready", 60.0)},
        )
        lc = make_lifecycle(sdk, manager_factory=lambda: FakeManager(deleted))
        with pytest.raises(SandboxRestoreError):
            lc.restore_from_snapshot("snap-x-1")
        assert deleted == ["snap-x-1"], "恢复失败(快照已被 SDK 消费)必须删快照防泄漏"

    def test_stop_after_restore_deletes_consumed_snapshot(self, sdk):
        # 快照一次性语义:restored VM 拆除后源快照已消费,须清理防泄漏
        deleted: list[str] = []
        lc = self._lifecycle_with_manager(sdk, deleted)
        lc.restore_from_snapshot("snap-x-1")
        lc.stop()
        assert deleted == ["snap-x-1"]

    def test_persist_after_restore_cleans_old_snapshot(self, sdk):
        deleted: list[str] = []
        lc = self._lifecycle_with_manager(sdk, deleted)
        lc.restore_from_snapshot("snap-old-1")
        new_id = lc.persist_to_snapshot()
        assert new_id != "snap-old-1"
        assert deleted == ["snap-old-1"], "旧快照被新快照取代,顺手清理"

    def test_plain_stop_does_not_touch_snapshots(self, sdk):
        deleted: list[str] = []
        lc = self._lifecycle_with_manager(sdk, deleted)
        lc.start()
        lc.stop()
        assert deleted == []

    def test_delete_snapshot_quiet_swallows_errors(self):
        deleted: list[str] = []
        delete_snapshot_quiet("snap-a", manager_factory=lambda: FakeManager(deleted))
        assert deleted == ["snap-a"]
        # 删除失败不抛(遗留快照交给运维;restored VM 活跃期间 SDK 本就拒删)
        delete_snapshot_quiet(
            "snap-b",
            manager_factory=lambda: FakeManager(deleted, error=SmolVMError("active")),
        )


@pytest.mark.parametrize(
    ("exc", "keyword"),
    [
        (HostError("no kvm"), "宿主"),
        (ImageError("bad rootfs"), "镜像"),
        (NetworkError("tap"), "网络"),
        (FirecrackerAPIError("api"), "Firecracker"),
        (OperationTimeoutError("run", 30.0), "超时"),
        (VMAlreadyExistsError("dup"), "已存在"),
        (VMNotFoundError("gone"), "不存在"),
        (SmolVMError("generic"), "SmolVM"),
    ],
)
def test_sdk_error_mapping_table(exc, keyword):
    assert keyword in describe_sdk_error(exc)


class TestAdoptChannelReadiness:
    """Phase B 实测教训:from_id 重连后 vsock 通道未必就绪,探针前须等待。

    L3 曾以「The guest control channel did not become ready」翻车——
    负载下重连握手比探针慢,收养被误判失败转清场。
    """

    def test_adopt_waits_for_channel_before_probe(self, sdk):
        lc = make_lifecycle(sdk)
        lc.adopt("hagent-abcd1234-x1y2z3")
        vm = sdk.vms[0]
        ready_index = vm.calls.index("wait_for_ready")
        probe_index = next(i for i, c in enumerate(vm.calls) if c.startswith("run:"))
        assert ready_index < probe_index, "wait_for_ready 必须先于探针"

    def test_adopt_channel_timeout_raises_adopt_error(self, sdk):
        sdk.adopt_vm = FakeVM(
            "hagent-s-a", {"wait_for_ready": OperationTimeoutError("ready", 60.0)}
        )
        with pytest.raises(SandboxAdoptError):
            make_lifecycle(sdk).adopt("hagent-s-a")
