---
name: emil-design-eng
description: 按 Emil Kowalski 的设计工程方法打磨组件反馈、状态衔接和动效细节；不用于一般前端逻辑修改。
---

# 设计工程

根据用户请求实现、修复或审查指定组件。已有任务时继续执行，不以技能欢迎语结束。项目品牌规范、已确认例外和用户要求优先于本文的审美建议。

- 先判断动效的用途、频率和响应成本；高频操作优先即时或轻量反馈，避免为装饰延迟交互。
- 复用项目组件、字体、图标、曲线与时长 token；不因示例而引入新的依赖或视觉体系。
- 动态过渡能从当前显示状态继续，弹层起点与触发器一致，手势保留连续性；支持减少动效、触屏和键盘反馈。
- 审查只报告有位置、证据和用户影响的问题。无问题可以通过；表格仅在多项比较更清楚时使用。
- 完成请求范围内的实现与相关检查后交付。视觉或真机验证不可用时说明限制，不把次日复查作为默认停止条件。

## 按需参考

- 动效选择、曲线、时长和弹簧：[motion.md](references/motion.md)。
- 按钮、弹层、提示与状态切换：[components.md](references/components.md)。
- transform、clip-path 与拖拽：[transforms-and-gestures.md](references/transforms-and-gestures.md)。
- 性能、减少动效与触屏：[performance-and-accessibility.md](references/performance-and-accessibility.md)。
- Sonner 的组件经验、交错动效与观察方法：[polish-and-inspection.md](references/polish-and-inspection.md)。

只读取本次问题需要的章节，不默认加载全部参考。
