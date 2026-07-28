"use client";

import { useId, useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ChevronIcon, SparkIcon } from "@/components/ui/icons";
import type { ChatMsg, SubagentRun, ToolCall } from "@/lib/hagent/timeline";
import { ToolSection } from "./ToolSection";
import { toolLabel } from "./toolLabel";

const stroke = { fill: "none" as const, stroke: "currentColor" as const };

export type ThinkingItem =
  | { kind: "reasoning"; id: string; text: string }
  | { kind: "tool"; id: string; call: ToolCall }
  | { kind: "subagent"; id: string; run: SubagentRun };

// 思考块：保留设计稿的 .cm-thinking-grid / .cm-thinking-item / .cm-tool-section 结构，
// 仅把硬编码内容替换为真实的推理文本与工具调用（含 5 个 parser 子任务）。
export function ThinkingBlock({
  items,
  summary,
  active = false,
}: {
  items: ThinkingItem[];
  summary: string;
  active?: boolean;
}) {
  // 默认收起；每个思考块各自维护开合（一个助手回合可能有多段思考块）。
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  const summaryRef = useRef<HTMLSpanElement>(null);
  const toggle = () => setOpen((v) => !v);

  // 等待态的扫光只承担「仍在思考」这一种状态提示。流结束后 active 变为 false，
  // useGSAP 会清理循环并让标题立即回到静态深灰；减弱动态偏好下始终保持静态。
  useGSAP(
    () => {
      const summaryEl = summaryRef.current;
      if (!active || !summaryEl || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

      gsap.fromTo(
        summaryEl,
        { backgroundPositionX: "160%" },
        { backgroundPositionX: "-60%", duration: 3.3, ease: "none", repeat: -1 },
      );
    },
    { dependencies: [active], revertOnUpdate: true },
  );

  if (items.length === 0) return null;

  return (
    <div className={`cm-thinking-grid${active ? " is-active" : ""}`} aria-expanded={open}>
      <div className="cm-thinking-header">
        <button
          className="cm-thinking-button"
          type="button"
          onClick={toggle}
          aria-expanded={open}
          aria-controls={bodyId}
        >
          <span className="cm-thinking-spark" aria-hidden="true">
            <SparkIcon animated={false} />
          </span>
          <span
            ref={summaryRef}
            className={`cm-summary-text${active ? " is-waiting" : ""}`}
          >
            {summary}
          </span>
          <ChevronIcon className="cm-chevron" />
        </button>
      </div>
      <div className="cm-thinking-body-wrap" id={bodyId}>
        <div className="cm-thinking-body">
          {items.map((it) => (
            <ThinkingItemView key={it.id} item={it} />
          ))}
        </div>
      </div>
    </div>
  );
}

// 单条思考项渲染。既用于折叠思考块内部，也用于「thinking 前/后的工具」在外层与正文同级渲染。
export function ThinkingItemView({ item: it }: { item: ThinkingItem }) {
  if (it.kind === "reasoning") {
    return (
      <div className="cm-thinking-item cm-thinking-item--reasoning">
        <div className="cm-thinking-item-icon">
          <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.5}>
            <circle cx="8" cy="8" r="6" />
            <path d="M8 4.5V8l2.2 1.5" />
          </svg>
        </div>
        <div className="cm-thinking-item-content">{it.text}</div>
      </div>
    );
  }
  if (it.kind === "tool") {
    return (
      <div className="cm-thinking-item">
        <div className="cm-thinking-item-icon">
          <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.5}>
            <path d="M9 1H4a1 1 0 00-1 1v12a1 1 0 001 1h8a1 1 0 001-1V5z" />
            <path d="M9 1v4h4" />
          </svg>
        </div>
        <div className="cm-thinking-item-content">
          <ToolSection call={it.call} />
        </div>
      </div>
    );
  }
  // subagent：只渲染状态气泡 + 一行轻量文字状态（最近动作）；不展开子代理自己的
  // message / 思考 / 工具——它们会平级铺出来淹没主流，且对用户无信息增量。
  const run = it.run;
  const status = subagentStatusText(run);
  return (
    <div className="cm-thinking-item">
      <div className="cm-thinking-item-icon">
        <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.5}>
          <path d="M3 3h4v4H3zM9 3h4v4H9zM3 9h4v4H3zM9 9h4v4H9z" />
        </svg>
      </div>
      <div className="cm-thinking-item-content">
        <div className={`cm-tool-section${run.status === "running" ? " is-running" : ""}`}>
          <div className="cm-tool-header">
            <div className="cm-tool-query">子任务 · {run.description}</div>
            <div className="cm-tool-count">{run.status === "running" ? "运行中" : "已完成"}</div>
            {run.status === "running" && <div className="cm-spinner" />}
          </div>
          {status && <div className="cm-subagent-status">{status}</div>}
        </div>
      </div>
    </div>
  );
}

/** 子任务的轻量状态文字：运行中显示最近动作，完成显示「已完成」。 */
function subagentStatusText(run: SubagentRun): string {
  if (run.status === "done") return "已完成";
  const action = latestActionLabel(run.children);
  return action ? `${action}…` : "运行中…";
}

/** 从子代理内部时间线里取「最近一次动作」的简短描述（倒序找第一条可读事件）。 */
function latestActionLabel(children: ChatMsg[]): string {
  for (let i = children.length - 1; i >= 0; i -= 1) {
    const m = children[i];
    if (!m) continue;
    if (m.role === "tool") return toolLabel(m.call);
    if (m.role === "subagent") return `子任务 ${m.run.description}`.trim();
    if (m.role === "thinking") return "思考中";
    if (m.role === "assistant_text") return "整理输出";
  }
  return "";
}

/** 把一段 ChatMsg[]（子任务内部时间线）转成 ThinkingItem[]。 */
export function msgsToThinkingItems(msgs: ChatMsg[]): ThinkingItem[] {
  const items: ThinkingItem[] = [];
  for (const m of msgs) {
    if (m.role === "thinking") items.push({ kind: "reasoning", id: m.id, text: m.content });
    else if (m.role === "assistant_text") items.push({ kind: "reasoning", id: m.id, text: m.content });
    else if (m.role === "tool") items.push({ kind: "tool", id: m.id, call: m.call });
    else if (m.role === "subagent") items.push({ kind: "subagent", id: m.id, run: m.run });
  }
  return items;
}
