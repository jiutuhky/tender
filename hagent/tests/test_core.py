from langchain_core.messages import AIMessage, HumanMessage

from hagent.config import HagentConfig
from hagent.core import create_hagent
from hagent.sanitize import (
    sanitize_anthropic_thinking_blocks,
    sanitize_anthropic_thinking_blocks_middleware,
)


def test_create_hagent_returns_runnable(monkeypatch):
    monkeypatch.setattr(
        "hagent.core._create_deep_agent",
        lambda **_kw: type(
            "FakeAgent",
            (),
            {"stream": lambda *_a, **_k: None, "invoke": lambda *_a, **_k: None},
        )(),
    )
    agent = create_hagent()
    assert hasattr(agent, "stream")
    assert hasattr(agent, "invoke")


def test_create_hagent_uses_base_prompt(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()
    assert "你是 Prose" in captured["system_prompt"]


def test_create_hagent_base_prompt_uses_claude_file_tool_names(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    create_hagent()

    system_prompt = captured["system_prompt"]
    assert "read_file" not in system_prompt
    assert "write_file" not in system_prompt
    assert "edit_file" not in system_prompt
    assert "Read" in system_prompt
    assert "Write" in system_prompt
    assert "Edit" in system_prompt


def test_create_hagent_base_prompt_mentions_task_tools(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    create_hagent()

    system_prompt = captured["system_prompt"]
    assert "TaskCreate" in system_prompt
    assert "TaskUpdate" in system_prompt
    assert "TaskList" in system_prompt
    assert "TaskGet" in system_prompt
    assert "write_todos" not in system_prompt


def test_create_hagent_base_prompt_mentions_skill_tool(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()

    system_prompt = captured["system_prompt"]
    assert "`Skill`" in system_prompt
    assert "/<skill-name>" in system_prompt
    assert "read_file" not in system_prompt


def test_create_hagent_injects_backend_workspace_into_prompt(tmp_path, monkeypatch):
    from deepagents.backends import FilesystemBackend

    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    workspace = tmp_path / "session-workspace"
    workspace.mkdir()
    backend = FilesystemBackend(root_dir=workspace, virtual_mode=False)

    create_hagent(backend=backend)

    assert "{{working_directory}}" not in captured["system_prompt"]
    assert f"主工作目录：{workspace}" in captured["system_prompt"]


def test_create_hagent_uses_filesystem_backend_and_keeps_permissions(monkeypatch):
    from deepagents.backends.protocol import SandboxBackendProtocol

    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()
    assert type(captured["backend"]).__name__ == "FilesystemBackend"
    assert not isinstance(captured["backend"], SandboxBackendProtocol)
    assert not hasattr(captured["backend"], "execute")
    assert "permissions" in captured
    assert len(captured["permissions"]) >= 2


def test_non_sandbox_backend_keeps_permissions(monkeypatch):
    """非 sandbox 后端（StateBackend 等）应保留 backend 和 permissions。"""
    from deepagents.backends import StateBackend

    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    backend = StateBackend()
    create_hagent(backend=backend)
    assert captured["backend"] is backend
    assert "permissions" in captured
    assert len(captured["permissions"]) >= 2


def test_execute_capable_backend_is_replaced_for_model_tools(tmp_path, monkeypatch):
    from hagent.backends import HagentLocalShellBackend

    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    shell_backend = HagentLocalShellBackend(root_dir=tmp_path, virtual_mode=False)

    create_hagent(backend=shell_backend)

    assert type(captured["backend"]).__name__ == "FilesystemBackend"
    assert not hasattr(captured["backend"], "execute")


def test_create_hagent_does_not_pass_subagents_to_deepagents(monkeypatch):
    """Hagent 自管 subagent，deepagents 不应收到 subagents 参数（应为 None）。"""
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()
    assert captured.get("subagents") is None


def test_create_hagent_disables_deepagents_general_purpose_subagent(monkeypatch):
    registered: dict = {}

    def fake_register(key, profile):
        registered["profile"] = profile

    monkeypatch.setattr("hagent.core.register_harness_profile", fake_register)
    monkeypatch.setattr("hagent.core._create_deep_agent", lambda **_kw: object())

    create_hagent()
    gp_profile = registered["profile"].general_purpose_subagent
    assert gp_profile is not None
    assert gp_profile.enabled is False


def test_create_hagent_adds_agent_tool_to_main_tools(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()
    tool_names = {t.name for t in captured["tools"]}
    assert "Agent" in tool_names


def test_create_hagent_registers_grep_and_glob_tools(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()
    tool_names = {t.name for t in captured["tools"]}
    assert {"Grep", "Glob"} <= tool_names


def test_create_hagent_excludes_deepagents_grep_glob_ls(monkeypatch):
    registered: dict = {}

    def fake_register(key, profile):
        registered["profile"] = profile

    monkeypatch.setattr("hagent.core.register_harness_profile", fake_register)
    monkeypatch.setattr("hagent.core._create_deep_agent", lambda **_kw: object())

    create_hagent()
    excluded = registered["profile"].excluded_tools
    assert {"grep", "glob", "ls"} <= set(excluded)


def test_agent_tool_description_lists_three_builtin_agents(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()
    agent_tool = next(t for t in captured["tools"] if t.name == "Agent")
    desc = agent_tool.description
    for name in ("general-purpose", "Explore", "Plan"):
        assert name in desc


def test_create_hagent_with_disable_builtin_omits_agent_tool(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    # agents_dirs=[] 隔离环境发现（project_root=Path.cwd() 会扫到仓库自带的 agent）：
    # 本例只验证「禁用内置 + 无 markdown agent → 无 Agent 工具」。
    create_hagent(disable_builtin_agents=True, agents_dirs=[])
    tool_names = {t.name for t in captured["tools"]}
    assert "Agent" not in tool_names


def test_create_hagent_extra_subagents_show_up_in_agent_tool_description(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    extra = [{
        "name": "reviewer",
        "description": "审查代码 PR",
        "system_prompt": "你是 reviewer。",
        "tools": ["Read"],
    }]
    create_hagent(extra_subagents=extra)
    agent_tool = next(t for t in captured["tools"] if t.name == "Agent")
    assert "reviewer" in agent_tool.description
    assert "审查代码 PR" in agent_tool.description


def test_create_hagent_loads_markdown_agents_from_workspace(tmp_path, monkeypatch):
    import yaml
    from deepagents.backends import FilesystemBackend

    agents_dir = tmp_path / ".hagent" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "reviewer.md").write_text(
        "---\n"
        + yaml.safe_dump({"name": "reviewer", "description": "审查"}, allow_unicode=True, sort_keys=False)
        + "---\n你是 reviewer。\n",
        encoding="utf-8",
    )
    backend = FilesystemBackend(root_dir=tmp_path, virtual_mode=False)

    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent(backend=backend)
    agent_tool = next(t for t in captured["tools"] if t.name == "Agent")
    assert "reviewer" in agent_tool.description


def test_create_hagent_uses_filesystem_backend_by_default(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()
    backend = captured["backend"]
    assert type(backend).__name__ == "FilesystemBackend"


def test_create_hagent_installs_thinking_block_sanitizer(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()

    assert any(m.name == "SanitizeAnthropicThinkingBlocks" for m in captured["middleware"])


def test_create_hagent_disables_summarization_middleware(monkeypatch):
    registered: dict = {}

    def fake_register_harness_profile(key, profile):
        registered["key"] = key
        registered["profile"] = profile

    monkeypatch.setattr("hagent.core.register_harness_profile", fake_register_harness_profile)
    monkeypatch.setattr("hagent.core._create_deep_agent", lambda **_kw: object())
    monkeypatch.delenv("HAGENT_MODEL", raising=False)

    create_hagent()

    assert registered["key"] == "anthropic:claude-sonnet-4-6"
    assert "SummarizationMiddleware" in registered["profile"].excluded_middleware
    assert "execute" in registered["profile"].excluded_tools
    assert "write_todos" in registered["profile"].excluded_tools


def test_create_hagent_raises_anthropic_compatible_output_budget(monkeypatch):
    registered: dict = {}

    def fake_register_provider_profile(key, profile):
        registered["key"] = key
        registered["profile"] = profile

    monkeypatch.setattr("hagent.core.register_provider_profile", fake_register_provider_profile)
    monkeypatch.setattr("hagent.core._create_deep_agent", lambda **_kw: object())

    create_hagent(
        config=HagentConfig(model="anthropic:qwen3.6-27b", langsmith_tracing=False)
    )

    assert registered["key"] == "anthropic:qwen3.6-27b"
    assert registered["profile"].init_kwargs["max_tokens"] == 32000


def test_create_hagent_preserves_known_claude_model_profile_budget(monkeypatch):
    registered: dict = {}

    def fake_register_provider_profile(key, profile):
        registered["key"] = key
        registered["profile"] = profile

    monkeypatch.setattr("hagent.core.register_provider_profile", fake_register_provider_profile)
    monkeypatch.setattr("hagent.core._create_deep_agent", lambda **_kw: object())

    create_hagent(
        config=HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False)
    )

    assert registered == {}


def test_create_hagent_disables_native_execute_and_adds_bash_tool(monkeypatch):
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

    create_hagent()

    tool_names = {tool.name for tool in captured["tools"]}
    bash_tool = next(tool for tool in captured["tools"] if tool.name == "Bash")
    assert "Bash" in tool_names
    assert "execute" not in tool_names
    assert "execute" in registered["profile"].excluded_tools
    assert "run_in_background" in bash_tool.description
    assert "dangerouslyDisableSandbox" in bash_tool.description


def test_create_hagent_bash_tool_runs_runtime(tmp_path, monkeypatch):
    from deepagents.backends import FilesystemBackend

    captured: dict = {}
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    backend = FilesystemBackend(root_dir=workspace, virtual_mode=False)

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    create_hagent(backend=backend)

    bash_tool = next(tool for tool in captured["tools"] if tool.name == "Bash")

    output = bash_tool.invoke({"command": "pwd"})

    assert str(workspace) in output


def test_create_hagent_default_bash_permissions_allow_pytest(tmp_path, monkeypatch):
    from deepagents.backends import FilesystemBackend

    captured: dict = {}
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    backend = FilesystemBackend(root_dir=workspace, virtual_mode=False)

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    create_hagent(
        config=HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False),
        backend=backend,
    )

    bash_tool = next(tool for tool in captured["tools"] if tool.name == "Bash")

    output = bash_tool.invoke({"command": "pytest --version"})

    assert "pytest" in output.lower()


def test_sanitize_anthropic_thinking_blocks_drops_signature_only_blocks():
    messages = [
        HumanMessage("next"),
        AIMessage(
            content=[
                {"type": "thinking", "signature": "sig", "index": 0},
                {"type": "text", "text": "answer", "index": 1},
            ],
            response_metadata={"model_provider": "anthropic"},
        ),
    ]

    cleaned = sanitize_anthropic_thinking_blocks(messages)

    assert cleaned[0] is messages[0]
    assert cleaned[1].content == [{"type": "text", "text": "answer", "index": 1}]
    assert messages[1].content[0]["type"] == "thinking"


def test_sanitize_anthropic_thinking_blocks_keeps_valid_thinking_blocks():
    messages = [
        AIMessage(
            content=[
                {
                    "type": "thinking",
                    "thinking": "reasoning",
                    "signature": "sig",
                    "index": 0,
                },
                {"type": "text", "text": "answer", "index": 1},
            ],
            response_metadata={"model_provider": "anthropic"},
        ),
    ]

    cleaned = sanitize_anthropic_thinking_blocks(messages)

    assert cleaned[0] is messages[0]


def _build_bad_messages():
    return [
        HumanMessage("hi"),
        AIMessage(
            content=[
                {"type": "thinking", "signature": "sig", "index": 0},
                {
                    "type": "tool_use",
                    "name": "Bash",
                    "id": "tu_1",
                    "input": {},
                    "index": 1,
                },
            ],
            response_metadata={"model_provider": "anthropic"},
        ),
    ]


class _FakeRequest:
    def __init__(self, messages):
        self.messages = messages

    def override(self, *, messages):
        return _FakeRequest(messages)


def test_sanitize_middleware_runs_on_sync_path():
    """wrap_model_call must scrub bad thinking blocks before reaching the model."""
    captured: dict = {}

    def handler(req: _FakeRequest) -> str:
        captured["messages"] = req.messages
        return "ok"

    result = sanitize_anthropic_thinking_blocks_middleware.wrap_model_call(
        _FakeRequest(_build_bad_messages()), handler
    )

    assert result == "ok"
    ai = captured["messages"][1]
    assert all(b.get("type") != "thinking" for b in ai.content)


def test_sanitize_middleware_runs_on_async_path():
    """awrap_model_call must also scrub — LangGraph's sync .stream() bridges to async
    internally, so a sync-only middleware would silently no-op in production."""
    import asyncio

    captured: dict = {}

    async def handler(req: _FakeRequest) -> str:
        captured["messages"] = req.messages
        return "ok"

    result = asyncio.run(
        sanitize_anthropic_thinking_blocks_middleware.awrap_model_call(
            _FakeRequest(_build_bad_messages()), handler
        )
    )

    assert result == "ok"
    ai = captured["messages"][1]
    assert all(b.get("type") != "thinking" for b in ai.content)


def test_sanitize_middleware_is_registered_on_both_hooks():
    """Regression guard: the @wrap_model_call decorator only attaches the sync hook,
    which silently no-ops on async paths. Both hooks must be overridden."""
    from langchain.agents.middleware import AgentMiddleware

    cls = type(sanitize_anthropic_thinking_blocks_middleware)
    assert cls.wrap_model_call is not AgentMiddleware.wrap_model_call
    assert cls.awrap_model_call is not AgentMiddleware.awrap_model_call


def test_create_hagent_raises_when_disable_builtin_without_general_purpose(monkeypatch):
    """Footgun guard: disabling built-ins + providing extras that don't include
    'general-purpose' must fail fast — the Agent tool's default route would
    otherwise be broken at runtime."""
    monkeypatch.setattr("hagent.core._create_deep_agent", lambda **_kw: object())
    import pytest

    extra = [{
        "name": "reviewer",
        "description": "审查 PR",
        "system_prompt": "你是 reviewer。",
        "tools": ["Read"],
    }]
    with pytest.raises(ValueError, match="general-purpose"):
        create_hagent(disable_builtin_agents=True, extra_subagents=extra)


def test_create_hagent_accepts_custom_general_purpose_when_builtin_disabled(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr("hagent.core._create_deep_agent", lambda **kw: captured.update(kw) or object())

    extra = [{
        "name": "general-purpose",
        "description": "自定义通用代理",
        "system_prompt": "你是自定义 GP。",
        "tools": ["Read"],
    }]
    create_hagent(disable_builtin_agents=True, extra_subagents=extra)
    tool_names = {t.name for t in captured["tools"]}
    assert "Agent" in tool_names
