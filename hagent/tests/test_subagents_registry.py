from pathlib import Path

import yaml
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from hagent.subagents.registry import assemble_subagents, compile_subagents


class _Args(BaseModel):
    x: int = 0


def _tool(name):
    return StructuredTool.from_function(name=name, description="t", func=lambda x=0: x, args_schema=_Args)


def _parent_tools():
    return [_tool("Bash"), _tool("Read"), _tool("Edit"), _tool("Write"), _tool("NotebookEdit")]


def test_default_returns_three_builtin_specs(tmp_path):
    specs = assemble_subagents(workspace=tmp_path, agents_dirs=[])
    names = {s["name"] for s in specs}
    assert names == {"general-purpose", "Explore", "Plan"}


def test_disable_builtin_returns_empty(tmp_path):
    specs = assemble_subagents(workspace=tmp_path, agents_dirs=[], disable_builtin=True)
    assert specs == []


def test_extra_subagents_override_same_name(tmp_path):
    extra = [{
        "name": "general-purpose",
        "description": "覆盖版",
        "system_prompt": "custom",
    }]
    specs = assemble_subagents(workspace=tmp_path, agents_dirs=[], extra_subagents=extra)
    gp = next(s for s in specs if s["name"] == "general-purpose")
    assert gp["description"] == "覆盖版"


def test_markdown_in_agents_dirs_takes_priority_over_builtin(tmp_path):
    d = tmp_path / "agents"
    d.mkdir()
    (d / "Explore.md").write_text(
        "---\n"
        + yaml.safe_dump({"name": "Explore", "description": "我的 Explore"}, allow_unicode=True, sort_keys=False)
        + "---\n自定义 Explore prompt\n",
        encoding="utf-8",
    )
    specs = assemble_subagents(workspace=tmp_path, agents_dirs=[d])
    explore = next(s for s in specs if s["name"] == "Explore")
    assert explore["description"] == "我的 Explore"


def test_default_agents_dirs_used_when_none_provided(tmp_path):
    d = tmp_path / ".hagent" / "agents"
    d.mkdir(parents=True)
    (d / "reviewer.md").write_text(
        "---\nname: reviewer\ndescription: 审查\n---\n你是 reviewer。\n",
        encoding="utf-8",
    )
    specs = assemble_subagents(workspace=tmp_path)
    assert any(s["name"] == "reviewer" for s in specs)


def test_project_root_agents_dir_discovered(tmp_path):
    # 仓库（project_root）与会话 workspace 是两个不同目录——server 运行时的真实情形：
    # workspace 是 /tmp 或容器内的一次性目录，agent 文件放在仓库的 .hagent/agents/。
    project_root = tmp_path / "repo"
    agents = project_root / ".hagent" / "agents"
    agents.mkdir(parents=True)
    (agents / "parser.md").write_text(
        "---\nname: parser\ndescription: 解析\n---\n你是 parser。\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "ws"
    workspace.mkdir()
    specs = assemble_subagents(workspace=workspace, project_root=project_root)
    assert any(s["name"] == "parser" for s in specs)


def test_project_root_none_does_not_scan_cwd(tmp_path):
    # project_root 为 None 时保持旧行为：只看 workspace + ~/.hagent，不引入 cwd。
    project_root = tmp_path / "repo"
    agents = project_root / ".hagent" / "agents"
    agents.mkdir(parents=True)
    (agents / "parser.md").write_text(
        "---\nname: parser\ndescription: 解析\n---\n你是 parser。\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "ws"
    workspace.mkdir()
    specs = assemble_subagents(workspace=workspace)  # 不传 project_root
    assert not any(s["name"] == "parser" for s in specs)


def test_agents_paths_env_overrides_defaults(tmp_path):
    custom = tmp_path / "custom"
    custom.mkdir()
    (custom / "envagent.md").write_text(
        "---\nname: envagent\ndescription: 来自 env\n---\nenv prompt\n",
        encoding="utf-8",
    )
    specs = assemble_subagents(workspace=tmp_path, agents_paths=str(custom))
    assert any(s["name"] == "envagent" for s in specs)


def test_compile_subagents_returns_runnables_keyed_by_name(monkeypatch):
    monkeypatch.setattr(
        "hagent.subagents.compiler.create_agent",
        lambda **kw: f"runnable-of-{kw['name']}",
    )
    specs = [
        {"name": "a", "description": "x", "system_prompt": "p", "tools": ["*"]},
        {"name": "b", "description": "y", "system_prompt": "q", "tools": ["*"]},
    ]
    runnables = compile_subagents(
        specs,
        parent_model="anthropic:claude-sonnet-4-6",
        parent_tools=_parent_tools(),
    )
    assert runnables == {"a": "runnable-of-a", "b": "runnable-of-b"}


def test_compile_empty_specs_returns_empty_dict():
    assert compile_subagents([], parent_model="m", parent_tools=[]) == {}


def test_priority_extras_beats_markdown_beats_builtin(tmp_path):
    """Locks the contract: extra_subagents > markdown > built-in for same name."""
    import yaml
    d = tmp_path / "agents"
    d.mkdir()
    (d / "Explore.md").write_text(
        "---\n"
        + yaml.safe_dump({"name": "Explore", "description": "markdown版"}, allow_unicode=True, sort_keys=False)
        + "---\n自定义 Explore prompt from markdown\n",
        encoding="utf-8",
    )
    extra = [{
        "name": "Explore",
        "description": "extra版",
        "system_prompt": "from extra_subagents",
    }]
    specs = assemble_subagents(workspace=tmp_path, agents_dirs=[d], extra_subagents=extra)
    explore = next(s for s in specs if s["name"] == "Explore")
    # extra wins both built-in and markdown
    assert explore["description"] == "extra版"
    assert explore["system_prompt"] == "from extra_subagents"
