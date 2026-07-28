# 04 抽屉详情升级:过滤定位 + 时间线 + 分值结构

Status: ready-for-human
Type: task

## Parent

`.scratch/canvas-matrix-choreography/PRD.md`

## What to build

点开卡片后的抽屉详情让用户高效定位关键信息:商务/技术矩阵详情顶部提供 全部/★实质性/高风险 即筛过滤签与分类锚点计数签(几百条逐条响应中快速聚焦致命条款);项目概要详情的关键时间节点升级为纵向时间线,投标截止节点高亮(含倒计时)、已过期节点淡化;评分办法详情顶部加按占比着色的分值结构堆叠条,「否决项/通过性条款」提升至最顶部红色警示区,评分项表格按分组显示小计。抽屉形态维持右侧滑入,既有键盘/焦点/无障碍行为不回退。实现前调用 frost-design 与 design-taste-frontend skill 校准。

## Acceptance criteria

- [x] 商务/技术详情:全部/★实质性/高风险 过滤签即点即筛;分类锚点签显示计数、点击跳至分组
- [x] 条目行保留 编号、标题、要求原文、来源行号;提取不完整时黄色提示条保留
- [x] 概要详情:时间节点纵向时间线,截止节点高亮含倒计时,过期节点淡化;KV 网格保留
- [x] 评分详情:分值结构堆叠条(价格/商务/技术/其他 按占比着色);否决项置顶红区;分组小计行
- [x] 回车/空格开卡、Esc 关抽屉、焦点陷阱等既有无障碍行为全部保留
- [x] `pnpm typecheck` 与 `pnpm lint` 全绿;浏览器走查:三类详情在真实数据与缺失字段下的呈现、过滤与锚点交互

## Blocked by

None — can start immediately.

## Comments

**2026-07-12 agent 实现记录**

- 商务/技术详情:`.cv-det-head` 吸顶头(macOS 分段控件形过滤签 + 分类锚点计数签),过滤谓词收拢 `REQ_FILTERS` 单一映射(签面计数与筛选同源不漂移);锚点跳转用 `scrollBy` 抵消吸顶头实测高度(scrollIntoView 会把分组顶进头下)。吸顶偏移与抽屉体内边距以 `--cv-drawer-pad` 同源变量绑定,改 padding 不再静默错位。锚点随当前过滤联动;单分组时锚点行自动隐藏;过滤空态/无条目空态分文案。
- 概要详情:`timelineNodes` 纯推导(now 走默认参,与 bidDeadline 同式)按时间升序排时间线,不可解析节点保持原序垫底;截止节点橙点高亮 + 倒计时徽标(warn 用新增 `.cv-face-badge.is-warn`,类名不再借「实质性」的 is-mand),过期节点整体淡化。KV 网格、分包、黄条保留。
- 评分详情:否决项红区置顶(`vetoRuleText` 容错读取 string/对象常见文案字段/JSON 兜底);删原四瓦片,换大号总分 + 分值结构堆叠条(单蓝色阶 is-price/is-business/is-technical + 灰 is-other,色值全在 CSS 修饰类,「其他」= 总分−三格差值 >0 才画,缺总分退化用三格之和作基数);评分项按 `SCORE_GROUP_ORDER` 固定序分组,组内表格 + 小计行;`mandatory_gate` 门槛项(schema 已有,matrix.ts 补类型)行内挂红「否决」徽标。
- 票3评审遗留③收口:抽屉 `MandatoryBadge` 与「高风险」改用卡面 `.cv-face-badge is-mand / is-risk` 同皮,橙=实质性、红=高风险全局统一。
- 共用件抽取:`GroupCard`(商务/技术/评分分组卡同壳)、`TruncNote`(300 条截断尾注)、`EmptyNote`。
- 走查(chrome-devtools,`__ws` 驱动):三类详情真实形数据呈现、过滤即点即筛、锚点跳转落位(头高 74+8px)、吸顶无缝隙、黄条保留、缺失字段变体(缺总分退化/无否决项不画红区/过期+中文日期+不可解析时间线/空条目)、Enter 开卡/Esc 关抽屉/焦点回原卡/焦点陷阱——全部通过;console 零错误;typecheck/lint 全绿。
- 双轴评审后修六处:分值段色值下沉 CSS 修饰类、GroupCard/TruncNote/EmptyNote 去重、过滤谓词单一映射、吸顶偏移同源变量、倒计时徽标 is-warn 语义类、分值段元组换具名字段。
- 评审后保留不改项(有意为之):①时间线按时排序(「时间线」形态即时序,后端原序仅对不可解析节点保留);②门槛项行内「否决」徽标与删四瓦片属规格外呈现,信息由红区/图例+大号总分等价承载;③`vetoRuleText` 留视图层(评分抽屉专用);④三格之和>总分的异常数据靠 flex 收缩优雅降级,不另做兜底提示。
