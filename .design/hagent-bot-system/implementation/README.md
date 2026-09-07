# 产品接入与独立审查

2026-09-07。已将确认的平面 Bot 系统接入产品代码：默认正面，转向由侧面补位与正面裁切表达方块体量，彩带作装饰，不使用 WebGL 或状态角标。

## 接入结果

- 主执行流头像使用新的 36 项通用动作引擎；工作期可显示彩带，完成保持完成姿态。只有观察到当前工作轮次，才播放一次完成庆祝。
- 右上任务看板的每个子代理都有独立 Bot，稳定身份色、独立活动和嵌套缩进；完成保留完成姿态。主连接结束不能证明子任务已取消，未完成行显示等待姿态与“状态待确认”。
- 新 SSE 轻量投影与现有时间线共用 rAF 批处理；活动按 parent_tool_use_id / call_id 隔离。参数分片与同类文本增量不会重复创建状态。
- 读取、检索、生成、核验、协同等由真实工具活动派生。人工介入、hook 阻断、缺页与错误优先于普通结束信号。流缺少正常终止事件时不宣告成功。
- 展开标题、收起胶囊和活动条共用状态文案；等待回应与部分完成不再显示完成绿。
- 角色共用帧时钟，减少动效、离屏、隐藏页签与卸载分支独立处理。新组件保留 React 静态首帧，动态节点由引擎单独创建和销毁。
- 旧移植引擎的几何、特技、粒子和多余模块已移除，保留应用原有通用工具图标与品牌标记。

## 代码入口

- `frontend/components/ui/ProseBot.tsx` / `prose-bot.css`：组件与主题；通过 `components/ui/icons/index.tsx` 统一导出。
- `frontend/lib/bot/`：通用目录、姿态、平面转向、绘制器、共享调度与生命周期。
- `frontend/lib/hagent/botSignals.ts`、`frontend/lib/bot/derive.ts`：事件投影与产品适配。
- `frontend/lib/store/workspace.ts`：保留批处理，并同步维护投影。
- `frontend/app/workspace/_components/MessageWindow.tsx`、`runStatus.ts`、`ActivityBar.tsx`：主角色与统一状态文案。
- `frontend/app/workspace/_components/canvas/AgentBoard.tsx`：连接真实 store 的容器与共用看板展示组件。
- `/botprobe`：只在开发模式开放，使用真实组件与隔离事件 fixture，不写入真实工作区、不发送后端任务。

## 验证

在 frontend 目录执行：

```bash
pnpm typecheck
pnpm lint
pnpm test:bot
```

当前环境未预装全局 pnpm，通过 `npm exec --yes --package=pnpm@10 -- pnpm <命令>` 执行相同脚本。新增测试使用 Node 24 原生类型剥离和 node:test，没有新增第三方测试框架。

17 项行为/生命周期回归覆盖：侧向体量与背面眼睛、36 项几何有效性、身份稳定、参数分片幂等、并发归属、活跃旧调用、人工介入、部分完成、统一状态文字、事件打断、完成去重、暂停继续、减少动效、隐藏页签与卸载清理。

## 独立审查

用户要求的独立审查代理 `bot_integration_review` 已完成代码和视觉 review，未修改产品代码。

发现 1 项 P2：收起模式的 MinTicker 未消费 attention / partial，可能在等待回应时误报“本轮处理完成”。已将覆盖文案收敛到 runStatus，展开、收起、活动条和状态点统一，新增回归测试；审查代理复核通过。

视觉验证使用真实组件和独立 fixture：1360×1000、390×844，浅深主题；主角色正面与侧面补位、彩带、5 个子代理及嵌套、连接中断、完成状态均正常，无横向溢出。系统减少动效后统计为 51 实例、0 活动、帧停止；卸载后为 0 实例、0 活动。每实例只有一个动态 SVG，看板键盘焦点环可见。

审查结论：没有未解决的可确认问题。未触发真实后端任务；隐藏页签行为由生命周期测试验证，未声称已完成后端端到端或真机触屏验收。

截图：[多 Bot 看板](board.png)、[主 Bot 思考与彩带](thinking.png)、[暗色窄屏](mobile-dark.png)。
