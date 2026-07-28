# 02 停靠飞行编排 + 失败态 + 抽屉动作清理

Status: ready-for-human
Type: task
Blocked by: 01

## Parent

`.scratch/canvas-matrix-choreography/PRD.md`

## What to build

亲历解析的会话里,生成完毕的瞬间四张卡以平滑的 gsap stagger 动画从四宫格飞向停靠列,中心区域浮现「下一步:生成投标大纲」的轻量非交互占位——布局变化本身告诉用户「解析阶段结束了」。失败如实呈现:部分失败照常停靠、失败卡橙色标注;流整体中断时未终态的卡面定格为「解析中断」,不再假装「解析中」。矩阵卡抽屉底部的假按钮(插入到文档/重新生成)移除,换成真实可用的「复制 JSON 路径」;失败卡的抽屉给出「可在对话中要求智能体重新解析」的引导文案。

## Acceptance criteria

- [x] 亲历解析的会话:四槽全终态后四卡 gsap stagger 飞向停靠列;恢复/刷新路径不重放(01 已定的直接停靠不被本票破坏)
- [x] 停靠完成后中心出现「下一步:生成投标大纲」占位,非交互纯提示
- [x] 停靠完成且用户未主动操作过视图时,画布自动适应(停靠列与占位完整可见)
- [x] `prefers-reduced-motion` 下不播放飞行动画,直切终态布局
- [x] 部分失败(如 3 ready + 1 error)照常停靠,失败卡显示橙色「解析失败」徽标
- [x] 流异常中断且存在未终态槽位时,居中定格,未终态卡面显示「解析中断」
- [x] 矩阵卡抽屉不再出现「插入到文档」「重新生成」假按钮;新增「复制 JSON 路径」可用动作;mock 卡抽屉不动
- [x] 失败槽位的抽屉详情含错误信息与对话重试引导文案
- [x] 动画一律 gsap,不手写 CSS keyframes;`pnpm typecheck` 与 `pnpm lint` 全绿;浏览器走查:飞行、占位、部分失败、全盘中断、reduced-motion

## Comments

**2026-07-12 agent 实现记录**

- 飞行走 FLIP:阶段切入「已停靠」的切换沿记录各卡「旧卡位→停靠位」位移(`flightRef`),卡位状态提交后由 `useLayoutEffect` 以 gsap timeline 反推起点再按停靠顺序 stagger(0.44s power3.inOut,间隔 0.06s)飞向终点,只动 transform,收尾 `clearProps`。拖拽过的卡从被拖位置起飞(FLIP 天然覆盖)。
- 评审(双轴)后修复两个真问题:①跨纪元(换项目)时上一项目的阶段沿泄漏会让恢复路径也播飞行——切换沿增加 `sameEpoch` 守卫,飞行只发生在同一项目同一模式内;②占位闪现一帧——推导阶段先翻 docked、卡位下帧才重铺,间隙里占位压在中心四卡上,改为占位由 `applyLayout` 提交的 `layoutStage` 驱动,与停靠卡位同帧出现(飞行时先被 gsap 置 0 再随队尾浮现,恢复路径直显)。
- 「解析中断」谓词收口:`isTerminalSlotStatus` / `isSlotInterrupted` 落 cardMeta,编排推导(choreography)、卡角徽标(matrixCardBadgeForPhase)、卡面/详情(SlotFallback)三处共用,不再各写一遍。
- 抽屉底部分两套:矩阵卡只保留「复制 JSON 路径」(clipboard API + execCommand 兜底,复制后 1.6s「已复制」回执;无 path 时禁用);mock 卡按钮组原样。失败与中断槽位的详情均附「可在对话中要求智能体重新解析」引导(中断属良性外溢,评审确认方向一致)。
- 占位为非交互虚线空槽(`.cv-next-hint`,aria-hidden、pointer-events:none),落在 `centerStageRect()` 中心,票1 预留的包围盒并入使「适应画布」同时框住停靠列与占位。
- 走查(chrome-devtools,`__ws` 驱动):飞行(mid-flight transform 实测在插值)、占位随飞行浮现/恢复直显、部分失败橙标停靠、全盘中断定格灰标、reduced-motion 直切(matchMedia 桩)、恢复路径零动画、复制动作、键盘开卡/Esc、mock 画布与 mock 抽屉回归——全部通过;`pnpm typecheck` `pnpm lint` 全绿。
- 评审遗留不改项:matrixViews 内联样式沿袭该文件既有惯例(后续统一收 `.cv-*` 时一并处理);`execCommand` 兜底仅非安全上下文触达。
