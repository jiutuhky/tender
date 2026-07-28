"""L4 gVisor-specific assertions — requires docker + runsc + HAGENT_TEST_GVISOR=1."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.gvisor

if os.environ.get("HAGENT_TEST_GVISOR") != "1":
    pytest.skip("HAGENT_TEST_GVISOR!=1; skipping gVisor tests", allow_module_level=True)


from hagent.sandbox.docker.sandbox import HagentDockerSandbox  # noqa: E402


@pytest.fixture
def gvisor_sandbox():
    sb = HagentDockerSandbox.start(prefer_runtime="runsc")
    yield sb
    sb.close()


def test_uname_indicates_gvisor_kernel(gvisor_sandbox):
    """gVisor reports a synthetic kernel version distinct from the host."""
    resp = gvisor_sandbox.execute("uname -r")
    assert resp.exit_code == 0
    host_uname = os.uname().release
    # gVisor's kernel string typically contains 'gvisor' or differs significantly
    # from the host. We just assert they're not identical — gVisor synthesises its
    # own version string.
    assert host_uname not in resp.output or "gvisor" in resp.output.lower()


def test_dmesg_blocked_or_empty(gvisor_sandbox):
    """gVisor blocks dmesg (no privileged kernel syscalls)."""
    resp = gvisor_sandbox.execute("dmesg 2>&1; true")
    # Either rejected ("Operation not permitted") or returns empty buffer.
    assert (
        "Operation not permitted" in resp.output
        or "Permission denied" in resp.output
        or resp.output.strip() == ""
    )


def test_manifest_runtime_is_runsc(gvisor_sandbox):
    """When start(prefer_runtime='runsc') succeeds, the manifest records runsc."""
    assert gvisor_sandbox.manifest.runtime == "runsc"
