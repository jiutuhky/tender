# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

Hagent 是基于 LangChain `deepagents`（0.6.x，当前 0.6.3）的薄包装层，把 deepagents 暴露成面向 Web 的 agent harness。`src/hagent/` 下都是「注入式胶水」：加载中文 base prompt、permissions、CC 对齐的自研工具、subagents / skills / hooks，最终在 `core.py` 的 `create_hagent(...)` 组装成 deepagents graph。

已落地能力：核心 + CLI、Agent Server（FastAPI + SSE）、Web 前端（`web/`，独立 Next.js 工程）、Docker/gVisor sandbox（SandboxPool + SessionManager）、SmolVM/Firecracker sandbox（server 默认 provider，含准入账本 + 孤儿治理）、Skills 子系统、CC hook 机制移植。Daytona 后端是 stub，只验证抽象不走全链路。

## 常用命令

```bash
source .venv/bin/activate        # 进虚拟环境

pytest -v                        # 全量测试（默认不需要外部 API key）
pytest tests/test_core.py::test_create_hagent_uses_base_prompt -v   # 单测
pytest tests/server -v           # server 路由 + SessionManager + sandbox 接入
pytest tests/sandbox -v          # sandbox 抽象（默认只跑 unit）
pytest tests/hooks -v            # hooks 子系统
```

门控测试（默认 skip，按需开启）：

```bash
HAGENT_TEST_DOCKER=1 pytest -m docker -v                          # docker 集成
HAGENT_TEST_GVISOR=1 pytest -m gvisor -v                          # gVisor 路径
HAGENT_TEST_SMOLVM=1 pytest -m smolvm -v                          # smolvm/Firecracker(需 KVM)
set -a && source .env && set +a && pytest tests/test_demo_e2e.py -v -s          # 真实模型（host）
HAGENT_TEST_DOCKER=1 ANTHROPIC_API_KEY=... pytest tests/test_demo_e2e_sandbox.py -v -s  # 真实模型 + sandbox
set -a && source .env && set +a && pytest tests/test_demo_e2e_prose_skill.py -v -s      # 真实模型 + 真实语料：skill 编排四矩阵 publish
```

运行与运维：

```bash
set -a && source .env && set +a
python -m hagent demo "你的指令"                   # host 模式
python -m hagent --sandbox docker demo "你的指令"  # HagentDockerSandbox
python -m hagent sandbox {ls,stop,logs}            # sandbox 容器运维

uvicorn hagent.server.app:create_app --factory --host 0.0.0.0 --port 8000  # Agent Server
./scripts/curl_smoke.sh                            # Server smoke（另起 shell）
cd web && npm run dev                              # Web 前端（需 Server 已起）
./scripts/check_base_prompt.sh                     # base prompt 完整性检查
```

## 架构

数据流：`server/routers/*` → `SessionManager`（SessionStore/SQLite ↔ SandboxPool）→ `create_hagent()` 组装的 deepagents graph → SSE 推流。

| 模块 | 职责 |
| --- | --- |
| `core.py` | `create_hagent()` 工厂，所有注入的汇合点：prompt / permissions / 自研工具 / subagents / skills / hooks middleware；禁用 deepagents 同名默认工具与 `SummarizationMiddleware` |
| `config.py` | base prompt 加载、`.env` 读取、`HagentConfig` |
| `permissions.py` | `DEFAULT_PERMISSIONS`（deny 系统目录在前、allow workspace 在后），按 session workspace 生成 |
| `bash_tool/` `file_tools/` `grep_tool/` `task_tools/` | CC 对齐的自研工具（Bash / Read·Write·Edit / Grep·Glob / TaskCreate·Update·List·Get），见下「自研工具」原则 |
| `subagents/` | CC 对齐 subagent：markdown agent 发现 → frontmatter 解析 → 编译 → `Agent` 工具注册（自管，不走 deepagents `SubAgentMiddleware`） |
| `skills/` | `Skill` 工具 + `HagentSkillsMiddleware`（skills catalog 注入 system prompt） |
| `hooks/` | CC hook 机制移植：27 事件、command/prompt/agent/http 四型执行器、三层 settings 合并、`HagentHooksMiddleware`（图内承载 PreToolUse/PostToolUse/Stop 等） |
| `backends.py` | `HagentLocalShellBackend`（默认 `inherit_env=False`，收窄环境泄漏面） |
| `assets/` | 结构化资产管理面（spec `2026-07-13-structured-assets-mcp.md`）：store/service/validators 唯一写入口 + FastMCP 工具面（15 个 `prose_*`，server 挂 `/mcp`、CLI stdio）+ loopback guard + actor 归属注入 + projection（发布物化：publish 后旧路径 final JSON 投影，`HAGENT_PUBLISH_PROJECTION` 开关，前端切 REST 后默认关）+ REST adapter（router.py：前端读端点 + 人工动作，输出模型与 MCP 共用 schemas.py） |
| `mcp_tools.py` | agent 侧真 MCP client（langchain-mcp-adapters）：loopback HTTP / stdio 连接构造 + sync 桥，经 `create_hagent(mcp_connection=...)` 注入工具面 |
| `sandbox/` | sandbox 抽象：protocol / docker（HagentDockerSandbox + image）/ **smolvm**（HagentSmolVMSandbox：image 烘焙（启动期）+ lifecycle（含 DISK 快照 persist/restore）+ reconciler + audit（命令 JSONL + sandbox_events 事件表）+ health（连败杀重建）+ metrics（/proc 采样）,Firecracker microVM,server 默认）/ daytona stub / providers（shell、file 适配）/ pool（prewarm + idle GC + max_lifetime + warm recycle + 快照休眠 + ledger 准入 + 补货熔断 + drain）/ ledger（容量账本）/ node（NodeClient 多机接缝,仅接口）/ supervisor（启动对账 + reaper/health/metrics 三循环） / **errors（沙箱基础设施错误契约：`SandboxUnavailable{reason}` + `[sandbox_unavailable:<reason>]` 中性文案表,两 provider 共用,SDK 原文只进日志）** |
| `ingest/` | PDF 入库管线：上传 PDF → OCR → 规范化 md + sidecar。`assembler.py` 是**唯一测试缝**（纯函数，版面块 →(md, sidecar)，行号一边追加一边记账）；`ocr_client.py` 分批调 PaddleOCR-VL HPS Triton HTTP 并做页级断点续跑；`pdf.py` 出预览版（**页数与逐页页面尺寸必须与原件一致**）；`blobs.py` 把原件/预览版按 sha256 存到 workspace 之外（不进 git）；`tasks.py` 登记在跑的解析，消息流据此在起 agent 前等它跑完 |
| `server/` | FastAPI app、SessionStore + ProjectStore（同一 SQLite、软删级联）、SessionManager、SSE、`routers/{sessions,messages,files,projects,project_files}` |
| `cli.py` / `__main__.py` | argparse 入口（demo、sandbox 运维子命令）；`__main__` 只路由不放业务逻辑 |

新增模块保持「一个文件一个职责」，避免堆大文件。

`web/` 是独立 Next.js 工程，遵循 `web/AGENTS.md` 与 `web/CLAUDE.md`；涉及 Next.js API、路由或框架配置时查本地已安装版本的相关指南。

## 开发原则

### 动 deepagents 上层前先读官方文档

触发条件：修改 deepagents API 调用或集成行为。先核对本目录 `deepagents/` 下相关 `.mdx`（官方文档镜像），按主题选择 backends / sandboxes / permissions / subagents / human-in-the-loop / event-streaming / mcp / harness / profiles / models；不要求逐份加载，纯注释与文字修改无需触发。

如 API 与猜测不符，**以 `.venv/lib/python3.12/site-packages/deepagents/` 实际源码为准**。历史上已两次因猜 API 名导致全 plan 返工，别再猜。

### 自研工具替换了 deepagents 默认工具

`core.py` 显式禁用 `execute / read_file / write_file / edit_file / write_todos / grep / glob / ls`，替换为 CC 对齐实现（`ls` 无对齐替代，目录列举回落 `Bash`）。修改工具 schema 或行为前，核对当前 spec 与现有测试断言（如 `null` 是否进入 JSON Schema）；`docs/plans/` 仅作历史背景，不能作为当前实施依据。

### Host / Sandbox 双模式

- host 模式（CLI 默认）是开发权宜方案：shell 不限路径，自研文件工具走 `FilesystemBackend` + file_permissions（**permissions 始终生效**，不是降级）。
- sandbox 模式下 `create_hagent` 自动切线：跳过 permissions，bash/file 工具改走 `SandboxShellProvider` + `SandboxFileTransport`（docker exec / vsock / 容器文件 API），LLM 可见 workspace 与宿主**物理分离**；base prompt 的 sandbox 段仅此模式注入。
- **server 默认 provider 是 smolvm**（Firecracker microVM,KVM 硬件级隔离）：启动经 `preflight_sandbox_kind()` 预检,失败按 `smolvm → docker → none` 降级并 WARNING;`HAGENT_SANDBOX_REQUIRE=smolvm` 强约束下预检失败直接拒绝启动。测试环境须显式 `HAGENT_SANDBOX_KIND=none`(tests/server/conftest.py 已兜底)。
- smolvm SDK 锁 `smolvm==0.0.25`,升级走显式任务并重跑 `HAGENT_TEST_SMOLVM=1 pytest -m smolvm -v`;SDK 调用点收敛在 `sandbox/smolvm/{image,lifecycle}.py`。
- **沙箱生命周期三条硬规则（2026-08-17 事故 a49b1a3d 后）**：① **run-hold**——project 有活跃 Run 时 pool GC 一律不 pause/persist/evict/max_lifetime 驱逐（`pool.set_active_run_fn(manager.has_active_runs)`），生命周期兜底 checkpoint 只在 VM 消亡场景（drain/shutdown/evict/release/健康杀重建）终结 Run；② **触达即活跃**——execute / upload / download / Bash SSH argv 四条通道入口都 `touch()` + `ensure_running()`（paused 自动唤醒并广播 "resumed"），新增通道必须照做；③ **错误契约**——沙箱层不可用一律经 `sandbox/errors.py` 产出中性文案，禁止把 SDK/客户端原文（尤其运维命令）喂给模型；工具异常由 `tool_error_guard.ToolErrorGuardMiddleware`（主图与子代理图均挂）转 error ToolMessage，不炸流。idle 阈值 `HAGENT_SANDBOX_IDLE_PAUSE_SECONDS`/`_EVICT_SECONDS`、run-hold 上限 `HAGENT_RUN_HOLD_MAX_SECONDS`。

### 子代理 / skills / hooks 的发现与缓存

- 三者的发现路径都是 `~/.hagent/` → 项目层（**server 进程 CWD**，非 LLM workspace），后者覆盖前者；只有 subagents 额外多一个 workspace 层（`<workspace>/agents`、`<workspace>/.hagent/agents`），skills 与 hooks 没有。sandbox 模式下 workspace 是 VM 内路径，宿主进程扫不到，所以 workspace 层实际只在 host 模式生效；`HAGENT_AGENTS_PATHS` / `HAGENT_SKILLS_PATHS` / `HAGENT_HOOKS_SETTINGS_PATHS` 环境变量**替换**默认路径。project_root 与 LLM workspace 物理分离——只认 workspace 永远扫不到仓库级配置。
- 子代理按 session 编译缓存：**改 agent 文件后需新建 session**，老 session 不热加载。
- frontmatter 解析对齐 CC 且更宽容（strict YAML → 加引号重试 → 宽松回退），实现在 `subagents/loader.py`——改前先读源码与测试。
- hooks 行为对齐基准是 `docs/cc-recovered-main`（CC 恢复源码）+ spec `2026-07-06-hagent-hooks-design.md`；middleware 钩子必须 **sync + async 成对实现**（SSE 走 async 路径）；hook 永远在宿主执行。使用指南见 `docs/hooks/README.md`。

### PDF 入库：两条不可动的约束

- **`use_doc_preprocessor` 恒为 false**：PaddleOCR-VL 的 unwarping 会让返回的 bbox 与原件错位，置 true 全文高亮整体失效。
- **预览版的页序、MediaBox、CropBox、Rotate、UserUnit 必须与原件逐页一致**：sidecar 的归一化 bbox 是按这套几何算出来的，改了页面几何全文高亮就整体错位，而且错得看不出来。`pdf.build_preview` 因此只压图片流与内容流，从不新建页、从不缩放页。

还有一条派生约束：**OCR 产出的 md 只读**（`file_tools/readonly.py` 在工具层拒写 `sources/` 下的 md 与 sidecar）。`line_span` 的正确性完全建立在这之上，放松它溯源会静默错位。

服务地址走配置：`HAGENT_OCR_BASE_URL`（另有 `HAGENT_OCR_BATCH_PAGES` / `HAGENT_OCR_TIMEOUT_SECONDS` / `HAGENT_OCR_RESTRUCTURE`、`HAGENT_BLOB_ROOT`、`HAGENT_INGEST_MAX_PAGES` / `HAGENT_INGEST_MAX_BYTES`）。

### 中文 base prompt 是协议级文件

`prompts/hagent_base.zh.md` 是 agent 主 system prompt。改动须配套更新 `prompts/decisions.md`（KEEP/MODIFY/DELETE 记录）+ 跑 `./scripts/check_base_prompt.sh`。**不在主对话里临时改**，走专门 sub-agent 流程。

### 凭据 / 环境变量

- API key 写仓库根 `.env`（已 gitignore），**绝不入仓**；`.env.local` / `.env.*.local` 作个人覆盖。
- Server 启动自动加载 `.env`（进程环境变量优先）；CLI / e2e 前 `set -a && source .env && set +a`。
- 门控 e2e 无 key 时 skip，不要改成强制要求。

## 相关文档

- 历史任务分解：`docs/plans/`（superpowers 时期存档，只读；plan-5 docker-backend 已被 sandbox spec 取代，勿按其实施）
- 提交与交付规范、sandbox 门控验证：见 `AGENTS.md`，记录实际结果而非仅列命令。
- 部署手册：`docs/deploy/smolvm.md`（KVM/kvm 组/sudoers/WSL2 固化/btrfs 建议/systemd 样例/`SMOLVM_DATABASE_URL`/出口白名单局限）

## No Negative Echo

生成最终产物及其包装时，包括标题、文件名、正文、注释、标签、commit、
PR 和交付说明，只描述最终采用的状态，假设读者没看过本次会话。

- 会话里的否决、中间尝试和措辞纠正，只当作控制信息，不要让它们成为最终产物的命名或叙述中心。
- 对每个交付面分别判断：不知道本次会话的读者需要这条信息吗？省略会不会导致不准确、不安全、误导或兼容性信息缺失？它是不是任务开始时已提交或用户确认状态中的真实变化，而且当前交付面需要解释它？
- 「不要提 X」不是让你写「无 X」。标题、文件名、开篇和标签应从正向目标重新生成，不要逐词修改被否文案。
- 保留真实的基线变化、已经执行的外部操作，以及必要的技术名称、诊断、测试和快照。任务开始前已有的用户改动不算被否内容。
- 不要把与本任务无关的改动写进本次 commit、PR 或交付说明。对比、引用、审计和迁移说明，只在用户要求或当前交付面确实需要时保留。
- 写完后通读全部用户可见内容及其包装，包括文件名、元数据和 hook 改写。内容发生变化后重新检查，不要另加「已清理」或「无残留」类声明。
