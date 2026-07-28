# 01 对象库与结构化资产服务

Status: resolved
Type: task

## Parent

`.scratch/structured-assets-mcp/PRD.md`（契约：hagent spec `2026-07-13-structured-assets-mcp.md` §3–§4）

## What to build

`src/hagent/assets/` 新模块：`documents` / `matrices` / `matrix_items` / `matrix_revisions` / `asset_events` 五表（挂现有 hagent SQLite，SessionStore 同库），`store.py` + `service.py` 领域动作层。服务层是唯一写入口：草稿生命周期（start_draft / submit_records / 行级 update·drop·move / set_meta）、publish 原子切换（快照 → 晋升 → 清草稿）、document registry（同 project+sha256 幂等）、条目乐观锁（expected_version 不符返回可行动冲突错误）、每笔变更写 asset_events（actor_kind/actor_ref/before/after/reason）。

## Acceptance criteria

- [x] 行级工具靶点规则成立：有草稿写草稿，无草稿写当前版；`submit_records` 在非草稿态被拒绝并给出下一步建议
- [x] published 状态下 `start_draft` 必须显式 `discard_manual_states=true`，否则拒绝
- [x] publish 原子性：中途失败不产生半切换状态；成功后 revisions 出现完整快照、rev 递增
- [x] 乐观锁：并发 update 同一条目，后写者收到冲突错误（含当前 version 与重读指引），审计记录双方
- [x] 全部动作产生 asset_events 记录；无任何代码路径绕过 service 直写对象表
- [x] `pytest tests/assets -v` 全绿；不依赖外部 API key

## Comments

2026-07-13（实现，agent）：落地为 `hagent/src/hagent/assets/`（model / errors / store / service），测试 `hagent/tests/assets/` 46 例全绿（全仓 1050 passed）。实现期决策：

- **revision 快照对象 = 晋升后的新当前版**（rev N = 第 N 次发布的完整内容）。spec §3 原文「快照 current 入 revisions」字面是快照出局旧版，但首个发布会得到空快照，与本票 AC「成功后 revisions 出现完整快照」矛盾；发布间隙的行级变更与人工状态靠 asset_events before/after 逐笔可恢复。已回写 spec §3。**如需在逃生门重发布时额外快照被覆盖的旧当前版（双快照），另开票。**
- 超本票清单但按 spec §4「service 与工具表一一对应」补齐：`set_item_response_status` / `confirm_item`（票 03/07 的消费接缝）与 `get_asset_service` 单例接线（镜像 `server/projects.py` 模式）。
- publish 的校验门禁留 `validate: Callable[[dict, list[MatrixItem]], None]` 接缝，票 02 的 validators.py 从此接入。
- 「同库」注记：`get_asset_service` 兜底与 `projects.get_project_store` 同为 `HAGENT_DB_PATH`；server 装配处（app.py 用 `HAGENT_SESSIONS_DB` 链）尚未调 `set_asset_service`，随票 03/07 挂载时闭环。
- 冲突审计：乐观锁冲突在独立提交路径落 `update_matrix_item` 事件（after=null + 冲突 reason）后再抛 `ConflictError`，满足「审计记录双方」。
