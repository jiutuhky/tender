import os

from hagent.backends import HagentLocalShellBackend


def test_local_shell_backend_uses_bash_for_brace_expansion(tmp_path):
    backend = HagentLocalShellBackend(root_dir=tmp_path, virtual_mode=False)

    result = backend.execute("mkdir -p app/{api/v1,core,models}")

    assert result.exit_code == 0
    assert (tmp_path / "app" / "api" / "v1").is_dir()
    assert (tmp_path / "app" / "core").is_dir()
    assert (tmp_path / "app" / "models").is_dir()
    assert not (tmp_path / "app" / "{api").exists()


def test_local_shell_backend_provides_basic_shell_environment(tmp_path):
    backend = HagentLocalShellBackend(root_dir=tmp_path, virtual_mode=False)

    result = backend.execute('printf "HOME=%s\\nPATH=%s\\n" "$HOME" "$PATH"')

    assert result.exit_code == 0
    assert f"HOME={os.path.expanduser('~')}" in result.output
    assert "PATH=" in result.output
    assert "PATH=\n" not in result.output
