# 01 编排骨架:阶段推导缝 + 真实模式去主轴

Status: ready-for-human
Type: task

## Parent

`.scratch/canvas-matrix-choreography/PRD.md`

## What to build

新项目进入画布后,用户看到的不再是假大纲卡混排,而是四张应答矩阵卡(概要→商务→技术→评分)以 2×2 四宫格居中呈现;当四个槽位全部到达终态(生成完毕),布局切换为左侧停靠列(本票直切,飞行动画属 02 票);从项目列表恢复或刷新页面时直接呈现停靠态。「重置画布」按当前编排阶段重铺卡位。

本票落地 PRD 的唯一新缝:编排阶段纯推导模块(输入四槽位状态 + 本会话是否亲历解析,输出 中心舞台 / 已停靠 / 解析中断 等阶段),画布容器只消费该模块;卡位坐标挂其下游。

## Acceptance criteria

- [x] 真实模式不再渲染 mock 主轴卡与任何连线;idle 演示 mockup 完全不受影响
- [x] 解析进行中四卡按 概要→商务→技术→评分 排成 2×2 四宫格居中,各卡徽标反映各自槽位状态
- [x] 四槽位全部终态(ready/error,error 计入)后布局切为停靠列:画布最左侧、同序垂直排列
- [x] 恢复/刷新已解析项目直接呈现停靠态,不经过居中阶段
- [x] 停靠切换一次性接管全部卡位(含被用户拖动过的),之后卡片仍可自由拖拽、系统不再干预
- [x] 「重置画布」:已停靠阶段铺回停靠列,未完毕阶段铺回四宫格
- [x] 编排阶段推导为无 DOM 依赖的纯函数模块,亲历标记仅存会话内存、不持久化
- [x] `pnpm typecheck` 与 `pnpm lint` 全绿;浏览器走查:新项目全程、恢复路径、重置两阶段行为

## Blocked by

None — can start immediately.

## Comments

**2026-07-12 agent 实现记录**

- 新缝落在 `frontend/app/workspace/_components/canvas/choreography.ts`:`deriveChoreoStage`(四槽状态 + 亲历 + 流中断 + 停靠单向阀 → center/docked/interrupted)与 `cardsForStage`(四宫格 / 停靠列坐标)均为纯函数,未来补单测的对象即此模块。
- 亲历标记 `witnessedParse` 落在 workspace store(仅内存):startParse=true,resumeProject/reset=false;未触碰 rAF 批处理。
- 画布容器边沿触发消费阶段:停靠切入一次性接管全部卡位,之后不再干预;「解析中断」定格原位(中断徽标属票 02)。进入真实模式无条件 fit(评审发现 idle 里动过视图会导致四宫格不可见);停靠切入 fitIfUntouched。
- 双轴评审(Standards/Spec)后修复两个真问题:①停靠后 checkpoint 静默刷新把 error 槽翻回 loading 会跌回中心舞台——已在推导模块加 `dockedBefore` 单向阀(同项目同会话停靠不回落);②touched 会话进入解析不居中——改无条件 fit。
- 有意保留的超票铺垫:停靠态包围盒并入中心舞台空区(`centerStageRect`),使「适应画布」呈现列贴左 + 中心留空;票 02 的「下一步」占位将落进该区域。
- 已知轻微项(评审 C2):恢复失败的项目仍以停靠列 + 灰色「等待解析」呈现,仅工具栏提示「解析异常」;失败呈现归票 02/04。
- 走查(chrome-devtools,`__ws` 驱动):新项目全程(四宫格居中→逐卡就绪→部分失败停靠)、恢复路径装载中即停靠、解析中拖拽→停靠接管→停靠后不干预、重置两阶段、中断定格、键盘开卡/Esc、idle mockup 回归——全部通过;typecheck/lint 全绿。
