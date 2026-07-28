Status: resolved
Blocked by: 03, 04

# 05 动效打磨 + 窄屏降级 + 键盘可达 + 全路径终验

## Parent

`.scratch/source-trace-preview/PRD.md`

## What to build

按 apple-design 原则在 Frost 约束内打磨整套溯源交互的动效：抽屉加宽与面板滑入编排为同一次连续「到场」（材质到场而非纯淡入）；全程可打断——动画中点其他签不锁输入，重定向从当前呈现值出发无跳变；面板从左缘滑入、退出走原路、缓动互为镜像；高亮出现用一次性短暂强调（染色淡入，micro 档）；签按下即时反馈。实现载体 gsap（仓库约定，不手写 keyframes），只动 transform/opacity，时长遵守 Frost 档位（micro 120 / float 200 / panel 320ms）与标准缓动，无无限循环；`prefers-reduced-motion` 下全部退化为即时切换。

窄屏（视口放不下双栏，阈值约 <1000px）降级为抽屉内二级视图：带「返回条目」，返回时恢复列表滚动位置。键盘可达：签可 Tab 聚焦、Enter 触发，双栏新增可聚焦元素纳入既有抽屉焦点圈；Esc 语义定稿（倾向一步关抽屉，面板关闭走显式按钮）。

最后做全路径实跑终验：起 hagent + 前端，上传真语料跑完解析，驱动 PRD 验收全路径（点签→加宽→定位高亮→多签切换→跨文档→三容错态→窄屏降级→reduced-motion→键盘），三质量门全绿。

## Acceptance criteria

- [ ] 加宽 + 滑入为连续编排，动画中断/重定向无跳变、不锁输入；进出路径与缓动镜像
- [ ] 高亮短暂强调一次性播放；所有动效只动 transform/opacity、符合 Frost 时长档位、无无限循环
- [ ] `prefers-reduced-motion` 下所有过渡（含平滑滚动）退化为即时切换
- [ ] 窄屏降级二级视图可用：返回条目、恢复列表滚动位置
- [ ] 签 Tab 可聚焦、Enter 触发；焦点圈完整；Esc 语义定稿并实现
- [ ] 全路径实跑通过 PRD Testing Decisions 清单；`pnpm typecheck` + `pnpm lint` + hagent pytest 全绿

## Blocked by

- 03 定位高亮 + 分层容错收口
- 04 覆盖面补全：评分表 + 否决项 + 多 ref + 跨文档

## Comments

**2026-07-16 实现完成（agent）**

- **transform-only 加宽编排（核心结构决策）**:「抽屉加宽」重构为「原文面板材质从主列后方滑出」——抽屉拆出 `.cv-drawer-main`(头+列表+mock 脚,恒定 548px,自带表面与左投影),panel 容器透明无投影;面板(z 序低于主列)自带材质+左投影,从主列后方滑出到位(x: 面板宽 → 0,panel 档 320ms),投影随左缘行进,视觉即「抽屉左缘连续生长」。加宽与滑入天然为同一次连续到场,全程只动 transform,列表零重排(不锁输入的底气)。退场走原路,缓动取标准曲线镜像控制点 (1,0,.68,.28)(apple-design「可逆过渡缓动互为镜像」,traceMotion.ts 注释与 CONTEXT.md 均已成文)。动效常量收 `canvas/traceMotion.ts`(CustomEase 注册,双组件共用)。
- **可打断**:gsap `overwrite:"auto"` 全程从当前呈现值出发——退场中重点签由 activeSeq effect 杀退场 tween 滑回(实测轨迹最大帧间位移 9.4px,无跳变);到场中点签/换文档不重演入场。
- **到场让位(实跑打磨)**:实测暴露缓存命中时 1700 行文档在滑入途中 commit 造成 ~240ms 冻帧;TracePanel 增 `arrived` 门控——面板落位前持骨架,落位后挂 DocView(取数并行预热不推迟网络);门控时长按形态传入(双栏 320/二级视图 200ms),只门控首挂,切签/跨文档无二次延迟。
- **高亮一次性强调**:`.cv-trace-hit` 染色收进 `::before` 覆盖层,gsap 驱动 `--cv-hit-in` 变量控制其 opacity(micro 120ms,一次性,seq 重点重播);实测中途 0.24→终值 1。CSS 变量逐帧样式重算非合成器直通,属字面/精神合规的权衡,已记录。
- **窄屏降级**:阈值按**抽屉容器实测宽**(<1000px,ResizeObserver)而非全局视口——分隔条拖窄画布同样降级(对规格「视口」的有意收严,CONTEXT.md 留痕)。二级视图 = 返回条+面板(float 档浮入,位移 8px,进出对称);列表 body 以 layout effect 藏显(隐藏前存 scrollTop、返回后恢复,实测 1200 保持);出口收敛返回条一处(面板 X 隐藏)。双栏⇆二级视图活体切换(拖分隔条)状态无损。
- **键盘可达**:签为原生 button(Tab/Enter 天然可达,data-chip-key 标识);焦点圈改为**只计可见元素**(修复:窄屏下 display:none 的列表签计入 first/last 会让 Tab 逃出抽屉);面板关闭/返回后焦点回发起签(`preventScroll`,不拉走刚恢复的列表滚动位);Esc 语义定稿:一步关抽屉、面板关闭走显式按钮,且 Esc 与遮罩/关闭钮同走镜像退场(改掉旧的即时移除)。
- **验证**:`pnpm typecheck`+`pnpm lint`+hagent pytest(1182 passed)三门绿。全路径实跑两轮:①真语料克隆项目+持久层注入(第二真文档/越界 ref/未注册 doc)——点签加宽、多签切换、跨文档自动切换定位(L121/123)、置灰签+悬停原因、断网错误态+重试成功、越界黄条、窄屏降级+滚动恢复、reduced-motion 全即时(面板 x=0 即时呈现/卸载、高亮无淡入、滚动 auto)、Tab/Enter/Esc/焦点圈全过,注入项目验后已清理;②浏览器真实上传 220180032 真语料→解析全程(4 矩阵 published、189 条)→评分表 53 签(含否决项)点签定位高亮全链路。
- **双轴 code review**:Standards 轴零硬违规,判断项 5 处已处理(选择器提常量、TRACE_EASE_IN/OUT 改 ENTER/EXIT、门控时长按形态传入、入场位移与镜像曲线的规范解释在 traceMotion.ts/CONTEXT.md 成文);Spec 轴发现焦点圈可见性缺口(已修,真 bug)与窄屏进出节奏不对称(退场 micro→float,已修);「到场让位」门控为「连续到场」验收的使能性修补非 creep;Esc 退场动画补齐为出口一致性收口。
