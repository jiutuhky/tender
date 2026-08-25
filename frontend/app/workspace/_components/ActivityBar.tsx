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
  const line = useWorkspaceStore((s) => activityLine(s.timeline, s.phase));
  const setStreamSize = useWorkspaceStore((s) => s.setStreamSize);

  return (
    <button
      type="button"
      // 玻璃走规范工具类。放置矩阵里活动条本应是 凝 lens·thin，但单屏 lens 预算(≤3)
      // 已被消息浮窗 / agent 看板 / 瞬态菜单占满，按规范「超预算降级」取 霜 soft·thin。
      className="cv-actbar is-running frost-glass frost-glass--soft frost-glass--interactive"
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
