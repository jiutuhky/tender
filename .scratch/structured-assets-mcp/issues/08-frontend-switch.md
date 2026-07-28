# 08 前端切换：REST 读 + 新槽位推导 + 关物化

Status: resolved
Type: task
Blocked by: 05, 06, 07

## Parent

`.scratch/structured-assets-mcp/PRD.md`（契约：hagent spec §8）

## What to build

前端矩阵数据源从扫 workspace 文件切到 REST：`lib/hagent/matrix.ts` 改调新端点（envelope+统计、条目分页）；resumeProject 改查矩阵状态端点；解析期间槽位状态推导改监听 SSE 新工具名事件（`prose_submit_matrix_records` 提交进度 / `prose_publish_matrix` 终态），恢复逐张点亮；抽屉内确认/偏离动作接 REST 写端点。全链路验证后关闭 06 票物化开关并删除旧扫描代码。触发方式不变（仍发 `/skill:bid-response-matrix` 消息）。

## Acceptance criteria

- [x] 新项目解析全流程：四卡逐张点亮 → 停靠编排正常（canvas-matrix-choreography 行为不回归）
- [x] 恢复/刷新路径直接呈现停靠态，数据来自 REST 而非文件
- [x] 抽屉确认/偏离操作落库并在审计中可见 actor=user
- [x] 物化开关关闭后 workspace 不再出现 `bid_response_matrix_*` 目录；旧扫描代码删除
- [x] `pnpm typecheck` + `pnpm lint` 全绿

## 实现记录（2026-07-13）

- 读路径：`app/api/hagent/projects/[pid]/matrices/**` 五条同源代理 + `api.ts` 客户端
  （状态汇总 / overview / 条目分页翻页 / confirm / response-status，409 抛
  `MatrixWriteConflictError` 带 current_version）。`assembleMatrixDocument`（matrix.ts）
  把 meta + 区段行按 dot-path 拼回旧 final JSON 形状，四张卡渲染组件零改动；items
  行级管理状态另存槽位 `itemRows`。
- 槽位推导（store）：`tool_call.started` 按 call_id 累积 args 分片、正则提取矩阵名；
  `prose_submit_matrix_records` → 翻「解析中」（仅 empty/error 槽），
  `prose_publish_matrix` completed → REST 装载点亮（门禁拒绝时装载发现未发布不落数据）。
  流末 `loadResults` 全量对账兜事件缺漏；恢复路径查状态端点只装载已发布矩阵。
  同 (pid, type) 装载共用 in-flight promise，跨项目靠 alive() 防串台。
- 抽屉人工动作：RequirementDetail 条目行加确认按钮 + 应答状态三态签
  （合规/正偏离/负偏离，语义色对齐徽标口径）；带 expected_version，409 时后台重载
  该矩阵并提示核对重试。矩阵卡的「复制 JSON 路径」动作随文件退场删除。
- 关物化：`projection_enabled` 默认翻转为关（显式 1/true/yes/on 才物化，留作排障
  逃生门）；`projection.py` 模块保留（偏离表导出接口在此）。删除
  `latestRunDir`/`MATRIX_FINAL_RE`/runDir 状态/checkpointed 触发刷新/
  `listWorkspaceFiles`/`readWorkspaceText` 及 workspace 文件读代理路由。
- 顺带：`toolLabel.ts` 补 15 个 `prose_*` 工具的中文流内说明（执行流可读性，超出票面）。
- 评审修正（双轴 code-review）：流正常收尾/恢复路径把未发布槽位 settle 为 error 终态
  （部分发布失败不卡停靠闸），流中断路径不 settle（保「解析中断」定格）；args 分片按
  call_id 续接不再校验空 tool_name（SSE §4.2 极早期分片）；人工动作无行级状态时拒绝盲写。
- 已知边界：REST 条目查询无 stage 参数（对齐 MCP「有草稿读草稿」靶点规则），
  `published_drafting`（逃生门重抽中）期间刷新页面会呈现在途草稿行而非上一发布版；
  同会话路径不受影响（就绪槽保留旧数据直到重新发布）。如需精确呈现需后端补 stage 读参。
- 验证：`pnpm typecheck` + `pnpm lint` 全绿；hagent `pytest tests/assets tests/server`
  359 passed（新增 default-off 物化测试）。运行时冒烟（种子对象库 + 双服务 + Chrome
  实操）：恢复路径停靠渲染、抽屉确认/偏离落库（asset_events actor_kind=user）、
  乐观锁冲突提示 + 自动刷新、publish 后零 `bid_response_matrix_*` 目录、
  SSE 事件推导（分片 args → loading，publish completed → REST 装载 ready）均通过。
  真实模型全流程（`/skill:bid-response-matrix` 实跑四卡逐张点亮）依赖门控 e2e 环境，
  推导链已按 SSE 契约（§4.2 args 分片 / call_id 回填 / 子代理 parent 归属）逐项冒烟。
