import { deriveSubagentBotState } from "@/lib/bot/derive";
import { BOT_DEFINITIONS, type BotPersistentState } from "@/lib/bot/states";
import type { BotSignals } from "@/lib/hagent/botSignals";
import type { ChatMsg, SubagentRun } from "@/lib/hagent/timeline";
import { MATRIX_TYPES } from "@/lib/hagent/matrix";
import type { MatrixSlots, RunPhase } from "@/lib/store/workspace";
import { toolLabel } from "./toolLabel";

// 运行状态的文案与语义派生。纯函数，无 React —— 三个消费方（消息浮窗标题栏、
// 胶囊、底部坞活动条）读的是同一套状态，文案必须一处定义。

export const PHASE_STATUS: Record<RunPhase, string> = {
  idle: "待命中",
  creating: "正在创建项目与会话",
  uploading: "正在上传招标文件",
  running: "正在解析招标文件",
  loading_results: "正在载入应答矩阵",
  done: "本轮处理完成",
  error: "操作未完成",
  cancelled: "本轮已停止",
};

export function isRunning(phase: RunPhase): boolean {
  return (
    phase === "running" || phase === "creating" || phase === "uploading" || phase === "loading_results"
  );
}

/** 真实终止/人工介入信号优先于页面的载入相位；所有状态文案共用。 */
function botStatusOverride(phase: RunPhase, signals?: BotSignals): string | null {
  if (phase === "cancelled" || signals?.cancelled) return PHASE_STATUS.cancelled;
  if (phase === "error" || signals?.failed) return PHASE_STATUS.error;
  if (signals?.attention) return BOT_DEFINITIONS[signals.attention].name;
  if (signals?.reading) return signals.ingestLabel ?? "正在解析原文";
  if (phase === "done" && signals?.partial) return "部分完成";
  return null;
}

/** 状态点不是头像角标，只辅助邻接文字；需要回应时不显示完成绿。 */
export function runDotState(phase: RunPhase, signals?: BotSignals): "idle" | "running" | "done" | "error" | "attention" {
  if (phase === "error" || signals?.failed) return "error";
  if (signals?.attention || phase === "done" && signals?.partial) return "attention";
  if (isRunning(phase)) return "running";
  if (phase === "done") return "done";
  return "idle";
}

export function runStatusText(phase: RunPhase, todoCount: number, readyCount: number, signals?: BotSignals): string {
  const override = botStatusOverride(phase,signals);
  if (override) return override;
  if (phase === "done" && readyCount) return `已提取 · ${readyCount} 类结果`;
  if (phase === "running" && todoCount) return `${PHASE_STATUS[phase]} · ${todoCount} 项任务`;
  return PHASE_STATUS[phase];
}

export function readyMatrixCount(matrices: MatrixSlots): number {
  return MATRIX_TYPES.filter((t) => matrices[t].status === "ready").length;
}

// 回溯上限：时间线在长会话里可达数千条，而「当前在做什么」只关心末尾一小段。
// 封顶后本函数是 O(1)，可以安全地当 zustand selector 每帧跑。
const SCAN_LIMIT = 400;

/**
 * 底部坞活动条的一行中文，如「正在提交矩阵条目 · 技术应答 · 4 次调用」。
 * 语域随品牌：状态先行，一律以「正在」起句。
 *
 * 刻意返回 string 而非对象：MessageWindow 用它当 selector，内容不变即 Object.is
 * 相等，zustand 跳过重渲——所以流式期大多数帧底部坞是静止的。
 */
export function activityLine(timeline: ChatMsg[], phase: RunPhase, signals?: BotSignals): string {
  const override = botStatusOverride(phase,signals);
  if (override) return override;
  if (!isRunning(phase)) return PHASE_STATUS[phase];

  let head = "";
  let calls = 0;
  const stop = Math.max(0, timeline.length - SCAN_LIMIT);
  for (let i = timeline.length - 1; i >= stop; i -= 1) {
    const m = timeline[i];
    if (!m || m.role === "user") break; // 回溯到本轮起点为止
    if (m.role === "tool") {
      calls += 1;
      if (!head) head = `正在${toolLabel(m.call)}`;
    } else if (m.role === "subagent") {
      calls += 1;
      if (!head) head = `正在执行子任务 ${m.run.description || m.run.subagentType}`.trim();
    }
  }

  if (!head) return PHASE_STATUS[phase];
  return calls > 1 ? `${head} · ${calls} 次调用` : head;
}

// —— 子代理看板（画布右上角 AgentBoard 的数据源）——

export interface SubagentBoardRow {
  callId: string;
  description: string;
  subagentType: string;
  status: "running" | "done" | "cancelled";
  /** 嵌套深度（顶层=0），看板按级缩进 */
  depth: number;
  /** 一行摘要：运行中=最近动作，完成=已完成 */
  summary: string;
  botState: BotPersistentState;
}

function collectFromLevel(msgs: ChatMsg[], depth: number, out: SubagentBoardRow[], live: boolean, signals?: BotSignals): void {
  for (const m of msgs) {
    if (m.role !== "subagent") continue;
    const botState = deriveSubagentBotState(m.run,live,signals);
    out.push({
      callId: m.run.call.call_id,
      description: m.run.description,
      subagentType: m.run.subagentType,
      status: m.run.status,
      depth,
      summary: m.run.status === "cancelled" ? "已停止" : m.run.status === "done" ? "已完成" : `${BOT_DEFINITIONS[botState].name}中`,
      botState,
    });
    collectFromLevel(m.run.children, depth + 1, out,live,signals);
  }
}

/**
 * 本轮派发的子代理列表（顶层 + 嵌套，按派发顺序）。
 * 与 activityLine 同一回扫策略：从末尾回到最近一条 user 消息为止——看板只反映
 * 当前这一轮，上一轮的子代理不残留。O(末段扫描)，可安全当每帧批处理的一部分跑。
 */
export function collectSubagentRuns(timeline: ChatMsg[],live=true,signals?: BotSignals): SubagentBoardRow[] {
  let start = timeline.length;
  while (start > 0) {
    const m = timeline[start - 1];
    if (!m || m.role === "user") break;
    start -= 1;
  }
  const out: SubagentBoardRow[] = [];
  collectFromLevel(timeline.slice(start), 0, out,live,signals);
  return out;
}

/**
 * 本轮是否派发过子代理。与 collectSubagentRuns 同一回扫策略，但首个 subagent 即返回，
 * 且返回原始值——所以可以安全地当每帧跑的 zustand selector（Object.is 兜住重渲），
 * 理由同 activityLine 的「刻意返回 string 而非对象」。
 */
export function hasSubagentRuns(timeline: ChatMsg[]): boolean {
  for (let i = timeline.length - 1; i >= 0; i -= 1) {
    const m = timeline[i];
    if (!m || m.role === "user") return false; // 回溯到本轮起点为止
    if (m.role === "subagent") return true;
  }
  return false;
}

/** 子任务的一行状态文字：运行中显示最近动作，完成显示「已完成」。 */
export function subagentStatusText(run: SubagentRun): string {
  if (run.status === "cancelled") return "已停止";
  if (run.status === "done") return "已完成";
  const action = latestActionLabel(run.children);
  return action ? `${action}……` : "运行中……";
}

/** 从子代理内部时间线里取「最近一次动作」的简短描述（倒序找第一条可读事件）。 */
export function latestActionLabel(children: ChatMsg[]): string {
  for (let i = children.length - 1; i >= 0; i -= 1) {
    const m = children[i];
    if (!m) continue;
    if (m.role === "tool") return toolLabel(m.call);
    if (m.role === "subagent") return `子任务 ${m.run.description}`.trim();
    if (m.role === "thinking") return "思考中";
    if (m.role === "assistant_text") return "正在整理输出";
  }
  return "";
}
