"use client";

import { useWorkspaceStore } from "@/lib/store/workspace";
import { ChevronIcon } from "@/components/ui/icons";
import { activityLine } from "./runStatus";

// 运行期的活动条：浮在输入坞正上方，一行报「智能体此刻在做什么」。
// 它顶替快捷 chips 的槽位（chips 在 busy 期本就无效），不新增第三行。
//
// 性能要点：订阅的是**派生字符串**而非 timeline。内容不变即 Object.is 相等，
// zustand 跳过重渲，所以流式逐 token 的绝大多数帧里底部坞是静止的。
export function ActivityBar() {
  const line = useWorkspaceStore((s) => activityLine(s.timeline, s.phase, s.botSignals));
  const setStreamSize = useWorkspaceStore((s) => s.setStreamSize);

  return (
    <button
      type="button"
      // 玻璃走规范工具类，按放置矩阵取 凝 lens·thin。单屏 lens 预算(≤3) 正好用满：
      // 本组件只在运行期渲染，同期在场的 lens 面只有消息浮窗与子代理看板；瞬态菜单
      // 是浮起即收的第四面，不计入常驻预算。霜 soft 在这里不成立——活动条浮在画布
      // 实底上，不折射就只剩一圈描边，读作贴片而非玻璃。
      className="cv-actbar is-running frost-glass frost-glass--lens frost-glass--interactive"
      data-thick="thin"
      title="展开执行流"
      onClick={() => setStreamSize("open")}
    >
      {/* 边框流光的载体。本组件只在运行期渲染，故恒为 is-running。 */}
      <span className="run-dot running" aria-hidden="true" />
      <span className="cv-actbar-text cv-shimmer" role="status" aria-live="polite">
        {line}
      </span>
      <ChevronIcon className="cv-actbar-chevron" width={11} height={11} aria-hidden="true" />
    </button>
  );
}
