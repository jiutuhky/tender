from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from hagent.subagents.tools import resolve_subagent_tools


class _Args(BaseModel):
    x: int = 0


def _make_tool(name: str):
    return StructuredTool.from_function(name=name, description="t", func=lambda x=0: x, args_schema=_Args)


def _names(tools):
    return [t.name for t in tools]


def test_wildcard_keeps_all_parent_tools():
    parent = [_make_tool("Bash"), _make_tool("Read"), _make_tool("Write")]
    resolved, unknown = resolve_subagent_tools({"tools": ["*"]}, parent)
    assert _names(resolved) == ["Bash", "Read", "Write"]
    assert unknown == []


def test_omitted_tools_inherits_all_parent_tools():
    parent = [_make_tool("Bash"), _make_tool("Read")]
    resolved, unknown = resolve_subagent_tools({}, parent)
    assert _names(resolved) == ["Bash", "Read"]


def test_allowlist_filters_parent_tools():
    parent = [_make_tool("Bash"), _make_tool("Read"), _make_tool("Write")]
    resolved, unknown = resolve_subagent_tools({"tools": ["Read", "Write"]}, parent)
    assert _names(resolved) == ["Read", "Write"]


def test_disallowed_tools_excludes_from_wildcard():
    parent = [_make_tool("Bash"), _make_tool("Read"), _make_tool("Edit"), _make_tool("Write")]
    resolved, unknown = resolve_subagent_tools(
        {"tools": ["*"], "disallowed_tools": ["Edit", "Write"]}, parent
    )
    assert _names(resolved) == ["Bash", "Read"]


def test_disallowed_combined_with_allowlist():
    parent = [_make_tool("Bash"), _make_tool("Read"), _make_tool("Write")]
    resolved, unknown = resolve_subagent_tools(
        {"tools": ["Bash", "Read", "Write"], "disallowed_tools": ["Write"]}, parent
    )
    assert _names(resolved) == ["Bash", "Read"]


def test_unknown_tool_names_returned_separately():
    parent = [_make_tool("Bash")]
    resolved, unknown = resolve_subagent_tools({"tools": ["Bash", "Ghost"]}, parent)
    assert _names(resolved) == ["Bash"]
    assert unknown == ["Ghost"]
