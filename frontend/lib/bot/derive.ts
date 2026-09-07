// 产品适配层：只从可信生命周期与作用域活动派生通用状态。
import type { ChatMsg, SubagentRun } from "@/lib/hagent/timeline";
import type { RunPhase } from "@/lib/store/workspace";
import {
  activityBotState,
  scopeActivity,
  emptyBotSignals,
  type BotSignals,
} from "../hagent/botSignals";
import type { BotPersistentState } from "./states";

/** 历史/静态数据没有实时投影时的回退；保留仍活跃的调用，而非只取最后一条消息。 */
function timelineActivity(messages: ChatMsg[]): BotPersistentState {
  const active: Record<string, string> = {};
  let latest: "working" | "generating" | "thinking" = "thinking";
  for (const message of messages) {
    if (message.role === "user") {
      for (const key of Object.keys(active)) delete active[key];
      latest = "thinking";
    }
    if (message.role === "thinking") latest = "thinking";
    if (message.role === "assistant_text") latest = "generating";
    if (message.role === "tool" || message.role === "subagent") {
      const call = message.role === "tool" ? message.call : message.run.call;
      const status =
        message.role === "tool" ? message.call.status : message.run.status;
      if (status === "running")
        active[call.call_id] =
          message.role === "subagent" ? "Agent" : call.tool_name;
      else delete active[call.call_id];
      latest = "working";
    }
  }
  return activityBotState({ active, latest });
}
export function deriveMainBotState(
  phase: RunPhase,
  timeline: ChatMsg[],
  signals: BotSignals = emptyBotSignals(),
): BotPersistentState {
  if (signals.failed || phase === "error") return "failed";
  if (signals.attention) return signals.attention;
  if (phase === "idle") return "idle";
  if (phase === "creating") return "connecting";
  if (phase === "uploading") return "sending";
  if (phase === "loading_results") return "settling";
  if (phase === "done") return signals.partial ? "partial" : "completed";
  if (signals.reading) return "reading";
  const activity = scopeActivity(signals);
  return activity ? activityBotState(activity) : timelineActivity(timeline);
}
export function deriveSubagentBotState(
  run: SubagentRun,
  live: boolean,
  signals?: BotSignals,
): BotPersistentState {
  if (run.status === "done") return "completed";
  // 连接/主流结束不能证明子任务已取消；保持等待形态并由文字说明状态待确认。
  if (!live || signals?.attention || signals?.failed) return "waiting";
  const activity = signals
    ? scopeActivity(signals, run.call.call_id)
    : undefined;
  return activity ? activityBotState(activity) : timelineActivity(run.children);
}
export function currentTurnKey(timeline: ChatMsg[]): string | undefined {
  for (let i = timeline.length - 1; i >= 0; i--)
    if (timeline[i]?.role === "user") return timeline[i]?.id;
  return undefined;
}
