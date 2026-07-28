"""L5 end-to-end demo — 真实模型 + 真实沙箱,按 provider 双门控。

docker:ANTHROPIC_API_KEY + HAGENT_TEST_DOCKER=1
smolvm:ANTHROPIC_API_KEY + HAGENT_TEST_SMOLVM=1(需 KVM + firecracker)
"""

from __future__ import annotations

import os

import pytest

pytestmark = [pytest.mark.e2e]

_GATE_ENV = {"docker": "HAGENT_TEST_DOCKER", "smolvm": "HAGENT_TEST_SMOLVM"}


def _require_gate(sandbox_kind: str) -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("requires ANTHROPIC_API_KEY")
    gate = _GATE_ENV[sandbox_kind]
    if os.environ.get(gate) != "1":
        pytest.skip(f"requires {gate}=1")


@pytest.mark.parametrize(
    "sandbox_kind",
    [
        pytest.param("docker", marks=pytest.mark.docker),
        pytest.param("smolvm", marks=pytest.mark.smolvm),
    ],
)
def test_demo_sandbox_runs_to_completion(monkeypatch, tmp_path, sandbox_kind):
    """Sanity check: hagent demo --sandbox <kind> completes with rc=0 against real model."""
    _require_gate(sandbox_kind)
    from hagent import cli

    monkeypatch.setenv("HAGENT_SANDBOX_KIND", sandbox_kind)
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))

    rc = cli.main([
        "demo",
        "--sandbox", sandbox_kind,
        "用 python 算 1+1 并写到 /workspace/result.txt，然后简短确认完成。",
    ])
    assert rc == 0
