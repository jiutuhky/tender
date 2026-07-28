from hagent.subagents import SubagentSpec
from hagent.subagents.types import resolve_model_alias


def test_subagent_spec_required_fields():
    spec: SubagentSpec = {
        "name": "x",
        "description": "y",
        "system_prompt": "z",
    }
    assert spec["name"] == "x"


def test_resolve_model_alias_known():
    assert resolve_model_alias("sonnet") == "anthropic:claude-sonnet-4-6"
    assert resolve_model_alias("opus") == "anthropic:claude-opus-4-7"
    assert resolve_model_alias("haiku") == "anthropic:claude-haiku-4-5"


def test_resolve_model_alias_inherit_returns_none():
    assert resolve_model_alias("inherit") is None


def test_resolve_model_alias_passthrough_for_provider_model_string():
    assert resolve_model_alias("anthropic:claude-sonnet-4-6") == "anthropic:claude-sonnet-4-6"
    assert resolve_model_alias("openai:gpt-5") == "openai:gpt-5"


def test_resolve_model_alias_none_returns_none():
    assert resolve_model_alias(None) is None
