"use client";

import { useId, useState } from "react";
import { ChevronIcon, ClockIcon, FileTextIcon, GridFourIcon, SparkIcon } from "@/components/ui/icons";
import type { ChatMsg, SubagentRun, ToolCall } from "@/lib/hagent/timeline";
import { ToolSection } from "./ToolSection";
import { subagentStatusText } from "./runStatus";

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
  const toggle = () => setOpen((v) => !v);

  // 「仍在思考」不再做无限扫光循环——规范的唯一循环豁免是运行态的消息窗 border beam,
  // 由它统一承担运行提示;标题只保留 is-waiting 的静态样式区分。

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
          <span className={`cm-summary-text${active ? " is-waiting" : ""}`}>
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
          <ClockIcon aria-hidden="true" />
        </div>
        <div className="cm-thinking-item-content">{it.text}</div>
      </div>
    );
  }
  if (it.kind === "tool") {
    return (
      <div className="cm-thinking-item">
        <div className="cm-thinking-item-icon">
          <FileTextIcon aria-hidden="true" />
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
        <GridFourIcon aria-hidden="true" />
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
