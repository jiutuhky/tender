"""Behavior parity between host and sandbox modes for Bash / Read / Edit / Grep / Glob tools.

Task A11:下半部为三方对照(host / docker / smolvm)——真实沙箱经
``real_sandbox`` 参数化 fixture 提供,docker 侧 HAGENT_TEST_DOCKER=1 门控,
smolvm 侧 @pytest.mark.smolvm(HAGENT_TEST_SMOLVM=1)门控,默认套件全 skip。
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from hagent.bash_tool import create_bash_tool
from hagent.bash_tool.runtime import BashRuntime
from hagent.bash_tool.shell_provider import ShellProvider
from hagent.file_tools.state import FileReadState
from hagent.file_tools.tools import create_edit_tool, create_read_tool
from hagent.grep_tool import create_grep_tools
from hagent.sandbox.providers.file import SandboxFileTransport

from tests.conftest_sandbox import fake_sandbox  # noqa: F401  reused fixture

HAS_RG = shutil.which("rg") is not None


def test_bash_simple_command_parity(tmp_path: Path, fake_sandbox):  # noqa: F811
    """Same Bash command on host and sandbox produces matching output.

    Both runtimes run locally (no docker), so the only difference is the working
    directory root. The tool output format must be identical after stripping
    sentinel lines that carry cwd state.
    """
    host_root = tmp_path / "host"
    host_root.mkdir()
    sandbox_root = Path(fake_sandbox.workspace_dir)

    host_runtime = BashRuntime(
        host_root,
        shell_provider=ShellProvider(host_root),
    )
    sb_runtime = BashRuntime(
        sandbox_root,
        shell_provider=ShellProvider(sandbox_root),
    )

    host_bash = create_bash_tool(workspace_root=host_root, runtime=host_runtime, permissions=None)
    sb_bash = create_bash_tool(workspace_root=sandbox_root, runtime=sb_runtime, permissions=None)

    host_out = host_bash.invoke({"command": "printf 'hi\\n'"})
    sb_out = sb_bash.invoke({"command": "printf 'hi\\n'"})

    def normalize(text: str) -> str:
        """Strip sentinel / cwd lines; normalise trailing whitespace."""
        lines = [ln for ln in text.splitlines() if not ln.startswith("__HAGENT_PWD__:")]
        return "\n".join(ln.rstrip() for ln in lines if ln.strip()).strip()

    assert normalize(host_out) == normalize(sb_out)

    host_runtime.close()
    sb_runtime.close()


def test_read_tool_cat_n_parity(tmp_path: Path, fake_sandbox):  # noqa: F811
    """Read tool output is byte-equal between host and sandbox.

    Paths differ, but line numbers and content bodies must match.
    """
    payload = "line one\nline two\nline three\n"

    # Host side
    host_file = tmp_path / "a.txt"
    host_file.write_text(payload, encoding="utf-8")

    # Sandbox side
    sandbox_path = f"{fake_sandbox.workspace_dir}/a.txt"
    fake_sandbox.upload_files([(sandbox_path, payload.encode("utf-8"))])

    host_state = FileReadState()
    sb_state = FileReadState()

    host_read = create_read_tool(
        workspace_root=tmp_path,
        permissions=None,
        state=host_state,
    )
    sb_read = create_read_tool(
        workspace_root=Path(fake_sandbox.workspace_dir),
        permissions=None,
        state=sb_state,
        transport=SandboxFileTransport(fake_sandbox),
    )

    host_out = host_read.invoke({"file_path": str(host_file)})
    sb_out = sb_read.invoke({"file_path": sandbox_path})

    def normalize(text: str) -> str:
        """Keep only numbered content lines; strip path-prefix differences."""
        return "\n".join(
            line for line in text.splitlines() if line and line[0].isdigit()
        )

    assert normalize(host_out) == normalize(sb_out)


def test_edit_string_not_found_message_parity(tmp_path: Path, fake_sandbox):  # noqa: F811
    """Edit tool's 'String not found' error is identical wording in host and sandbox."""
    # Host side
    host_file = tmp_path / "a.txt"
    host_file.write_text("alpha\n", encoding="utf-8")

    # Sandbox side
    sandbox_path = f"{fake_sandbox.workspace_dir}/a.txt"
    fake_sandbox.upload_files([(sandbox_path, b"alpha\n")])

    host_state = FileReadState()
    sb_state = FileReadState()

    sb_transport = SandboxFileTransport(fake_sandbox)

    host_read = create_read_tool(workspace_root=tmp_path, permissions=None, state=host_state)
    sb_read = create_read_tool(
        workspace_root=Path(fake_sandbox.workspace_dir),
        permissions=None,
        state=sb_state,
        transport=sb_transport,
    )
    host_edit = create_edit_tool(workspace_root=tmp_path, permissions=None, state=host_state)
    sb_edit = create_edit_tool(
        workspace_root=Path(fake_sandbox.workspace_dir),
        permissions=None,
        state=sb_state,
        transport=sb_transport,
    )

    # Seed state — Edit requires a prior Read in the same FileReadState.
    host_read.invoke({"file_path": str(host_file)})
    sb_read.invoke({"file_path": sandbox_path})

    host_out = host_edit.invoke(
        {"file_path": str(host_file), "old_string": "missing", "new_string": "x"}
    )
    sb_out = sb_edit.invoke(
        {"file_path": sandbox_path, "old_string": "missing", "new_string": "x"}
    )

    assert "String to replace not found" in host_out
    assert "String to replace not found" in sb_out


def _seed(root: Path) -> None:
    (root / "a.py").write_text("def foo():\n    pass\n")
    (root / "b.md").write_text("foo bar\n")
    (root / "sub").mkdir(exist_ok=True)
    (root / "sub" / "c.py").write_text("foo = 1\n")


def test_glob_parity(tmp_path: Path, fake_sandbox):  # noqa: F811
    """Glob returns the same set of (relative) files on host and sandbox.

    Glob runs `python3` in the workspace via the executor; the sandbox path goes
    through ``sandbox.execute`` (local subprocess in the fake sandbox)."""
    host_root = tmp_path / "host"
    host_root.mkdir()
    sb_root = Path(fake_sandbox.workspace_dir)
    _seed(host_root)
    _seed(sb_root)

    _, host_glob = create_grep_tools(workspace_root=host_root, sandbox=None, permissions=None)
    _, sb_glob = create_grep_tools(workspace_root=sb_root, sandbox=fake_sandbox, permissions=None)

    def rels(out: str, base: Path) -> set[str]:
        return {str(Path(p).relative_to(base)) for p in out.splitlines()}

    host_out = host_glob.invoke({"pattern": "**/*.py"})
    sb_out = sb_glob.invoke({"pattern": "**/*.py"})
    assert rels(host_out, host_root) == rels(sb_out, sb_root) == {"a.py", "sub/c.py"}


@pytest.mark.skipif(not HAS_RG, reason="ripgrep not installed; sandbox Grep needs rg")
def test_grep_files_with_matches_parity(tmp_path: Path, fake_sandbox):  # noqa: F811
    """Grep (files_with_matches) returns the same files on host and sandbox."""
    host_root = tmp_path / "host"
    host_root.mkdir()
    sb_root = Path(fake_sandbox.workspace_dir)
    _seed(host_root)
    _seed(sb_root)

    host_grep, _ = create_grep_tools(workspace_root=host_root, sandbox=None, permissions=None)
    sb_grep, _ = create_grep_tools(workspace_root=sb_root, sandbox=fake_sandbox, permissions=None)

    def rels(out: str, base: Path) -> set[str]:
        return {str(Path(p).relative_to(base)) for p in out.splitlines()}

    host_out = host_grep.invoke({"pattern": "foo"})
    sb_out = sb_grep.invoke({"pattern": "foo"})
    assert rels(host_out, host_root) == rels(sb_out, sb_root) == {"a.py", "b.md", "sub/c.py"}


# ---------------------------------------------------------------------------
# Task A11 — 三方对照:host × 真实 docker × 真实 smolvm
# ---------------------------------------------------------------------------


def _make_real_sandbox(kind: str):
    if kind == "docker":
        if os.environ.get("HAGENT_TEST_DOCKER") != "1":
            pytest.skip("HAGENT_TEST_DOCKER!=1; skipping docker parity")
        from hagent.sandbox.docker.sandbox import HagentDockerSandbox

        return HagentDockerSandbox.start(prefer_runtime="runc")
    from hagent.sandbox.smolvm.sandbox import HagentSmolVMSandbox

    return HagentSmolVMSandbox.start(project_id="parity")


@pytest.fixture(
    params=[
        pytest.param("docker", marks=pytest.mark.docker),
        pytest.param("smolvm", marks=pytest.mark.smolvm),
    ]
)
def real_sandbox(request):
    sb = _make_real_sandbox(request.param)
    yield sb
    sb.close()


def _seed_sandbox(sb) -> None:
    ws = sb.workspace_dir
    sb.upload_files(
        [
            (f"{ws}/a.py", b"def foo():\n    pass\n"),
            (f"{ws}/b.md", b"foo bar\n"),
            (f"{ws}/sub/c.py", b"foo = 1\n"),
        ]
    )


def test_real_bash_echo_parity(tmp_path: Path, real_sandbox):
    resp = real_sandbox.execute("printf 'hi\\n'; printf 'warn\\n' >&2; exit 3")
    assert resp.exit_code == 3
    # 输出格式契约(与 docker provider byte-equal):stdout 原样 + [stderr] 前缀
    assert resp.output == "hi\n[stderr] warn\n"


def test_real_read_tool_parity(tmp_path: Path, real_sandbox):
    payload = "line one\nline two\nline three\n"
    host_file = tmp_path / "a.txt"
    host_file.write_text(payload, encoding="utf-8")
    sandbox_path = f"{real_sandbox.workspace_dir}/a.txt"
    up = real_sandbox.upload_files([(sandbox_path, payload.encode("utf-8"))])
    assert up[0].error is None

    host_read = create_read_tool(workspace_root=tmp_path, permissions=None, state=FileReadState())
    sb_read = create_read_tool(
        workspace_root=Path(real_sandbox.workspace_dir),
        permissions=None,
        state=FileReadState(),
        transport=SandboxFileTransport(real_sandbox),
    )
    host_out = host_read.invoke({"file_path": str(host_file)})
    sb_out = sb_read.invoke({"file_path": sandbox_path})

    def numbered(text: str) -> str:
        return "\n".join(line for line in text.splitlines() if line and line[0].isdigit())

    assert numbered(host_out) == numbered(sb_out)


def test_real_glob_grep_parity(tmp_path: Path, real_sandbox):
    host_root = tmp_path / "host"
    host_root.mkdir()
    _seed(host_root)
    _seed_sandbox(real_sandbox)
    sb_root = Path(real_sandbox.workspace_dir)

    host_grep, host_glob = create_grep_tools(
        workspace_root=host_root, sandbox=None, permissions=None
    )
    sb_grep, sb_glob = create_grep_tools(
        workspace_root=sb_root, sandbox=real_sandbox, permissions=None
    )

    def rels(out: str, base: Path) -> set[str]:
        return {str(Path(p).relative_to(base)) for p in out.splitlines() if p.strip()}

    assert (
        rels(host_glob.invoke({"pattern": "**/*.py"}), host_root)
        == rels(sb_glob.invoke({"pattern": "**/*.py"}), sb_root)
        == {"a.py", "sub/c.py"}
    )
    if HAS_RG:
        assert (
            rels(host_grep.invoke({"pattern": "foo"}), host_root)
            == rels(sb_grep.invoke({"pattern": "foo"}), sb_root)
            == {"a.py", "b.md", "sub/c.py"}
        )


def test_real_edit_error_parity(tmp_path: Path, real_sandbox):
    sandbox_path = f"{real_sandbox.workspace_dir}/a.txt"
    real_sandbox.upload_files([(sandbox_path, b"alpha\n")])
    state = FileReadState()
    transport = SandboxFileTransport(real_sandbox)
    sb_read = create_read_tool(
        workspace_root=Path(real_sandbox.workspace_dir),
        permissions=None,
        state=state,
        transport=transport,
    )
    sb_edit = create_edit_tool(
        workspace_root=Path(real_sandbox.workspace_dir),
        permissions=None,
        state=state,
        transport=transport,
    )
    sb_read.invoke({"file_path": sandbox_path})
    out = sb_edit.invoke({"file_path": sandbox_path, "old_string": "missing", "new_string": "x"})
    assert "String to replace not found" in out
