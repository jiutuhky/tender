// 每个逻辑模型调用独立跟踪预算；事件过期检查发生在所有 UI 投影之前。
import type { ChatStreamEvent } from "./timeline";

export interface ModelAttempt {
  model_call_id: string;
  parent_tool_use_id?: string | null;
  attempt: number;
  max_retries: number;
  status: "requesting" | "retrying" | "slow" | "completed";
  message?: string;
  retry?: number;
  next_attempt_at?: number;
}
export interface ModelFailure {
  message?: string;
  category?: string;
  action?: string;
  attempts?: number;
  status_code?: number;
  request_id?: string;
  checkpoint_saved?: boolean;
  checkpoint_message?: string;
}
export interface ModelRecovery {
  calls: Record<string, ModelAttempt>;
  failure: ModelFailure | null;
  cancelled: boolean;
  checkpointSaved: boolean;
}
export const emptyModelRecovery = (): ModelRecovery => ({ calls: {}, failure: null, cancelled: false, checkpointSaved: false });

export function acceptsModelEvent(state: ModelRecovery, event: ChatStreamEvent): boolean {
  const data = event.data as Partial<ModelAttempt> | null;
  if (!data?.model_call_id || typeof data.attempt !== "number") return true;
  const current = state.calls[data.model_call_id];
  if (!current) return true;
  if (data.attempt < current.attempt) return false;
  if (current.status === "completed" && (event.event === "message.delta" || event.event === "tool_call.started")) return false;
  return true;
}

export function reduceModelRecovery(state: ModelRecovery, event: ChatStreamEvent): ModelRecovery {
  if (event.event === "run.started") return emptyModelRecovery();
  if (!acceptsModelEvent(state, event)) return state;
  if (event.event === "run.cancelled" || event.event === "error") {
    const data = event.data as ModelFailure;
    return { ...state, calls: {}, failure: event.event === "error" ? data : null, cancelled: event.event === "run.cancelled", checkpointSaved: data.checkpoint_saved === true };
  }
  if (event.event === "workspace.checkpointed" || event.event === "done") return { ...state, checkpointSaved: (event.data as ModelFailure).checkpoint_saved === true };
  const data = event.data as Partial<ModelAttempt>;
  const active = data?.model_call_id ? state.calls[data.model_call_id] : undefined;
  if (active?.status === "slow" && (event.event === "message.delta" || event.event === "tool_call.started")) {
    return { ...state, calls: { ...state.calls, [active.model_call_id]: { ...active, status: "requesting", message: undefined } } };
  }
  if (!event.event.startsWith("model.") || !data?.model_call_id || typeof data.attempt !== "number") return state;
  const status = event.event === "model.retry" ? "retrying" : event.event === "model.call.completed" ? "completed" : event.event === "model.slow" ? "slow" : "requesting";
  const call: ModelAttempt = {
    ...state.calls[data.model_call_id], ...data,
    model_call_id: data.model_call_id,
    // 失败后立刻拒收该尝试的迟到增量，下一次 started 使用相同的新编号。
    attempt: data.attempt + (status === "retrying" ? 1 : 0),
    max_retries: data.max_retries ?? 10, status,
  };
  return { ...state, calls: { ...state.calls, [call.model_call_id]: call } };
}

export function retryCountdown(call: ModelAttempt, now: number): number {
  return Math.max(0, Math.ceil(((call.next_attempt_at ?? now) - now) / 1000));
}
