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
