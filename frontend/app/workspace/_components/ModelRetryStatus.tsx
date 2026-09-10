"use client";

import { useEffect, useState } from "react";
import { useWorkspaceStore } from "@/lib/store/workspace";
import { retryCountdown, type ModelAttempt } from "@/lib/hagent/modelRecovery";
import type { ChatMsg } from "@/lib/hagent/timeline";
import "./model-retry.css";

function subtaskTitle(messages: ChatMsg[], id: string): string | undefined {
  for (const message of messages) {
    if (message.role !== "subagent") continue;
    if (message.run.call.call_id === id) return message.run.description;
    const nested = subtaskTitle(message.run.children, id);
    if (nested) return nested;
  }
}

/** 按尝试挂载计时器；本地更新不会触发工作台或其他子任务重渲。 */
function Countdown({ call }: { call: ModelAttempt }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, []);
  const seconds = retryCountdown(call, now);
  return <>{seconds ? `${seconds} 秒后重试` : "即将重试"}（{call.retry}/{call.max_retries}）</>;
}

function RetryNotice({ call }: { call: ModelAttempt }) {
  const title = useWorkspaceStore((state) => call.parent_tool_use_id ? subtaskTitle(state.timeline, call.parent_tool_use_id) ?? "子任务" : "主智能体");
  return <div className="model-retry-notice" role="status" aria-live="polite">
    <span className="model-retry-scope">{title}</span>
    <p>{call.message} {call.status === "retrying" && <><Countdown key={call.attempt} call={call} />。已有成果会保留。</>}</p>
  </div>;
}

export function ModelRetryStatus() {
  const calls = useWorkspaceStore((s) => s.modelRecovery.calls);
  const running = useWorkspaceStore((s) => s.phase === "running" && !s.botSignals.ended);
  const failure = useWorkspaceStore((s) => s.modelRecovery.failure);
  const waiting = Object.values(calls).filter((call) => call.status === "retrying" || call.status === "slow");
  if (!running) return null;
  return <div className="model-retry-notices">
    {waiting.map((call) => <RetryNotice key={call.model_call_id} call={call} />)}
    {failure && <p role="alert">{failure.message}</p>}
  </div>;
}
