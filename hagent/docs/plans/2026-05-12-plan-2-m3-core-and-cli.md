# Plan 2 — M3 Hagent Core + CLI Demo

> **存档说明**：本 plan 产出自已退役的 superpowers 工作流，仅作历史参考；新工作一律走仓根 tickets.md（Matt 契约）。

**Goal**: 实现 `hagent.core.create_hagent` 工厂、默认权限、预置 subagents、加载 Plan 1 产出的中文 base prompt，把 `python -m hagent demo "..."` CLI 端到端跑通（用 `LocalShellBackend`，宿主上执行）。

**Architecture**: 在 deepagents 之上的薄包装层——`create_hagent(...)` 调用 `deepagents.create_deep_agent(...)`，注入 (1) base prompt（中文）作为 `system_prompt`、(2) DEFAULT_PERMISSIONS 列表、(3) researcher + coder subagent 字典、(4) `LocalShellBackend` 实例。CLI 是 `hagent.cli` 模块，argparse 解析 `demo` 子命令。LangSmith trace 仅靠 env var 启用，零代码。

**Tech Stack**: Python 3.11+, deepagents>=0.5.4, **langchain-anthropic>=0.3**（demo 用 Claude；Plan 2 Task 0 把它加进 pyproject.toml 依赖）, argparse（stdlib，不引入 click）, pytest, pytest-asyncio。

**Spec reference**: `docs/specs/2026-05-12-hagent-backend-design.md` §3（架构）、§4 Track A M3 + LangSmith、§6（base prompt 已由 Plan 1 产出）、§7（permissions）。

**Depends on**: Plan 1 已合入 main：`prompts/hagent_base.zh.md`、`src/hagent/` 骨架、`.venv` 已有 deepagents。

---

### Task 0: 补依赖 `langchain-anthropic`

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 编辑 pyproject.toml `dependencies` 数组，追加一行**

```toml
    "langchain-anthropic>=0.3",
```

成为：
```toml
dependencies = [
    "deepagents>=0.5.4",
    "langchain-anthropic>=0.3",
]
```

- [ ] **Step 2: 重新安装**

```bash
source .venv/bin/activate && pip install -e ".[dev]"
```

- [ ] **Step 3: 验证 provider 可解析**

```bash
python -c "from langchain.chat_models import init_chat_model; m = init_chat_model('anthropic:claude-haiku-4-5'); print(type(m).__name__)"
```

Expected: 输出 `ChatAnthropic`（无 API key 也能实例化；调用时才需要 key）。

- [ ] **Step 4: 提交**

```bash
git add pyproject.toml
git commit -m "chore: add langchain-anthropic dependency for demo CLI"
```

---

### Task 1: 加载 base prompt 的 config 模块

**Files:**
- Create: `src/hagent/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 写失败测试 `tests/test_config.py`**

```python
from pathlib import Path

from hagent.config import (
    HagentConfig,
    load_base_prompt,
    PROMPT_PATH,
)


def test_prompt_path_resolves_to_repo_prompts():
    assert PROMPT_PATH.name == "hagent_base.zh.md"
    assert PROMPT_PATH.exists()


def test_load_base_prompt_returns_non_empty_chinese():
    text = load_base_prompt()
    assert len(text) > 1000
    # 含必要的中文字符（"你是 Hagent" 出现在首段）
    assert "你是 Hagent" in text


def test_hagent_config_defaults(monkeypatch):
    monkeypatch.delenv("HAGENT_MODEL", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    cfg = HagentConfig.from_env()
    assert cfg.model == "anthropic:claude-sonnet-4-6"
    assert cfg.langsmith_tracing is False


def test_hagent_config_env_overrides(monkeypatch):
    monkeypatch.setenv("HAGENT_MODEL", "anthropic:claude-opus-4-7")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    cfg = HagentConfig.from_env()
    assert cfg.model == "anthropic:claude-opus-4-7"
    assert cfg.langsmith_tracing is True
```

- [ ] **Step 2: 跑测试，验证 FAIL**

```bash
source .venv/bin/activate && pytest tests/test_config.py -v
```
Expected: ImportError / ModuleNotFoundError on `hagent.config`.

- [ ] **Step 3: 写 `src/hagent/config.py`**

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROMPT_PATH = REPO_ROOT / "prompts" / "hagent_base.zh.md"

DEFAULT_MODEL = "anthropic:claude-sonnet-4-6"


def load_base_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


@dataclass(frozen=True)
class HagentConfig:
    model: str
    langsmith_tracing: bool

    @classmethod
    def from_env(cls) -> "HagentConfig":
        return cls(
            model=os.environ.get("HAGENT_MODEL", DEFAULT_MODEL),
            langsmith_tracing=os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true",
        )
```

- [ ] **Step 4: 跑测试，验证 PASS**

```bash
pytest tests/test_config.py -v
```
Expected: 4 passed.

- [ ] **Step 5: 提交**

```bash
git add src/hagent/config.py tests/test_config.py
git commit -m "feat: add config module with base prompt loader and env config"
```

---

### Task 2: 默认 permissions

**Files:**
- Create: `src/hagent/permissions.py`
- Create: `tests/test_permissions.py`

- [ ] **Step 1: 写失败测试 `tests/test_permissions.py`**

```python
from deepagents import FilesystemPermission

from hagent.permissions import DEFAULT_PERMISSIONS


def test_default_permissions_is_list_of_filesystem_permissions():
    assert isinstance(DEFAULT_PERMISSIONS, list)
    assert len(DEFAULT_PERMISSIONS) >= 2
    for p in DEFAULT_PERMISSIONS:
        assert isinstance(p, FilesystemPermission)


def test_deny_rule_comes_before_allow_rule():
    # first-match-wins：deny 必须排前面
    first_deny_idx = next(i for i, p in enumerate(DEFAULT_PERMISSIONS) if p.mode == "deny")
    first_allow_idx = next(i for i, p in enumerate(DEFAULT_PERMISSIONS) if p.mode == "allow")
    assert first_deny_idx < first_allow_idx


def test_workspace_is_allowed_path():
    allow_rules = [p for p in DEFAULT_PERMISSIONS if p.mode == "allow"]
    paths_allowed = [path for p in allow_rules for path in p.paths]
    assert any("workspace" in path for path in paths_allowed)


def test_system_dirs_are_denied():
    deny_rules = [p for p in DEFAULT_PERMISSIONS if p.mode == "deny"]
    paths_denied = [path for p in deny_rules for path in p.paths]
    for sysdir in ["/etc/**", "/usr/**", "/var/**", "/root/**"]:
        assert sysdir in paths_denied
```

- [ ] **Step 2: 跑，验证 FAIL**

```bash
pytest tests/test_permissions.py -v
```

- [ ] **Step 3: 写 `src/hagent/permissions.py`**

```python
from __future__ import annotations

from deepagents import FilesystemPermission

DEFAULT_PERMISSIONS: list[FilesystemPermission] = [
    FilesystemPermission(
        operations=["write"],
        paths=["/etc/**", "/usr/**", "/var/**", "/root/**", "/home/**"],
        mode="deny",
    ),
    FilesystemPermission(
        operations=["read", "write"],
        paths=["/workspace/**", "/tmp/hagent/**"],
        mode="allow",
    ),
]
```

- [ ] **Step 4: 跑，验证 PASS**

```bash
pytest tests/test_permissions.py -v
```

- [ ] **Step 5: 提交**

```bash
git add src/hagent/permissions.py tests/test_permissions.py
git commit -m "feat: add default FilesystemPermission set (deny system dirs, allow workspace)"
```

---

### Task 3: 预置 subagents (researcher + coder)

**Files:**
- Create: `src/hagent/subagents.py`
- Create: `tests/test_subagents.py`

- [ ] **Step 1: 写失败测试 `tests/test_subagents.py`**

```python
from hagent.subagents import RESEARCHER, CODER, BUILTIN_SUBAGENTS


def test_researcher_has_required_keys():
    for key in ("name", "description", "system_prompt"):
        assert key in RESEARCHER
    assert RESEARCHER["name"] == "researcher"


def test_coder_has_required_keys():
    for key in ("name", "description", "system_prompt"):
        assert key in CODER
    assert CODER["name"] == "coder"


def test_builtin_list_contains_both():
    names = {a["name"] for a in BUILTIN_SUBAGENTS}
    assert names == {"researcher", "coder"}


def test_subagent_prompts_are_chinese():
    for a in BUILTIN_SUBAGENTS:
        # 至少包含一些中文字符
        chinese_chars = [c for c in a["system_prompt"] if "一" <= c <= "鿿"]
        assert len(chinese_chars) > 20, f"{a['name']} prompt 应为中文"
```

- [ ] **Step 2: 跑，验证 FAIL**

```bash
pytest tests/test_subagents.py -v
```

- [ ] **Step 3: 写 `src/hagent/subagents.py`**

```python
from __future__ import annotations

from typing import TypedDict


class SubagentDict(TypedDict, total=False):
    name: str
    description: str
    system_prompt: str


RESEARCHER: SubagentDict = {
    "name": "researcher",
    "description": (
        "做深度调研：在沙箱内读取文件、grep、查阅技术文档。"
        "适合需要广泛搜集信息或多文件交叉对比的子任务。"
    ),
    "system_prompt": (
        "你是 Hagent 的 researcher 子代理。任务范围：在用户的工作目录中做信息搜集"
        "（读文件、glob、grep、阅读 README 等）。不要修改文件，不要执行可能有副作用的命令。"
        "完成后用一段简洁文字总结发现，并明确指出可信度与证据来源（file_path:line_number）。"
    ),
}

CODER: SubagentDict = {
    "name": "coder",
    "description": (
        "聚焦在单个代码任务（写函数、改 bug、加测试）的小步实现。"
        "适合主任务被拆分后某一具体子步骤的执行。"
    ),
    "system_prompt": (
        "你是 Hagent 的 coder 子代理。在收到明确任务（要改的文件 + 期望行为）后："
        "先用 read_file 确认现状，必要时写测试，再用 edit_file / write_file 修改，"
        "最后用 execute 跑测试或脚本确认。完成后报告：改了哪些文件、跑了什么验证、结果。"
    ),
}

BUILTIN_SUBAGENTS: list[SubagentDict] = [RESEARCHER, CODER]
```

- [ ] **Step 4: 跑，验证 PASS**

- [ ] **Step 5: 提交**

```bash
git add src/hagent/subagents.py tests/test_subagents.py
git commit -m "feat: add builtin researcher and coder subagent configs"
```

---

### Task 4: `create_hagent` 工厂

**Files:**
- Create: `src/hagent/core.py`
- Create: `tests/test_core.py`

- [ ] **Step 1: 写失败测试 `tests/test_core.py`**

```python
import pytest

from hagent.core import create_hagent


def test_create_hagent_returns_runnable():
    agent = create_hagent()
    # deepagents 工厂返回的是 LangGraph runnable，至少要有 stream 方法
    assert hasattr(agent, "stream")
    assert hasattr(agent, "invoke")


def test_create_hagent_uses_base_prompt(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()
    assert "你是 Hagent" in captured["system_prompt"]


def test_create_hagent_attaches_permissions(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()
    assert "permissions" in captured
    assert len(captured["permissions"]) >= 2


def test_create_hagent_attaches_subagents(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()
    sa_names = {a["name"] for a in captured["subagents"]}
    assert sa_names == {"researcher", "coder"}


def test_create_hagent_uses_local_shell_backend_by_default(monkeypatch):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    create_hagent()
    backend = captured["backend"]
    # LocalShellBackend 是 deepagents 自带，实例类名核对
    assert type(backend).__name__ == "LocalShellBackend"
```

- [ ] **Step 2: 跑，验证 FAIL**

```bash
pytest tests/test_core.py -v
```

- [ ] **Step 3: 写 `src/hagent/core.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from deepagents import create_deep_agent as _create_deep_agent
from deepagents.backends import LocalShellBackend

from hagent.config import HagentConfig, load_base_prompt
from hagent.permissions import DEFAULT_PERMISSIONS
from hagent.subagents import BUILTIN_SUBAGENTS

DEFAULT_WORKSPACE = Path("/tmp/hagent/workspace")


def create_hagent(
    config: HagentConfig | None = None,
    backend: Any | None = None,
    extra_subagents: list[dict] | None = None,
    extra_tools: list[Any] | None = None,
    checkpointer: Any | None = None,
) -> Any:
    cfg = config or HagentConfig.from_env()
    DEFAULT_WORKSPACE.mkdir(parents=True, exist_ok=True)

    backend = backend or LocalShellBackend(root_dir=str(DEFAULT_WORKSPACE))

    subagents = list(BUILTIN_SUBAGENTS)
    if extra_subagents:
        subagents.extend(extra_subagents)

    kwargs: dict[str, Any] = dict(
        model=cfg.model,
        tools=list(extra_tools or []),
        system_prompt=load_base_prompt(),
        subagents=subagents,
        backend=backend,
        permissions=DEFAULT_PERMISSIONS,
    )
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer

    return _create_deep_agent(**kwargs)
```

注意：`checkpointer` 是可选参数；Plan 2 的 CLI demo 不传，Plan 3 Agent Server 会传一个 SqliteSaver 实例进来以保证 thread 持久化（spec §11 "再问换成柱状图"依赖此）。

- [ ] **Step 4: 跑测试**

```bash
pytest tests/test_core.py -v
```

注意：第一个测试 `test_create_hagent_returns_runnable` 会真实调用 `create_deep_agent`，可能因为没设 Anthropic API key 而 fail 在模型初始化。如果出现 "API key" 相关错误，跳过这个测试，把它改为：

```python
def test_create_hagent_returns_runnable(monkeypatch):
    monkeypatch.setattr("hagent.core._create_deep_agent", lambda **kw: type("FakeAgent", (), {"stream": lambda *a, **k: None, "invoke": lambda *a, **k: None})())
    agent = create_hagent()
    assert hasattr(agent, "stream")
    assert hasattr(agent, "invoke")
```

其余 4 个 monkeypatch 的测试不需要真实 API key，必须 PASS。

- [ ] **Step 5: 提交**

```bash
git add src/hagent/core.py tests/test_core.py
git commit -m "feat: add create_hagent factory wiring deepagents with base prompt, permissions, subagents"
```

---

### Task 5: CLI demo 子命令

**Files:**
- Modify: `src/hagent/__main__.py`
- Create: `src/hagent/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: 写失败测试 `tests/test_cli.py`**

```python
import subprocess
import sys


def test_cli_help_lists_demo():
    result = subprocess.run(
        [sys.executable, "-m", "hagent", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "demo" in result.stdout


def test_cli_demo_requires_message():
    result = subprocess.run(
        [sys.executable, "-m", "hagent", "demo"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    # argparse 缺位置参数时打到 stderr
    assert "message" in result.stderr.lower()


def test_cli_no_subcommand_prints_version():
    result = subprocess.run(
        [sys.executable, "-m", "hagent"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "hagent" in result.stdout
```

- [ ] **Step 2: 跑，验证 FAIL**

```bash
pytest tests/test_cli.py -v
```

- [ ] **Step 3: 写 `src/hagent/cli.py`**

```python
from __future__ import annotations

import argparse
import sys

from hagent import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hagent", description="Hagent CLI")
    parser.add_argument("--version", action="version", version=f"hagent {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    demo = subparsers.add_parser("demo", help="跑一个端到端 demo")
    demo.add_argument("message", help="给 agent 的用户消息")
    demo.add_argument(
        "--max-steps", type=int, default=40, help="recursion_limit (默认 40)"
    )

    return parser


def run_demo(message: str, max_steps: int) -> int:
    # 延迟 import：避免 --help 也要加载完整的 langchain 栈
    from hagent.core import create_hagent

    agent = create_hagent()
    print(f"[hagent] message: {message}")
    print(f"[hagent] running (max_steps={max_steps})…")
    final_state = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"recursion_limit": max_steps},
    )
    final_msg = final_state["messages"][-1]
    content = getattr(final_msg, "content", final_msg)
    print(f"\n[hagent] final answer:\n{content}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        print(f"hagent {__version__}")
        print("Usage: hagent demo <message>")
        return 0
    if args.command == "demo":
        return run_demo(args.message, args.max_steps)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 改写 `src/hagent/__main__.py` 路由到 cli.main**

```python
from hagent.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 跑测试**

```bash
pytest tests/test_cli.py tests/test_smoke.py -v
```

Expected: `test_cli_help_lists_demo` / `test_cli_demo_requires_message` / `test_cli_no_subcommand_prints_version` PASS。

注意：Plan 1 的 `test_cli_runs` 期望 stdout 包含 `"hagent 0.0.1"` —— 我们改 __main__ 后这条仍然成立（新 main 在无 subcommand 时打印 `f"hagent {__version__}"`）；但 Plan 1 还断言 "Plan 1 scaffold only..." 那行。改完 __main__ 这条不再打印——需要把 `tests/test_smoke.py::test_cli_runs` 里那条断言改成只检查 `"hagent 0.0.1"` 即可（即放宽断言）。

修改 `tests/test_smoke.py::test_cli_runs`：

```python
def test_cli_runs():
    result = subprocess.run(
        [sys.executable, "-m", "hagent"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "hagent 0.0.1" in result.stdout
```

（去掉 "Plan 1 scaffold only..." 那条断言。）

- [ ] **Step 6: 全量跑测试**

```bash
pytest -v
```

Expected: 全过。

- [ ] **Step 7: 提交**

```bash
git add src/hagent/cli.py src/hagent/__main__.py tests/test_cli.py tests/test_smoke.py
git commit -m "feat: add hagent CLI with demo subcommand (argparse, lazy import)"
```

---

### Task 6: 真实 API 端到端 demo（gated by env）

**Files:**
- Create: `tests/test_demo_e2e.py`

- [ ] **Step 1: 写门控的端到端测试**

```python
import os
import subprocess
import sys

import pytest


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY 未设置，跳过真实模型 e2e 测试",
)
def test_cli_demo_simple_arithmetic(tmp_path, monkeypatch):
    # 用一个最小任务避免烧 token：让 agent 算 2+2 不需要工具
    monkeypatch.setenv("HAGENT_MODEL", "anthropic:claude-haiku-4-5")
    result = subprocess.run(
        [sys.executable, "-m", "hagent", "demo", "用 read_file 看一眼 /workspace 里有什么文件，没有就回复 empty。"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    print("STDOUT:", result.stdout[-500:])
    print("STDERR:", result.stderr[-500:])
    assert result.returncode == 0
    assert "final answer" in result.stdout.lower()
```

- [ ] **Step 2: 跑（无 API key 时自动 skip）**

```bash
pytest tests/test_demo_e2e.py -v
```

Expected: SKIPPED（无 ANTHROPIC_API_KEY）或 PASSED（有 key）。

如果用户已设 API key 并希望真实跑：

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pytest tests/test_demo_e2e.py -v -s
```

- [ ] **Step 3: 提交**

```bash
git add tests/test_demo_e2e.py
git commit -m "test: add gated end-to-end CLI demo test"
```

---

### Task 7: 手动 dogfood demo（人工 review，不是自动测试）

- [ ] **Step 1: 用户确认 ANTHROPIC_API_KEY 已设置**

向用户输出：

> "Plan 2 自动化测试全过。现在要做一次真实模型的 dogfood 跑。需要你确认（1）`ANTHROPIC_API_KEY` 已设到环境里；（2）可以接受一次调用 Claude 的 token 成本（约 ¢1-5 cent）。Ready 后告诉我。"

- [ ] **Step 2: 跑真实 demo**

```bash
source .venv/bin/activate && python -m hagent demo "在 /workspace 写一个 hello.py 打印 'hello hagent'，然后用 execute 跑它"
```

Expected：
- 看到模型 plan
- 看到 write_file 调用
- 看到 execute 调用
- 最终 stdout 含 "hello hagent"
- 退出码 0
- 文件 `/tmp/hagent/workspace/hello.py` 真实存在

如果模型 plan 不调工具或行为偏离 → 不算 fail，记录现象。Plan 3 的 SSE 适配会更细粒度地暴露这些路径。

- [ ] **Step 3: 用户 review 结果**

把上一步的完整输出贴给用户。用户回"通过"才能进入 Task 8。

---

### Task 8: Plan 2 收口

- [ ] **Step 1: 跑全量 + check 脚本**

```bash
source .venv/bin/activate && pytest -v && ./scripts/check_base_prompt.sh
```

Expected: 全过。

- [ ] **Step 2: 检查 git log**

```bash
git log --oneline plan-2-m3-core 2>/dev/null || git log --oneline -15
```

Expected: ~7 个 commit 在 plan-2 分支：config / permissions / subagents / core / cli / e2e test / （可能的）fix-up。

- [ ] **Step 3: 通知用户**

> "Plan 2 完成：M3 核心模块 + CLI demo 已 ready；自动化测试全过；真实 dogfood demo 用户确认通过。准备合 main + 进入 Plan 3（M4 Agent Server）。"

---

## Plan 2 完整 Done 标准（对应 spec §4 M3）

- ✅ `hagent.config` 加载 base prompt + 环境变量配置
- ✅ `hagent.permissions.DEFAULT_PERMISSIONS` deny 系统目录 + allow workspace
- ✅ `hagent.subagents` researcher + coder 字典
- ✅ `hagent.core.create_hagent` 工厂函数，注入 base prompt / permissions / subagents / LocalShellBackend
- ✅ `hagent.cli` CLI 入口 + `demo` 子命令
- ✅ 全量单元测试 pass（不含门控 e2e）
- ✅ `python -m hagent demo "..."` 用真实 Claude 跑通 CSV / hello world 类任务
- ✅ LangSmith trace（设 `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY` 后自动启用，不需要代码）
- ✅ 所有产物入 git
