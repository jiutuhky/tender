# Plan 1 — 项目脚手架 + Mp 子代理产出中文 Base Prompt

> **存档说明**：本 plan 产出自已退役的 superpowers 工作流，仅作历史参考；新工作一律走仓根 tickets.md（Matt 契约）。

**Goal**: 建立 Hagent Python 项目骨架（pyproject、包目录、测试入口），并通过 Mp 子代理把 `docs/claude-code-prompt-full.md` 改造成 Hagent 用的中文 base prompt 文件，作为后续 Plan 2 (M3 集成) 的输入依赖。

**Architecture**: Python 3.11 src-layout 包；Plan 1 不引入任何运行时逻辑，只产出两类工件——(1) 可被 `pip install -e .` 安装的最小骨架；(2) `prompts/hagent_base.zh.md` + `prompts/decisions.md`。Mp 任务用主 Claude 会话调度一次 Agent 工具（subagent_type=general-purpose），把 spec 第 6 节作为完整规约喂进去。

**Tech Stack**: Python 3.11, hatchling (PEP 517 build backend), pytest, deepagents (PyPI，仅作为下游 plan 的依赖锁定)。

**Spec reference**: `docs/specs/2026-05-12-hagent-backend-design.md` 第 6 节（Prompt 适配策略 + Mp 子代理 spec）+ 第 4 节 Mp 模块（Done 标准）。

---

### Task 1: 写 .gitignore

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: 写 .gitignore**

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.eggs/
dist/
build/

# Virtual envs
.venv/
venv/
env/

# Editors
.vscode/
.idea/
*.swp
.DS_Store

# Pytest
.pytest_cache/
.coverage
htmlcov/

# Reference docs (deepagents 官方 docs 是镜像，不入仓)
deepagents/

# Hagent 本地 runtime 工件（后续 plan 才产生）
.hagent/
*.sqlite
*.sqlite-journal
```

- [ ] **Step 2: 提交**

```bash
git add .gitignore
git commit -m "chore: add .gitignore"
```

---

### Task 2: 写 pyproject.toml

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: 写 pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "hagent"
version = "0.0.1"
description = "Hagent — Web-based agent harness built on deepagents"
readme = "README.md"
requires-python = ">=3.11"
authors = [{ name = "hankeyang" }]
license = { text = "Apache-2.0" }
dependencies = [
    "deepagents>=0.5.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "tiktoken>=0.7",
]

[project.scripts]
hagent = "hagent.__main__:main"

[tool.hatch.build.targets.wheel]
packages = ["src/hagent"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"
```

- [ ] **Step 2: 写最小 README.md（pyproject 要求存在）**

```markdown
# Hagent

通用 Web Harness Agent 框架，基于 LangChain `deepagents`。

详细设计见 `docs/specs/2026-05-12-hagent-backend-design.md`。

## 开发

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```
```

- [ ] **Step 3: 提交**

```bash
git add pyproject.toml README.md
git commit -m "chore: add pyproject.toml and README"
```

---

### Task 3: 创建 src/hagent 包结构

**Files:**
- Create: `src/hagent/__init__.py`
- Create: `src/hagent/__main__.py`
- Create: `src/hagent/_version.py`

- [ ] **Step 1: 写 `src/hagent/_version.py`**

```python
__version__ = "0.0.1"
```

- [ ] **Step 2: 写 `src/hagent/__init__.py`**

```python
from hagent._version import __version__

__all__ = ["__version__"]
```

- [ ] **Step 3: 写 `src/hagent/__main__.py`**

```python
from hagent import __version__


def main() -> int:
    print(f"hagent {__version__}")
    print("Plan 1 scaffold only; CLI commands land in Plan 2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 提交**

```bash
git add src/hagent
git commit -m "feat: add hagent package skeleton"
```

---

### Task 4: 验证脚手架可安装、可导入、可运行

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: 写失败测试 `tests/test_smoke.py`**

```python
import subprocess
import sys

import hagent


def test_version_exposed():
    assert hagent.__version__ == "0.0.1"


def test_cli_runs():
    result = subprocess.run(
        [sys.executable, "-m", "hagent"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "hagent 0.0.1" in result.stdout
```

- [ ] **Step 2: 写空 `tests/__init__.py` 和 `tests/conftest.py`**

`tests/__init__.py`:
```python
```

`tests/conftest.py`:
```python
```

- [ ] **Step 3: 建虚拟环境并安装**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Expected: 安装成功，包括 deepagents 全量依赖；末尾输出 `Successfully installed ...`。如果 deepagents 安装失败（如网络或版本不存在），降级到 `pip install -e .` 跳过 dev extras，并把失败信息记在 PR 里。

- [ ] **Step 4: 跑测试**

```bash
pytest tests/test_smoke.py -v
```

Expected: 两个测试都 PASS。

- [ ] **Step 5: 跑 CLI 一次（人眼检查）**

```bash
python -m hagent
```

Expected stdout:
```
hagent 0.0.1
Plan 1 scaffold only; CLI commands land in Plan 2.
```

- [ ] **Step 6: 提交**

```bash
git add tests/
git commit -m "test: add scaffold smoke tests"
```

---

### Task 5: 创建 prompts/ 目录

**Files:**
- Create: `prompts/.gitkeep`

- [ ] **Step 1: 建目录占位**

```bash
mkdir -p prompts
touch prompts/.gitkeep
```

- [ ] **Step 2: 提交**

```bash
git add prompts/.gitkeep
git commit -m "chore: add prompts/ directory placeholder"
```

---

### Task 6: 调度 Mp 子代理产出中文 base prompt

**Files:**
- Read: `docs/claude-code-prompt-full.md` (609 行的源 prompt)
- Read: `docs/specs/2026-05-12-hagent-backend-design.md` §6 (裁剪规则)
- Create (by subagent): `prompts/hagent_base.zh.md`
- Create (by subagent): `prompts/decisions.md`

注意：本任务的"执行者"是主 Claude 会话本身——通过一次 `Agent` 工具调用调度一个 general-purpose subagent 去产出文件。本任务**不**是让另一个 Claude 来重新撰写 prompt；它是让 subagent 严格按规约执行翻译+裁剪。

- [ ] **Step 1: 主会话用 Agent 工具调度 Mp，prompt 用以下完整文本（不要改写、不要省略）**

````text
你是一个执行严格规约的子代理。任务：把 /home/han/workplace/Hagent/docs/claude-code-prompt-full.md 改造成 Hagent 项目用的中文 base system prompt。

## 强制阅读

1. 完整读 /home/han/workplace/Hagent/docs/claude-code-prompt-full.md（609 行）
2. 完整读 /home/han/workplace/Hagent/docs/specs/2026-05-12-hagent-backend-design.md 的 §6（"Prompt 适配策略 + Mp 子代理 spec"）

§6 包含决策树 + 各 section 预处置约束表 + 你自身的 Done 标准。整份输出必须严格符合 §6。

## 决策树（来自 §6，重复一遍作为锚点）

每个原 prompt 段落按以下决策树处置，**默认是"保留 + 翻译"**：

```
原段落 → 是否引用 Hagent 没有的实体？
         ├─ 是（CLI命令、Anthropic 专有概念、不存在的工具）→ DELETE
         └─ 否 → 是否描述了与 Hagent 形态冲突的事实？
                 ├─ 是（terminal、CLI-only 假设、Claude Code 身份）→ MODIFY（最小改动）
                 └─ 否 → KEEP + 准确翻译为中文
```

**KEEP 段一律不允许压缩 / 合并 / 改写句式**——只翻译，措辞和段落结构 1:1 对齐。

## 工具名映射（强制 replace_all）

| 原名 | 新名 |
|---|---|
| Read | read_file |
| Edit | edit_file |
| Write | write_file |
| Bash | execute |
| TaskCreate | write_todos |

注意 Bash 映射为 `execute`（不是 `bash`）——deepagents 的 shell-exec 工具叫 `execute`。

## 其他强制 MODIFY

- 身份段：`Claude Code, Anthropic's official CLI for Claude` → `Hagent，一个基于 deepagents 的开源 Web Agent harness`；同段后半句"interactive agent that helps users…"完整保留并翻译
- # System 段："rendered in monospace font" → "渲染在 Web Chat UI 中，支持 Markdown"
- # auto memory 段：路径 `~/.claude/projects/<project-slug>/memory/` → `/workspace/.hagent/memory/`
- # Environment 段：整段替换为 Hagent 运行时占位符（沙箱类型 / 工作目录 / 模型 provider，由 runtime 注入）

## 强制 DELETE

- # System 中的 hooks 段（"Users may configure 'hooks'…"整段）
- # Doing tasks 末尾的 `/help` + `github.com/anthropics/claude-code/issues` 链接段
- # Session-specific guidance 整段（! 命令 / Agent subagent_type / Explore / /<skill-name> / /schedule / /ultrareview 全部基于 Claude Code CLI 特有机制）
- # Tools 整段（完整工具 schema 列表，deepagents 自带工具注册表）

## 翻译规范

- 技术术语保留英文：prompt cache、SSE、JSON-RPC、tool use、HITL、token、LangSmith、Markdown、CommonMark、CLI、UI、API、HTTP/HTTPS、PR、commit、merge、rebase、worktree
- 句子边界、列表（含编号/项目符号）、强调标记（IMPORTANT / CRITICAL / Note / 加粗等）完整保留
- 代码块（` ``` `）和 inline code（`` ` ``）原样保留
- 链接 markdown 语法 [text](url) 保留；URL 不翻译
- 不允许添加任何原文没有的内容（不要"补充说明"）
- 不允许合并段落或拆分段落

## 输出文件

1. `/home/han/workplace/Hagent/prompts/hagent_base.zh.md`：最终 prompt 文本，纯中文（除技术术语 + 代码 + 链接 + 严格 MODIFY 后保留的英文）
2. `/home/han/workplace/Hagent/prompts/decisions.md`：决策记录，结构如下：

```markdown
# Hagent Base Prompt — Mp 子代理决策记录

源文件: docs/claude-code-prompt-full.md (609 行)
规约: docs/specs/2026-05-12-hagent-backend-design.md §6
生成时间: <填实际日期>

## 逐 section 处置

| 原 section / 段落 | 起止行 | 处置 | 理由 |
|---|---|---|---|
| 开头身份段 | 8-9 | MODIFY | §6 表行: "开头身份段" |
| 第一条 IMPORTANT (security) | 11 | KEEP | §6 表行: "两条 IMPORTANT" |
| 第二条 IMPORTANT (URL) | 12 | KEEP | §6 表行: "两条 IMPORTANT" |
| # System | 14-20 | KEEP (1 处 MODIFY: monospace; 1 处 DELETE: hooks) | §6 表行: "# System" |
| ... | ... | ... | ... |

## 工具名映射统计

- Read → read_file: N 处
- Edit → edit_file: N 处
- Write → write_file: N 处
- Bash → execute: N 处
- TaskCreate → write_todos: N 处

## 自检报告

- [x] 无 `Claude Code` 残留（grep 结果: 0）
- [x] 无 `Anthropic` 残留（grep 结果: 0，除非是合法引用如 URL safety 通用原则）
- [x] 无 `Claude Opus` 残留
- [x] KEEP 段英文原文与中文译文逐段比对完成，无信息丢失
- [x] tiktoken 计量：源 prompt N tokens；输出 prompt M tokens

## LLM-as-judge 比对样本

随机抽 3-5 个 KEEP 段，给出英文原文 + 中文译文 + 一行判断"语义是否完整"。
```

## 工作步骤建议

1. 先把 docs/claude-code-prompt-full.md 整文读完
2. 读 §6 表，构造内部处置 map
3. 按原文顺序逐段处置：DELETE → 跳过；MODIFY → 改写后翻译；KEEP → 直接翻译
4. 工具名 replace_all 在所有 KEEP/MODIFY 段执行
5. 输出两份文件
6. grep / tiktoken 自检
7. 写 decisions.md

## 完成标准（执行前最后核对）

- 两个文件都存在
- prompts/hagent_base.zh.md：中文 + 必要英文术语；不含 "Claude Code" / "Anthropic" / "Claude Opus" / "claude-opus-" 等残留（合法引用除外，需在 decisions.md 标注）
- prompts/decisions.md 覆盖原 prompt 每个 section
- decisions.md 末尾有完整自检报告 + tiktoken 计数 + LLM-as-judge 样本

不要省略、不要走捷径。如果遇到表里没说怎么处置的情况，回到决策树推断；如果决策树也不清晰，**KEEP + 翻译**是默认安全选项。
````

Expected: subagent 返回时 prompts/ 下出现两个新文件。如果 subagent 报告失败或部分完成，记录失败信息并不要进入 Step 2。

- [ ] **Step 2: 文件存在性检查**

```bash
ls -la prompts/
```

Expected:
```
prompts/.gitkeep
prompts/decisions.md
prompts/hagent_base.zh.md
```

任一文件缺失 → 重新调度 subagent 并修正它的输入。

---

### Task 7: 验证 Mp 输出（自动化部分）

**Files:**
- Read: `prompts/hagent_base.zh.md`
- Read: `prompts/decisions.md`
- Create: `scripts/check_base_prompt.sh`

- [ ] **Step 1: 写自动化检查脚本 `scripts/check_base_prompt.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

PROMPT="prompts/hagent_base.zh.md"
DEC="prompts/decisions.md"

if [[ ! -f "$PROMPT" ]]; then
    echo "FAIL: $PROMPT not found"
    exit 1
fi
if [[ ! -f "$DEC" ]]; then
    echo "FAIL: $DEC not found"
    exit 1
fi

# 禁用词检查（除非在合法引用中，子代理需要在 decisions.md 里 justify）
for term in "Claude Code" "Anthropic" "Claude Opus" "claude-opus-"; do
    if grep -q "$term" "$PROMPT"; then
        echo "WARN: '$term' found in $PROMPT — verify in decisions.md whether it's a legitimate retention"
        grep -n "$term" "$PROMPT" || true
    fi
done

# 工具名映射应该已替换
for old in "TaskCreate" " Bash " " Edit " " Read " " Write "; do
    if grep -q "$old" "$PROMPT"; then
        echo "WARN: old tool name '$old' (with spaces) found in $PROMPT — verify mapping was applied"
        grep -n "$old" "$PROMPT" || true
    fi
done

# decisions.md 必须覆盖关键标题
for section in "开头身份段" "IMPORTANT" "# System" "# Doing tasks" "# Executing actions" "# Using your tools" "# Tone and style" "# auto memory" "# Environment" "# Context management" "# Session-specific" "# Tools"; do
    if ! grep -q "$section" "$DEC"; then
        echo "FAIL: $DEC missing coverage of section '$section'"
        exit 1
    fi
done

# tiktoken 计数报告应该在 decisions.md 末尾
if ! grep -qi "tiktoken" "$DEC"; then
    echo "FAIL: $DEC missing tiktoken token count report"
    exit 1
fi

echo "OK: scaffold checks passed"
```

- [ ] **Step 2: 赋可执行权限并跑**

```bash
chmod +x scripts/check_base_prompt.sh
./scripts/check_base_prompt.sh
```

Expected: 最后一行 `OK: scaffold checks passed`。

如果出现 `WARN`：人工 review 这些位置是否合法（例如"Anthropic"出现在 URL safety 段的通用安全表述里是合法的，但出现在身份段就不合法）。把不合法的位置反馈给 Mp 子代理重做或手工修正。

如果出现 `FAIL`：必须修正后再继续。

- [ ] **Step 3: 提交脚本**

```bash
git add scripts/check_base_prompt.sh
git commit -m "test: add base prompt verification script"
```

---

### Task 8: 人工 review gate

- [ ] **Step 1: 通知用户 Mp 产物准备好**

向用户输出（不需要工具，直接发文字）：

> "Mp 产出已落盘到 prompts/hagent_base.zh.md 和 prompts/decisions.md，自动化检查脚本通过。请人工 review 这两个文件——重点确认 (1) 中文翻译没有走样、没有添油加醋；(2) KEEP 段信息完整；(3) decisions.md 的处置理由合理。Review 通过后回复'通过'，未通过请指出具体行号的问题。"

- [ ] **Step 2: 等待用户响应**

如果用户指出具体问题：
- 若问题是翻译质量 / 信息遗漏 → 重新调度 Mp 子代理，把用户反馈作为附加约束加入 prompt
- 若问题是 decisions.md 内容 → 让 Mp 重写 decisions.md
- 修正后回到 Task 7 重跑自动化检查

如果用户回"通过" → 继续 Step 3。

- [ ] **Step 3: 提交 Mp 产物**

```bash
git add prompts/hagent_base.zh.md prompts/decisions.md
git commit -m "feat: add Chinese base prompt adapted from Claude Code prompt

Generated by Mp sub-agent following spec §6 cut rules:
- Surgical adaptation, default KEEP + translate
- Tool name mapping Read/Edit/Write/Bash/TaskCreate → deepagents names
- Memory path replaced with /workspace/.hagent/memory/
- Session-specific CLI guidance and tool schemas removed
- Human-reviewed and approved before commit
"
```

---

### Task 9: Plan 1 收口

- [ ] **Step 1: 跑全量测试一次确认**

```bash
pytest
./scripts/check_base_prompt.sh
```

Expected: 都通过。

- [ ] **Step 2: 检查仓库状态**

```bash
git status
git log --oneline
```

Expected：
- 工作树干净
- 有约 6-8 个 commit：.gitignore / pyproject / package skeleton / smoke tests / prompts dir / verification script / Mp output / （可能的 fix-up commits）

- [ ] **Step 3: 向用户确认 Plan 1 完成**

> "Plan 1 完成：项目脚手架可安装、smoke test 过、Mp 产出的中文 base prompt 已落盘并通过自动化检查 + 人工 review。准备进入 Plan 2（M3 Hagent core + CLI demo）。"

---

## Plan 1 完整 Done 标准（对应 spec §4 Mp 模块 + Track A 起步）

- ✅ `pyproject.toml` + `src/hagent/` + `tests/` 结构存在
- ✅ `pip install -e ".[dev]"` 成功
- ✅ `python -m hagent` 输出版本信息
- ✅ `pytest` 全过（含 scaffold smoke tests）
- ✅ `prompts/hagent_base.zh.md` 存在、为中文、无禁用词残留
- ✅ `prompts/decisions.md` 存在、覆盖原 prompt 每个 section、含自检报告 + tiktoken 计数
- ✅ `scripts/check_base_prompt.sh` 通过
- ✅ 人工 review 通过
- ✅ 所有产物入 git
