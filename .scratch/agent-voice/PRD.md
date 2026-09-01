# Agent 回复语气与信息密度治理（agent-voice）

Status: needs-triage
Date: 2026-08-30

## 问题陈述

hagent 面向用户的回复**过于冗长、术语密度过高**：会向标书从业者提到 JSON 字段、
内部状态枚举、条目 ID、保真度阈值等实现细节，中间过程旁白刷屏且中英混杂。
体感是「专业但不懂交流的程序员」，而产品定位是「贴心的标书同事」。

## 证据（来自 /tmp/hagent/threads.sqlite 三个真实会话）

量化（按主图 / 子代理分列）：

| 会话 | 层 | 文本气泡数 | 英文主导 | 含内部词汇 |
|---|---|---|---|---|
| 5815fb64 | 主 agent | 19 | 0 | 8（42%） |
| 5815fb64 | 子代理 | 89 | 25 | 41（46%） |
| 93593375 | 主 agent | 14 | 0 | 5（36%） |
| 93593375 | 子代理 | 49 | **44（90%）** | 28（57%） |
| 9b838cd2 | 主 agent | 9 | 0 | 5 | 
| 9b838cd2 | 子代理 | 72 | 42（58%） | 37（51%） |

典型样本：

- 主 agent 最终总结（用户必读面）：「basic_info published 31 条 0 error / 0 warning…
  TECH-016 保真度 0.8684 略低于阈值……sequence_coverage=1.0，仅单元格边界 ngram
  因表格标签字符失配……已在 technical 的 extraction_summary 里注明理由」。
- 主 agent 过程旁白：「四矩阵均为 empty，走全流程。先注册源文档、开四张草稿」
  「文档已登记（doc-7e86ec8fd2），四张草稿已开启」。
- 子代理旁白（嵌套渲染在 Agent 节点下）：「Batch 3 submitted. Continuing with
  batch 4.」「Now the unresolved_items section.」——大量英文 + 内部区段名。

## 根因分层

### L1 · base prompt（`hagent/prompts/hagent_base.zh.md`）——主因

1. **无语言硬规则**：全文没有「面向用户的文本一律简体中文」。主 agent 恰好没跑偏，
   子代理（同一 base prompt）大面积英文自言自语。
2. **旁白节奏被放大**：「第一次调用工具前说明一句 + 关键节点简短更新 + 简短是好的，
   沉默不好」——模型把它执行成**每次工具调用前都发一句**，一轮任务 10~20 条旁白。
   缺「阶段边界才说话，单步操作不播报」的粒度约束。
3. **「翻译层」规则缺位**：已有「回复里不出现文件路径」，但没有推广成总原则——
   **内部实现词汇不出现在面向用户的文本里**（JSON/字段名/工具名/状态枚举
   published·drafting·empty/条目 ID BIZ-054/doc_id/envelope/校验分数）。模型于是
   镜像工具面词汇对用户说话。
4. **最终汇报无「用户口径」规范**：结论先行有了，但没有规定汇报用业务语言
   （「四张应答矩阵已生成并可在画布查看」而非状态枚举表格）。

### L2 · skill / subagent 层（`.hagent/skills/bid-response-matrix/`、`.hagent/agents/`）

5. **SKILL.md「最终响应」直接教坏口径**：要求按 `prose_get_matrix_status` 口径汇报
   状态与计数、warning 及理由、`unresolved_items`——模型照做，术语直出。应改为
   「数据口径取自工具，**表达口径用用户语言**」并给对照示例。
6. **worker 无语言/旁白约束**：worker 定义与 worker-instructions 只规范了抽取行为，
   没约束过程文本语言与节奏；其收尾技术汇报（给主 agent，合理）与过程英文旁白
   （用户可见，不合理）未区分。

### L3 · 工具面（低优先）

7. `prose_*` 工具描述/错误 hint 术语密集——这是模型-工具接口，本身正确；但错误
   文案被模型转述时会漏出（`project_mismatch` 等）。可在 L1 翻译层规则内覆盖，
   不必改工具面。

### L4 · 前端渲染层（`frontend/app/workspace/_components/AgentStream.tsx`）——放大器

8. **文本旁白与最终答复同权重渲染**：thinking/工具调用会折叠进 ThinkingBlock，
   但 `assistant_text` 一律满级正文气泡；模型 tool-loop 里的一句话旁白因此以
   与最终交付相同的视觉分量刷屏。渲染层无「过程旁白降级」概念。

## 方案（分层，可独立实施）

### 方案 A · base prompt「语气与风格」章节扩充（L1，杠杆最大）

在 `hagent_base.zh.md` 的「语气与风格」追加/改写四条：

- **语言**：面向用户的一切文本一律简体中文（代码、命令、专有名词除外）。
- **翻译层**：内部实现词汇不出现在回复里——工具名、JSON/字段名、状态枚举、
  条目 ID、校验分数属于工作环境内部细节；对用户只说业务语言，并给 3~4 组
  对照示例（published→已发布；unresolved_items→需要你确认的事项；
  「TECH-016 保真度 0.8684」→「有一处台式终端参数因原文格式问题需要你复核」）。
- **旁白节奏**：过程更新只在阶段边界（开工、换阶段、遇阻、收尾）说话；
  连续的同类工具操作不逐步播报。
- **汇报口径**：最终总结按「用户拿到了什么 → 哪里需要用户出手」组织，
  数字和状态服务于判断，不罗列内部计量。

> 流程约束：该文件是协议级文件——按 hagent/CLAUDE.md，须配套更新
> `prompts/decisions.md`（MODIFY 记录）+ 跑 `./scripts/check_base_prompt.sh`，
> 且走专门 sub-agent 流程实施，不在主对话临时改。

### 方案 B · skill 与 worker 口径修正（L2，止住「教坏」源头）

- `bid-response-matrix/SKILL.md`「最终响应」改写：明确「数据取状态工具口径、
  表达用用户语言」，给出好/坏示例各一段。
- `matrix-extraction-worker.md` 增加两条：过程文本一律简体中文；
  只在阶段边界发过程更新（收尾技术汇报保持现状——那是给主 agent 的协议）。

### 方案 C · 前端过程旁白降级（L4，治体感放大器）

`AgentStream.tsx` 的 groupTurns 已按「正文为界」分段：可把**后面还跟着工具调用的
文本段**视为过程旁白，并入 ThinkingBlock 折叠区或降级为 dim 单行（类似 CC 终端的
灰色过程行），只有回合末段文本保持满级正文。子代理内部文本维持现状（已聚合）。
涉及 `lib/hagent/timeline.ts` 分组语义，改前须对照 `docs/sse-message-events.md`。

### 不做的事

- 不改 `prose_*` 工具描述与错误契约（模型-工具接口，术语是必要的）。
- 不引入输出后处理/改写管线（治标且有失真风险）。

## 建议顺序

A（主因）→ B（源头）→ C（体感）。A+B 是纯 prompt/文档改动，可先行；
C 是前端行为改动，建议单独出票。

## Comments
