Status: ready-for-agent
Blocked by: 02

# 03 PDF 载体：定位与版面高亮

## Parent

`.scratch/pdf-source-trace/PRD.md`

## What to build

点任一来源签，预览层打开该文档的**预览版 PDF 原件**，翻到命中矩形所在页、把矩形滚到视野中部，并在页面上把矩形高亮出来。核验人员看到的是原件那张纸，OCR 讹误当场现形。同一条目的多条来源用层内步进器逐条走完，跨页也走得通；一条来源跨页时两页上的矩形都高亮。

高亮走 EmbedPDF 的 annotation 能力：程序化建矩形，`autoCommit: false` 保证纯内存不写进 PDF，`readOnly` 使其渲染但完全惰性（不可选中、无手柄、无菜单）。若 `readOnly` 的视觉不可控，退回照其 Layout Analysis 插件的覆盖层形状自写一层。全局单活跃 ref 的语义不变——点任何签即切换定位与高亮、旧高亮清除、活跃签点亮。

预览层只管「看」：Selection 插件不装，不做文本层，不做全文搜索。

**本票第一步是实测 EmbedPDF 的 WASM 首屏体积并记在票里**——这是决策闸口，不可接受时触发回到页位图方案的重议（PRD「Further Notes」有备而来），先量再写，避免返工写在后面。

## Acceptance criteria

- [ ] EmbedPDF 的 WASM 首屏体积已实测并记录在本票 Comments 中，结论明确（可接受 / 触发重议）
- [ ] 点来源签打开预览层并渲染该文档的预览版 PDF
- [ ] 翻到命中矩形所在页，矩形滚动到视野中部
- [ ] 矩形按 sidecar 的归一化 bbox 画在页面正确位置上；缩放后不漂移
- [ ] 高亮不写进 PDF（`autoCommit: false`），且不可选中、无手柄、无菜单
- [ ] 一条来源跨页时，两页上的矩形都被高亮
- [ ] 多来源步进器在同一条目的全部来源间走完，跨页与跨文档均可
- [ ] 全局单活跃 ref：点任何签即切换，旧高亮清除，活跃签点亮
- [ ] 对照条内嵌的人工动作（确认 / 应答状态标注）在层内照常可用
- [ ] 未安装 Selection 插件，预览层不提供选中与搜索
- [ ] `pnpm typecheck` + `pnpm lint` 通过

## Blocked by

- 02 前端：取数打通与载体解耦（预勾）
