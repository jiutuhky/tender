---
name: bid-response-matrix
description: Parse tender and procurement documents (RFP/RFQ, 招标文件) into four source-backed response matrices — basic_info, business, technical, scoring — for bid preparation and frontend display. Use when the user provides tender or bid documents and asks to extract requirements, scoring criteria, mandatory clauses, or a compliance/response matrix (解析招标文件、生成应答矩阵、提取评分办法、商务/技术/资质要求).
---

# Bid Response Matrix

把一套招标文件抽取成四个源文可溯的应答矩阵：`basic_info`、`business`、`technical`、`scoring`。矩阵活在对象库里，读写只走 `prose_*` 工具；每个工具自身的参数与行为契约在其 description 里，本文件只做编排。两份参考文件按需加载：

- `references/worker-instructions.md` —— 单次抽取 pass 的完整认知指南（分类、mandatory 信号、粒度、冲突处理、覆盖自检）。每个 pass 开工前必须通读。
- `references/response-matrix-schema.md` —— 数据契约：envelope 与各区段记录的形状。提交任何记录前先读目标矩阵的章节。

## 前置

- **project_id 是 hagent 项目 id，不是招标文件正文里的项目编号**（别拿「项目编号：2025-XX-001」当它用）。你无从直接看到它——workspace 在你眼里就是 `/workspace`。所以：**不要猜，先随便调一次 `prose_get_matrix_status`**，工具会在错误里把本会话正确的 project_id 告诉你（`project_mismatch` / `project_not_found`），照它给的值重试即可。猜出来的 id 会被工具面直接拒绝。
- 抽取只读 OCR 规范化 Markdown——每个 `line_span` 都指向该 Markdown 文件的行号。源文件若是 PDF、DOCX 等格式，先用可用的转换器转成 Markdown 放进 project workspace，此后只从转换产物抽取。

## 编排

1. **恢复检查**：先 `prose_get_matrix_status` 看四矩阵现状。全新项目四矩阵为 `empty`，走下面全流程；有 `drafting` 残留说明上次中断，从残留进度续跑；已 `published` 的矩阵改走「增量维护」（见下节），不重抽。

2. **注册文档**：每个源 Markdown 用 `prose_register_document` 登记拿 doc_id。条目的 `source_refs` 只能引用已注册的 doc_id，未注册的引用过不了校验。

3. **开草稿**：四个矩阵各调一次 `prose_start_matrix_draft`。

4. **派发抽取 pass**：每个矩阵一个 pass。用 `Agent` 工具四路并发，`subagent_type` 指定 `matrix-extraction-worker`（它继承主 agent 的全部工具面，能直接调 `prose_*` 提交草稿）；没有该类型就用 `general-purpose`；`Agent` 工具不可用时自己顺序跑四遍，指南一字不差同样适用。worker prompt 必须给足：目标矩阵类型、project_id、各 doc_id 与对应源文件路径、`references/worker-instructions.md` 与 `references/response-matrix-schema.md` 的完整路径，以及「先通读 worker-instructions 再动手」的要求。worker 只知道 prompt 里写的内容——给路径让它自己读，不要转述指南摘要。

5. **主 agent 复核**：四个 pass 都汇报完成后，用 `prose_get_matrix` 的分组统计定位可疑面（某类计数异常、unset 桶过大），再 `prose_query_matrix_items` 抽查条目本体，做跨矩阵裁决：重复条目 `prose_drop_matrix_item`，归类错的 `prose_move_matrix_item`，字段修正 `prose_update_matrix_item`，envelope 修正 `prose_set_matrix_meta`。worker 汇报里的低置信与未决点优先核。另核一处跨矩阵自洽：technical 有 ▲ 条款（`param_nature`）而 scoring 的 `evaluation.deviation_rules` 为空，或反之，通常意味着某一侧漏抽——责成对应 pass 补齐。

6. **校验修复环**：`prose_validate_matrix` 跑全部矩阵，照报告里每条 issue 的 hint 逐条修。保真类失败集中成批修：先读齐所有失败条目引用的源文 span，再一轮改完，然后整体重跑校验；一轮一批，直到 `all_pass`。error 必须清零；warning 仅当招标文件确实缺该信息、或原文本身含混时才允许保留。

7. **发布**：四个矩阵各 `prose_publish_matrix`。被门禁拒绝就带着报告回到第 6 步，修完再发。四矩阵全部 `published` 才算跑完。

## 增量维护（补遗、澄清、发布后的修正）

已发布矩阵的默认维护方式是行级增量：`prose_update_matrix_item` / `prose_drop_matrix_item` / `prose_move_matrix_item` 直接作用于当前版，用户的确认与偏离标注天然保留。补遗或澄清文件先注册（第 2 步），再把新增或变化的条款逐条落成行级修正。全量重抽是逃生门：必须先获得用户明确同意，再开草稿并显式传 `discard_manual_states=true`。

## 最终响应

向用户汇报：四矩阵的发布状态与条目计数（`prose_get_matrix_status` 口径）、校验里保留的 warning 及其理由、`unresolved_items` 里需要人工裁决的高影响项。保持简短——数据都在对象库里，前端会展示，不要在回复里复制条目内容。
