from unittest.mock import MagicMock

from hagent.config import HagentConfig
from hagent.core import create_hagent


def test_agent_tool_present_with_three_builtin_in_description(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()
    agent_tool = next(t for t in captured["tools"] if t.name == "Agent")
    for name in ("general-purpose", "Explore", "Plan"):
        assert name in agent_tool.description


def test_subagent_compilation_uses_full_parent_tool_pool_for_general_purpose(monkeypatch):
    captured: dict = {}
    runnables_seen: dict = {}

    def spy_create_agent(**kw):
        runnables_seen[kw["name"]] = {"tools": list(kw["tools"]), "model": kw["model"]}
        return MagicMock()

    monkeypatch.setattr("hagent.subagents.compiler.create_agent", spy_create_agent)
    monkeypatch.setattr("hagent.core._create_deep_agent", lambda **kw: captured.update(kw) or object())

    create_hagent()

    gp = runnables_seen["general-purpose"]
    main_tool_names = {t.name for t in captured["tools"] if t.name != "Agent"}
    assert {t.name for t in gp["tools"]} == main_tool_names


def test_explore_subagent_does_not_get_edit_or_write_tool(monkeypatch):
    runnables_seen: dict = {}

    def spy_create_agent(**kw):
        runnables_seen[kw["name"]] = [t.name for t in kw["tools"]]
        return MagicMock()

    monkeypatch.setattr("hagent.subagents.compiler.create_agent", spy_create_agent)
    monkeypatch.setattr("hagent.core._create_deep_agent", lambda **kw: object())

    create_hagent()

    explore_tools = set(runnables_seen["Explore"])
    assert "Edit" not in explore_tools
    assert "Write" not in explore_tools
    assert "Bash" in explore_tools
    assert "Read" in explore_tools


def test_no_subagent_pins_unknown_model(monkeypatch):
    runnables_seen: dict = {}

    def spy_create_agent(**kw):
        runnables_seen[kw["name"]] = kw["model"]
        return MagicMock()

    monkeypatch.setattr("hagent.subagents.compiler.create_agent", spy_create_agent)
    monkeypatch.setattr("hagent.core._create_deep_agent", lambda **kw: object())

    create_hagent()

    for name, model in runnables_seen.items():
        assert getattr(model, "model", None), f"{name} model 必须解析为可调用模型，实际 {model}"


def test_subagents_inherit_anthropic_compatible_output_budget(monkeypatch):
    runnables_seen: dict = {}

    def spy_create_agent(**kw):
        runnables_seen[kw["name"]] = kw["model"]
        return MagicMock()

    monkeypatch.setattr("hagent.subagents.compiler.create_agent", spy_create_agent)
    monkeypatch.setattr("hagent.core._create_deep_agent", lambda **kw: object())

    create_hagent(
        config=HagentConfig(model="anthropic:qwen3.6-27b", langsmith_tracing=False)
    )

    assert runnables_seen["general-purpose"].model == "qwen3.6-27b"
    assert runnables_seen["general-purpose"].max_tokens == 32000
