# Repository Guidelines

面向所有编码 agent（Codex / Claude Code / 其他）的 hagent 仓库指南。架构细节与开发原则的完整版在 `CLAUDE.md`（普通 markdown，按需直接打开读）。

## 项目结构

- `src/hagent/` —— Python 包（requires-python >=3.11，venv 当前 3.12）。`core.py` 是 `create_hagent()` 工厂、所有注入的汇合点；`config.py` / `permissions.py` / `backends.py`；CC 对齐自研工具在 `bash_tool/` `file_tools/` `grep_tool/` `task_tools/`；`subagents/` `skills/` `hooks/` 三个子系统；`sandbox/`（docker / smolvm=Firecracker microVM（server 默认 provider）/ daytona stub / pool / ledger / supervisor）；`server/`（FastAPI + SSE，`routers/{sessions,messages,files,projects}`）；入口 `cli.py` / `__main__.py`。
- `tests/` 镜像包结构：`tests/server/`、`tests/sandbox/`、`tests/hooks/` 等。
- `prompts/` —— 中文 base prompt（协议级文件，见「关键约束」）；`scripts/` —— 辅助脚本；`web/` —— 独立 Next.js 工程，有自己的 `web/AGENTS.md` 与 `web/CLAUDE.md`。
- `docs/specs/` —— 设计规格（当前实施对象：`2026-07-10-project-workspace-design.md`）；`docs/plans/` —— 只读历史存档，**勿按其实施**；`docs/hooks/` 使用指南；`docs/deploy/` 部署手册。

## 工作项与领域文档

- 新工作项一律走仓库根 `.scratch/<feature>/`，约定见根 `docs/agents/issue-tracker.md`；仓库根 `tickets.md` 是该约定之前的 M1 拆票，内容仍有效。
- 领域词汇与架构决策：根 `CONTEXT-MAP.md` 索引各上下文的 `CONTEXT.md`（多上下文布局），全局 ADR 在根 `docs/adr/`，消费规则见根 `docs/agents/domain.md`。

## 构建、测试与开发命令

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest -v                        # 全量测试（默认不需要外部 API key）
pytest tests/server -v           # server 路由 + SessionManager + sandbox 接入
pytest tests/test_core.py::test_create_hagent_uses_base_prompt -v   # 单测示例
```

门控测试（默认 skip，按需开启）：

```bash
HAGENT_TEST_DOCKER=1 pytest -m docker -v
HAGENT_TEST_GVISOR=1 pytest -m gvisor -v
HAGENT_TEST_SMOLVM=1 pytest -m smolvm -v                            # 需 KVM
set -a && source .env && set +a && pytest tests/test_demo_e2e.py -v -s   # 真实模型
```

运行与联调：

```bash
uvicorn hagent.server.app:create_app --factory --host 0.0.0.0 --port 8000
./scripts/curl_smoke.sh                            # Server smoke（另起 shell）
cd web && npm install && npm run dev               # Web 前端（需 Server 已起）
```

## 编码风格与命名

- 清晰带类型的 Python，一个模块一个职责，避免堆大文件。
- 测试文件 `test_<module>.py`，测试函数 `test_<behavior>`；unit 测试用 `monkeypatch` / 本地 stub，不打真实模型。
- 前端遵循 `web/` 内既有 TypeScript / Next.js 约定；改 Next.js 相关代码前先读 `web/node_modules/next/dist/docs/` 下的本地文档，不凭训练数据写。

## 关键约束（改这些区域前必读）

- **deepagents 上层**（`core.py`、`subagents/`、`permissions.py`、`backends.py` 或任何 `deepagents.*` 调用）：先读仓库根 `deepagents/` 目录下对应的官方 `.mdx` 文档镜像；与预期不符时以 `.venv/lib/python3.12/site-packages/deepagents/` 实际源码为准，**不要猜 API**。
- **自研工具**（Bash / Read·Write·Edit / Grep·Glob / Task*）替换了 deepagents 同名默认工具，schema 与行为对齐 Claude Code 是反复磨过的细节——改前先读对应 spec 与现有测试断言。
- **`prompts/hagent_base.zh.md` 是协议级文件**：改动须同步更新 `prompts/decisions.md` 并跑 `./scripts/check_base_prompt.sh`，不在主对话里临时改。
- **凭据**：API key 只放仓库根 `.env`（已 gitignore），`.env.local` / `.env.*.local` 作个人覆盖，绝不入仓；门控 e2e 无 key 时 skip，不要改成强制要求。
- **smolvm SDK 锁 `smolvm==0.0.25`**：升级走显式任务，并重跑 `HAGENT_TEST_SMOLVM=1 pytest -m smolvm -v`。

## 提交与 PR

- Conventional Commit 风格带 scope：`feat(web):`、`fix(server):`、`test(server):`、`docs(spec):` 等；提交保持小而聚焦。
- PR 描述须写明行为变化、列出跑过的验证命令、链接相关 spec / 工作项，前端可见改动附截图。
- 涉及 sandbox 的改动，PR 描述必须包含以下验证：

```bash
HAGENT_TEST_DOCKER=1 pytest -m docker -v
```

如果改动涉及 gVisor 路径：

```bash
HAGENT_TEST_GVISOR=1 pytest -m gvisor -v
```

如果改动涉及 smolvm（Firecracker）路径：

```bash
HAGENT_TEST_SMOLVM=1 pytest -m smolvm -v
```
