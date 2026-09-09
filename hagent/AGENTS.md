# Repository Guidelines

面向所有编码 agent（Codex / Claude Code / 其他）的 hagent 仓库指南。架构细节与开发原则的完整版在 `CLAUDE.md`（普通 markdown，按需直接打开读）。

## 项目结构

- `src/hagent/` —— Python 包（requires-python >=3.11，venv 当前 3.12）。`core.py` 是 `create_hagent()` 工厂、所有注入的汇合点；`config.py` / `permissions.py` / `backends.py`；CC 对齐自研工具在 `bash_tool/` `file_tools/` `grep_tool/` `task_tools/`；`subagents/` `skills/` `hooks/` 三个子系统；`sandbox/`（docker / smolvm=Firecracker microVM（server 默认 provider）/ daytona stub / pool / ledger / supervisor）；`server/`（FastAPI + SSE，`routers/{sessions,messages,files,projects}`）；入口 `cli.py` / `__main__.py`。
- `tests/` 镜像包结构：`tests/server/`、`tests/sandbox/`、`tests/hooks/` 等。
- `prompts/` —— 中文 base prompt（协议级文件，见「关键约束」）；`scripts/` —— 辅助脚本；`web/` —— 独立 Next.js 工程，有自己的 `web/AGENTS.md` 与 `web/CLAUDE.md`。
- `docs/specs/` —— 设计规格（当前实施对象：`2026-07-10-project-workspace-design.md`）；`docs/plans/` —— 只读历史存档，**勿按其实施**；`docs/hooks/` 使用指南；`docs/deploy/` 部署手册。

## 领域文档

- 领域词汇与架构决策：根 `CONTEXT-MAP.md` 索引各上下文的 `CONTEXT.md`（多上下文布局），全局 ADR 在根 `docs/adr/`，消费规则见根 `docs/agents/domain.md`。

## 构建、测试与开发命令

命令在 `hagent/` 下执行。按受影响模块选择测试；纯指令/文档修改检查引用与格式即可。默认 unit 测试可直接运行并修复本次引入的失败；全量与门控集成测试按改动覆盖面选择，保留以下 sandbox 验证要求。环境不可用时如实记录未运行项，不把 skip 当作通过。

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
- 独立前端遵循 `web/AGENTS.md`；涉及 Next.js API、路由或框架配置时查已安装版本的相关文档。

## 关键约束（改这些区域前必读）

- **deepagents API 或集成行为**：改动前核对 `hagent/deepagents/` 中对应的官方 `.mdx` 镜像（本目录下为 `deepagents/`）；与实际行为不符时以本目录 `.venv` 安装的 deepagents 源码为准。文件中的纯注释或文字修改不触发整套文档阅读。
- **自研工具**（Bash / Read·Write·Edit / Grep·Glob / Task*）替换了 deepagents 同名默认工具，schema 与行为对齐 Claude Code 是反复磨过的细节——改前先读对应 spec 与现有测试断言。
- **`prompts/hagent_base.zh.md` 是协议级文件**：改动须同步更新 `prompts/decisions.md` 并跑 `./scripts/check_base_prompt.sh`，不在主对话里临时改。
- **凭据**：API key 只放仓库根 `.env`（已 gitignore），`.env.local` / `.env.*.local` 作个人覆盖，绝不入仓；门控 e2e 无 key 时 skip，不要改成强制要求。
- **smolvm SDK 锁 `smolvm==0.0.25`**：升级走显式任务，并重跑 `HAGENT_TEST_SMOLVM=1 pytest -m smolvm -v`。

## No Negative Echo

生成最终产物及其包装时，包括标题、文件名、正文、注释、标签、commit、
PR 和交付说明，只描述最终采用的状态，假设读者没看过本次会话。

- 会话里的否决、中间尝试和措辞纠正，只当作控制信息，不要让它们成为最终产物的命名或叙述中心。
- 对每个交付面分别判断：不知道本次会话的读者需要这条信息吗？省略会不会导致不准确、不安全、误导或兼容性信息缺失？它是不是任务开始时已提交或用户确认状态中的真实变化，而且当前交付面需要解释它？
- 「不要提 X」不是让你写「无 X」。标题、文件名、开篇和标签应从正向目标重新生成，不要逐词修改被否文案。
- 保留真实的基线变化、已经执行的外部操作，以及必要的技术名称、诊断、测试和快照。任务开始前已有的用户改动不算被否内容。
- 不要把与本任务无关的改动写进本次 commit、PR 或交付说明。对比、引用、审计和迁移说明，只在用户要求或当前交付面确实需要时保留。
- 写完后通读全部用户可见内容及其包装，包括文件名、元数据和 hook 改写。内容发生变化后重新检查，不要另加「已清理」或「无残留」类声明。

## 提交与交付

- Conventional Commit 风格带 scope：`feat(web):`、`fix(server):`、`test(server):`、`docs(spec):` 等；提交保持小而聚焦。
- 交付记录说明行为变化、实际验证结果与相关 spec；若用户另外要求 PR，采用相同内容。可见改动在浏览器可用时附截图。
- 涉及 sandbox 实现的改动，交付记录须包含以下验证结果：

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
