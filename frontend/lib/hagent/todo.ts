// hagent 任务清单（Task V2）的前端投影。
//
// 后端四件套 TaskCreate / TaskGet / TaskUpdate / TaskList 任一完成，路由层就拉一次
// 全量并推 SSE `todo.updated`；deepagents 内置的 write_todos 已在 core.py 禁用，
// 所以这里只有一套任务系统。字段权威定义见 hagent/src/hagent/task_tools/models.py
// 的 task_to_todo()。

export type TodoStatus = "pending" | "in_progress" | "completed" | "cancelled";

export interface TodoItem {
  /** 渲染 key。后端给 id 就用 id;legacy 兜底形状没有 id,退回按位合成(见 normalizeTodos)。 */
  key: string;
  /** 任务名(后端 subject) */
  content: string;
  status: TodoStatus;
  /** 被别的任务卡着——派生成原始值,行组件才能走浅比较 */
  blocked: boolean;
  /** 进行时说法(「正在编制技术偏差表」)。后端仅在非空时落键。 */
  activeForm?: string;
}

function isStatus(v: unknown): v is TodoStatus {
  // 不用 (["pending",...] as const).includes(v):形参是元素字面量联合,v: unknown 编译不过。
  return v === "pending" || v === "in_progress" || v === "completed";
}

function str(v: unknown): string {
  return typeof v === "string" ? v : "";
}

/**
 * 把后端 todos 归一化成 TodoItem[]。**只在 store 的 todo.updated 分支里调一次**——
 * 放 render 里会在流式期每帧重跑,放 flush 外层会每个 rAF 帧换一次引用。
 *
 * 吃两种形状:SSE 推的是 `{todos: [...]}`,REST `GET /sessions/{sid}/todos` 是裸数组。
 * 坏项丢弃而非抛错:契约漂移时看板少一行,好过整卡炸掉。
 */
export function normalizeTodos(input: unknown): TodoItem[] {
  const raw = Array.isArray(input)
    ? input
    : Array.isArray((input as { todos?: unknown })?.todos)
      ? ((input as { todos: unknown[] }).todos)
      : [];

  const out: TodoItem[] = [];
  for (const [i, entry] of raw.entries()) {
    if (!entry || typeof entry !== "object") continue;
    const t = entry as Record<string, unknown>;
    const content = str(t.content);
    const status = t.status;
    if (!content || !isStatus(status)) continue;

    // key 必须跨快照稳定:一变行就重挂载,完成时的删除线 transition 就补不了间。
    // legacy 兜底形状(SDK TodoWrite,messages.py:469)没有 id,按「位次+内容」合成。
    const id = str(t.id);
    const activeForm = str(t.activeForm);
    out.push({
      key: id || `${i}:${content}`,
      content,
      status,
      blocked: Array.isArray(t.blockedBy) && t.blockedBy.length > 0,
      ...(activeForm ? { activeForm } : {}),
    });
  }
  return out;
}

/** 行文案:进行中优先用进行时说法,缺省回落任务名。 */
export function todoLabel(t: TodoItem): string {
  return t.status === "in_progress" && t.activeForm ? t.activeForm : t.content;
}

/** 读屏用的状态词。视觉上状态只有色点与删除线,不给这个读屏用户就拿到零信息。 */
export const TODO_STATUS_TEXT: Record<TodoStatus, string> = {
  pending: "待办",
  in_progress: "进行中",
  completed: "已完成",
  cancelled: "已停止",
};
