from hagent.subagents.description import render_agent_tool_description


def _specs():
    return [
        {"name": "general-purpose", "description": "通用代理"},
        {"name": "Explore", "description": "只读探索代理"},
        {"name": "Plan", "description": "架构规划代理"},
    ]


def test_renders_available_agents_block():
    desc = render_agent_tool_description(_specs())
    assert "- general-purpose: 通用代理" in desc
    assert "- Explore: 只读探索代理" in desc
    assert "- Plan: 架构规划代理" in desc


def test_contains_cc_aligned_sections():
    desc = render_agent_tool_description(_specs())
    for kw in ("Available agent types", "When NOT to use", "Usage notes", "Example usage"):
        assert kw in desc


def test_avoids_prohibited_provenance():
    desc = render_agent_tool_description(_specs()).lower()
    for banned in ("claude code", "anthropic", "claude opus"):
        assert banned not in desc


def test_strips_unsupported_features():
    desc = render_agent_tool_description(_specs())
    for unsupported in ("run_in_background", "isolation:", "SendMessage", "team_name", "coordinator"):
        assert unsupported not in desc


def test_mentions_default_subagent_type_behavior():
    desc = render_agent_tool_description(_specs())
    assert "general-purpose" in desc
    assert "omit" in desc.lower() or "default" in desc.lower()


def test_handles_empty_specs_gracefully():
    desc = render_agent_tool_description([])
    assert "Available agent types" in desc
    assert "(none)" in desc.lower() or "no subagents" in desc.lower()
