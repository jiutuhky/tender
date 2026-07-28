# 06 发布物化双轨：导出投影兜住旧前端

Status: resolved
Type: task
Blocked by: 03

## Parent

`.scratch/structured-assets-mcp/PRD.md`（契约：hagent spec §8）

## What to build

`src/hagent/assets/projection.py`：publish 成功后把该矩阵物化为旧路径兼容 JSON（`bid_response_matrix_<slug>_<ts>/final/<matrix_type>.json`，envelope 含 generated_at/source_documents 由对象库导出），受配置开关（默认开，08 票完成后关）。物化是只读投影：不回读、不参与校验、重发布即覆盖。偏离表导出复用同模块（按应答状态过滤的投影，格式后续票定义，本票留接口）。

## Acceptance criteria

- [x] 四矩阵 publish 后旧前端（未改动的 `lib/hagent/matrix.ts` 扫描 + resumeProject）能正常发现并渲染
- [x] 物化文件 schema 与原 final JSON 契约一致（对拍原脚本产物）
- [x] 开关关闭时零文件写入
- [x] 物化失败不影响 publish 事务（投影是 best-effort，失败记 WARNING）

## Resolution notes

- 原三脚本从未入库（git 历史无 `assemble_matrix.py` 等），「对拍原脚本产物」落地为对拍
  现存契约：`frontend/lib/hagent/matrix.ts` 类型 + `workspace.ts` 扫描正则 + `validators.META_SKELETONS`
  区段嵌套路径（`tests/assets/test_projection.py` 锁定）。
- 物化文件由投影自行 git 提交：前端经 `git ls-files` 列举 workspace，而 sandbox 模式
  checkpoint 只收 guest 变更，host 侧投影文件不提交就永远不可见。
- 实现期定案已回写 spec §8。
