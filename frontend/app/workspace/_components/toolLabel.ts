import type { ToolCall } from "@/lib/hagent/timeline";

// 对象库(结构化资产)工具面:prose_* 工具的中文说明,矩阵名跟在动作后
const PROSE_TOOL_ZH: Record<string, string> = {
  prose_register_document: "注册源文件",
  prose_list_documents: "列举源文件",
  prose_start_matrix_draft: "开矩阵草稿",
  prose_submit_matrix_records: "提交矩阵条目",
  prose_update_matrix_item: "修订矩阵条目",
  prose_drop_matrix_item: "删除矩阵条目",
  prose_move_matrix_item: "移动矩阵条目",
  prose_set_matrix_meta: "更新矩阵元信息",
  prose_validate_matrix: "校验矩阵",
  prose_publish_matrix: "发布矩阵",
  prose_get_matrix: "读取矩阵总览",
  prose_query_matrix_items: "查询矩阵条目",
  prose_get_matrix_status: "查询矩阵状态",
  prose_set_item_response_status: "代录应答状态",
  prose_confirm_matrix_item: "代录条目确认",
};

const MATRIX_ZH: Record<string, string> = {
  basic_info: "项目概要",
  business: "商务应答",
  technical: "技术应答",
  scoring: "评分办法",
};

/** 把一个工具调用渲染成简洁的中文说明（用于 .cm-tool-query）。 */
export function toolLabel(call: ToolCall): string {
  let args: Record<string, unknown> = {};
  try {
    args = JSON.parse(call.args) as Record<string, unknown>;
  } catch {
    /* args 可能是流式未闭合的 JSON 片段，忽略 */
  }
  const s = (k: string) => (typeof args[k] === "string" ? (args[k] as string) : "");
  const base = (p: string) => p.split("/").pop() || p;

  switch (call.tool_name) {
    case "Read":
      return `读取 ${base(s("file_path") || s("path"))}`;
    case "Write":
      return `写入 ${base(s("file_path") || s("path"))}`;
    case "Edit":
      return `编辑 ${base(s("file_path") || s("path"))}`;
    case "Bash":
      return `执行命令 ${truncate(s("command"), 80)}`;
    case "glob":
    case "Glob":
      return `查找文件 ${s("pattern") || s("glob")}`;
    case "Skill":
      return `调用技能 ${s("skill") || s("name")}`;
    case "Agent":
      return `子任务 ${s("description") || ""}`.trim();   // 中文描述优先，不落英文标识
    case "TaskCreate":
      return "任务清单 · 新建";
    case "TaskUpdate":
      return "任务清单 · 更新";
    case "TaskList":
      return "任务清单 · 列出";
    case "TaskGet":
      return "任务清单 · 查看";
    default: {
      const prose = PROSE_TOOL_ZH[call.tool_name];
      if (prose) {
        const matrix = s("matrix") || s("matrix_type") || s("to_matrix");
        const zh = MATRIX_ZH[matrix];
        return zh ? `${prose} · ${zh}` : prose;
      }
      // 产品面恒为简体中文：未登记的工具名不直出英文标识（技术名只进 console/日志）。
      return "工具调用";
    }
  }
}

function truncate(s: string, n: number): string {
  if (!s) return "";
  return s.length > n ? `${s.slice(0, n)}…` : s;
}
