from deepagents.backends import FilesystemBackend

from hagent.config import HagentConfig
from hagent.core import create_hagent


def test_create_hagent_registers_claude_file_tools_and_excludes_deepagents_tools(
    monkeypatch, tmp_path
):
    captured: dict = {}
    registered: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    def fake_register_harness_profile(key, profile):
        registered["key"] = key
        registered["profile"] = profile

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    monkeypatch.setattr("hagent.core.register_harness_profile", fake_register_harness_profile)

    backend = FilesystemBackend(root_dir=tmp_path, virtual_mode=False)
    create_hagent(config=HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False), backend=backend)

    tool_names = {tool.name for tool in captured["tools"]}
    assert {"Read", "Write", "Edit", "Bash", "Grep", "Glob"}.issubset(tool_names)
    assert not {"read_file", "write_file", "edit_file", "execute"} & tool_names
    assert registered["key"] == "anthropic:claude-sonnet-4-6"
    assert set(registered["profile"].excluded_tools) == {
        "read_file",
        "write_file",
        "edit_file",
        "execute",
        "write_todos",
        "grep",
        "glob",
        "ls",
    }


def test_claude_file_tools_share_file_state_metadata(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    backend = FilesystemBackend(root_dir=tmp_path, virtual_mode=False)
    create_hagent(config=HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False), backend=backend)

    file_tools = [tool for tool in captured["tools"] if tool.name in {"Read", "Write", "Edit"}]
    assert {tool.name for tool in file_tools} == {"Read", "Write", "Edit"}

    states = [tool.metadata["hagent_file_state"] for tool in file_tools]
    assert states[0] is states[1] is states[2]


def test_create_hagent_prioritizes_workspace_allow_file_permission(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    backend = FilesystemBackend(root_dir=tmp_path, virtual_mode=False)
    create_hagent(config=HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False), backend=backend)

    first_rule = captured["permissions"][0]
    assert first_rule.mode == "allow"
    assert set(first_rule.operations) == {"read", "write"}
    assert str(tmp_path.resolve()) in first_rule.paths
    assert f"{tmp_path.resolve()}/**" in first_rule.paths
