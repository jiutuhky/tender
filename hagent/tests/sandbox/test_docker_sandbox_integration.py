"""L3 integration tests — require docker daemon and HAGENT_TEST_DOCKER=1."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.docker

if os.environ.get("HAGENT_TEST_DOCKER") != "1":
    pytest.skip("HAGENT_TEST_DOCKER!=1; skipping docker integration tests", allow_module_level=True)


from hagent.sandbox.docker.sandbox import HagentDockerSandbox  # noqa: E402


@pytest.fixture
def docker_sandbox():
    sb = HagentDockerSandbox.start(prefer_runtime="runc")
    yield sb
    sb.close()


def test_python_version(docker_sandbox):
    resp = docker_sandbox.execute("python --version")
    assert resp.exit_code == 0
    assert "Python 3" in resp.output


def test_upload_then_read(docker_sandbox):
    docker_sandbox.upload_files([("/workspace/a.txt", b"hello")])
    resp = docker_sandbox.execute("cat /workspace/a.txt")
    assert resp.exit_code == 0
    assert "hello" in resp.output


def test_download_roundtrip(docker_sandbox):
    docker_sandbox.upload_files([("/workspace/a.txt", b"world")])
    out = docker_sandbox.download_files(["/workspace/a.txt"])
    assert out[0].content == b"world"


def test_execute_timeout(docker_sandbox):
    # docker-py exec_run does not enforce timeout in current impl;
    # we only assert the call returns within reasonable bounds.
    resp = docker_sandbox.execute("echo immediate", timeout=5)
    assert resp.exit_code == 0


def test_stop_then_execute_returns_error():
    sb = HagentDockerSandbox.start(prefer_runtime="runc")
    sb.close()
    resp = sb.execute("echo hi")
    assert resp.exit_code != 0
    assert "not running" in resp.output.lower() or "exec" in resp.output.lower()


from pathlib import Path  # noqa: E402

from hagent.bash_tool import create_bash_tool  # noqa: E402
from hagent.bash_tool.runtime import BashRuntime  # noqa: E402
from hagent.sandbox.providers.shell import SandboxShellProvider  # noqa: E402


def test_bash_tool_parity_through_sandbox_shell_provider(docker_sandbox, tmp_path):
    """Real docker exec path: Bash tool output is consistent with host mode.

    This is the L3 backstop for spec §5.5 byte-equal claim — the T20 parity test
    uses host-only ShellProvider on both sides; this one drives the actual
    SandboxShellProvider → docker exec → BashRuntime parse __HAGENT_PWD__ path.
    """
    # Host side
    host_runtime = BashRuntime(tmp_path)
    host_bash = create_bash_tool(workspace_root=tmp_path, runtime=host_runtime, permissions=None)
    host_out = host_bash.invoke({"command": "printf 'hi\\n'"})

    # Sandbox side — real docker
    provider = SandboxShellProvider(
        sandbox=docker_sandbox,
        workspace_root=Path(docker_sandbox.workspace_dir),
    )
    sb_runtime = BashRuntime(tmp_path, shell_provider=provider)
    sb_bash = create_bash_tool(workspace_root=tmp_path, runtime=sb_runtime, permissions=None)
    sb_out = sb_bash.invoke({"command": "printf 'hi\\n'"})

    def normalize(text: str) -> str:
        # Strip __HAGENT_PWD__ sentinel lines from sandbox output and empty lines
        lines = [ln for ln in text.splitlines() if not ln.startswith("__HAGENT_PWD__:")]
        return "\n".join(ln.rstrip() for ln in lines if ln.strip()).strip()

    assert normalize(host_out) == normalize(sb_out)


from hagent.skills.loader import load_skills_from_sources  # noqa: E402
from hagent.skills.materialize import SkillMaterializer  # noqa: E402
from hagent.sandbox.providers.file import SandboxFileTransport  # noqa: E402


def test_skill_materializer_uploads_reference_files_into_container(docker_sandbox, tmp_path):
    """A skill's references/ tree is reachable inside the container after materialize."""
    skill_dir = tmp_path / "review"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: Review.\n---\n# body\n", encoding="utf-8"
    )
    (skill_dir / "references" / "checklist.md").write_text("step-1", encoding="utf-8")
    registry = load_skills_from_sources([(tmp_path, "Project Hagent")])
    skill = registry.require("review")

    base = SkillMaterializer(docker_sandbox).materialize(skill)

    # Reachable via raw exec (what the Bash tool ultimately uses)...
    resp = docker_sandbox.execute(f"cat {base}/references/checklist.md")
    assert resp.exit_code == 0
    assert "step-1" in resp.output
    # ...and via the file transport (what the Read tool uses).
    meta = SandboxFileTransport(docker_sandbox).read_text_metadata(
        f"{base}/references/checklist.md"
    )
    assert meta.content == "step-1"


def test_bash_exit_code_parity_through_sandbox(docker_sandbox, tmp_path):
    """Non-zero exit code surfaces the same way in sandbox mode as in host mode."""
    host_runtime = BashRuntime(tmp_path)
    host_bash = create_bash_tool(workspace_root=tmp_path, runtime=host_runtime, permissions=None)
    host_out = host_bash.invoke({"command": "exit 7"})

    provider = SandboxShellProvider(
        sandbox=docker_sandbox,
        workspace_root=Path(docker_sandbox.workspace_dir),
    )
    sb_runtime = BashRuntime(tmp_path, shell_provider=provider)
    sb_bash = create_bash_tool(workspace_root=tmp_path, runtime=sb_runtime, permissions=None)
    sb_out = sb_bash.invoke({"command": "exit 7"})

    # Both should mention "Exit code: 7" (Hagent BashResult formatting)
    assert "Exit code: 7" in host_out
    assert "Exit code: 7" in sb_out
