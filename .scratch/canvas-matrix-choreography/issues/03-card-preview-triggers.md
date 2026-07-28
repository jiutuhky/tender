# 03 卡面预览:决策触发器重排

Status: ready-for-human
Type: task

## Parent

`.scratch/canvas-matrix-choreography/PRD.md`

## What to build

投标经理扫一眼画布,每张卡面就亮出各自的决策触发器,回答「要不要点开细看」:项目概要卡把投标截止时间(含剩余天数,临近变警示色)置为全卡最醒目一行;商务/技术卡把「实质性 N 项」从脚注小字升格为★橙色风险徽标(漏一条即废标),技术卡在存在高风险条目时追加「高风险 N」;评分卡在价格/商务/技术三格下加权重占比微条,一眼可辨价格标还是技术标。载入中的卡面用骨架条替代灰字。实现前调用 frost-design 与 design-taste-frontend skill 校准。

## Acceptance criteria

- [x] 概要卡:截止日期 + 剩余天数倒计时单独醒目一行,临近截止变警示色;保留项目名称、预算、采购方式/评标方法
- [x] 商务/技术卡:★实质性橙色徽标醒目呈现;保留 top 4 分类条形图;技术卡有高风险条目时显示「高风险 N」
- [x] 评分卡:总分 + 方法 + 三格保留,三格下新增权重占比微条(分值/总分)
- [x] loading 态卡面为骨架条,与「解析中」徽标呼应;所有计数 tabular-nums
- [x] 卡宽维持 232;数据缺失字段一律「—」防御式呈现;样式走语义化 className 与画布作用域 token,遵守 mono 白名单与浅色背景硬约束
- [x] `pnpm typecheck` 与 `pnpm lint` 全绿;浏览器走查:四卡在 等待/解析中/就绪/失败 各态下的卡面

## Blocked by

None — can start immediately.

## Comments

**2026-07-12 agent 实现记录**

- 新增 `canvas/deadline.ts` 纯工具(无 DOM 依赖,与 choreography 同为未来单元可测点):容错解析 datetime(ISO/「2026-07-24 09:30」/中文年月日,兜底三段数字并回读校验防 13 月翻滚)、日历天数差、倒计时呈现(≤7 天警示 `DEADLINE_WARN_DAYS`,今日截止/已截止分档)。解析不动返回 null,卡面「—」兜底。
- 概要卡:截止行为全卡唯一着色块 + 最重字重(`.cv-face-deadline`),临近整块翻橙;删「关键节点 N 项」脚注(时间线归抽屉详情,US-30)。商务/技术卡:`★ 实质性 N 项` 橙徽标(0 项翻中性灰不误报),技术卡追加红系「高风险 N」;top4 条形图与「共 N 条」保留。评分卡:三格下 `.cv-face-weight` 权重微条,总分缺失退化用三格之和作基数,子分缺失的格不画空轨道。
- 骨架条(`.cv-skel`)覆盖 loading 与 empty+解析流进行中——与「解析中」徽标(`matrixCardBadgeForPhase`)同一语义口径;静态呈现(Frost 禁无限循环动效),进行感由卡顶蓝条+徽标承担。等待/失败/中断态保持文字呈现。
- META 卡高按就绪态实测更新(256/244/244/208),修停靠列卡片重叠(卡身内容自适应,h 只喂编排间距)。
- 走查(chrome-devtools,`__ws` 驱动):四态卡面、倒计时六变体(warn/past/今日/中文格式/不可解析/缺失)、实质性 0 项、缺总分权重退化、部分失败停靠、全盘中断定格、键盘开卡/Esc、mock 画布回归——全部通过;typecheck/lint 全绿。
- 双轴评审后修三处:预算数值补 tabular-nums、`parseDeadline` 越界日期回读校验、子分缺失不渲染空权重轨道。
- 评审遗留不改项:①「解析进行中」谓词在 matrixViews/CanvasPane/store 等五处各写(建议后续收口 store selector);②徽标底色 rgba 字面量沿袭画布既有惯例(scPair 等同式),未抽 token;③实质性徽标卡面橙/抽屉红两套皮,抽屉侧属票4范围,届时统一。
