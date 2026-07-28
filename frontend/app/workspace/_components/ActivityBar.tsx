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
  const streamSize = useWorkspaceStore((s) => s.streamSize);
  const lastOpenSize = useWorkspaceStore((s) => s.lastOpenSize);
  const setStreamSize = useWorkspaceStore((s) => s.setStreamSize);

  return (
    <button
      type="button"
      className="cv-actbar is-running"
      // 玻璃材质走内联：构建期 Lightning CSS 会丢掉样式表里无前缀的 backdrop-filter
      style={{
        backdropFilter: "blur(20px) saturate(180%)",
        WebkitBackdropFilter: "blur(20px) saturate(180%)",
      }}
      title="展开执行流"
      onClick={() => setStreamSize(streamSize === "capsule" ? lastOpenSize : "expanded")}
    >
      {/* 边框流光的载体。本组件只在运行期渲染，故恒为 is-running。 */}
      <span className="cv-sheen" aria-hidden="true" />
      <span className="run-dot running" aria-hidden="true" />
      <span className="cv-actbar-text cv-shimmer" role="status" aria-live="polite">
        {line}
      </span>
      <ChevronIcon className="cv-actbar-chevron" width={11} height={11} aria-hidden="true" />
    </button>
  );
}
