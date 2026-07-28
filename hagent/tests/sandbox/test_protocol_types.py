from __future__ import annotations

import pytest

from hagent.sandbox import HagentSandboxProtocol, SandboxKind


def test_sandbox_kind_values():
    assert SandboxKind.NONE.value == "none"
    assert SandboxKind.DOCKER.value == "docker"
    assert SandboxKind.DAYTONA.value == "daytona"
    assert SandboxKind.SMOLVM.value == "smolvm"


def test_sandbox_kind_from_str_case_insensitive():
    assert SandboxKind.from_str("Docker") is SandboxKind.DOCKER
    assert SandboxKind.from_str("none") is SandboxKind.NONE
    assert SandboxKind.from_str("SmolVM") is SandboxKind.SMOLVM


def test_sandbox_kind_smolvm_roundtrip():
    assert SandboxKind.from_str(SandboxKind.SMOLVM.value) is SandboxKind.SMOLVM


def test_sandbox_kind_from_str_rejects_unknown():
    with pytest.raises(ValueError, match="unknown sandbox kind"):
        SandboxKind.from_str("e2b")


def test_protocol_requires_execute_and_lifecycle_methods():
    # 用 abstract 子类——HagentSandboxProtocol 必须暴露 close()、workspace_dir 等
    expected_attrs = {"execute", "upload_files", "download_files", "id", "workspace_dir", "close", "kind"}
    for name in expected_attrs:
        assert hasattr(HagentSandboxProtocol, name), f"missing {name}"
