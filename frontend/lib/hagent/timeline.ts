// SSE 事件 → 聊天时间线 reducer。
// 移植自 hagent/web/src/lib/chat_timeline.ts（纯函数，原样保留）。
// 把后端 SSE 事件（message.delta / tool_call.started / tool_call.completed / error）
// reduce 成 ChatMsg[]，并把 Agent 工具调用嵌套成 subagent run（体现解析 skill 的 5 个 parser + verifier）。
// 归属靠后端事件携带的 parent_tool_use_id（= 派发该子代理的 Agent 工具 call_id），
// 不靠 liveness 猜测——并行多 Agent 下猜测会互相嵌套、串台并无限嵌套拖垮渲染。

export type ToolCall = {
  call_id: string;
  tool_name: string;
  args: string;
  result?: string;
  status: "running" | "done";
};

export type SubagentRun = {
  call: ToolCall;
  status: "running" | "done";
  description: string;
  prompt: string;
  subagentType: string;
  children: ChatMsg[];
};

export type ChatMsg =
  | { id: string; role: "user"; content: string }
  | { id: string; role: "assistant_text"; content: string }
  | { id: string; role: "thinking"; content: string }
  | { id: string; role: "tool"; call: ToolCall }
  | { id: string; role: "subagent"; run: SubagentRun }
  | { id: string; role: "error"; content: string };

export type ChatStreamEvent = {
  event: string;
  data: unknown;
};

type AgentArgs = {
  description?: string;
  prompt?: string;
  subagent_type?: string | null;
};

function newId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random()}`;
}

function appendStreamChunk(msgs: ChatMsg[], kind: "thinking" | "text", chunk: string): ChatMsg[] {
  if (!chunk) return msgs;
  const role: "thinking" | "assistant_text" = kind === "thinking" ? "thinking" : "assistant_text";
  const last = msgs[msgs.length - 1];
  if (last && last.role === role) {
    const copy = [...msgs];
    copy[copy.length - 1] = { ...last, content: last.content + chunk };
    return copy;
  }
  const newMsg: ChatMsg =
    role === "thinking"
      ? { id: newId("th"), role: "thinking", content: chunk }
      : { id: newId("at"), role: "assistant_text", content: chunk };
  return [...msgs, newMsg];
}

function appendContentDelta(msgs: ChatMsg[], contentChunk: string | unknown): ChatMsg[] {
  const items: Array<{ kind: "thinking" | "text"; text: string }> = [];
  if (typeof contentChunk === "string" && contentChunk) {
    items.push({ kind: "text", text: contentChunk });
  } else if (Array.isArray(contentChunk)) {
    for (const b of contentChunk) {
      const block = b as { type?: string; text?: string; thinking?: string };
      if (block.type === "thinking" && block.thinking) items.push({ kind: "thinking", text: block.thinking });
      else if (block.type === "text" && block.text) items.push({ kind: "text", text: block.text });
    }
  }
  let next = msgs;
  for (const it of items) next = appendStreamChunk(next, it.kind, it.text);
  return next;
}

function parseAgentArgs(rawArgs: string): AgentArgs {
  try {
    const parsed = JSON.parse(rawArgs) as AgentArgs;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function enrichSubagentRun(call: ToolCall, children: ChatMsg[] = []): SubagentRun {
  const args = parseAgentArgs(call.args);
  return {
    call,
    status: call.status,
    description: args.description?.trim() || "Subagent task",
    prompt: args.prompt?.trim() || "",
    subagentType: args.subagent_type?.trim() || "general-purpose",
    children,
  };
}

function updateToolCall(msgs: ChatMsg[], callId: string, updater: (call: ToolCall) => ToolCall): ChatMsg[] {
  const idx = msgs.findIndex((x) => x.role === "tool" && x.call.call_id === callId);
  if (idx < 0) return msgs;
  const cur = msgs[idx];
  if (!cur || cur.role !== "tool") return msgs;
  const copy = [...msgs];
  copy[idx] = { ...cur, call: updater(cur.call) };
  return copy;
}

function appendOrUpdateToolStarted(msgs: ChatMsg[], callId: string, toolName: string, argsChunk: string): ChatMsg[] {
  const updated = updateToolCall(msgs, callId, (call) => ({
    ...call,
    args: call.args + argsChunk,
    tool_name: call.tool_name || toolName,
  }));
  if (updated !== msgs) return updated;
  return [
    ...msgs,
    {
      id: `t-${callId}`,
      role: "tool",
      call: { call_id: callId, tool_name: toolName, args: argsChunk, status: "running" },
    },
  ];
}

function appendOrUpdateToolCompleted(
  msgs: ChatMsg[],
  callId: string,
  toolName: string,
  resultSummary?: string,
): ChatMsg[] {
  const updated = updateToolCall(msgs, callId, (call) => ({
    ...call,
    result: resultSummary,
    status: "done",
    tool_name: call.tool_name || toolName,
  }));
  if (updated !== msgs) return updated;
  return [
    ...msgs,
    {
      id: `t-${callId || Date.now()}`,
      role: "tool",
      call: { call_id: callId, tool_name: toolName, args: "", result: resultSummary, status: "done" },
    },
  ];
}

// --- parent_tool_use_id 路由（对齐 CC 的 parentToolUseID 分组）---
//
// 后端给每个 tool_call.* / message.delta 事件带上 parent_tool_use_id：主 agent 为
// null/空，子代理事件 = 派发它的 Agent 工具 call_id。我们据此把事件精确路由到对应
// 层级，绝不靠「最后一个 running 子代理」猜测——那在并行多 Agent 下会把平级子代理
// 互相嵌套、串台、永不收尾，进而无限嵌套拖垮渲染。

/** 在 msgs 树中找到 call_id===parentId 的 subagent，对其 children 应用 fn。 */
function mapChildrenOf(
  msgs: ChatMsg[],
  parentId: string,
  fn: (children: ChatMsg[]) => ChatMsg[],
): { msgs: ChatMsg[]; found: boolean } {
  for (let i = 0; i < msgs.length; i += 1) {
    const m = msgs[i];
    if (!m || m.role !== "subagent") continue;
    if (m.run.call.call_id === parentId) {
      const copy = [...msgs];
      copy[i] = { ...m, run: { ...m.run, children: fn(m.run.children) } };
      return { msgs: copy, found: true };
    }
    const r = mapChildrenOf(m.run.children, parentId, fn);
    if (r.found) {
      const copy = [...msgs];
      copy[i] = { ...m, run: { ...m.run, children: r.msgs } };
      return { msgs: copy, found: true };
    }
  }
  return { msgs, found: false };
}

/** 把 fn 应用到 parentId 指定的层级（空 = 顶层；找不到则防御性落回顶层）。 */
function routeInto(
  msgs: ChatMsg[],
  parentId: string | null | undefined,
  fn: (level: ChatMsg[]) => ChatMsg[],
): ChatMsg[] {
  if (!parentId) return fn(msgs);
  const r = mapChildrenOf(msgs, parentId, fn);
  return r.found ? r.msgs : fn(msgs);
}

function startToolInLevel(level: ChatMsg[], callId: string, toolName: string, argsChunk: string): ChatMsg[] {
  if (toolName === "Agent") {
    // 同 call_id 的子代理已存在（args 分片续传）→ 更新；否则新建一个 running 子代理。
    const idx = level.findIndex((x) => x.role === "subagent" && x.run.call.call_id === callId);
    const cur = idx >= 0 ? level[idx] : undefined;
    if (cur && cur.role === "subagent") {
      const call: ToolCall = {
        ...cur.run.call,
        args: cur.run.call.args + argsChunk,
        tool_name: cur.run.call.tool_name || toolName,
      };
      const copy = [...level];
      copy[idx] = { ...cur, run: enrichSubagentRun(call, cur.run.children) };
      return copy;
    }
    const call: ToolCall = { call_id: callId, tool_name: toolName, args: argsChunk, status: "running" };
    return [...level, { id: `sa-${callId}`, role: "subagent", run: enrichSubagentRun(call) }];
  }
  return appendOrUpdateToolStarted(level, callId, toolName, argsChunk);
}

function completeInLevel(level: ChatMsg[], callId: string, toolName: string, resultSummary?: string): ChatMsg[] {
  // 该层级里若有同 call_id 的子代理 → 是 Agent 完成事件，收尾该子代理；
  // 否则是普通工具完成。
  const idx = level.findIndex((x) => x.role === "subagent" && x.run.call.call_id === callId);
  const cur = idx >= 0 ? level[idx] : undefined;
  if (cur && cur.role === "subagent") {
    const copy = [...level];
    copy[idx] = {
      ...cur,
      run: {
        ...cur.run,
        status: "done",
        call: { ...cur.run.call, result: resultSummary, status: "done", tool_name: cur.run.call.tool_name || toolName },
      },
    };
    return copy;
  }
  return appendOrUpdateToolCompleted(level, callId, toolName, resultSummary);
}

function reduceIntoList(msgs: ChatMsg[], ev: ChatStreamEvent): ChatMsg[] {
  if (ev.event === "message.delta") {
    const d = ev.data as { content_chunk?: string | unknown; parent_tool_use_id?: string | null };
    return routeInto(msgs, d.parent_tool_use_id, (level) => appendContentDelta(level, d.content_chunk));
  }

  if (ev.event === "tool_call.started") {
    const d = ev.data as { call_id?: string; tool_name?: string; args_chunk?: string; parent_tool_use_id?: string | null };
    const callId = d.call_id || `anon-${Date.now()}-${Math.random()}`;
    const toolName = d.tool_name || "unknown";
    const argsChunk = d.args_chunk || "";
    return routeInto(msgs, d.parent_tool_use_id, (level) => startToolInLevel(level, callId, toolName, argsChunk));
  }

  if (ev.event === "tool_call.completed") {
    const d = ev.data as { call_id?: string; tool_name?: string; result_summary?: string; parent_tool_use_id?: string | null };
    const callId = d.call_id || "";
    const toolName = d.tool_name || "";
    return routeInto(msgs, d.parent_tool_use_id, (level) => completeInLevel(level, callId, toolName, d.result_summary));
  }

  if (ev.event === "error") {
    const d = ev.data as { message?: string };
    return [...msgs, { id: newId("e"), role: "error", content: d.message ?? "unknown error" }];
  }

  return msgs;
}

export function reduceChatEvent(msgs: ChatMsg[], ev: ChatStreamEvent): ChatMsg[] {
  return reduceIntoList(msgs, ev);
}
