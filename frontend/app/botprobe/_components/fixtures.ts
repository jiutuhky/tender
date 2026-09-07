import {
  reduceChatEvent,
  type ChatMsg,
  type ChatStreamEvent,
} from "@/lib/hagent/timeline";
import { emptyBotSignals, reduceBotSignals } from "@/lib/hagent/botSignals";
import type { TodoItem } from "@/lib/hagent/todo";

export const DEMO_TODOS: TodoItem[] = [
  {
    key: "prepare",
    content: "准备源文件",
    status: "completed",
    blocked: false,
  },
  {
    key: "extract",
    content: "整理应答要点",
    activeForm: "正在整理应答要点",
    status: "in_progress",
    blocked: false,
  },
  {
    key: "verify",
    content: "汇总并复核结果",
    status: "pending",
    blocked: true,
  },
];
export function botReviewFixture(complete = false) {
  const events: ChatStreamEvent[] = [
    { event: "run.started", data: { run_id: "review-turn" } },
  ];
  const agents = [
    ["source-reader", "阅读招标文件", "Read"],
    ["business-writer", "整理商务应答", "prose_submit_matrix_records"],
    ["technical-verifier", "检查技术要求", "prose_validate_matrix"],
    ["research-helper", "检索补充资料", "WebSearch"],
  ];
  agents.forEach(([id, description, tool]) => {
    events.push({
      event: "tool_call.started",
      data: {
        call_id: id,
        tool_name: "Agent",
        args_chunk: JSON.stringify({
          description,
          subagent_type: "general-purpose",
        }),
      },
    });
    events.push({
      event: "tool_call.started",
      data: {
        call_id: `${id}-tool`,
        parent_tool_use_id: id,
        tool_name: tool,
        args_chunk: "{}",
      },
    });
  });
  events.push({
    event: "tool_call.started",
    data: {
      call_id: "nested-reader",
      parent_tool_use_id: "source-reader",
      tool_name: "Agent",
      args_chunk: JSON.stringify({ description: "对照原文段落" }),
    },
  });
  events.push({
    event: "message.delta",
    data: {
      parent_tool_use_id: "nested-reader",
      content_chunk: [{ type: "thinking", thinking: "对照上下文" }],
    },
  });
  events.push({
    event: "tool_call.completed",
    data: {
      call_id: "research-helper",
      tool_name: "Agent",
      result_summary: "检索完成",
    },
  });
  if (complete)
    for (const [id] of agents)
      events.push({
        event: "tool_call.completed",
        data: { call_id: id, tool_name: "Agent", result_summary: "工作完成" },
      });
  if (complete)
    events.push({
      event: "tool_call.completed",
      data: {
        call_id: "nested-reader",
        parent_tool_use_id: "source-reader",
        tool_name: "Agent",
        result_summary: "工作完成",
      },
    });
  let timeline: ChatMsg[] = [
    { id: "review-user-turn", role: "user", content: "请协作整理应答要点。" },
  ];
  let signals = emptyBotSignals();
  for (const event of events) {
    timeline = reduceChatEvent(timeline, event);
    signals = reduceBotSignals(signals, event);
  }
  return { timeline, signals };
}
