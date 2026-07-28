# Hagent Subagents Alignment Implementation Plan

> **存档说明**：本 plan 产出自已退役的 superpowers 工作流，仅作历史参考；新工作一律走仓根 tickets.md（Matt 契约）。

**Goal:** 把 Hagent 的 subagent 能力与行为完整对齐到 Claude Code（CC）：CC 风格内置代理集（`general-purpose`/`Explore`/`Plan`，简体中文 prompt）；每个代理可声明 `tools` / `disallowedTools` / `model`；从 `~/.hagent/agents/`、`<workspace>/agents/`、`<workspace>/.hagent/agents/` 自动加载 markdown agent 文件；**独立实现** 一个名为 `Agent` 的工具（CC schema：`description` 短摘要 + `prompt` 完整任务 + `subagent_type?` 默认 `general-purpose`），不再使用 deepagents 注册的 `task` 工具；CC 风格的工具描述（含可用代理列表 + 何时用/不用 + 示例）；以及主 base prompt 新增的「使用 subagent」段。本计划范围限定为**同步、单回合**的 subagent 调用；async / `run_in_background`、worktree 隔离、SendMessage / team_name、agent memory、skills / MCP / hooks per-agent、`permissionMode`、`maxTurns`、`model` 字段（调用时模型覆盖）不在本期。

**Architecture:** 把当前 `src/hagent/subagents.py`（单文件 RESEARCHER/CODER）升级为 `src/hagent/subagents/` 包，并完全自管 subagent 链路：

- **不让 deepagents 注册 SubAgentMiddleware** —— 给 `create_deep_agent` 传 `subagents=None`，并在 `HarnessProfile.general_purpose_subagent` 设置 `enabled=False` 抑制默认 GP；deepagents 因此既不会注入 `task` 工具，也不会自动追加 `general-purpose` subagent
- **`compiler.compile_subagent_runnable(spec, parent_model, parent_tools)`** —— 用 `langchain.agents.create_agent(model, tools, system_prompt, name)` 直接编译每个 subagent；不挂 `FilesystemMiddleware` / `TodoListMiddleware` / `SummarizationMiddleware`，因为这些 deepagents 内置中间件注入的 `read_file` / `write_file` / `edit_file` / `write_todos` 已被 Hagent 替换成 `Read` / `Write` / `Edit` / `TaskCreate` 等自研工具
- **`agent_tool.build_agent_tool(runnables, description)`** —— 返回名为 `Agent` 的 `StructuredTool`，schema 为 `AgentToolInput`：`description: str`（短摘要，3-5 词）+ `prompt: str`（完整任务）+ `subagent_type: str | None = None`（默认 `general-purpose`）；运行时按 deepagents `_build_task_tool` 同款逻辑路由：取 `runtime.state`（去掉 `messages` / `todos` / `structured_response`）+ `HumanMessage(content=prompt)` → 选中的 runnable.invoke → 取最后一条 message text，返回 `Command(update={"messages": [ToolMessage(content, tool_call_id=...)]})`
- **`description.render_agent_tool_description(specs)`** —— 渲染 CC 风格描述文本：title + Available agent types 列表 + When NOT to use + Usage notes + Examples，不掺任何 Claude Code / Anthropic 字眼
- **`registry.assemble_subagents(...)`** —— built-in / markdown / `extra_subagents` 三档优先级合并，去重；返回 `list[SubagentSpec]` 给上游 compile
- **`core.py`** —— 装配 parent tools → `assemble_subagents` → 逐个 `compile_subagent_runnable` → `build_agent_tool` → 把 `Agent` 工具追加到 `tools=[...]`；`_create_deep_agent` 传 `subagents=None`；`HarnessProfile.general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)`

Subagent 之间的隔离仍依赖 `langchain.agents.create_agent` 内置 graph 的 state 隔离；调用方文件权限通过 parent 注入的 `Read` / `Write` / `Edit` 自研工具（`permissions_for_workspace` 已绑定的实例）自然继承，per-agent permissions / tools / model 通过 spec 在 compile 阶段固化（本期不实现 runtime model 覆盖）。

**Tech Stack:** Python 3.12+、deepagents 0.5.9（仅复用 `create_deep_agent` 主链路 + `HarnessProfile` + `GeneralPurposeSubagentProfile`）、`langchain.agents.create_agent`（直接调用）、`langchain_core.tools.StructuredTool` / `ToolRuntime` / `langgraph.types.Command`、PyYAML 6.x（已装）、pytest、monkeypatch。

---

## Required Context

- `HarnessProfile.general_purpose_subagent: GeneralPurposeSubagentProfile | None = None`（`.venv/lib/python3.12/site-packages/deepagents/profiles/harness/harness_profiles.py:710`）。`GeneralPurposeSubagentProfile(enabled=False)` 让 deepagents `graph.py:618` 的自动追加跳过。结合 `subagents=None`，`graph.py:684` 的 `if inline_subagents:` 条件不成立，`SubAgentMiddleware` 完全不会进 middleware stack，因此 `task` 工具不会被注入主 agent。
- deepagents 0.5.9 `_build_task_tool`（`middleware/subagents.py:386-526`）的路由逻辑可复用范本：取 `runtime.tool_call_id`（缺失则 raise）、`runtime.state` 排除 `messages`/`todos`/`structured_response`、注入新的 `HumanMessage`、`subagent.invoke(state, config)`、最后从 `result["messages"][-1].text.rstrip()` 取文本、`Command(update={...})` 回流。本计划在 `agent_tool.py` 写自己的版本，schema 改为 CC 的 description+prompt+subagent_type，工具名 `Agent`。
- `langchain.agents.create_agent(model, tools, system_prompt, name)` 返回 `CompiledStateGraph`，state 含 `messages` 键，可直接被我们的 Agent 工具 invoke。subagent 的中间件栈我们刻意不挂 `FilesystemMiddleware` / `TodoListMiddleware` —— 这两个会注入 `read_file` / `write_file` / `edit_file` / `write_todos` 等 deepagents 工具，而 Hagent 已把这些禁用并用 `Read`/`Write`/`Edit`/`TaskCreate/...` 替代；subagent 通过 parent_tools 直接拿到 Hagent 工具集即可。`PatchToolCallsMiddleware` / `AnthropicPromptCachingMiddleware` 也先不加，本期保持 subagent 中间件栈为空，必要时后续 plan 再补 prompt caching。
- CC `AgentTool.prompt`（`docs/cc-recovered-main/src/tools/AgentTool/prompt.ts`）的非 fork 分支模板章节：标题段 → `Available agent types and the tools they have access to:` → `When NOT to use the ${AGENT_TOOL_NAME} tool` → `Usage notes` → 示例。本计划在 `description.py` 复刻这些段落，剔除 CC 专属（`run_in_background` / `isolation` / `SendMessage` / `team_name` / coordinator）。`AGENT_TOOL_NAME = 'Agent'`。
- CC 内置代理：`general-purpose`（`tools=['*']`，inherit model，prompt 与主 agent 同质）；`Explore`（`disallowedTools=[Edit, Write, NotebookEdit, Agent, ExitPlanMode]`、`omitClaudeMd=true`、极强只读 prompt）；`Plan`（同 Explore 的 disallowed，软件架构师 prompt、`omitClaudeMd=true`）。本计划落地这三个，prompt 用简体中文重写（避开 `check_base_prompt.sh` 禁用词；`Agent` / `ExitPlanMode` 在 Hagent 这边不存在或仍叫 `Agent`，因此 disallowed 只保留 `Edit` / `Write` / `NotebookEdit`）。
- CC markdown agent 文件 frontmatter：`name` / `description` / `tools` / `disallowedTools` / `model` / `color` / `permissionMode` / `maxTurns` / `skills` / `mcpServers` / `hooks` / `background` / `memory` / `isolation` / `initialPrompt` / `requiredMcpServers`。本期识别并落地 `name` / `description` / `tools` / `disallowedTools` / `model`（别名映射） / `color`；其余字段**识别但忽略并记 warning**，便于后续 plan 渐进启用。
- 现存测试 `tests/test_subagents.py` 与 `tests/test_core.py::test_create_hagent_attaches_subagents` 假定 RESEARCHER / CODER。本计划替换内置集，这两个测试同步更新。
- `scripts/check_base_prompt.sh` 禁用词：`Claude Code` / `Anthropic` / `Claude Opus` / `claude-opus-` / `write_todos`；必现词：`TaskCreate` / `TaskGet` / `TaskUpdate` / `TaskList`；`decisions.md` 必须覆盖固定章节。新增「使用 subagent」段不得违反任一约束。
- 模型别名（subagent spec 的 `model` 字段）：`sonnet` / `opus` / `haiku` / `inherit` / 已是 `provider:id` 形式的直通。`inherit` → spec 里删掉 `model` 字段，回退到 parent。**注意：本期不实现「Agent 工具调用时 runtime 覆盖 model」**——subagent runnable 在 `create_hagent` 时编译，model 固化；CC schema 里的 `model` 入参不收，留 TODO 给后续 plan。

## File Structure

Create:

- `src/hagent/subagents/__init__.py` — 公开 API
- `src/hagent/subagents/types.py` — `SubagentSpec` TypedDict、`MODEL_ALIASES`、`resolve_model_alias`
- `src/hagent/subagents/tools.py` — `resolve_subagent_tools(spec, parent_tools)`
- `src/hagent/subagents/builtin.py` — `GENERAL_PURPOSE` / `EXPLORE` / `PLAN`、`BUILTIN_SUBAGENT_SPECS`
- `src/hagent/subagents/loader.py` — `load_markdown_agents(dirs)`
- `src/hagent/subagents/compiler.py` — `compile_subagent_runnable(spec, parent_model, parent_tools)`
- `src/hagent/subagents/agent_tool.py` — `AgentToolInput`、`build_agent_tool(runnables, description)`
- `src/hagent/subagents/description.py` — `render_agent_tool_description(specs)`
- `src/hagent/subagents/registry.py` — `assemble_subagents(...)`、`compile_subagents(specs, parent_model, parent_tools)`

Delete:

- `src/hagent/subagents.py`

Modify:

- `src/hagent/core.py` — 替换 subagent 接线：本地 compile + 注册 `Agent` 工具 + 关闭 deepagents subagent 机制
- `prompts/hagent_base.zh.md` — 在 `# Using your tools` 之后新增 `# 使用 subagent` 段（讲 `Agent` 工具）
- `prompts/decisions.md` — 追加变更记录
- `CLAUDE.md` — 更新「架构」表对 `subagents/` 包的描述

Test:

- `tests/test_subagents.py` — 改写为新 API 的 types 测试
- `tests/test_subagents_tools.py`
- `tests/test_subagents_builtin.py`
- `tests/test_subagents_loader.py`
- `tests/test_subagents_compiler.py`
- `tests/test_subagents_agent_tool.py`
- `tests/test_subagents_description.py`
- `tests/test_subagents_registry.py`
- `tests/test_subagents_e2e_mock.py`
- `tests/test_core.py` — 更新 + 新增 5 个用例

---

### Task 1: 公开类型与模型别名

**Files:**
- Create: `src/hagent/subagents/__init__.py`
- Create: `src/hagent/subagents/types.py`
- Delete: `src/hagent/subagents.py`
- Test: `tests/test_subagents.py`（改写）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_subagents.py
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
```

- [ ] **Step 2: 跑测试验证失败**

Run: `pytest tests/test_subagents.py -v`
Expected: ImportError

- [ ] **Step 3: 切换文件 / 目录**

```bash
git rm src/hagent/subagents.py
mkdir -p src/hagent/subagents
```

- [ ] **Step 4: 写 types.py**

```python
# src/hagent/subagents/types.py
from __future__ import annotations

from typing import NotRequired, TypedDict

MODEL_ALIASES: dict[str, str | None] = {
    "sonnet": "anthropic:claude-sonnet-4-6",
    "opus": "anthropic:claude-opus-4-7",
    "haiku": "anthropic:claude-haiku-4-5",
    "inherit": None,
}


def resolve_model_alias(model: str | None) -> str | None:
    if model is None:
        return None
    if model in MODEL_ALIASES:
        return MODEL_ALIASES[model]
    return model


class SubagentSpec(TypedDict, total=False):
    name: str
    description: str
    system_prompt: str
    tools: NotRequired[list[str]]
    disallowed_tools: NotRequired[list[str]]
    model: NotRequired[str | None]
    color: NotRequired[str]
    omit_claude_md: NotRequired[bool]
    source: NotRequired[str]
```

- [ ] **Step 5: 写 `__init__.py` 最小版**

```python
# src/hagent/subagents/__init__.py
from hagent.subagents.types import SubagentSpec, resolve_model_alias

__all__ = ["SubagentSpec", "resolve_model_alias"]
```

- [ ] **Step 6: 跑测试验证通过**

Run: `pytest tests/test_subagents.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add src/hagent/subagents/ tests/test_subagents.py
git commit -m "refactor(subagents): split subagents.py into package with SubagentSpec and aliases"
```

---

### Task 2: 工具解析（allowlist / disallowed / wildcard）

**Files:**
- Create: `src/hagent/subagents/tools.py`
- Test: `tests/test_subagents_tools.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_subagents_tools.py
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
```

- [ ] **Step 2: 跑测试验证失败**

Run: `pytest tests/test_subagents_tools.py -v`
Expected: ModuleNotFoundError

- [ ] **Step 3: 写 tools.py**

```python
# src/hagent/subagents/tools.py
from __future__ import annotations

from typing import Any, Sequence


def resolve_subagent_tools(
    spec: dict[str, Any],
    parent_tools: Sequence[Any],
) -> tuple[list[Any], list[str]]:
    requested = spec.get("tools")
    disallowed = set(spec.get("disallowed_tools") or [])

    name_to_tool = {t.name: t for t in parent_tools}
    unknown: list[str] = []

    if requested is None or requested == ["*"]:
        resolved = list(parent_tools)
    else:
        resolved = []
        seen: set[str] = set()
        for name in requested:
            if name in name_to_tool and name not in seen:
                resolved.append(name_to_tool[name])
                seen.add(name)
            elif name not in name_to_tool:
                unknown.append(name)

    if disallowed:
        resolved = [t for t in resolved if t.name not in disallowed]

    return resolved, unknown
```

- [ ] **Step 4: 跑测试验证通过**

Run: `pytest tests/test_subagents_tools.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/hagent/subagents/tools.py tests/test_subagents_tools.py
git commit -m "feat(subagents): add resolve_subagent_tools (wildcard/allow/disallow)"
```

---

### Task 3: 三个内置 subagent（zh-CN）

**Files:**
- Create: `src/hagent/subagents/builtin.py`
- Test: `tests/test_subagents_builtin.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_subagents_builtin.py
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
```

- [ ] **Step 2: 跑测试验证失败**

Run: `pytest tests/test_subagents_builtin.py -v`
Expected: ModuleNotFoundError

- [ ] **Step 3: 写 builtin.py**

```python
# src/hagent/subagents/builtin.py
from __future__ import annotations

from hagent.subagents.types import SubagentSpec

GENERAL_PURPOSE: SubagentSpec = {
    "name": "general-purpose",
    "description": (
        "通用子代理：用于研究复杂问题、跨多个文件搜索代码、执行多步骤任务。"
        "当你不确定关键字或文件位于何处、可能需要多轮搜索时优先用它，"
        "可以隔离主对话上下文。它拥有与主代理相同的工具集。"
    ),
    "system_prompt": (
        "你是 Hagent 的 general-purpose 子代理。根据调用方给出的任务完整执行，"
        "不要半途而废，但也不要过度发挥。你的强项：在大型代码库里搜索代码、配置、模式；"
        "分析多个文件理解系统架构；研究需要多轮探索的复杂问题；执行多步骤的调查任务。\n\n"
        "工作准则：\n"
        "- 搜索：不知道内容在哪里时先广撒网；知道具体路径时直接用 Read。\n"
        "- 分析：先广后窄；第一种策略没结果时换一种策略，多试几种命名约定与目录布局。\n"
        "- 务必彻底：检查多个位置、考虑不同命名、查相关文件。\n"
        "- 除非绝对必要，不要新建文件；优先编辑已有文件，绝不主动创建 *.md / README。\n"
        "- 完成后只回报关键发现：调用方会把它转述给最终用户，所以只需要要点，"
        "不要堆砌中间工具输出。"
    ),
    "tools": ["*"],
}

_READ_ONLY_DISALLOWED = ["Edit", "Write", "NotebookEdit"]

EXPLORE: SubagentSpec = {
    "name": "Explore",
    "description": (
        "快速只读探索代理。用于按 glob 模式找文件（如 src/**/*.py）、"
        "按关键字 grep 代码、回答关于代码库的具体问题。"
        "调用时请指定彻底程度：quick（基础搜索）/medium（中等探索）/very thorough（全面分析）。"
    ),
    "system_prompt": (
        "你是 Hagent 的 Explore 子代理，文件搜索与代码定位专家。\n\n"
        "=== 严格只读模式：禁止任何文件修改 ===\n"
        "你被明确禁止：\n"
        "- 创建新文件（任何形式的 Write / touch / 文件创建）\n"
        "- 修改已有文件（任何 Edit 操作）\n"
        "- 删除文件（rm 或任何删除）\n"
        "- 移动 / 复制文件（mv / cp）\n"
        "- 在任何位置（包括 /tmp）创建临时文件\n"
        "- 使用 > / >> / | / heredoc 写入文件\n"
        "- 运行任何会改变系统状态的命令\n\n"
        "你的角色仅是搜索与分析已有代码。你没有文件修改工具，尝试也会失败。\n\n"
        "工作准则：\n"
        "- Read 用于你已经知道路径的具体文件读取\n"
        "- Bash 仅用于只读操作（ls / git status / git log / git diff / find / grep / cat / head / tail）\n"
        "- 严禁用 Bash 执行 mkdir / touch / rm / cp / mv / git add / git commit / npm install / pip install 等\n"
        "- 根据调用方指定的彻底程度调整搜索深度\n"
        "- 最终报告作为常规消息回复，不要尝试通过创建文件来传递结果\n"
        "- 尽可能并行触发 grep / 文件读取，效率优先\n\n"
        "高效完成搜索任务，把发现清晰汇报。"
    ),
    "tools": ["*"],
    "disallowed_tools": list(_READ_ONLY_DISALLOWED),
    "omit_claude_md": True,
}

PLAN: SubagentSpec = {
    "name": "Plan",
    "description": (
        "架构与实现规划代理。用于在动手前梳理实现策略：给出分步骤实现计划、"
        "找出关键文件、权衡架构取舍。"
    ),
    "system_prompt": (
        "你是 Hagent 的 Plan 子代理，软件架构与规划专家。你的职责是探索代码库、设计实现方案。\n\n"
        "=== 严格只读模式：禁止任何文件修改 ===\n"
        "禁止事项同 Explore：不得创建、修改、删除、移动文件，不得用 Bash 改变系统状态。"
        "你没有文件修改工具。\n\n"
        "工作流程：\n"
        "1. 理解需求：聚焦调用方提出的要求与视角。\n"
        "2. 充分探索：读取被指明的文件；用 Bash / Read 等只读手段查找模式与现有约定、"
        "理解当前架构、识别可类比的已有特性、跟踪相关代码路径。\n"
        "3. 设计方案：基于探索结果给出实现思路，考虑取舍，遵循已有模式。\n"
        "4. 细化计划：给出分步骤实现策略、依赖与顺序、可能的难点。\n\n"
        "输出末尾必须包含一节：\n\n"
        "### 实现关键文件\n"
        "列出 3-5 个对实现该计划最关键的文件路径。\n\n"
        "记住：你只能探索与规划，绝不能写、改、删任何文件。"
    ),
    "tools": ["*"],
    "disallowed_tools": list(_READ_ONLY_DISALLOWED),
    "omit_claude_md": True,
}

BUILTIN_SUBAGENT_SPECS: list[SubagentSpec] = [GENERAL_PURPOSE, EXPLORE, PLAN]
```

- [ ] **Step 4: 跑测试验证通过**

Run: `pytest tests/test_subagents_builtin.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/hagent/subagents/builtin.py tests/test_subagents_builtin.py
git commit -m "feat(subagents): add CC-aligned builtin agents (general-purpose, Explore, Plan)"
```

---

### Task 4: Markdown agent 文件加载器

**Files:**
- Create: `src/hagent/subagents/loader.py`
- Test: `tests/test_subagents_loader.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_subagents_loader.py
import logging
from pathlib import Path

import yaml

from hagent.subagents.loader import load_markdown_agents


def _write(path: Path, frontmatter: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False)
    path.write_text(f"---\n{fm}---\n{body}", encoding="utf-8")


def test_load_basic_agent(tmp_path):
    _write(tmp_path / "reviewer.md", {"name": "reviewer", "description": "审查代码"}, "你是 reviewer。")
    specs = load_markdown_agents([tmp_path])
    assert len(specs) == 1
    assert specs[0]["name"] == "reviewer"
    assert specs[0]["description"] == "审查代码"
    assert specs[0]["system_prompt"].strip() == "你是 reviewer。"
    assert specs[0]["source"] == str(tmp_path)


def test_load_with_tools_and_disallowed_and_model(tmp_path):
    _write(
        tmp_path / "researcher.md",
        {
            "name": "researcher",
            "description": "调研代理",
            "tools": ["Read", "Bash"],
            "disallowedTools": ["Bash"],
            "model": "haiku",
            "color": "blue",
        },
        "调研代理 system prompt。",
    )
    specs = load_markdown_agents([tmp_path])
    assert specs[0]["tools"] == ["Read", "Bash"]
    assert specs[0]["disallowed_tools"] == ["Bash"]
    assert specs[0]["model"] == "haiku"
    assert specs[0]["color"] == "blue"


def test_missing_name_or_description_is_skipped(tmp_path):
    _write(tmp_path / "no_name.md", {"description": "x"}, "body")
    _write(tmp_path / "no_desc.md", {"name": "x"}, "body")
    assert load_markdown_agents([tmp_path]) == []


def test_unsupported_fields_are_logged_and_ignored(tmp_path, caplog):
    _write(
        tmp_path / "fancy.md",
        {
            "name": "fancy",
            "description": "演示",
            "permissionMode": "plan",
            "maxTurns": 7,
            "skills": ["a"],
            "mcpServers": ["x"],
            "hooks": {"Stop": []},
            "memory": "user",
            "isolation": "worktree",
            "background": True,
        },
        "正文",
    )
    with caplog.at_level(logging.WARNING, logger="hagent.subagents.loader"):
        specs = load_markdown_agents([tmp_path])
    assert specs[0]["name"] == "fancy"
    for key in ("permissionMode", "maxTurns", "skills", "mcpServers", "hooks", "memory", "isolation", "background"):
        assert key not in specs[0]
        assert key in caplog.text


def test_dir_priority_later_overrides_earlier(tmp_path):
    user = tmp_path / "user"
    project = tmp_path / "project"
    _write(user / "x.md", {"name": "x", "description": "user版"}, "u")
    _write(project / "x.md", {"name": "x", "description": "project版"}, "p")
    specs = load_markdown_agents([user, project])
    by_name = {s["name"]: s for s in specs}
    assert by_name["x"]["description"] == "project版"


def test_missing_directory_is_silently_ignored(tmp_path):
    assert load_markdown_agents([tmp_path / "does_not_exist"]) == []


def test_non_md_files_are_ignored(tmp_path):
    (tmp_path / "README.txt").write_text("not an agent", encoding="utf-8")
    assert load_markdown_agents([tmp_path]) == []


def test_invalid_yaml_is_skipped_with_warning(tmp_path, caplog):
    (tmp_path / "bad.md").write_text("---\nname: [unclosed\n---\nbody", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="hagent.subagents.loader"):
        specs = load_markdown_agents([tmp_path])
    assert specs == []
    assert "bad.md" in caplog.text
```

- [ ] **Step 2: 跑测试验证失败**

Run: `pytest tests/test_subagents_loader.py -v`
Expected: ModuleNotFoundError

- [ ] **Step 3: 写 loader.py**

```python
# src/hagent/subagents/loader.py
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable

import yaml

from hagent.subagents.types import SubagentSpec

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
_IGNORED_FRONTMATTER_KEYS = (
    "permissionMode",
    "maxTurns",
    "skills",
    "mcpServers",
    "hooks",
    "memory",
    "isolation",
    "background",
    "initialPrompt",
    "requiredMcpServers",
)


def _parse_one(path: Path) -> SubagentSpec | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as err:
        logger.warning("failed to read %s: %s", path, err)
        return None

    m = _FRONTMATTER_RE.match(text)
    if not m:
        logger.warning("no YAML frontmatter in %s", path)
        return None
    raw_fm, body = m.group(1), m.group(2)

    try:
        fm = yaml.safe_load(raw_fm) or {}
    except yaml.YAMLError as err:
        logger.warning("invalid YAML frontmatter in %s: %s", path, err)
        return None
    if not isinstance(fm, dict):
        logger.warning("frontmatter in %s is not a mapping", path)
        return None

    name = fm.get("name")
    description = fm.get("description")
    if not isinstance(name, str) or not name.strip():
        logger.warning("agent %s missing required 'name'", path)
        return None
    if not isinstance(description, str) or not description.strip():
        logger.warning("agent %s missing required 'description'", path)
        return None

    spec: SubagentSpec = {
        "name": name.strip(),
        "description": description.strip(),
        "system_prompt": body.strip(),
        "source": str(path.parent),
    }
    tools = fm.get("tools")
    if isinstance(tools, list):
        spec["tools"] = [str(t) for t in tools]
    disallowed = fm.get("disallowedTools")
    if isinstance(disallowed, list):
        spec["disallowed_tools"] = [str(t) for t in disallowed]
    model = fm.get("model")
    if isinstance(model, str) and model.strip():
        spec["model"] = model.strip()
    color = fm.get("color")
    if isinstance(color, str) and color.strip():
        spec["color"] = color.strip()

    ignored = [k for k in _IGNORED_FRONTMATTER_KEYS if k in fm]
    if ignored:
        logger.warning(
            "agent %s declares unsupported keys %s; ignored in this release",
            path,
            ignored,
        )
    return spec


def load_markdown_agents(dirs: Iterable[Path]) -> list[SubagentSpec]:
    seen_by_name: dict[str, SubagentSpec] = {}
    for raw in dirs:
        d = Path(raw)
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.md")):
            spec = _parse_one(path)
            if spec is None:
                continue
            seen_by_name[spec["name"]] = spec  # 后到的覆盖先到的
    return list(seen_by_name.values())
```

- [ ] **Step 4: 跑测试验证通过**

Run: `pytest tests/test_subagents_loader.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/hagent/subagents/loader.py tests/test_subagents_loader.py
git commit -m "feat(subagents): add markdown agent loader"
```

---

### Task 5: Subagent runnable 编译器

**Files:**
- Create: `src/hagent/subagents/compiler.py`
- Test: `tests/test_subagents_compiler.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_subagents_compiler.py
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from hagent.subagents.compiler import compile_subagent_runnable


class _Args(BaseModel):
    x: int = 0


def _tool(name):
    return StructuredTool.from_function(name=name, description="t", func=lambda x=0: x, args_schema=_Args)


def test_compile_uses_parent_model_when_spec_omits_model(monkeypatch):
    captured: dict = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return "fake_runnable"

    monkeypatch.setattr("hagent.subagents.compiler.create_agent", fake_create_agent)
    spec = {"name": "x", "description": "y", "system_prompt": "z", "tools": ["*"]}
    runnable = compile_subagent_runnable(
        spec, parent_model="anthropic:claude-sonnet-4-6", parent_tools=[_tool("Read")]
    )
    assert runnable == "fake_runnable"
    assert captured["model"] == "anthropic:claude-sonnet-4-6"
    assert captured["system_prompt"] == "z"
    assert captured["name"] == "x"
    assert [t.name for t in captured["tools"]] == ["Read"]


def test_compile_resolves_model_alias(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "hagent.subagents.compiler.create_agent", lambda **kw: captured.update(kw) or "x"
    )
    compile_subagent_runnable(
        {"name": "x", "description": "y", "system_prompt": "z", "tools": ["*"], "model": "haiku"},
        parent_model="anthropic:claude-sonnet-4-6",
        parent_tools=[_tool("Read")],
    )
    assert captured["model"] == "anthropic:claude-haiku-4-5"


def test_compile_with_inherit_keeps_parent_model(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "hagent.subagents.compiler.create_agent", lambda **kw: captured.update(kw) or "x"
    )
    compile_subagent_runnable(
        {"name": "x", "description": "y", "system_prompt": "z", "tools": ["*"], "model": "inherit"},
        parent_model="anthropic:claude-sonnet-4-6",
        parent_tools=[_tool("Read")],
    )
    assert captured["model"] == "anthropic:claude-sonnet-4-6"


def test_compile_applies_tool_resolution(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "hagent.subagents.compiler.create_agent", lambda **kw: captured.update(kw) or "x"
    )
    parent = [_tool("Read"), _tool("Edit"), _tool("Write")]
    compile_subagent_runnable(
        {
            "name": "x",
            "description": "y",
            "system_prompt": "z",
            "tools": ["*"],
            "disallowed_tools": ["Edit", "Write"],
        },
        parent_model="anthropic:claude-sonnet-4-6",
        parent_tools=parent,
    )
    assert [t.name for t in captured["tools"]] == ["Read"]


def test_compile_warns_on_unknown_tools(monkeypatch, caplog):
    import logging
    monkeypatch.setattr("hagent.subagents.compiler.create_agent", lambda **kw: "x")
    with caplog.at_level(logging.WARNING, logger="hagent.subagents.compiler"):
        compile_subagent_runnable(
            {"name": "x", "description": "y", "system_prompt": "z", "tools": ["Read", "Ghost"]},
            parent_model="anthropic:claude-sonnet-4-6",
            parent_tools=[_tool("Read")],
        )
    assert "Ghost" in caplog.text
```

- [ ] **Step 2: 跑测试验证失败**

Run: `pytest tests/test_subagents_compiler.py -v`
Expected: ModuleNotFoundError

- [ ] **Step 3: 写 compiler.py**

```python
# src/hagent/subagents/compiler.py
from __future__ import annotations

import logging
from typing import Any

from langchain.agents import create_agent

from hagent.subagents.tools import resolve_subagent_tools
from hagent.subagents.types import SubagentSpec, resolve_model_alias

logger = logging.getLogger(__name__)


def compile_subagent_runnable(
    spec: SubagentSpec,
    *,
    parent_model: str,
    parent_tools: list[Any],
) -> Any:
    """把一个 SubagentSpec 编译成 langchain runnable。

    model 解析：spec.model 通过 resolve_model_alias 解析；为 None / 缺失 / 'inherit'
    时回落到 parent_model。本期不实现 runtime model 覆盖。
    """
    resolved_tools, unknown = resolve_subagent_tools(dict(spec), parent_tools)
    if unknown:
        logger.warning(
            "subagent %s references unknown tool(s) %s; dropped",
            spec.get("name", "<unnamed>"),
            unknown,
        )

    spec_model = spec.get("model") if isinstance(spec.get("model"), str) else None
    resolved_model = resolve_model_alias(spec_model)
    model = resolved_model if resolved_model is not None else parent_model

    return create_agent(
        model=model,
        tools=list(resolved_tools),
        system_prompt=spec["system_prompt"],
        name=spec["name"],
    )
```

- [ ] **Step 4: 跑测试验证通过**

Run: `pytest tests/test_subagents_compiler.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/hagent/subagents/compiler.py tests/test_subagents_compiler.py
git commit -m "feat(subagents): add compile_subagent_runnable using langchain.agents.create_agent"
```

---

### Task 6: `Agent` 工具（CC schema：description + prompt + subagent_type?）

**Files:**
- Create: `src/hagent/subagents/agent_tool.py`
- Test: `tests/test_subagents_agent_tool.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_subagents_agent_tool.py
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from hagent.subagents.agent_tool import AgentToolInput, build_agent_tool


def _runtime(*, tool_call_id="call-1", state=None, config=None):
    return SimpleNamespace(
        tool_call_id=tool_call_id,
        state=state or {"messages": ["should_be_dropped"]},
        config=config or {},
    )


def test_agent_tool_name_is_Agent():
    tool = build_agent_tool({"general-purpose": MagicMock()}, "desc")
    assert tool.name == "Agent"


def test_agent_tool_description_passed_through():
    tool = build_agent_tool({"general-purpose": MagicMock()}, "my-description")
    assert tool.description == "my-description"


def test_agent_tool_schema_has_required_and_optional_fields():
    schema = AgentToolInput.model_json_schema()
    props = schema["properties"]
    assert set(props) == {"description", "prompt", "subagent_type"}
    assert set(schema.get("required", [])) == {"description", "prompt"}
    assert "general-purpose" in (props["subagent_type"].get("description") or "") or \
        props["subagent_type"].get("default") in (None, "general-purpose")


def test_agent_tool_routes_to_default_general_purpose_when_subagent_type_omitted():
    gp = MagicMock()
    gp.invoke.return_value = {"messages": [AIMessage(content="hello")]}
    tool = build_agent_tool({"general-purpose": gp, "Explore": MagicMock()}, "desc")
    result = tool.invoke(
        {"description": "short", "prompt": "do X"},
        config={"configurable": {"__pregel_runtime": _runtime()}},
    )
    # invoked
    gp.invoke.assert_called_once()
    invoked_state = gp.invoke.call_args[0][0]
    assert invoked_state["messages"] == [HumanMessage(content="do X")]


def test_agent_tool_routes_by_subagent_type():
    explore = MagicMock()
    explore.invoke.return_value = {"messages": [AIMessage(content="found")]}
    gp = MagicMock()
    tool = build_agent_tool({"general-purpose": gp, "Explore": explore}, "desc")
    tool.invoke(
        {"description": "search", "prompt": "find Foo", "subagent_type": "Explore"},
        config={"configurable": {"__pregel_runtime": _runtime()}},
    )
    explore.invoke.assert_called_once()
    gp.invoke.assert_not_called()


def test_agent_tool_unknown_subagent_type_returns_error_string():
    tool = build_agent_tool({"general-purpose": MagicMock()}, "desc")
    out = tool.invoke(
        {"description": "x", "prompt": "y", "subagent_type": "ghost"},
        config={"configurable": {"__pregel_runtime": _runtime()}},
    )
    assert "ghost" in str(out)
    assert "general-purpose" in str(out)


def test_agent_tool_returns_command_with_tool_message():
    gp = MagicMock()
    gp.invoke.return_value = {"messages": [AIMessage(content="hi  ")]}
    tool = build_agent_tool({"general-purpose": gp}, "desc")
    out = tool.invoke(
        {"description": "x", "prompt": "y"},
        config={"configurable": {"__pregel_runtime": _runtime(tool_call_id="call-42")}},
    )
    assert isinstance(out, Command)
    update = out.update
    assert "messages" in update
    msg = update["messages"][0]
    assert isinstance(msg, ToolMessage)
    assert msg.tool_call_id == "call-42"
    assert msg.content == "hi"  # 右侧 trim


def test_agent_tool_excludes_messages_todos_from_passed_state():
    gp = MagicMock()
    gp.invoke.return_value = {"messages": [AIMessage(content="ok")]}
    tool = build_agent_tool({"general-purpose": gp}, "desc")
    state = {"messages": ["x"], "todos": ["a"], "structured_response": "b", "files": {"f": 1}}
    tool.invoke(
        {"description": "x", "prompt": "y"},
        config={"configurable": {"__pregel_runtime": _runtime(state=state)}},
    )
    passed_state = gp.invoke.call_args[0][0]
    assert "todos" not in passed_state
    assert "structured_response" not in passed_state
    assert passed_state["messages"] == [HumanMessage(content="y")]
    assert passed_state["files"] == {"f": 1}


def test_agent_tool_raises_when_tool_call_id_missing():
    gp = MagicMock()
    tool = build_agent_tool({"general-purpose": gp}, "desc")
    with pytest.raises(ValueError, match="tool_call_id"):
        tool.invoke(
            {"description": "x", "prompt": "y"},
            config={"configurable": {"__pregel_runtime": _runtime(tool_call_id=None)}},
        )
```

> **注意：** `langchain_core` 在不同版本里 `ToolRuntime` 的 `runtime.tool_call_id` / `runtime.state` / `runtime.config` 字段注入方式可能略异。如果上面的测试桩 fixture 写法在当前依赖版本不工作，落实施者需先 Read `langchain_core.tools.structured.StructuredTool` 源码（或 `deepagents/middleware/subagents.py:472-494` 的 `task()` 用法）改成版本兼容的方式注入 runtime，再让测试通过。Step 3 的实现也必须以 `langchain_core` 现行 API 为准。

- [ ] **Step 2: 跑测试验证失败**

Run: `pytest tests/test_subagents_agent_tool.py -v`
Expected: ModuleNotFoundError

- [ ] **Step 3: 写 agent_tool.py**

```python
# src/hagent/subagents/agent_tool.py
from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool, ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel, Field

_EXCLUDED_STATE_KEYS: frozenset[str] = frozenset({"messages", "todos", "structured_response"})
_DEFAULT_SUBAGENT = "general-purpose"


class AgentToolInput(BaseModel):
    """CC-aligned Agent tool input schema."""

    description: str = Field(
        description="A short (3-5 word) description of the task. Shown to the user as a label."
    )
    prompt: str = Field(
        description=(
            "The full task brief for the subagent. The subagent does not see the parent conversation; "
            "include all the context it needs."
        )
    )
    subagent_type: str | None = Field(
        default=None,
        description=(
            "The type of specialized subagent to use. Omit to use the general-purpose agent. "
            "Must match one of the available agent types listed in the tool description."
        ),
    )


def build_agent_tool(
    runnables: dict[str, Any],
    description: str,
) -> StructuredTool:
    """构造 CC 对齐的 `Agent` 工具，路由到 pre-compiled subagent runnables。"""

    def _prepare_state(runtime: ToolRuntime, prompt: str) -> dict[str, Any]:
        state = {
            k: v
            for k, v in (runtime.state or {}).items()
            if k not in _EXCLUDED_STATE_KEYS
        }
        state["messages"] = [HumanMessage(content=prompt)]
        return state

    def _forward_config(runtime: ToolRuntime) -> dict[str, Any]:
        parent = runtime.config or {}
        out: dict[str, Any] = {}
        for key in ("callbacks", "tags", "configurable"):
            if key in parent:
                out[key] = parent[key]
        return out

    def _finalize(result: dict[str, Any], tool_call_id: str) -> Command:
        content = ""
        msgs = result.get("messages") if isinstance(result, dict) else None
        if msgs:
            last = msgs[-1]
            text = getattr(last, "text", None)
            if text is None:
                text = getattr(last, "content", "")
                if isinstance(text, list):
                    text = "".join(
                        block.get("text", "") for block in text if isinstance(block, dict)
                    )
            content = (text or "").rstrip()
        state_update = {
            k: v
            for k, v in (result or {}).items()
            if k not in _EXCLUDED_STATE_KEYS
        }
        return Command(
            update={
                **state_update,
                "messages": [ToolMessage(content, tool_call_id=tool_call_id)],
            }
        )

    def agent(
        description: str,
        prompt: str,
        subagent_type: str | None,
        runtime: ToolRuntime,
    ) -> Any:
        if not runtime.tool_call_id:
            raise ValueError("Agent tool invocation requires runtime.tool_call_id")
        target = subagent_type or _DEFAULT_SUBAGENT
        if target not in runnables:
            available = ", ".join(f"`{k}`" for k in runnables)
            return (
                f"Cannot invoke subagent '{target}' — not registered. "
                f"Available subagents: {available}."
            )
        runnable = runnables[target]
        state = _prepare_state(runtime, prompt)
        config = _forward_config(runtime)
        result = runnable.invoke(state, config)
        return _finalize(result, runtime.tool_call_id)

    async def aagent(
        description: str,
        prompt: str,
        subagent_type: str | None,
        runtime: ToolRuntime,
    ) -> Any:
        if not runtime.tool_call_id:
            raise ValueError("Agent tool invocation requires runtime.tool_call_id")
        target = subagent_type or _DEFAULT_SUBAGENT
        if target not in runnables:
            available = ", ".join(f"`{k}`" for k in runnables)
            return (
                f"Cannot invoke subagent '{target}' — not registered. "
                f"Available subagents: {available}."
            )
        runnable = runnables[target]
        state = _prepare_state(runtime, prompt)
        config = _forward_config(runtime)
        result = await runnable.ainvoke(state, config)
        return _finalize(result, runtime.tool_call_id)

    return StructuredTool.from_function(
        name="Agent",
        func=agent,
        coroutine=aagent,
        description=description,
        infer_schema=False,
        args_schema=AgentToolInput,
    )
```

- [ ] **Step 4: 跑测试验证通过**

Run: `pytest tests/test_subagents_agent_tool.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/hagent/subagents/agent_tool.py tests/test_subagents_agent_tool.py
git commit -m "feat(subagents): add Agent tool with CC schema (description+prompt+subagent_type)"
```

---

### Task 7: Agent 工具描述渲染器

**Files:**
- Create: `src/hagent/subagents/description.py`
- Test: `tests/test_subagents_description.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_subagents_description.py
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
```

- [ ] **Step 2: 跑测试验证失败**

Run: `pytest tests/test_subagents_description.py -v`
Expected: ModuleNotFoundError

- [ ] **Step 3: 写 description.py**

```python
# src/hagent/subagents/description.py
from __future__ import annotations

from typing import Sequence

from hagent.subagents.types import SubagentSpec


def _render_agent_listing(specs: Sequence[SubagentSpec]) -> str:
    if not specs:
        return "(no subagents available)"
    return "\n".join(f"- {s['name']}: {s['description']}" for s in specs)


def render_agent_tool_description(specs: Sequence[SubagentSpec]) -> str:
    listing = _render_agent_listing(specs)
    return f"""Launch a new subagent to handle a complex, multi-step task in an isolated context window.

Available agent types and the tools they have access to:
{listing}

When using the Agent tool, specify a `subagent_type` to select which agent to use. If omitted, the general-purpose agent is used by default. Put the full task brief in the `prompt` parameter — the subagent only sees that string. Use `description` for a short 3-5 word label.

When NOT to use the Agent tool:
- If you want to read a specific file path, use Read directly — that is faster than spawning a subagent.
- If you are searching for a specific symbol in a single file or a small set (2-3 files), use Read directly.
- If the task is trivial (a few tool calls) and delegation would not reduce context usage.
- If you need to observe the subagent's intermediate steps — the Agent tool hides them.

Usage notes:
- Always provide a self-contained brief in `prompt`. The subagent does not see the parent conversation; describe what to do, what's already known, what's in/out of scope.
- For pure lookups, hand over the exact command or keywords. For investigations, hand over the question and let the subagent decide the steps.
- Launch multiple subagents concurrently when the work is independent — use a single message with multiple Agent tool calls.
- When the subagent finishes, it returns a single message back to you. The user does not see that result directly; summarise it for them.
- The subagent's findings are generally trustworthy; you do not need to redo its work to verify unless it reports failure or low confidence.
- Clearly state whether the subagent should write code, run analysis, or only research — it does not know the user's intent.

Example usage:

<example>
User: "Where is the SSE writer defined?"
Assistant: <thinking>Single-shot lookup — Explore can answer this without polluting my context.</thinking>
Calls Agent(description="locate SSE writer", prompt="Find where the SSE writer is defined in src/hagent/server. Return file paths and the symbol names. Quick search.", subagent_type="Explore")
</example>

<example>
User: "Plan a refactor that splits backends.py into per-backend modules."
Assistant: Calls Agent(description="plan backend split", prompt="Design how to split src/hagent/backends.py into one module per backend class. List the steps, the new file layout, and the migration risks. Include a 'Critical Files' section at the end.", subagent_type="Plan")
</example>"""
```

- [ ] **Step 4: 跑测试验证通过**

Run: `pytest tests/test_subagents_description.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/hagent/subagents/description.py tests/test_subagents_description.py
git commit -m "feat(subagents): add CC-aligned Agent tool description renderer"
```

---

### Task 8: Registry — 合并 specs + 批量 compile

**Files:**
- Create: `src/hagent/subagents/registry.py`
- Modify: `src/hagent/subagents/__init__.py`
- Test: `tests/test_subagents_registry.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_subagents_registry.py
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
```

- [ ] **Step 2: 跑测试验证失败**

Run: `pytest tests/test_subagents_registry.py -v`
Expected: ModuleNotFoundError

- [ ] **Step 3: 写 registry.py**

```python
# src/hagent/subagents/registry.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

from hagent.subagents.builtin import BUILTIN_SUBAGENT_SPECS
from hagent.subagents.compiler import compile_subagent_runnable
from hagent.subagents.loader import load_markdown_agents
from hagent.subagents.types import SubagentSpec

logger = logging.getLogger(__name__)


def _default_agents_dirs(workspace: Path) -> list[Path]:
    workspace = Path(workspace)
    home = Path.home()
    # 后到的覆盖先到的：user → project agents/ → project .hagent/agents/
    return [
        home / ".hagent" / "agents",
        workspace / "agents",
        workspace / ".hagent" / "agents",
    ]


def assemble_subagents(
    *,
    workspace: Path,
    extra_subagents: Iterable[dict[str, Any]] | None = None,
    agents_dirs: Iterable[Path] | None = None,
    disable_builtin: bool = False,
) -> list[SubagentSpec]:
    """合并 built-in / markdown / extra_subagents，去重；返回 SubagentSpec 列表。

    同名后到的覆盖先到的。
    """
    by_name: dict[str, SubagentSpec] = {}

    if not disable_builtin:
        for spec in BUILTIN_SUBAGENT_SPECS:
            by_name[spec["name"]] = dict(spec)  # type: ignore[assignment]

    dirs = list(agents_dirs) if agents_dirs is not None else _default_agents_dirs(workspace)
    for md_spec in load_markdown_agents(dirs):
        by_name[md_spec["name"]] = md_spec

    for raw in extra_subagents or []:
        if "name" not in raw or "description" not in raw or "system_prompt" not in raw:
            logger.warning("skipping malformed extra subagent: %s", raw)
            continue
        by_name[raw["name"]] = dict(raw)  # type: ignore[assignment]

    return list(by_name.values())


def compile_subagents(
    specs: Iterable[SubagentSpec],
    *,
    parent_model: str,
    parent_tools: list[Any],
) -> dict[str, Any]:
    """把 SubagentSpec 列表批量编译成 {name: runnable} 字典。"""
    runnables: dict[str, Any] = {}
    for spec in specs:
        runnables[spec["name"]] = compile_subagent_runnable(
            spec, parent_model=parent_model, parent_tools=parent_tools
        )
    return runnables
```

- [ ] **Step 4: 更新 `__init__.py` 公开 API**

```python
# src/hagent/subagents/__init__.py
from hagent.subagents.agent_tool import AgentToolInput, build_agent_tool
from hagent.subagents.builtin import BUILTIN_SUBAGENT_SPECS, EXPLORE, GENERAL_PURPOSE, PLAN
from hagent.subagents.compiler import compile_subagent_runnable
from hagent.subagents.description import render_agent_tool_description
from hagent.subagents.loader import load_markdown_agents
from hagent.subagents.registry import assemble_subagents, compile_subagents
from hagent.subagents.tools import resolve_subagent_tools
from hagent.subagents.types import SubagentSpec, resolve_model_alias

# 向后兼容：保留旧符号，但内容已换成 CC 对齐的内置集
BUILTIN_SUBAGENTS = BUILTIN_SUBAGENT_SPECS

__all__ = [
    "AgentToolInput",
    "BUILTIN_SUBAGENTS",
    "BUILTIN_SUBAGENT_SPECS",
    "EXPLORE",
    "GENERAL_PURPOSE",
    "PLAN",
    "SubagentSpec",
    "assemble_subagents",
    "build_agent_tool",
    "compile_subagent_runnable",
    "compile_subagents",
    "load_markdown_agents",
    "render_agent_tool_description",
    "resolve_model_alias",
    "resolve_subagent_tools",
]
```

- [ ] **Step 5: 跑测试验证通过**

Run: `pytest tests/test_subagents_registry.py tests/test_subagents.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/hagent/subagents/registry.py src/hagent/subagents/__init__.py tests/test_subagents_registry.py
git commit -m "feat(subagents): add assemble_subagents and compile_subagents helpers"
```

---

### Task 9: core.py 接线 —— 自管 subagent 链路 + 注册 `Agent` 工具

**Files:**
- Modify: `src/hagent/core.py`
- Test: `tests/test_core.py`

- [ ] **Step 1: 写失败测试（新增 5 个 + 改写 1 个）**

把下面 6 个用例加进 `tests/test_core.py`（替换旧的 `test_create_hagent_attaches_subagents`）：

```python
def test_create_hagent_does_not_pass_subagents_to_deepagents(monkeypatch):
    """Hagent 自管 subagent，deepagents 不应收到 subagents 参数（应为 None / 缺省）。"""
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()
    # deepagents 不应被注入 subagents
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
    create_hagent(disable_builtin_agents=True)
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
```

并且把旧的 `test_create_hagent_attaches_subagents` 直接**删掉**（它假定 deepagents 收到 subagents 列表，新架构里不再成立）。

- [ ] **Step 2: 跑测试验证失败**

Run: `pytest tests/test_core.py -v`
Expected: 大量 FAIL（subagents 不再被传入 / Agent 工具不在 tools 列表 / GeneralPurposeSubagentProfile 不在 profile）

- [ ] **Step 3: 改 `core.py`**

```python
# src/hagent/core.py 全文（核心改动）
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent as _create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import SandboxBackendProtocol
from deepagents.profiles import HarnessProfile, register_harness_profile
from deepagents.profiles.harness.harness_profiles import GeneralPurposeSubagentProfile
from langchain.agents.middleware import wrap_model_call

from hagent.bash_tool import BashRuntime, create_bash_tool
from hagent.config import HagentConfig, render_base_prompt
from hagent.file_tools import create_claude_file_tools
from hagent.permissions import permissions_for_workspace
from hagent.subagents import (
    assemble_subagents,
    build_agent_tool,
    compile_subagents,
    render_agent_tool_description,
)
from hagent.task_tools import TaskStore, create_task_tools

DEFAULT_WORKSPACE = Path("/tmp/hagent/workspace")
DISABLED_DEEPAGENTS_MIDDLEWARE = frozenset({"SummarizationMiddleware"})
DISABLED_DEEPAGENTS_TOOLS = frozenset(
    {"execute", "read_file", "write_file", "edit_file", "write_todos"}
)


def _backend_working_directory(backend: Any) -> Path:
    cwd = getattr(backend, "cwd", None)
    return Path(cwd).resolve() if cwd is not None else DEFAULT_WORKSPACE.resolve()


def _filesystem_backend_for_workspace(workspace: Path) -> FilesystemBackend:
    return FilesystemBackend(root_dir=workspace, virtual_mode=False)


def _backend_for_model_tools(backend: Any) -> Any:
    if isinstance(backend, SandboxBackendProtocol) or hasattr(backend, "execute"):
        return _filesystem_backend_for_workspace(_backend_working_directory(backend))
    return backend


def sanitize_anthropic_thinking_blocks(messages: list[Any]) -> list[Any]:
    cleaned_messages: list[Any] = []
    for message in messages:
        content = getattr(message, "content", None)
        if not isinstance(content, list):
            cleaned_messages.append(message)
            continue
        cleaned_content = [
            block
            for block in content
            if not (
                isinstance(block, dict)
                and block.get("type") == "thinking"
                and not block.get("thinking")
            )
        ]
        if len(cleaned_content) == len(content):
            cleaned_messages.append(message)
        else:
            cleaned_messages.append(message.model_copy(update={"content": cleaned_content}))
    return cleaned_messages


@wrap_model_call(name="SanitizeAnthropicThinkingBlocks")
def sanitize_anthropic_thinking_blocks_middleware(request: Any, handler: Any) -> Any:
    return handler(request.override(messages=sanitize_anthropic_thinking_blocks(request.messages)))


def create_hagent(
    config: HagentConfig | None = None,
    backend: Any | None = None,
    extra_subagents: list[dict] | None = None,
    extra_tools: list[Any] | None = None,
    checkpointer: Any | None = None,
    task_list_id: str | None = None,
    agents_dirs: list[Path] | None = None,
    disable_builtin_agents: bool = False,
) -> Any:
    cfg = config or HagentConfig.from_env()
    register_harness_profile(
        cfg.model,
        HarnessProfile(
            excluded_middleware=DISABLED_DEEPAGENTS_MIDDLEWARE,
            excluded_tools=DISABLED_DEEPAGENTS_TOOLS,
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )
    DEFAULT_WORKSPACE.mkdir(parents=True, exist_ok=True)

    requested_backend = backend or _filesystem_backend_for_workspace(DEFAULT_WORKSPACE.resolve())
    requested_workspace = (
        _backend_working_directory(requested_backend)
        if requested_backend is not None
        else DEFAULT_WORKSPACE.resolve()
    )
    backend = _backend_for_model_tools(requested_backend)

    working_directory = requested_workspace
    bash_runtime = BashRuntime(working_directory)
    bash_tool = create_bash_tool(
        workspace_root=working_directory,
        runtime=bash_runtime,
        permissions=cfg.bash_permissions,
    )
    file_permissions = permissions_for_workspace(working_directory)
    file_tools = create_claude_file_tools(
        workspace_root=working_directory,
        permissions=file_permissions,
    )
    task_store = TaskStore(
        working_directory,
        task_list_id=task_list_id or os.environ.get("HAGENT_TASK_LIST_ID", "tasklist"),
    )
    task_tools = create_task_tools(task_store)

    # Parent tool pool — subagents 编译时也从这里取
    parent_tools: list[Any] = [bash_tool, *file_tools, *task_tools, *list(extra_tools or [])]

    # Subagent specs + 编译 + Agent 工具
    specs = assemble_subagents(
        workspace=working_directory,
        extra_subagents=extra_subagents,
        agents_dirs=agents_dirs,
        disable_builtin=disable_builtin_agents,
    )
    agent_tool = None
    if specs:
        runnables = compile_subagents(
            specs, parent_model=cfg.model, parent_tools=parent_tools
        )
        agent_tool = build_agent_tool(runnables, render_agent_tool_description(specs))

    all_tools = list(parent_tools)
    if agent_tool is not None:
        all_tools.append(agent_tool)

    kwargs: dict[str, Any] = dict(
        model=cfg.model,
        tools=all_tools,
        middleware=[sanitize_anthropic_thinking_blocks_middleware],
        system_prompt=render_base_prompt(
            sandbox_type=type(backend).__name__,
            working_directory=str(working_directory),
            is_git_repo=(working_directory / ".git").exists(),
            shell=os.environ.get("SHELL", "unknown"),
            model=cfg.model,
        ),
        subagents=None,
        backend=backend,
        permissions=file_permissions,
    )
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer

    agent = _create_deep_agent(**kwargs)
    try:
        setattr(agent, "_hagent_bash_runtime", bash_runtime)
    except Exception:
        pass
    try:
        setattr(agent, "_hagent_task_store", task_store)
    except Exception:
        pass
    return agent
```

> **落实注意：** `GeneralPurposeSubagentProfile` 的 import 路径以 `.venv/lib/python3.12/site-packages/deepagents/profiles/__init__.py` 的实际 re-export 为准。Step 3 写的是 `from deepagents.profiles.harness.harness_profiles import GeneralPurposeSubagentProfile`，若 `deepagents.profiles` 顶层也 re-export 了它，改成更短的路径。Read 该 `__init__.py` 确认后再下手。

- [ ] **Step 4: 跑 core 测试 + 全套测试**

Run: `pytest tests/test_core.py -v && pytest -v`
Expected: 全绿；其中包括既有的 `test_create_hagent_disables_summarization_middleware` 仍然 PASS（excluded_middleware / excluded_tools 不变）

- [ ] **Step 5: 提交**

```bash
git add src/hagent/core.py tests/test_core.py
git commit -m "feat(core): self-manage subagents via Agent tool, disable deepagents subagent path"
```

---

### Task 10: base prompt 新增「使用 subagent」段（讲 `Agent` 工具）

**Files:**
- Modify: `prompts/hagent_base.zh.md`
- Modify: `prompts/decisions.md`

- [ ] **Step 1: 在 `# Using your tools` 之后、`# Tone and style` 之前插入新段**

```markdown
# 使用 subagent

当任务复杂、多步骤、且可以完全独立完成时，用 `Agent` 工具把它委派给一个 subagent。Subagent 在独立上下文窗口里工作，完成后只把最终结果回报给你，从而避免大量中间工具输出把主对话挤爆。

`Agent` 工具参数：
- `description`：3-5 词的短摘要，用作显示给用户的标签
- `prompt`：完整的任务简报；subagent 看不到当前对话，必须在 `prompt` 字段写清楚要做什么、已知什么、范围内/外、期望结果
- `subagent_type`：可选；省略时默认使用 `general-purpose`

何时使用 subagent：
- 任务需要多次搜索 / 读文件 / 多轮推理才能定位答案
- 任务可以拆解成相互独立的子任务时（并行触发多个 `Agent` 调用）
- 你只关心最终结论，不需要看到中间步骤

何时不要用 subagent：
- 你已经知道要读哪个具体文件 — 直接用 `Read` 更快
- 任务只需要几次工具调用 — 直接做完更简洁
- 你需要观察中间步骤来判断方向 — subagent 会隐藏过程

可用的内置 subagent：
- `general-purpose`：通用多步骤代理；拥有与主代理相同的工具集
- `Explore`：只读快速搜索代理；不能写文件 / 不能 Edit；适合"找在哪里 / 谁引用了它 / 模式是什么"类问题
- `Plan`：架构与规划代理；只读；产出分步实现计划与关键文件列表

撰写 subagent prompt 的要点：
- 查找类任务：直接给出搜索命令或关键词
- 调查类任务：把问题原样转过去，让 subagent 自行决定步骤
- 委派之后要相信 subagent 的结论；只有它自己报告失败或低置信度时才需要再验证

需要时优先在单条消息里并行触发多个 `Agent` 调用以提升效率。
```

- [ ] **Step 2: 在 `prompts/decisions.md` 末尾追加变更记录**

```markdown

---

## 2026-05-14 subagent 段落补充

在 `# Using your tools` 与 `# Tone and style` 之间新增 `# 使用 subagent` 段。讲解 `Agent` 工具（自管，CC schema：description + prompt + subagent_type?）、何时委派 / 不委派、可用内置 subagent（general-purpose / Explore / Plan）、撰写 subagent prompt 的要点。

| 段落 | 处置 | 理由 |
|---|---|---|
| `# 使用 subagent` | ADD | 当前 base prompt 缺乏委派指引，模型倾向把所有工作压在主线程，导致上下文膨胀；Hagent 自己实现了 `Agent` 工具（替代 deepagents `task` 工具），prompt 需明确告知 |

- 内置 subagent 名（`general-purpose` / `Explore` / `Plan`）与 `src/hagent/subagents/builtin.py` 一致。
- 段落正文为简体中文；无 `Claude Code` / `Anthropic` / `Claude Opus` / `write_todos` 残留。
- 工具名 `Agent`（驼峰）与 `src/hagent/subagents/agent_tool.py` 注册名一致。
- `tiktoken` 计量在下次主修订时重算（本次为增量补充）。
```

- [ ] **Step 3: 跑 base prompt 检查与全套测试**

Run: `./scripts/check_base_prompt.sh && pytest -v`
Expected: `OK: scaffold checks passed`；pytest 全绿。

- [ ] **Step 4: 提交**

```bash
git add prompts/hagent_base.zh.md prompts/decisions.md
git commit -m "docs(prompt): add subagent usage section advertising the Agent tool"
```

---

### Task 11: e2e mock smoke

**Files:**
- Test: `tests/test_subagents_e2e_mock.py`

- [ ] **Step 1: 写测试**

```python
# tests/test_subagents_e2e_mock.py
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

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

    real_create_agent = __import__("langchain.agents", fromlist=["create_agent"]).create_agent

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

    import re
    for name, model in runnables_seen.items():
        assert re.match(r"^[a-z_]+:", str(model)), f"{name} model 必须为 provider:id 形式，实际 {model}"
```

- [ ] **Step 2: 跑测试验证通过**

Run: `pytest tests/test_subagents_e2e_mock.py -v && pytest -v`
Expected: PASS（4 个 + 全套）

- [ ] **Step 3: 提交**

```bash
git add tests/test_subagents_e2e_mock.py
git commit -m "test(subagents): e2e mock — Agent tool registered, subagents compiled with right tool pools"
```

---

### Task 12: 文档收尾

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/specs/2026-05-12-hagent-backend-design.md`（若需要 patch）

- [ ] **Step 1: 更新 `CLAUDE.md` 的「架构」表**

```markdown
| `subagents/` | CC 对齐的 subagent 实现：`types.py` 类型与模型别名 / `tools.py` 工具白黑名单解析 / `builtin.py` general-purpose+Explore+Plan / `loader.py` markdown agent 文件加载 / `compiler.py` 用 langchain.agents.create_agent 编译 runnable / `agent_tool.py` `Agent` 工具（CC schema: description+prompt+subagent_type?）/ `description.py` 工具描述渲染 / `registry.py` assemble_subagents + compile_subagents 入口 |
```

- [ ] **Step 2: 在「编写 deepagents 上层代码前必读官方文档」表追加新行**

```markdown
| Subagent 接线（自管 Agent 工具，不走 deepagents SubAgentMiddleware） | `src/hagent/subagents/*.py` 源码 + `.venv/lib/python3.12/site-packages/deepagents/profiles/harness/harness_profiles.py`（`GeneralPurposeSubagentProfile`）+ `.venv/lib/python3.12/site-packages/deepagents/middleware/subagents.py:386-526`（路由逻辑参考） |
```

- [ ] **Step 3: 评估是否需要给 backend-design spec 打 patch**

```bash
grep -n "subagent\|sub-agent\|RESEARCHER\|CODER\|researcher\|coder" docs/specs/2026-05-12-hagent-backend-design.md
```

如果 spec 在原 RESEARCHER/CODER 上有硬契约或在 subagent 接线上做了与本计划冲突的描述，在 spec 末尾追加 patch 节：

```markdown

---

## 2026-05-14 Patch — subagent 接线对齐 CC

自 2026-05-14 起，Hagent subagent 实现完全对齐 Claude Code：
- 内置 RESEARCHER / CODER 被替换为 `general-purpose` / `Explore` / `Plan`（CC 命名 + 简体中文 prompt）
- 工具名从 deepagents `task` 改为自管 `Agent`（CC schema：description + prompt + subagent_type?）
- Hagent 自行实现 Agent 工具与 subagent runnable 编译，不再使用 deepagents `SubAgentMiddleware`
- 详见 `docs/plans/2026-05-14-hagent-subagents.md`
```

- [ ] **Step 4: 提交**

```bash
git add CLAUDE.md docs/specs/2026-05-12-hagent-backend-design.md
git commit -m "docs: update CLAUDE.md and backend spec for CC-aligned subagent implementation"
```

---

## Self-Review

- **Spec 覆盖**：CC `AgentTool` 工具名/schema/默认 subagent_type/描述模板 → Task 6 + Task 7。CC 内置代理 → Task 3。markdown agent 文件 → Task 4。subagent 隔离编译 → Task 5。整体 wiring → Task 9。base prompt 教学 → Task 10。
- **本期范围外**：runtime `model` 覆盖、async / `run_in_background`、worktree 隔离、SendMessage / team_name、agent memory、skills / MCP / hooks per-agent、`permissionMode` / `maxTurns` / `isolation` / `background`（markdown loader 识别但 warning + 忽略，留作后续 plan 接入）。
- **Placeholder 扫描**：所有 Step 含完整代码或具体命令；测试用例都是可运行的；prompt 段是最终文本。
- **类型一致性**：内部 `SubagentSpec` 用 snake_case（`disallowed_tools`/`omit_claude_md`）；markdown frontmatter 用 camelCase（`disallowedTools`/`omitClaudeMd`），loader 负责映射；`Agent` 工具 schema 字段 `subagent_type` 在两端拼写一致。
- **测试约束**：所有 `_create_deep_agent` / `langchain.agents.create_agent` 调用通过 monkeypatch 注入桩，绝不打真实 API。
- **关键依赖确认**：`HarnessProfile.general_purpose_subagent` 字段已在 `harness_profiles.py:710` 存在；`GeneralPurposeSubagentProfile(enabled=False)` 已在 `graph.py:618` 触发跳过逻辑；`subagents=None` 走 `graph.py:684` 的「if inline_subagents:」短路，`SubAgentMiddleware` 不会被实例化。

## Execution Handoff

Plan 已更新到 `docs/plans/2026-05-14-hagent-subagents.md`。两种执行方式：

**1. Subagent-Driven（推荐）** — 主代理每个 Task 派一个 fresh subagent，task 之间审阅，迭代快、上下文干净。

**2. Inline Execution** — 在当前会话内按 task 顺序执行，每个 task 完成后 checkpoint 给你看。

**请选哪一种？**
