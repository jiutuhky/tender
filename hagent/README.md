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

## 运行 Agent Server

以下命令在 `hagent/` 目录执行；从 Prose 仓库根目录启动前先运行 `cd hagent`。
服务按进程工作目录发现 `.hagent/` 下的技能、子代理与 hooks 配置。

```bash
source .venv/bin/activate
# 在仓库根目录 .env 中配置 ANTHROPIC_API_KEY 等变量；
# Agent Server 启动时会自动加载 .env，已有进程环境变量优先。

uvicorn hagent.server.app:create_app --factory --host 0.0.0.0 --port 8000
```

使用其他端口时，同时设置内部工具服务地址。例如后端运行在 8011 时，设置
`HAGENT_MCP_URL=http://127.0.0.1:8011/mcp`；该地址必须指向本进程提供的
`/mcp`，否则智能体在首次发送消息、加载工具时会连接失败。

另起一个 shell 跑 smoke 测试：

```bash
./scripts/curl_smoke.sh
```

## 运行 Web 前端

```bash
cd web
npm install   # 首次
npm run dev
```

打开 http://localhost:3000。需要 Agent Server 已在 8000 端口跑（见上一节）。

可选环境变量（`web/.env`）：
- `NEXT_PUBLIC_HAGENT_API_BASE`（默认 `http://localhost:8000`）
- `NEXT_PUBLIC_HAGENT_API_KEY`（与 server 的 `HAGENT_API_KEY` 一致）


## 模型调用恢复

主智能体和所有编译子智能体共用 `model_retry` 恢复层。默认最多 10 次重试，即每个模型轮
最多 11 次请求；SDK 内层重试关闭。保持配置中的 Anthropic 模型、网关与认证方式。
新模型轮独立计算预算，不重跑此前成功的工具，不设置累计重试时间上限。

在 `hagent/.env` 或服务进程环境中配置：

| 环境变量 | 默认值 | 含义 |
|---|---:|---|
| `HAGENT_MODEL_MAX_RETRIES` | `10` | 初始请求之后允许的重试次数，`0` 禁用重试 |
| `HAGENT_MODEL_RETRY_BASE_MS` | `500` | 指数退避起点，毫秒 |
| `HAGENT_MODEL_RETRY_MAX_DELAY_MS` | `32000` | 退避基准上限，正抖动之前 |
| `HAGENT_MODEL_CONNECT_TIMEOUT_SECONDS` | `10` | 建连超时 |
| `HAGENT_MODEL_FIRST_RESPONSE_TIMEOUT_SECONDS` | `600` | 首响应有效事件等待上限 |
| `HAGENT_MODEL_STREAM_IDLE_TIMEOUT_SECONDS` | `90` | 流内无有效进展上限 |

第 r 次重试等待 `min(500 × 2^(r−1), 32000)` 毫秒，再加 0–25% 正抖动。
服务端的有效 `retry-after-ms` 优先，其次 `Retry-After`（秒或 HTTP 日期），在要求的时间后
再加最多 1 秒抖动。`x-should-retry:false` 禁止重试；认证、账单、权限、参数、上下文、模型、
协议和证书错误始终优先快速失败，包括网关用 HTTP 500 包装的 `convert_request_failed`。
连接故障、限流、过载、临时服务错误、不完整响应和超时允许重试。

看门狗默认开启：45 秒无进展提示较慢，90 秒关闭响应并重试。自定义更短超时时，较慢提示
提前到该超时的一半。文字、思考、工具参数增量视为有效进展，心跳不续期；正常持续输出
不受生成总时长限制。同步入口和异步入口共用异步传输和同一分类、预算、退避策略。
每次尝试独占请求客户端，取消和流结束都会回收响应、待处理读取及客户端。

Web 端倒计时与“停止本轮”通过 SSE 及幂等取消 API 实现，具体契约见
[消息事件手册](docs/sse-message-events.md#9-模型重试输出替换与取消)。运行级取消不会删除会话或项目文件。

实现参考仓库内 Claude Code 的 `withRetry.ts`、`claude.ts` 流看门狗和 `client.ts` 超时设置；
不切换用户配置的模型。故障模拟使用本地 MockTransport，不访问真实模型或启动沙箱：

```bash
.venv/bin/pytest tests/model_retry tests/server tests/test_tool_error_guard.py -q
cd ../frontend
pnpm test:recovery
pnpm typecheck
pnpm lint
pnpm build
```
