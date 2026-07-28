Status: resolved
Blocked by: 03

# 04 覆盖面补全：评分表 + 否决项 + 多 ref + 跨文档

## Parent

`.scratch/source-trace-preview/PRD.md`

## What to build

溯源能力从商务/技术条目扩到 PRD 收口的全覆盖面：评分办法表格的「来源」列升级为来源签（顺带修复现状只显示第一条 ref 的信息丢失——多条 ref 全部成签）；否决项红区里带合法 source_refs 的条目给签（复用同一套签组件，没有 refs 的不显示）；条目多签逐一点跳、每签独立定位；来源跨文档时点签自动切换面板文档并定位（缓存命中则无感）。

basic_info（项目概要）卡不动——PRD 明确出范围。

## Acceptance criteria

- [ ] 评分表来源列为可点签，多条 ref 全部呈现，点击行为与条目签一致
- [ ] 否决项带合法 refs 的呈现签并可溯源；无 refs 的否决项无签、无兜底
- [ ] 同条目多签逐一点跳，活跃态在签间正确迁移
- [ ] 跨文档 ref 点签后面板切换文档并定位高亮，容错分层对新文档同样生效
- [ ] basic_info 卡无任何变化
- [ ] `pnpm typecheck` + `pnpm lint` 通过；真语料实跑可演示评分卡全链路

## Blocked by

- 03 定位高亮 + 分层容错收口

## Comments

**2026-07-16 实现完成（agent）**

- 签组件收口:票03 的 SourceLine 拆为三层——`SourceChips`(纯签组,三处落点共用,compact 变体签面只留行号、完整来源进悬停)、`SourceRow`(「来源」标签行,条目底部与否决项红区共用,无 Provider 回退纯文本、拼不出文本整行不渲染)、`SourceLine`(条目壳,签身份取业务 id 缺省 useId)。
- 评分表「来源」列:`fmtLineSpan(第一条)` 纯文本升级为签组,多条 ref 全部成签(修复 PRD 点名的信息丢失),列宽 72→96px,单元格用 `.cv-src-row.is-cell` 修饰类去标签行上边距(不写内联覆盖)。点击行为与条目签一致(同一 openTrace/activeKey 口径)。
- 否决项红区:`asSourceRefs`(lib/hagent/matrix.ts 防御式取值区)把无形状约束的 pass_fail_rules 条目解析为合法 SourceRef 列表——错型字段丢弃,非空坏条目(字段全坏对象/字符串)退化空壳 ref 走置灰签+悬停原因(坏数据可见),null 与空数组才是「无签、无兜底」。签身份 `veto:{业务id(PFR-xxx)|序}`。顺带修复 `vetoRuleText` 缺 `rule_text` 键——真语料 payload 用此键,修前红区显示 JSON 串。
- 跨文档:机制随票02/03 的 activeDoc 推导天然成立(activeRef.document_id → 注册表 → TracePanel 按 doc.id:sha256 重挂),本票零代码,实跑验证。
- 验证:`pnpm typecheck` + `pnpm lint` 绿;真语料实跑(信保项目)——评分表 30 签全呈现、点签定位居中、L1090 命中整表高亮退化顶部对齐、否决项 5 条全带签且点签命中原文条款(L955 文字逐字对上)、同条目双签(BIZ-003)逐一点跳活跃态迁移、basic_info 抽屉零签零加宽;合成补测(fetch 拦截,真语料单文档/无多 ref 评分项)——跨文档点签切换文档并定位 L5-7、越界 ref 对新文档照出黄条、缓存命中回切无感、无 refs 否决项无签无兜底行,控制台零错误。
- 双轴 code review:Standards 轴零硬违规,判断项 3 处已修(否决项无 Provider 孤「来源」标签行——SourceRow 收口;marginTop 内联反向覆盖——改 `.is-cell` 修饰类;签行外壳重复——随收口消解);Spec 轴规格达成完整,轻微项 2 处已修(非对象 ref 条目静默丢弃改为空壳签可见;veto 签身份改业务 id),`rule_text` 判定为使能性修补非 creep,compact 悬停为窄列正当自由度。
