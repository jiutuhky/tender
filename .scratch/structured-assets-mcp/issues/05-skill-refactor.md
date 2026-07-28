# 05 skill 重构：bid-response-matrix 瘦身

Status: resolved
Type: task
Blocked by: 04

## Parent

`.scratch/structured-assets-mcp/PRD.md`（契约：hagent spec §7）

## What to build

重构 `hagent/.hagent/skills/bid-response-matrix/`：SKILL.md 重写为工具化编排（注册文档 → 开草稿 ×4 → 派 4 worker 用 `prose_submit_matrix_records` → 行级修复 → validate → publish）；`worker-instructions.md` 保留认知指南（分类/mandatory 信号/粒度/冲突保守处理/覆盖自检），删除文件写纪律与中间文件协议；删除 `scripts/` 三脚本与 schema reference 的中间文件章节。遵循 writing-great-skills 规范（重构时加载该 skill）。resource 镜像联动：`prose://guides/extraction` 直读本 skill 的指南文件，单一来源。

## Acceptance criteria

- [x] skill 全文无一处文件写路径引用（run folder / scratch folder / chunk / merge_plan / final JSON 概念全部退场）
- [x] 认知指南与工具 description 零重复：方法论只在 skill/镜像 resource，工具契约只在 description
- [x] 门控 e2e（真实模型 + 真实招标语料）：skill 编排走通四矩阵 publish，保真校验 pass（deepseek-v4-flash + 信保体系语料实跑，170 条 0 error，6 分钟）
- [x] `.hagent` 下既有 skill eval 流程可对新版 skill 复跑（语料路径更新；新工作区 bid-response-matrix-workspace，grade.py 对实跑产物 13/13）
