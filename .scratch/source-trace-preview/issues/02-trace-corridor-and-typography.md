Status: resolved
Blocked by: 01

# 02 溯源走廊：来源签 → 成品排版的原文面板

## Parent

`.scratch/source-trace-preview/PRD.md`

## What to build

核验人员在商务/技术应答矩阵的抽屉详情里，点击条目的**来源签**（由「来源 L120-124 · 技术需求」纯文本行升级而来），抽屉加宽为**对照双栏**：左栏原文面板以渲染态呈现招标文件全文（含语料中单行内联 HTML 大表格的成型渲染），右栏条目列表原样可操作（过滤签、分类锚点、人工动作不受影响）。面板取数期间有载入占位；打开后常驻，显式关闭回单栏，关抽屉整体重置。document_id 不在注册表的签置灰不可点（最简判定，悬停说明留 03 票收口）。

排版一次做到成品：层级密度取文档预览原型页（衬线标题、正文 14px/1.75、全边框表格），颜色映射 Frost token；文档字体保留原型衬线栈，并**为原文面板破例引入 Web 字体**（破例范围严格限定在面板内），同步给 CLAUDE.md「零 Web 字体」硬约束条目与 frost-design skill 加注记，避免后续评审误判违规。

本票不做行号定位与高亮（03 票）；动效用最朴素的既有抽屉语言即可，编排打磨留 05 票。

## Acceptance criteria

- [ ] 商务/技术条目的来源行升级为来源签，每条 ref 一个签；registry 缺失的签置灰不可点
- [ ] 点签后抽屉加宽双栏，原文面板渲染整篇文档：标题层级、列表、单行 HTML 表格全部成型可读
- [ ] 面板载入占位、常驻、显式关闭回单栏、关抽屉重置，均符合 PRD 生命周期决策
- [ ] 双栏下右栏过滤签、分类锚点跳转、确认/应答状态标注全部照常工作
- [ ] 排版对齐原型层级密度且颜色走 Frost token；衬线 Web 字体只作用于面板，站点其余部分不受影响
- [ ] CLAUDE.md 与 frost-design skill 的破例注记已落
- [ ] `pnpm typecheck` + `pnpm lint` 通过；真语料实跑可演示「点签看到原文」

## Blocked by

- 01 契约与数据层打通

## Comments

**2026-07-16 实现完成（agent），commit 75c79cc**

- 来源签：`matrixViews.tsx` SourceLine 升级为签组（每 ref 一签，`fmtSourceRef` 收进 `lib/hagent/matrix.ts` 与多 ref 版同源）；registry 缺 document_id（含注册表载入中/失败）置灰不可点，无 Provider 场景回退纯文本行。
- 双栏：溯源状态（注册表 + 活跃 ref）收 `traceContext.tsx`，挂 `CanvasDrawer` 局部——关抽屉卸载即整体重置，不进全局 store；`is-trace` 加宽 min(1128px,100%)，右栏过滤签/锚点/人工动作实测照常。开合为即时切换，编排动效留票05。
- 原文面板：`TracePanel.tsx` 走 use()+Suspense 消费票01数据层缓存（载入骨架=fallback，错误边界可重试）；`lib/trace/blocks.ts` 纯模块分段（标题/段落/列表/管道表格/HTML 块，1-based 行区间钉 `data-line-start/end`，票03 直接消费）；`lib/trace/sanitize.ts` 白名单净化 OCR 单行 HTML 大表格，净化后为空按纯文本如实呈现。
- 排版：层级密度对齐 archive/preview.html（正文 14px/1.75、全边框表格逐字对齐；标题字号按面板宽度合理缩放 21/17.5，h3 起转无衬线同原型），颜色全走 Frost token；衬线 Web 字体经 next/font 自托管（Newsreader + Noto Serif SC），变量类只挂 `.cv-trace-doc`。CLAUDE.md 与 frost-design skill（SKILL.md + readme.md）破例注记已落。
- 验证：`pnpm typecheck` + `pnpm lint` 绿；真语料实跑（信保项目，40 签全点亮）验收「点签→双栏→整篇渲染（含 L1034 附表1 大表格成型）→载入骨架→显式关闭回单栏→关抽屉重置→字体作用域（body 仍系统栈）」全过，控制台零错误。
- 双轴 code review：Spec 轴通过无相悖；Standards 轴 1 硬违规已修（X 图标提取为 `XIcon` 进图标库，顺清 CanvasDrawer 既有内联 SVG）。遗留给票03：注册表载入失败目前仅 console.warn + 置灰，需纳入分层容错的可见收口。
