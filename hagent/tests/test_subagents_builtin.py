from hagent.subagents.builtin import (
    BUILTIN_SUBAGENT_SPECS,
    EXPLORE,
    GENERAL_PURPOSE,
    PLAN,
)


def test_builtin_set_matches_cc():
    names = {spec["name"] for spec in BUILTIN_SUBAGENT_SPECS}
    assert names == {"general-purpose", "Explore", "Plan"}


def test_general_purpose_has_wildcard_tools():
    assert GENERAL_PURPOSE["tools"] == ["*"]
    assert "model" not in GENERAL_PURPOSE


def test_explore_is_read_only():
    disallowed = set(EXPLORE["disallowed_tools"])
    for t in ("Edit", "Write", "NotebookEdit"):
        assert t in disallowed
    assert EXPLORE.get("omit_claude_md") is True


def test_plan_is_read_only_architect():
    disallowed = set(PLAN["disallowed_tools"])
    for t in ("Edit", "Write", "NotebookEdit"):
        assert t in disallowed
    assert PLAN.get("omit_claude_md") is True


def test_builtin_prompts_are_simplified_chinese():
    for spec in BUILTIN_SUBAGENT_SPECS:
        chinese = [c for c in spec["system_prompt"] if "一" <= c <= "鿿"]
        assert len(chinese) >= 50


def test_builtin_prompts_have_no_provenance_terms():
    for spec in BUILTIN_SUBAGENT_SPECS:
        prompt = spec["system_prompt"].lower()
        for banned in ("claude code", "anthropic", "claude opus"):
            assert banned not in prompt
