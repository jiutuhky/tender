import assert from "node:assert/strict";
import test from "node:test";

import { reduceChatEvent, type ChatMsg, type SubagentRun } from "./chat_timeline.ts";

function sub(msg: ChatMsg | undefined): SubagentRun {
  assert.ok(msg && msg.role === "subagent");
  return msg.run;
}

test("groups streamed subagent activity under the Agent tool call", () => {
  let msgs: ChatMsg[] = [];

  msgs = reduceChatEvent(msgs, {
    event: "tool_call.started",
    data: {
      call_id: "agent-1",
      tool_name: "Agent",
      args_chunk: '{"description":"Audit web UI","prompt":"Inspect messages","subagent_type":"Explore"}',
      parent_tool_use_id: null,
    },
  });
  // 子代理内部事件带 parent_tool_use_id = 该 Agent 的 call_id
  msgs = reduceChatEvent(msgs, {
    event: "message.delta",
    data: { content_chunk: "I am checking the message renderer.", parent_tool_use_id: "agent-1" },
  });
  msgs = reduceChatEvent(msgs, {
    event: "tool_call.started",
    data: { call_id: "read-1", tool_name: "Read", args_chunk: '{"file_path":"web/src/app/page.tsx"}', parent_tool_use_id: "agent-1" },
  });
  msgs = reduceChatEvent(msgs, {
    event: "tool_call.completed",
    data: { call_id: "read-1", tool_name: "Read", result_summary: "page contents", parent_tool_use_id: "agent-1" },
  });
  // Agent 完成事件在父级发出（parent_tool_use_id = null），按 call_id 收尾子代理
  msgs = reduceChatEvent(msgs, {
    event: "tool_call.completed",
    data: { call_id: "agent-1", tool_name: "Agent", result_summary: "Found the flat timeline issue.", parent_tool_use_id: null },
  });

  assert.equal(msgs.length, 1);
  const run = sub(msgs[0]);
  assert.equal(run.call.tool_name, "Agent");
  assert.equal(run.status, "done");
  assert.equal(run.description, "Audit web UI");
  assert.equal(run.subagentType, "Explore");
  assert.equal(run.children.length, 2);
  assert.equal(run.children[0]?.role, "assistant_text");
  assert.equal(run.children[1]?.role, "tool");
  assert.equal(run.call.result, "Found the flat timeline issue.");
});

test("parallel subagents stay siblings, never nest into each other", () => {
  let msgs: ChatMsg[] = [];

  // 主 agent 在一轮里并行派发两个 Agent
  msgs = reduceChatEvent(msgs, {
    event: "tool_call.started",
    data: { call_id: "agent-A", tool_name: "Agent", args_chunk: '{"description":"Parse 资格","prompt":"..."}', parent_tool_use_id: null },
  });
  msgs = reduceChatEvent(msgs, {
    event: "tool_call.started",
    data: { call_id: "agent-B", tool_name: "Agent", args_chunk: '{"description":"Parse 评分","prompt":"..."}', parent_tool_use_id: null },
  });

  // 两个子代理的内部事件交错到达，各带自己的 parent_tool_use_id
  msgs = reduceChatEvent(msgs, {
    event: "message.delta",
    data: { content_chunk: "A working", parent_tool_use_id: "agent-A" },
  });
  msgs = reduceChatEvent(msgs, {
    event: "message.delta",
    data: { content_chunk: "B working", parent_tool_use_id: "agent-B" },
  });
  msgs = reduceChatEvent(msgs, {
    event: "tool_call.started",
    data: { call_id: "readB", tool_name: "Read", args_chunk: "{}", parent_tool_use_id: "agent-B" },
  });
  msgs = reduceChatEvent(msgs, {
    event: "tool_call.started",
    data: { call_id: "readA", tool_name: "Read", args_chunk: "{}", parent_tool_use_id: "agent-A" },
  });
  msgs = reduceChatEvent(msgs, {
    event: "tool_call.completed",
    data: { call_id: "readA", tool_name: "Read", result_summary: "rA", parent_tool_use_id: "agent-A" },
  });
  msgs = reduceChatEvent(msgs, {
    event: "tool_call.completed",
    data: { call_id: "readB", tool_name: "Read", result_summary: "rB", parent_tool_use_id: "agent-B" },
  });

  // 完成顺序与启动顺序不同
  msgs = reduceChatEvent(msgs, {
    event: "tool_call.completed",
    data: { call_id: "agent-B", tool_name: "Agent", result_summary: "B done", parent_tool_use_id: null },
  });
  msgs = reduceChatEvent(msgs, {
    event: "tool_call.completed",
    data: { call_id: "agent-A", tool_name: "Agent", result_summary: "A done", parent_tool_use_id: null },
  });

  // 顶层是两个平级 subagent，互不嵌套
  assert.equal(msgs.length, 2);
  const a = sub(msgs[0]);
  const b = sub(msgs[1]);
  assert.equal(a.call.call_id, "agent-A");
  assert.equal(b.call.call_id, "agent-B");

  // 各自收尾、各自的内部事件归位，绝不串台
  assert.equal(a.status, "done");
  assert.equal(b.status, "done");
  assert.equal(a.call.result, "A done");
  assert.equal(b.call.result, "B done");

  // A 的 children 只有 A 的文本 + A 的 Read；B 同理。B 不在 A 里面。
  assert.equal(a.children.length, 2);
  assert.equal(a.children[0]?.role, "assistant_text");
  assert.equal(a.children[0]?.role === "assistant_text" && a.children[0].content, "A working");
  assert.ok(a.children.every((c) => c.role !== "subagent"));
  assert.equal(b.children.length, 2);
  assert.equal(b.children[0]?.role === "assistant_text" && b.children[0].content, "B working");
  assert.ok(b.children.every((c) => c.role !== "subagent"));
});

test("nested subagent nests under its direct parent by parent_tool_use_id", () => {
  let msgs: ChatMsg[] = [];

  msgs = reduceChatEvent(msgs, {
    event: "tool_call.started",
    data: { call_id: "outer", tool_name: "Agent", args_chunk: '{"description":"Outer"}', parent_tool_use_id: null },
  });
  // outer 内部又派发一个 Agent（parent_tool_use_id = outer）
  msgs = reduceChatEvent(msgs, {
    event: "tool_call.started",
    data: { call_id: "inner", tool_name: "Agent", args_chunk: '{"description":"Inner"}', parent_tool_use_id: "outer" },
  });
  // inner 内部的文本（parent_tool_use_id = inner）
  msgs = reduceChatEvent(msgs, {
    event: "message.delta",
    data: { content_chunk: "deep work", parent_tool_use_id: "inner" },
  });
  msgs = reduceChatEvent(msgs, {
    event: "tool_call.completed",
    data: { call_id: "inner", tool_name: "Agent", result_summary: "inner done", parent_tool_use_id: "outer" },
  });
  msgs = reduceChatEvent(msgs, {
    event: "tool_call.completed",
    data: { call_id: "outer", tool_name: "Agent", result_summary: "outer done", parent_tool_use_id: null },
  });

  assert.equal(msgs.length, 1);
  const outer = sub(msgs[0]);
  assert.equal(outer.call.call_id, "outer");
  assert.equal(outer.status, "done");
  assert.equal(outer.children.length, 1);
  const inner = sub(outer.children[0]);
  assert.equal(inner.call.call_id, "inner");
  assert.equal(inner.status, "done");
  assert.equal(inner.call.result, "inner done");
  assert.equal(inner.children.length, 1);
  assert.equal(inner.children[0]?.role === "assistant_text" && inner.children[0].content, "deep work");
});
