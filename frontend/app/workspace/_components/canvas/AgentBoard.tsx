"use client";

import { memo, useId, type CSSProperties } from "react";
import { useWorkspaceStore } from "@/lib/store/workspace";
import { CheckIcon, CircleDashedIcon, ClockIcon, ProseBot } from "@/components/ui/icons";
import {
  TODO_STATUS_TEXT,
  todoLabel,
  type TodoStatus,
  type TodoItem,
} from "@/lib/hagent/todo";
import type { BotPersistentState } from "@/lib/bot/states";
import { collectSubagentRuns, isRunning, type SubagentBoardRow } from "../runStatus";
import "./agent-board.css";

// 单层执行看板：任务步骤与子任务共享同一表面，只有列表本身滚动。
// 分段订阅保持独立，流式摘要更新不会重绘未改变的任务清单。

/** 已知矩阵标识与执行角色转成阅读文案，不修改原始任务描述或 SSE 数据。 */
function readableLabel(text: string): string {
  const labels: Record<string, string> = {
    basic_info: "项目概要",
    business: "商务要求",
    technical: "技术要求",
    scoring: "评分办法",
  };
  return text
    .replace(
      /抽取\s*(basic_info|business|technical|scoring)\s*矩阵/g,
      (_, key: string) => `提取${labels[key]}`,
    )
    .replace(
      /\b(basic_info|business|technical|scoring)\b/g,
      (key) => labels[key] ?? key,
    )
    .replace(/抽取\s+worker\b/gi, "抽取任务")
    .replace(/主\s+agent\s*/gi, "主智能体");
}

/** 看板只使用一个播报区域，避免流式过程中多段同时打断读屏。 */
function announceProps(on: boolean) {
  return on
    ? ({ role: "status", "aria-live": "polite", "aria-atomic": true } as const)
    : {};
}

export function AgentBoard() {
  const todos = useWorkspaceStore((s) => s.todos);
  const timeline = useWorkspaceStore((s) => s.timeline);
  const signals = useWorkspaceStore((s) => s.botSignals);
  const running = useWorkspaceStore((s) => isRunning(s.phase));
  const live = running && !signals.attention && !signals.failed;
  const rows = collectSubagentRuns(timeline,live,signals);
  return <AgentBoardView todos={todos} rows={rows} live={live} />;
}

/** 产品和独立验收页共用展示组件；模拟数据不写入真实工作区 store。 */
export function AgentBoardView({todos,rows,live}: {todos: TodoItem[];rows: SubagentBoardRow[];live: boolean}) {
  const hasTasks = todos.length > 0;
  const hasAgents = rows.length > 0;
  if (!hasTasks && !hasAgents) return null;

  return (
    <section
      className="cv-agentboard"
      data-state={live ? "live" : "done"}
      aria-label="执行看板"
    >
      <div
        className="cv-agentboard-scroll"
        tabIndex={0}
        aria-label="任务与子任务进度"
      >
        <TaskSection todos={todos} announce />
        <SubagentSection rows={rows} live={live} announce={!hasTasks} />
      </div>
    </section>
  );
}

const TaskSection = memo(function TaskSection({ announce,todos }: { announce: boolean; todos: TodoItem[] }) {
  const headingId = useId();
  if (!todos.length) return null;
  const doneCount = todos.filter((t) => t.status === "completed").length;

  return (
    <section className="cv-agentboard-sec" aria-labelledby={headingId}>
      <header className="cv-agentboard-head" {...announceProps(announce)}>
        <h2 id={headingId}>任务进度</h2>
        <span>
          {doneCount} / {todos.length} 已完成
        </span>
      </header>
      <progress
        className="cv-agentboard-progress"
        value={doneCount}
        max={todos.length}
        aria-label="任务完成进度"
      />
      <ol className="cv-agentboard-list cv-agentboard-tasks">
        {todos.map((t) => (
          <TaskRow
            key={t.key}
            label={readableLabel(todoLabel(t))}
            status={t.status}
            blocked={t.blocked}
          />
        ))}
      </ol>
    </section>
  );
});

const TaskRow = memo(function TaskRow({
  label,
  status,
  blocked,
}: {
  label: string;
  status: TodoStatus;
  blocked: boolean;
}) {
  const done = status === "completed";
  const active = status === "in_progress";
  const Icon = done ? CheckIcon : active ? ClockIcon : CircleDashedIcon;
  return (
    <li
      className={`cv-agentboard-task${done ? " is-done" : active ? " is-running" : ""}`}
      aria-label={`${label} · ${TODO_STATUS_TEXT[status]}${blocked && !done && !active ? " · 等待前置任务" : ""}`}
    >
      <span className="cv-agentboard-marker" aria-hidden="true">
        <Icon width={15} height={15} />
      </span>
      <div className="cv-agentboard-task-copy">
        <span className="cv-agentboard-task-text">
          {label}
          {active && <span className="cv-agentboard-sweep" aria-hidden="true">{label}</span>}
        </span>
      </div>
    </li>
  );
});

function SubagentSection({
  rows,
  live,
  announce,
}: {
  rows: SubagentBoardRow[];
  live: boolean;
  announce: boolean;
}) {
  const headingId = useId();
  if (!rows.length) return null;
  const unfinished = rows.filter((r) => r.status === "running").length;
  const completed = rows.length - unfinished;
  const summary = [
    unfinished ? `${unfinished} ${live ? "进行中" : "状态待确认"}` : "",
    completed ? `${completed} 已完成` : "",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <section className="cv-agentboard-sec" aria-labelledby={headingId}>
      <header className="cv-agentboard-head" {...announceProps(announce)}>
        <h2 id={headingId}>协作智能体</h2>
        <span>{summary}</span>
      </header>
      <ul className="cv-agentboard-list">
        {rows.map((row) => (
          <AgentRow
            key={row.callId}
            identity={row.callId}
            botState={row.botState}
            description={readableLabel(row.description) || "协作智能体"}
            summary={row.summary}
            running={row.status === "running"}
            depth={row.depth}
            live={live}
          />
        ))}
      </ul>
    </section>
  );
}

const AgentRow = memo(function AgentRow({
  identity,
  botState,
  description,
  summary,
  running,
  depth,
  live,
}: {
  identity: string;
  botState: BotPersistentState;
  description: string;
  summary: string;
  running: boolean;
  depth: number;
  live: boolean;
}) {
  const state = running ? (live ? "running" : "stopped") : "done";
  const statusLabel =
    state === "running" ? "进行中" : state === "done" ? "已完成" : "状态待确认";
  // 没有具体动作时仅显示一次状态；有动作时让摘要回答「正在做什么」。
  const action =
    state === "running" && summary && !/^运行中[.…\s]*$/.test(summary)
      ? readableLabel(summary.replace(/[.…]+$/, ""))
      : null;
  return (
    <li
      className={`cv-agentboard-row is-${state}`}
      style={{ "--depth": Math.min(depth, 2) } as CSSProperties}
      aria-label={`${description} · ${statusLabel}${action ? ` · ${action}` : ""}`}
    >
      <span className="cv-agentboard-avatar" aria-hidden="true">
        <ProseBot
          state={botState}
          identity={identity}
          size={40}
          intensity="quiet"
          ribbons={false}
          spawn={running && live}
          completionKey={identity}
          aria-hidden="true"
        />
      </span>
      <div className="cv-agentboard-main">
        <span className="cv-agentboard-desc">
          {description}
          {state === "running" && (
            <span className="cv-agentboard-sweep" aria-hidden="true">{description}</span>
          )}
        </span>
        {(action || state !== "running") && (
          <span className="cv-agentboard-summary">{action || statusLabel}</span>
        )}
      </div>
    </li>
  );
});
