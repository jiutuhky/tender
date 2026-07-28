"""Task A10 — preflight_sandbox_kind:smolvm→docker→none 降级链 + REQUIRE 强约束。"""

from __future__ import annotations

import logging

import pytest

from hagent import config as config_mod
from hagent.config import preflight_sandbox_kind
from hagent.sandbox import SandboxKind


@pytest.fixture
def all_probes_pass(monkeypatch):
    monkeypatch.setattr(config_mod, "_probe_kvm", lambda: None)
    monkeypatch.setattr(config_mod, "_probe_firecracker", lambda: None)
    monkeypatch.setattr(config_mod, "_probe_sudoers", lambda: None)
    monkeypatch.setattr(config_mod, "_probe_smolvm_import", lambda: None)
    monkeypatch.setattr(config_mod, "_probe_docker", lambda: None)
    monkeypatch.delenv("HAGENT_SANDBOX_KIND", raising=False)
    monkeypatch.delenv("HAGENT_SANDBOX_REQUIRE", raising=False)


def test_default_requested_kind_is_smolvm(all_probes_pass):
    # spec D5:server 侧默认 smolvm
    assert preflight_sandbox_kind() is SandboxKind.SMOLVM


def test_env_requested_kind_respected(all_probes_pass, monkeypatch):
    monkeypatch.setenv("HAGENT_SANDBOX_KIND", "docker")
    assert preflight_sandbox_kind() is SandboxKind.DOCKER


def test_none_short_circuits_probes(monkeypatch):
    # kind=none 不做任何探测(测试环境保持零外部依赖)
    def boom():
        raise AssertionError("none 不应触发探测")

    monkeypatch.setattr(config_mod, "_probe_kvm", boom)
    monkeypatch.setattr(config_mod, "_probe_docker", boom)
    assert preflight_sandbox_kind("none") is SandboxKind.NONE


@pytest.mark.parametrize(
    ("probe_name", "problem"),
    [
        ("_probe_kvm", "无 /dev/kvm 读写权限"),
        ("_probe_firecracker", "缺 firecracker 二进制"),
        ("_probe_sudoers", "缺 sudoers 配置"),
        ("_probe_smolvm_import", "smolvm 未安装"),
    ],
)
def test_smolvm_probe_failure_degrades_to_docker(
    all_probes_pass, monkeypatch, caplog, probe_name, problem
):
    monkeypatch.setattr(config_mod, probe_name, lambda: problem)
    with caplog.at_level(logging.WARNING):
        kind = preflight_sandbox_kind("smolvm")
    assert kind is SandboxKind.DOCKER
    assert any(problem in r.message for r in caplog.records), "逐项 WARNING 须打印缺什么"


def test_double_degrade_to_none(all_probes_pass, monkeypatch, caplog):
    monkeypatch.setattr(config_mod, "_probe_kvm", lambda: "缺 kvm")
    monkeypatch.setattr(config_mod, "_probe_docker", lambda: "docker daemon 不可达")
    with caplog.at_level(logging.WARNING):
        kind = preflight_sandbox_kind("smolvm")
    assert kind is SandboxKind.NONE


def test_require_smolvm_fails_hard(all_probes_pass, monkeypatch):
    monkeypatch.setenv("HAGENT_SANDBOX_REQUIRE", "smolvm")
    monkeypatch.setattr(config_mod, "_probe_kvm", lambda: "缺 kvm")
    with pytest.raises(RuntimeError, match="HAGENT_SANDBOX_REQUIRE"):
        preflight_sandbox_kind("smolvm")


def test_require_satisfied_when_probes_pass(all_probes_pass, monkeypatch):
    monkeypatch.setenv("HAGENT_SANDBOX_REQUIRE", "smolvm")
    assert preflight_sandbox_kind("smolvm") is SandboxKind.SMOLVM


def test_docker_requested_skips_smolvm_probes(all_probes_pass, monkeypatch):
    def boom():
        raise AssertionError("docker 请求不应探 smolvm")

    monkeypatch.setattr(config_mod, "_probe_kvm", boom)
    assert preflight_sandbox_kind("docker") is SandboxKind.DOCKER
