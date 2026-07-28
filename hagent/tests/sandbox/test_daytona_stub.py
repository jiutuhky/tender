from __future__ import annotations

import pytest

from hagent.sandbox import SandboxKind
from hagent.sandbox.daytona.sandbox import HagentDaytonaSandbox


def test_daytona_stub_kind():
    sb = HagentDaytonaSandbox()
    assert sb.kind is SandboxKind.DAYTONA


def test_daytona_stub_workspace_dir():
    sb = HagentDaytonaSandbox()
    assert sb.workspace_dir == "/workspace"


def test_daytona_stub_methods_raise_not_implemented():
    sb = HagentDaytonaSandbox()
    with pytest.raises(NotImplementedError):
        sb.execute("echo hi")


@pytest.mark.skip(reason="Daytona implementation deferred to follow-up — proves abstraction is not docker-bound")
def test_daytona_full_contract():
    """Placeholder for langchain-daytona contract test; intentionally skipped."""
    pass
