# 07 REST adapter：前端读端点与人工动作

Status: resolved
Type: task
Blocked by: 01, 02

## Parent

`.scratch/structured-assets-mcp/PRD.md`（契约：hagent spec §2 S2、§4–§5）

## What to build

`src/hagent/assets/router.py` 挂 `server/routers/`：读——矩阵 envelope + 分组统计（决策触发器数字）、条目分页查询（过滤参数与 MCP `prose_query_matrix_items` 对齐，偏离表投影同源）、四矩阵状态汇总（08 票恢复路径用）；写——人工动作 confirm / set_response_status（audit actor_kind=user）。与 MCP adapter 同委托 service.py，无独立业务逻辑。

## Acceptance criteria

- [x] 读写全部经 service 层，审计事件区分 user 与 agent 来源
- [x] 条目查询与 MCP 工具同参数同结果（同一过滤/分页语义）
- [x] 人工动作与 agent 写并发时乐观锁行为正确（409 + 当前 version）
- [x] `pytest tests/server -v` 覆盖新路由，全绿（tests/server/test_assets_api.py，13 例；全量 1160 passed）

## 实现记录（2026-07-13）

- 路由：`GET /projects/{pid}/matrices`（四矩阵汇总）、`GET …/matrices/{type}`（overview）、
  `GET …/matrices/{type}/items`（分页查询）、`POST …/items/{id}/confirm`、
  `PUT …/items/{id}/response-status`。
- 同结果由共用模型锁定：读输出模型与转换器抽到 `assets/schemas.py`，MCP 与 REST 同一来源。
- 人工动作乐观锁：service 层 `confirm_item` / `set_item_response_status` 增加可选
  `expected_version`（被拒尝试照落审计），REST 映射 409 + `current_version`。
