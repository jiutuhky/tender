@AGENTS.md

## API base 端口必须与后端一致

前端通过 `web/.env` 的 `NEXT_PUBLIC_HAGENT_API_BASE`（默认 `http://localhost:8000`）请求后端。**该端口必须等于 Agent Server 实际监听端口（README / `hagent/CLAUDE.md` / `scripts/curl_smoke.sh` 一律 8000）**，否则 `createSession` 等 fetch 报 `Failed to fetch`（指向了没有服务的端口）。改完 `.env` 后必须重启 `next dev`——`NEXT_PUBLIC_*` 在启动时注入，热更新不生效。

## Sandbox 模式下的前端行为

当 server 端启用 sandbox（`HAGENT_SANDBOX_KIND=docker`），所有新建 session 默认在 docker 容器内运行：

- 文件 API（`/sessions/{sid}/files`、`/sessions/{sid}/files/{path}`）行为不变——内部由 server 透明转 `sandbox.upload_files` / `download_files`。
- `sandbox.created` / `sandbox.paused` / `sandbox.resumed` / `sandbox.evicted` / `sandbox.error` 事件**仅在 `sse.py` 定义（`render_sandbox_event` / `SandboxEvent`）并有契约测试，当前尚未接入 `/sessions/{sid}/messages` 消息流**——`render_sandbox_event` 无生产调用方，前端不会收到这些事件，**不要据此假设它们会到达**。若未来接入，注意其帧格式与主流不同（`data` 自带 `event` 键、无自增 `id:` 行）。消息流上的全部事件契约见 `hagent/docs/sse-message-events.md`。
- 文件树展示的路径是 sandbox 内路径（`/workspace/...`），不要尝试转换为 host 路径。
- 创建 session 的 `POST /sessions` body 接受可选 `sandbox_kind: "none" | "docker" | "daytona"`；前端 UI 默认透传 server 的默认值。
