"use client";

import { useId, useState } from "react";
import { ChevronIcon, WrenchIcon } from "@/components/ui/icons";
import { ThinkingItemView, type ThinkingItem } from "./ThinkingBlock";

// 工具调用块：与 ThinkingBlock 结构对称的可折叠卡片。
// 适用范围：thinking 之外的连续工具/子任务调用——即 partitionItems 的 before/after 段，
// 或全无 thinking 时的整段 items。默认收起，展开后内部用同一套 .cm-thinking-item 时间线。
// 摘要按动词聚合呈现「读取 3 个文件 · 搜索 2 次 · ...」，让用户一眼看到本段做了什么。
export function ToolCallBlock({ items, active = false }: { items: ThinkingItem[]; active?: boolean }) {
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  const toggle = () => setOpen((v) => !v);

  if (items.length === 0) return null;

  const summary = aggregateSummary(items);

  return (
    <div className={`cm-thinking-grid cm-tools-grid${active ? " is-active" : ""}`} aria-expanded={open}>
      <div className="cm-thinking-header">
        <button
          className="cm-thinking-button"
          type="button"
          onClick={toggle}
          aria-expanded={open}
          aria-controls={bodyId}
        >
          <span className={`cm-thinking-spark cm-tools-spark${active ? " is-active" : ""}`} aria-hidden="true">
            <WrenchIcon />
          </span>
          <span className="cm-summary-text">{summary}</span>
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

// —— 摘要聚合 ——
// 同工具名（含 subagent 视为一类）按出现顺序累计计数；输出形如「读取 3 个文件 · 搜索 2 次」。
// 不去重文件路径——这里记的是「做了多少次」，不是「涉及多少资源」。

type VerbDef = { verb: string; unit: string };

function verbDef(toolName: string): VerbDef {
  switch (toolName) {
    case "Read":
    case "read_file":
      return { verb: "读取", unit: "个文件" };
    case "Write":
      return { verb: "写入", unit: "个文件" };
    case "Edit":
    case "edit_file":
      return { verb: "编辑", unit: "个文件" };
    case "Grep":
      return { verb: "搜索", unit: "次" };
    case "Glob":
    case "glob":
      return { verb: "匹配文件", unit: "次" };
    case "Bash":
      return { verb: "执行", unit: "次命令" };
    case "WebFetch":
      return { verb: "抓取", unit: "个网页" };
    case "WebSearch":
      return { verb: "网络搜索", unit: "次" };
    case "TodoWrite":
      return { verb: "更新任务清单", unit: "次" };
    case "Skill":
      return { verb: "调用", unit: "次技能" };
    default:
      return { verb: "调用工具", unit: "次" };
  }
}

function aggregateSummary(items: ThinkingItem[]): string {
  type Bucket = { verb: string; unit: string; count: number };
  const map = new Map<string, Bucket>();
  const order: string[] = [];
  for (const it of items) {
    let key: string;
    let def: VerbDef;
    if (it.kind === "subagent") {
      key = "subagent";
      def = { verb: "调度", unit: "个子任务" };
    } else if (it.kind === "tool") {
      key = `t:${it.call.tool_name || "unknown"}`;
      def = verbDef(it.call.tool_name);
    } else {
      continue;
    }
    let b = map.get(key);
    if (!b) {
      b = { ...def, count: 0 };
      map.set(key, b);
      order.push(key);
    }
    b.count += 1;
  }
  const parts: string[] = [];
  for (const k of order) {
    const b = map.get(k);
    if (b) parts.push(`${b.verb} ${b.count} ${b.unit}`);
  }
  return parts.length ? parts.join(" · ") : "工具调用";
}

/** 当任一 item 处于 running 状态时，整块视为 active。 */
export function anyItemRunning(items: ThinkingItem[]): boolean {
  return items.some((i) => {
    if (i.kind === "tool") return i.call.status === "running";
    if (i.kind === "subagent") return i.run.status === "running";
    return false;
  });
}
