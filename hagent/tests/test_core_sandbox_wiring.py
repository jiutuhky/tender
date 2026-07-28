from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hagent.config import HagentConfig
from hagent.sandbox import SandboxKind


def test_create_hagent_with_sandbox_none_uses_local_backend():
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    cfg = HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False, sandbox_kind=SandboxKind.NONE)
    with patch("hagent.core._create_deep_agent", side_effect=fake_create):
        from hagent.core import create_hagent
        create_hagent(config=cfg)
    assert "permissions" in captured  # host mode keeps permissions


def test_create_hagent_with_sandbox_docker_skips_permissions_and_uses_sandbox_backend(tmp_path):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    sandbox = MagicMock()
    sandbox.workspace_dir = str(tmp_path / "workspace")
    sandbox._container = MagicMock(id="cidcid")
    sandbox.kind.value = "docker"

    cfg = HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False, sandbox_kind=SandboxKind.DOCKER)
    with patch("hagent.core._create_deep_agent", side_effect=fake_create), \
         patch("hagent.core.HagentDockerSandbox") as mock_sb_cls:
        mock_sb_cls.start.return_value = sandbox
        from hagent.core import create_hagent
        create_hagent(config=cfg)
    assert captured["backend"] is sandbox
    # sandbox mode: deepagents FilesystemPermission is bypassed
    assert "permissions" not in captured or captured["permissions"] in (None, [])


def test_create_hagent_explicit_sandbox_param_overrides_config(tmp_path):
    """Passing sandbox=<instance> bypasses HagentDockerSandbox.start() factory."""
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    sandbox = MagicMock()
    sandbox.workspace_dir = str(tmp_path / "workspace")
    sandbox._container = MagicMock(id="cidcid")
    sandbox.kind.value = "docker"

    cfg = HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False, sandbox_kind=SandboxKind.NONE)
    with patch("hagent.core._create_deep_agent", side_effect=fake_create):
        from hagent.core import create_hagent
        create_hagent(config=cfg, sandbox=sandbox)
    assert captured["backend"] is sandbox


def test_create_hagent_with_explicit_backend_does_not_auto_start_container(tmp_path):
    """When caller already passed a non-sandbox backend, an env-driven
    sandbox_kind=docker must NOT silently spin up a second container.

    Repro: server/agents.py passes a FilesystemBackend without sandbox=, and
    if HAGENT_SANDBOX_KIND=docker is set in env, core.py used to call
    HagentDockerSandbox.start() anyway — yielding two containers per session
    (one from SandboxPool.acquire, another from this auto-start)."""
    from deepagents.backends import FilesystemBackend

    backend = FilesystemBackend(root_dir=str(tmp_path / "ws"), virtual_mode=False)

    cfg = HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False, sandbox_kind=SandboxKind.DOCKER)
    with patch("hagent.core._create_deep_agent", side_effect=lambda **kw: MagicMock()), \
         patch("hagent.core.HagentDockerSandbox") as mock_sb_cls:
        from hagent.core import create_hagent
        create_hagent(config=cfg, backend=backend)
    mock_sb_cls.start.assert_not_called()
