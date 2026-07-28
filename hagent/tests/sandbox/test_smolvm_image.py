"""Task A3 — smolvm 镜像烘焙:Dockerfile 物料 + ensure_boot_image 缓存/单飞。"""

from __future__ import annotations

import threading
import time

import pytest

from hagent.sandbox.smolvm import image as image_mod
from hagent.sandbox.smolvm.image import HAGENT_DOCKERFILE, ensure_boot_image


@pytest.fixture(autouse=True)
def _reset_image_cache():
    image_mod.reset_cache()
    yield
    image_mod.reset_cache()


class TestDockerfileMaterials:
    """镜像四要素:python3 / rg / guest-agent / sshd(F7),外加 /workspace 内建。"""

    def test_python_base(self):
        # 与 docker provider 同源:python:3.12-slim 基座自带 python3
        assert "python:3.12-slim" in HAGENT_DOCKERFILE

    def test_ripgrep(self):
        assert "ripgrep" in HAGENT_DOCKERFILE

    def test_guest_agent_copy(self):
        # DockerRootfsBuilder 不自动注入 agent(F7),必须显式 COPY
        assert "COPY smolvm-guest-agent /usr/local/bin/smolvm-guest-agent" in HAGENT_DOCKERFILE

    def test_sshd(self):
        assert "openssh-server" in HAGENT_DOCKERFILE

    def test_host_keys_baked_at_build(self):
        # F13:运行期 keygen 依赖 boot 后熵会阻塞 init,host key 必须烘焙期生成
        assert "ssh-keygen -A" in HAGENT_DOCKERFILE

    def test_workspace_builtin(self):
        # Firecracker 无 bind-mount,/workspace 必须随镜像内建(spec §7)
        assert "mkdir -p /workspace" in HAGENT_DOCKERFILE

    def test_init_copy(self):
        assert "COPY init /init" in HAGENT_DOCKERFILE

    def test_docker_provider_shared_materials(self):
        # D3:物料与 docker provider Dockerfile 同源维护
        for pkg in ("bash", "git", "coreutils", "procps", "ca-certificates", "curl"):
            assert pkg in HAGENT_DOCKERFILE, f"missing shared package: {pkg}"


class _FakeBuilder:
    """替身 DockerRootfsBuilder:记录构造参数与 build 调用次数。"""

    instances: list["_FakeBuilder"] = []
    build_started = threading.Event()
    build_release = threading.Event()
    blocking = False

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.build_calls = 0
        _FakeBuilder.instances.append(self)

    def build_boot_image(self, **kwargs):
        self.build_kwargs = kwargs
        self.build_calls += 1
        if _FakeBuilder.blocking:
            _FakeBuilder.build_started.set()
            assert _FakeBuilder.build_release.wait(timeout=5), "release 未触发"
        return object()

    @classmethod
    def reset(cls):
        cls.instances = []
        cls.build_started = threading.Event()
        cls.build_release = threading.Event()
        cls.blocking = False


@pytest.fixture
def fake_builder(monkeypatch):
    _FakeBuilder.reset()
    monkeypatch.setattr(image_mod, "DockerRootfsBuilder", _FakeBuilder)
    # context 物料解析会触发 guest-agent 下载/密钥生成,单元测试全部替身化
    monkeypatch.setattr(image_mod, "_build_context", lambda: {"init": "#!/bin/sh"})
    return _FakeBuilder


class TestEnsureBootImage:
    def test_builds_once_then_cache_hit(self, fake_builder):
        img1 = ensure_boot_image()
        img2 = ensure_boot_image()
        assert img1 is img2
        assert len(fake_builder.instances) == 1
        assert fake_builder.instances[0].build_calls == 1

    def test_passes_firecracker_backend_and_ssh_boot_args(self, fake_builder):
        ensure_boot_image()
        build_kwargs = fake_builder.instances[0].build_kwargs
        assert build_kwargs["backend"] == "firecracker"
        # SSH_BOOT_ARGS 含 init=/init,决定自建 init 脚本被引导
        assert "init=/init" in build_kwargs["boot_args"]

    def test_ssh_capable_flag_set(self, fake_builder):
        ensure_boot_image()
        assert fake_builder.instances[0].kwargs["ssh_capable"] is True

    def test_disk_mib_env_override(self, fake_builder, monkeypatch):
        monkeypatch.setenv("HAGENT_SMOLVM_DISK_MIB", "2048")
        ensure_boot_image()
        assert fake_builder.instances[0].kwargs["rootfs_size_mb"] == 2048

    def test_concurrent_calls_single_flight(self, fake_builder):
        fake_builder.blocking = True
        results: list[object] = []

        def call():
            results.append(ensure_boot_image())

        t1 = threading.Thread(target=call)
        t2 = threading.Thread(target=call)
        t1.start()
        assert fake_builder.build_started.wait(timeout=5)
        t2.start()
        time.sleep(0.05)  # 给 t2 一个真的跑进单飞临界区的窗口
        fake_builder.build_release.set()
        t1.join(timeout=5)
        t2.join(timeout=5)
        assert len(results) == 2
        assert results[0] is results[1]
        assert len(fake_builder.instances) == 1, "并发下不应重复构建"
        assert fake_builder.instances[0].build_calls == 1


@pytest.mark.smolvm
def test_real_build_smoke():
    image = ensure_boot_image()
    assert image.rootfs_path.is_file()
    assert image.ssh_capable is True
