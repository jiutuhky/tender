// SSE 的轻量运行投影，和时间线共用 store 的帧批处理；不保存工具入参或 token 正文。
import type { BotPersistentState } from "@/lib/bot/states";
import type { ChatStreamEvent } from "./timeline";

export interface BotActivity {
  active: Readonly<Record<string, string>>;
  latest: "thinking" | "generating" | "working";
}
export interface BotSignals {
  scopes: Readonly<Record<string, BotActivity>>;
  attention: "awaiting-input" | "blocked" | null;
  reading: boolean;
  ingestLabel?: string;
  partial: boolean;
  failed: boolean;
  ended: boolean;
  runId: string | null;
}
export function emptyBotSignals(): BotSignals {
  return {
    scopes: {},
    attention: null,
    reading: false,
    partial: false,
    failed: false,
    ended: false,
    runId: null,
  };
}
const record = (data: unknown): Record<string, unknown> =>
  data && typeof data === "object" && !Array.isArray(data)
    ? (data as Record<string, unknown>)
    : {};
const own = <T>(
  map: Readonly<Record<string, T>>,
  key: string,
): T | undefined => (Object.hasOwn(map, key) ? map[key] : undefined);
export function scopeActivity(
  signals: BotSignals,
  parent = "",
): BotActivity | undefined {
  return own(signals.scopes, parent);
}

export function reduceBotSignals(
  signals: BotSignals,
  event: ChatStreamEvent,
): BotSignals {
  const data = record(event.data);
  if (event.event === "run.started")
    return {
      ...signals,
      runId: typeof data.run_id === "string" ? data.run_id : null,
      reading: false,
    };
  if (event.event === "ingest.progress")
    return { ...signals, reading: true, ingestLabel: typeof data.label === "string" ? data.label : "正在解析原文" };
  if (event.event === "ingest.completed")
    return {
      ...signals,
      reading: false,
      partial:
        signals.partial ||
        (Array.isArray(data.failed_pages) && data.failed_pages.length > 0),
    };
  if (event.event === "ingest.failed")
    return { ...signals, reading: false, partial: true };
  if (event.event === "interrupt.requested")
    return { ...signals, attention: "awaiting-input" };
  if (event.event === "hook.blocked")
    return { ...signals, attention: "blocked" };
  if (event.event === "error")
    return {
      ...signals,
      failed: true,
      ended: true,
      reading: false,
      attention: null,
    };
  if (event.event === "done")
    return { ...signals, ended: true, reading: false };
  const scope =
    typeof data.parent_tool_use_id === "string" ? data.parent_tool_use_id : "";
  const previous = scopeActivity(signals, scope);
  const activity: BotActivity = previous ?? { active: {}, latest: "working" };
  let next = activity;
  if (event.event === "tool_call.started") {
    const id = typeof data.call_id === "string" ? data.call_id : "";
    if (!id) return signals;
    const name =
      typeof data.tool_name === "string" && data.tool_name
        ? data.tool_name
        : (own(activity.active, id) ?? "unknown");
    if (own(activity.active, id) === name) return signals;
    next = { active: { ...activity.active, [id]: name }, latest: "working" };
  } else if (event.event === "tool_call.completed") {
    const id = typeof data.call_id === "string" ? data.call_id : "";
    if (!id) return signals;
    const active = { ...activity.active };
    delete active[id];
    next = { active, latest: "working" };
  } else if (event.event === "message.delta") {
    const chunk = data.content_chunk;
    let latest: BotActivity["latest"] | null = null;
    if (typeof chunk === "string" && chunk) latest = "generating";
    if (Array.isArray(chunk))
      for (const entry of chunk) {
        const block = record(entry);
        if (
          block.type === "thinking" &&
          typeof block.thinking === "string" &&
          block.thinking
        )
          latest = "thinking";
        if (
          block.type === "text" &&
          typeof block.text === "string" &&
          block.text
        )
          latest = "generating";
      }
    if (!latest || previous?.latest === latest) return signals;
    next = { ...activity, latest };
  } else return signals;
  return { ...signals, scopes: { ...signals.scopes, [scope]: next } };
}

const READ = new Set([
  "Read",
  "read_file",
  "WebFetch",
  "prose_get_matrix",
  "prose_get_matrix_status",
]);
const SEARCH = new Set([
  "Glob",
  "glob",
  "Grep",
  "grep",
  "WebSearch",
  "prose_list_documents",
  "prose_query_matrix_items",
]);
const WRITE = new Set([
  "Write",
  "Edit",
  "write_file",
  "edit_file",
  "NotebookEdit",
  "prose_start_matrix_draft",
  "prose_submit_matrix_records",
  "prose_update_matrix_item",
  "prose_drop_matrix_item",
  "prose_move_matrix_item",
  "prose_set_matrix_meta",
  "prose_set_item_response_status",
  "prose_confirm_matrix_item",
]);
export function toolBotState(name: string): BotPersistentState {
  if (READ.has(name)) return "reading";
  if (SEARCH.has(name)) return "searching";
  if (WRITE.has(name)) return "generating";
  if (name === "prose_validate_matrix") return "verifying";
  if (name === "prose_publish_matrix") return "settling";
  if (name === "TaskCreate" || name === "TaskUpdate") return "planning";
  return "working";
}
export function activityBotState(activity: BotActivity): BotPersistentState {
  const active = Object.values(activity.active);
  const direct = active.filter((name) => name !== "Agent");
  if (direct.length) {
    const states = direct.map(toolBotState);
    return states.every((state) => state === states[0])
      ? states[0]!
      : "working";
  }
  if (activity.latest !== "working") return activity.latest;
  return active.includes("Agent") ? "coordinating" : "working";
}
