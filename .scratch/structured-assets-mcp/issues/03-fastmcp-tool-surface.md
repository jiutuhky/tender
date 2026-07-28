# 03 FastMCP 工具面与双 transport

Status: resolved
Type: task
Blocked by: 01, 02

## Parent

`.scratch/structured-assets-mcp/PRD.md`（契约：hagent spec §5–§6）

## What to build

`src/hagent/assets/mcp.py`：15 个 `prose_*` 工具（清单与参数见 spec §5 表），全部薄委托 service.py。Pydantic 输入/输出 schema（structured output）；annotations（读类 readOnlyHint、drop 与 discard 路径 destructiveHint、register_document idempotentHint）；`submit_records` schema 强制 maxItems=10；`query_matrix_items` 强制分页（limit 默认 20，返回 has_more/next_offset/total_count）+ 过滤参数（含应答状态 = 偏离表投影）；`get_matrix` 只返回 envelope + 分组统计。resources：`prose://contracts/matrix-schema`、`prose://guides/extraction`（直读 skill 目录文件）。挂载：hagent FastAPI `/mcp`（Streamable HTTP，stateless JSON，绑 127.0.0.1 + Origin 校验）；另提供 stdio 入口（CLI 用，日志走 stderr）。

## Acceptance criteria

- [x] MCP Inspector 连通两种 transport，工具清单/schema/annotations 与 spec §5 一致（以 MCP SDK client 自动化验证：真 stdio 子进程 + HTTP JSON-RPC 双链路断言清单/schema/annotations；Inspector 手测命令见 Comments）
- [x] 工具 description 只含该工具自身契约，不含抽取方法论（职责剥离纪律）
- [x] 草稿态等一切状态只在 DB：同一草稿流程跨 stdio 与 HTTP 两个 client 交替操作行为一致
- [x] 非 loopback Origin 的 HTTP 请求被拒
- [x] 错误返回结构化且可行动（含建议下一步），不暴露内部栈
- [x] pytest 起 stdio client 走通 注册→开草稿→提交→修复→validate→publish 全链
- [x] `prose_publish_matrix` 无条件挂全套门禁（`service.publish_gate`），不存在绕过校验的发布路径（票 02 评审遗留：服务层 `publish(validate=None)` 是可选接缝，强制性由本票落实）

## Comments

2026-07-13（实现，agent）：落地为 `hagent/src/hagent/assets/mcp.py`（15 工具 + 2 resource + LoopbackOnlyASGI + stdio 入口），挂载改 `hagent/src/hagent/server/app.py`，服务层接缝扩展 `service.py`/`store.py`/`model.py`。测试 `tests/assets/test_mcp_{surface,transports}.py` + `test_mcp_seams.py`，全仓 1122 passed。实现期决策（已回写 spec §5–§6）：

- **`prose_register_document` 不收 sha256**：服务端按 workspace 相对路径读文件计算（`service.register_workspace_document`，含路径穿越防护）。agent 自报 sha 既不可信也多余。
- **「最近校验摘要」数据源**：`validate_matrix` 默认仍纯读；MCP 工具调用传 actor 时落一条 `validate_matrix` 审计事件（status/error_count/checked_items 摘要），`prose_get_matrix_status` 读最近一条。对象数据不被触碰，annotation 仍标 readOnlyHint。
- **发布无旁路**：新增 `service.publish_gated`（gate + publish 组合），MCP/REST adapter 一律走它。
- **挂载方式**：FastMCP 子 app 自带 `/mcp` 路径、整体挂 FastAPI 根（`Mount("/mcp")` 会对不带尾斜杠的 POST /mcp 发 307，部分 client 不跟随）；`LoopbackOnlyASGI` 双校验（对端 IP + Origin 均须 loopback），仅作用于 `/mcp` 路径。
- **stdio 入口** `python -m hagent.assets.mcp`：DB 路径 env 链与 server 一致（`HAGENT_SESSIONS_DB` → `HAGENT_DB_PATH` → 默认）；对象库连接开 WAL + busy_timeout 支撑跨进程共享；日志只进 stderr。
- **错误面**：ToolError 文本内嵌 JSON（code/message/hint；乐观锁冲突加 current_version；publish 拒绝附完整校验报告）；意外异常只透出异常类型名，栈进 server 日志。
- run 归属经 `HAGENT_MCP_ACTOR_REF` 注入 actor_ref，票 04 client 接线时闭环。

双轴评审（Standards + Spec 并行子代理）后的修正：`publish_gated` 门禁报告落校验摘要事件（发布后 status 摘要不陈旧，拒绝也留痕）；`LoopbackOnlyASGI` 拆到 `assets/mcp_guard.py`（一文件一职责）；DB 路径 env 链收敛为 `config.resolve_sessions_db_path()`（app.py / stdio 入口 / `get_asset_service` 三处共用，顺带闭环票 01 备注的兜底路径分叉）；`store.item_stats` 返回 `MatrixStats`（去掉字典隐式耦合）。评审建议中**拒绝**的一条：`_default_workspace_for` 不改用 ProjectWorkspace——`hagent.server` 包 `__init__` 连带加载 app.py（其 import 本模块，成环），且 stdio 子进程不该背上 server 依赖，注释已说明。

Inspector 手测：`npx @modelcontextprotocol/inspector`——stdio 填 `python -m hagent.assets.mcp`（cwd hagent/、带 env）；HTTP 起 server 后连 `http://127.0.0.1:8000/mcp`（Streamable HTTP）。
