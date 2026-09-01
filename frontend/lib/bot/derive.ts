// hagent 事件 → Bot 状态。
//
// 映射的原则是**只映射看得出区别的事**：后端能区分二十种工具，但一个 24px 的图标上
// 「在检索」和「在写」的差别才立得住，「在读第几个文件」立不住。所以工具按动作大类
// 归三档：找（searching）、写（writing）、干（working）。
//
// 情绪一组状态在这里没有对应事件——它们由引擎在待命期随机穿插，或等后续接线。

import type { ChatMsg } from "@/lib/hagent/timeline";
import type { RunPhase } from "@/lib/store/workspace";
import type { BotState } from "./states";

/** 回扫上限，与 runStatus.activityLine 同一策略：只关心「当前在做什么」。 */
const SCAN_LIMIT = 120;

const SEARCH_TOOLS = new Set([
  "Read", "Glob", "glob", "Grep", "grep", "WebFetch", "WebSearch",
  "prose_list_documents", "prose_get_matrix", "prose_query_matrix_items",
  "prose_get_matrix_status",
]);

const WRITE_TOOLS = new Set([
  "Write", "Edit", "NotebookEdit",
  "prose_start_matrix_draft", "prose_submit_matrix_records", "prose_update_matrix_item",
  "prose_drop_matrix_item", "prose_move_matrix_item", "prose_set_matrix_meta",
  "prose_publish_matrix", "prose_set_item_response_status", "prose_confirm_matrix_item",
]);

function toolState(name: string): BotState {
  if (SEARCH_TOOLS.has(name)) return "searching";
  if (WRITE_TOOLS.has(name)) return "writing";
  return "working";
}

/**
 * 主 Bot（画布消息窗）的状态。
 *
 * running 档要再往时间线里看一眼：同样是「正在跑」，派子代理、思考、检索、落笔是四件
 * 完全不同的事，头像应该分得出来——这正是把动效做成状态机而不是一段循环的理由。
 */
export function deriveMainBotState(phase: RunPhase, timeline: ChatMsg[]): BotState {
  switch (phase) {
    case "idle":
      return "idle";
    case "creating":
      return "spawning";
    case "uploading":
      return "uploading";
    case "loading_results":
      return "loading";
    case "done":
      return "idle";
    case "error":
      return "alerting";
    case "running":
      break;
  }

  const stop = Math.max(0, timeline.length - SCAN_LIMIT);
  for (let i = timeline.length - 1; i >= stop; i -= 1) {
    const m = timeline[i];
    if (!m || m.role === "user") break;
    if (m.role === "subagent") {
      // 派了子代理还在跑 → 环绕形态：主 Bot 在「盯着一圈工人」
      return m.run.status === "running" ? "orbit" : "working";
    }
    if (m.role === "tool") {
      return m.call.status === "running" ? toolState(m.call.tool_name) : "working";
    }
    if (m.role === "thinking") return "thinking";
    if (m.role === "assistant_text") return "dictating";
    if (m.role === "error") return "alerting";
  }
  return "thinking";
}

/** 子代理看板一行的状态。看板上的 Bot 只有「在干活」和「干完了」两档。 */
export function deriveSubagentBotState(status: "running" | "done", live: boolean): BotState {
  if (status === "done") return "idle";
  return live ? "working" : "bored";
}
