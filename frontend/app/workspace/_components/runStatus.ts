import type { ChatMsg } from "@/lib/hagent/timeline";
import { MATRIX_TYPES } from "@/lib/hagent/matrix";
import type { MatrixSlots, RunPhase } from "@/lib/store/workspace";
import { toolLabel } from "./toolLabel";

// 运行状态的文案与语义派生。纯函数，无 React —— 三个消费方（消息浮窗标题栏、
// 胶囊、底部坞活动条）读的是同一套状态，文案必须一处定义。

export const PHASE_STATUS: Record<RunPhase, string> = {
  idle: "待命中",
  creating: "创建项目与会话",
  uploading: "上传招标文件",
  running: "智能体解析中",
  loading_results: "载入应答矩阵",
  done: "解析完成",
  error: "出错",
};

export function isRunning(phase: RunPhase): boolean {
  return (
    phase === "running" || phase === "creating" || phase === "uploading" || phase === "loading_results"
  );
}

/** 状态点语义（品牌：蓝只授予「正在进行」，成功用绿，待命用灰）。 */
export function runDotState(phase: RunPhase): "idle" | "running" | "done" | "error" {
  if (isRunning(phase)) return "running";
  if (phase === "done") return "done";
  if (phase === "error") return "error";
  return "idle";
}

export function runStatusText(phase: RunPhase, todoCount: number, readyCount: number): string {
  if (phase === "done" && readyCount) return `已完成 · ${readyCount} 张矩阵`;
  if (phase === "running" && todoCount) return `${PHASE_STATUS[phase]} · ${todoCount} 项任务`;
  return PHASE_STATUS[phase];
}

export function readyMatrixCount(matrices: MatrixSlots): number {
  return MATRIX_TYPES.filter((t) => matrices[t].status === "ready").length;
}

// 回溯上限：时间线在长会话里可达数千条，而「当前在做什么」只关心末尾一小段。
// 封顶后本函数是 O(1)，可以安全地当 zustand selector 每帧跑。
const SCAN_LIMIT = 400;

/**
 * 底部坞活动条的一行中文，如「正在提交矩阵条目 · 技术应答 · 4 次调用」。
 * 语域随品牌：状态先行，一律以「正在」起句。
 *
 * 刻意返回 string 而非对象：ActivityBar 用它当 selector，内容不变即 Object.is
 * 相等，zustand 跳过重渲——所以流式期大多数帧底部坞是静止的。
 */
export function activityLine(timeline: ChatMsg[], phase: RunPhase): string {
  if (!isRunning(phase)) return PHASE_STATUS[phase];

  let head = "";
  let calls = 0;
  const stop = Math.max(0, timeline.length - SCAN_LIMIT);
  for (let i = timeline.length - 1; i >= stop; i -= 1) {
    const m = timeline[i];
    if (!m || m.role === "user") break; // 回溯到本轮起点为止
    if (m.role === "tool") {
      calls += 1;
      if (!head) head = `正在${toolLabel(m.call)}`;
    } else if (m.role === "subagent") {
      calls += 1;
      if (!head) head = `正在执行子任务 ${m.run.description || m.run.subagentType}`.trim();
    }
  }

  if (!head) return PHASE_STATUS[phase];
  return calls > 1 ? `${head} · ${calls} 次调用` : head;
}
