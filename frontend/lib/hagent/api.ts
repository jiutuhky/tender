// hagent 后端客户端（经 Next.js 同源代理 /api/hagent/*）。
// 移植自 hagent/web/src/lib/hagent_api.ts；改动：BASE 改同源相对路径，
// 鉴权与上游 base 由服务端 route handler 负责（见 frontend/lib/server/upstream.ts），
// 浏览器侧不再持有 API key。

import type {
  MatrixItemRow,
  MatrixItemsPage,
  MatrixOverview,
  MatrixType,
  ProjectMatrixStatus,
  ResponseStatus,
} from "@/lib/hagent/matrix";
import { normalizeTodos, type TodoItem } from "@/lib/hagent/todo";

const BASE = "/api/hagent";

/** 操作英文标识 → 面向用户的中文陈述（产品面文案恒为简体中文、正式采购语域）。 */
const OP_LABEL: Record<string, string> = {
  createProject: "创建项目",
  listProjects: "载入项目列表",
  getProject: "读取项目",
  patchProject: "更新项目",
  createSession: "创建会话",
  listSamples: "载入样本列表",
  uploadProjectSample: "上传样本招标文件",
  uploadProjectFile: "上传招标文件",
  getMatrixStatus: "读取矩阵状态",
  getMatrixOverview: "读取矩阵总览",
  queryMatrixItems: "查询矩阵条目",
  listDocuments: "载入文档列表",
  getWorkspaceFileText: "读取工作区文件",
  getTodos: "读取待办",
  streamMessage: "发送指令",
};

/**
 * 构造面向用户的中文错误：message 恒为中文陈述句，供执行流直接呈现；
 * 原始技术细节（HTTP 状态、响应体片段）挂在 cause 上，只进 console 与日志。
 */
function apiError(op: string, status: number, detail?: string): Error {
  const label = OP_LABEL[op] ?? "请求后端";
  let errorCode: string | undefined;
  try {
    const parsed = JSON.parse(detail ?? "null") as { detail?: { code?: string } } | null;
    errorCode = parsed?.detail?.code;
  } catch {
    // 兼容代理错误页或旧版后端返回的非 JSON 错误。
  }
  const message =
    op === "streamMessage" && status === 503 &&
    (errorCode === "sandbox_capacity_unavailable" || detail?.includes("sandbox pool exhausted"))
      ? "任务执行资源暂时不足，请约 30 秒后在当前会话重试，无需重新上传文件。"
      : errorCode === "upstream_unavailable"
        ? "执行服务暂时无法连接，请稍后在当前会话重试。"
      : `未能${label}，请稍后重试。`;
  const err = new Error(message, {
    cause: `${op} failed: ${status}${detail ? ` ${detail}` : ""}`,
  });
  return err;
}

export interface SessionInfo {
  session_id: string;
  status: string;
  project_id: string;
}

export interface SampleInfo {
  filename: string;
  size: number;
}

export interface ProjectUploadResult {
  path: string;
  size: number;
  /** 上传形成的 workspace commit sha */
  revision: string | null;
  /** 租约活跃时是否已同步注入 VM(无租约为 false,由下一轮追平) */
  sandbox_synced: boolean;
  /** PDF 上传后异步解析，原件不位于 workspace files。 */
  parsing?: { pages: number };
}

/** 项目下 session 摘要(嵌在 GET /projects/{pid} 的 sessions 数组里)。 */
export interface ProjectSessionInfo {
  id: string;
  status: string;
  created_at: number;
  last_active: number;
  project_id: string | null;
}

export interface ProjectInfo {
  id: string;
  name: string;
  status: string;
  /** epoch 秒(上游 time.time()) */
  created_at: number;
  updated_at: number;
  metadata: Record<string, unknown> | null;
  latest_session: { id: string; status: string } | null;
  /** 仅 GET /projects/{pid} 详情返回,最新在前 */
  sessions?: ProjectSessionInfo[];
}

export async function createProject(
  name: string,
  metadata?: Record<string, unknown>,
): Promise<ProjectInfo> {
  const r = await fetch(`${BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(metadata ? { name, metadata } : { name }),
  });
  if (!r.ok) throw apiError("createProject", r.status);
  return r.json();
}

export async function listProjects(): Promise<ProjectInfo[]> {
  const r = await fetch(`${BASE}/projects`);
  if (!r.ok) throw apiError("listProjects", r.status);
  return r.json();
}

export async function getProject(pid: string): Promise<ProjectInfo> {
  const r = await fetch(`${BASE}/projects/${pid}`);
  if (!r.ok) throw apiError("getProject", r.status);
  return r.json();
}

export async function patchProject(
  pid: string,
  patch: { name?: string; status?: string; metadata?: Record<string, unknown> },
): Promise<ProjectInfo> {
  const r = await fetch(`${BASE}/projects/${pid}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw apiError("patchProject", r.status);
  return r.json();
}

/** 创建会话。会话只是项目内的对话容器,后端要求必须归属项目(spec §4.4)。 */
export async function createSession(opts: { projectId: string }): Promise<SessionInfo> {
  const r = await fetch(`${BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: opts.projectId }),
  });
  if (!r.ok) throw apiError("createSession", r.status);
  return r.json();
}

export async function listSamples(): Promise<SampleInfo[]> {
  const r = await fetch(`${BASE}/samples`);
  if (!r.ok) throw apiError("listSamples", r.status);
  return r.json();
}

/** 把 data/ 下的样本（服务端读盘）上传到项目 workspace 的 sources/。 */
export async function uploadProjectSample(pid: string, filename: string): Promise<ProjectUploadResult> {
  const r = await fetch(`${BASE}/projects/${pid}/upload-sample`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  });
  if (!r.ok) throw apiError("uploadProjectSample", r.status);
  return r.json();
}

/** 用户上传本地 PDF 或 Markdown 到项目 workspace(落 sources/ 并形成提交)。 */
export async function uploadProjectFile(pid: string, file: File, relativePath = file.name, signal?: AbortSignal): Promise<ProjectUploadResult> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("path", `sources/${relativePath}`);
  const r = await fetch(`${BASE}/projects/${pid}/files`, { method: "POST", body: fd, signal });
  if (!r.ok) throw apiError("uploadProjectFile", r.status);
  return r.json();
}

export interface WorkspaceFile { path: string; size: number }

/** 全部素材清单独立于仅包含已注册原文的 documents。 */
export async function listWorkspaceFiles(pid: string, signal?: AbortSignal): Promise<WorkspaceFile[]> {
  const response = await fetch(`${BASE}/projects/${encodeURIComponent(pid)}/workspace/files`, { cache: "no-store", signal });
  if (!response.ok) throw new Error("文件列表载入失败，请重试。");
  return response.json();
}

export function workspaceFileUrl(pid: string, path: string): string {
  return `${BASE}/projects/${encodeURIComponent(pid)}/workspace/files/${path.split("/").map(encodeURIComponent).join("/")}`;
}

/* ---------- 结构化资产(应答矩阵)REST 端点,契约见 hagent assets/router.py ---------- */

/** 四矩阵状态汇总(恢复/刷新路径的入口查询)。 */
export async function getMatrixStatus(pid: string): Promise<ProjectMatrixStatus> {
  const r = await fetch(`${BASE}/projects/${pid}/matrices`);
  if (!r.ok) throw apiError("getMatrixStatus", r.status);
  return r.json();
}

/** 矩阵总览:envelope(meta)+ 分组统计,不含条目本体。 */
export async function getMatrixOverview(pid: string, type: MatrixType): Promise<MatrixOverview> {
  const r = await fetch(`${BASE}/projects/${pid}/matrices/${type}`);
  if (!r.ok) throw apiError("getMatrixOverview", r.status);
  return r.json();
}

/** 条目分页查询(过滤参数与 MCP prose_query_matrix_items 对齐;偏离表 = response_status 过滤的同源投影)。 */
export async function queryMatrixItems(
  pid: string,
  type: MatrixType,
  params: { limit?: number; offset?: number; section?: string; response_status?: ResponseStatus } = {},
): Promise<MatrixItemsPage> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) qs.set(k, String(v));
  }
  const search = qs.size ? `?${qs}` : "";
  const r = await fetch(`${BASE}/projects/${pid}/matrices/${type}/items${search}`);
  if (!r.ok) throw apiError("queryMatrixItems", r.status);
  return r.json();
}

// 服务端分页上限(assets/schemas.py QUERY_LIMIT_MAX);翻页护栏防御 total_count 异常时死循环
const PAGE_LIMIT = 100;
const PAGE_CAP = 100; // 100 页 × 100 条,远超单矩阵/单项目注册表实际规模

/** 拉取矩阵全部条目行(按服务端上限逐页翻完)。 */
export async function fetchAllMatrixItems(pid: string, type: MatrixType): Promise<MatrixItemRow[]> {
  const rows: MatrixItemRow[] = [];
  let offset: number | null = 0;
  for (let page = 0; offset !== null && page < PAGE_CAP; page++) {
    const batch: MatrixItemsPage = await queryMatrixItems(pid, type, {
      limit: PAGE_LIMIT,
      offset,
    });
    rows.push(...batch.items);
    offset = batch.has_more ? batch.next_offset : null;
  }
  return rows;
}

/* ---------- 文档注册表与原文(溯源预览取数),契约见 hagent assets/router.py 与 server/routers/project_files.py ---------- */

/** 文档注册表记录(document_id → workspace 路径映射)。 */
export interface DocumentRecord {
  has_preview?: boolean;
  origin_sha256?: string | null;
  preview_sha256?: string | null;
  id: string;
  path: string;
  sha256: string;
  doc_type: string | null;
  registered_at: string;
  /** 注册时的幂等标记,列表读恒为 false */
  created: boolean;
}

export interface DocumentsPage {
  documents: DocumentRecord[];
  total_count: number;
  limit: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
}

/** 文档注册表分页读(分页语义与条目查询同构)。 */
export async function listDocuments(
  pid: string,
  params: { limit?: number; offset?: number } = {},
  signal?: AbortSignal,
): Promise<DocumentsPage> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) qs.set(k, String(v));
  }
  const search = qs.size ? `?${qs}` : "";
  const r = await fetch(`${BASE}/projects/${pid}/documents${search}`, { signal });
  if (!r.ok) throw apiError("listDocuments", r.status);
  return r.json();
}

/** 拉取项目全部注册文档(按服务端上限逐页翻完,护栏同 fetchAllMatrixItems)。 */
export async function fetchAllDocuments(pid: string, signal?: AbortSignal): Promise<DocumentRecord[]> {
  const records: DocumentRecord[] = [];
  let offset: number | null = 0;
  for (let page = 0; offset !== null && page < PAGE_CAP; page++) {
    signal?.throwIfAborted();
    const batch: DocumentsPage = await listDocuments(pid, {
      limit: PAGE_LIMIT,
      offset,
    }, signal);
    records.push(...batch.documents);
    offset = batch.has_more ? batch.next_offset : null;
  }
  return records;
}

/** 读 project workspace 文件文本(招标文件 OCR Markdown 原文)。 */
export async function getWorkspaceFileText(pid: string, path: string): Promise<string> {
  const encoded = path.split("/").map(encodeURIComponent).join("/");
  const r = await fetch(`${BASE}/projects/${pid}/workspace/files/${encoded}`);
  if (!r.ok) throw apiError("getWorkspaceFileText", r.status);
  return r.text();
}

/** 人工写动作的乐观锁冲突(409):携带服务端当前 version,调用方据此重载再试。 */
export class MatrixWriteConflictError extends Error {
  readonly currentVersion: number | null;
  constructor(message: string, currentVersion: number | null) {
    super(message);
    this.name = "MatrixWriteConflictError";
    this.currentVersion = currentVersion;
  }
}

const MATRIX_ACTION_LABEL: Record<string, string> = {
  confirmMatrixItem: "确认条目",
  setMatrixItemResponseStatus: "更新应答状态",
};

async function matrixWriteError(r: Response, action: string): Promise<Error> {
  let detail: { code?: string; message?: string; current_version?: number } = {};
  try {
    detail = ((await r.json()) as { detail?: typeof detail }).detail ?? {};
  } catch {
    /* 非 JSON 错误体,用状态码兜底 */
  }
  // 上游 detail.message 已是中文；无则回落到中文陈述，技术细节挂 cause。
  const message = detail.message || `未能${MATRIX_ACTION_LABEL[action] ?? "写入矩阵"}，请稍后重试。`;
  if (r.status === 409) return new MatrixWriteConflictError(message, detail.current_version ?? null);
  return new Error(message, { cause: `${action} failed: ${r.status}` });
}

/** 用户确认条目(审计 actor=user);expected_version 不符时抛 MatrixWriteConflictError。 */
export async function confirmMatrixItem(
  pid: string,
  type: MatrixType,
  itemId: string,
  expectedVersion?: number,
): Promise<MatrixItemRow> {
  const r = await fetch(
    `${BASE}/projects/${pid}/matrices/${type}/items/${encodeURIComponent(itemId)}/confirm`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(expectedVersion === undefined ? {} : { expected_version: expectedVersion }),
    },
  );
  if (!r.ok) throw await matrixWriteError(r, "confirmMatrixItem");
  return r.json();
}

/** 用户标注应答状态(合规/正偏离/负偏离,审计 actor=user);并发守卫同 confirm。 */
export async function setMatrixItemResponseStatus(
  pid: string,
  type: MatrixType,
  itemId: string,
  opts: { status: ResponseStatus; note?: string; reason?: string; expectedVersion?: number },
): Promise<MatrixItemRow> {
  const r = await fetch(
    `${BASE}/projects/${pid}/matrices/${type}/items/${encodeURIComponent(itemId)}/response-status`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: opts.status,
        note: opts.note ?? null,
        reason: opts.reason ?? null,
        expected_version: opts.expectedVersion ?? null,
      }),
    },
  );
  if (!r.ok) throw await matrixWriteError(r, "setMatrixItemResponseStatus");
  return r.json();
}

/** 冷启动/恢复路径的全量待办。注意该端点返回**裸数组**,而 SSE todo.updated 是
 *  `{todos:[...]}`——两种形状的差异收在 normalizeTodos 里,调用方不必分辨。 */
export async function getTodos(sid: string): Promise<TodoItem[]> {
  const r = await fetch(`${BASE}/sessions/${sid}/todos`);
  if (!r.ok) throw apiError("getTodos", r.status);
  return normalizeTodos(await r.json());
}

export interface SSEEvent {
  id: string;
  event: string;
  data: unknown;
}

/** 向 session 发送一条消息，按 SSE 帧逐个 yield 事件。fetch + ReadableStream 读法原样保留。 */
export async function* streamMessage(sid: string, content: string): AsyncIterable<SSEEvent> {
  const r = await fetch(`${BASE}/sessions/${sid}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!r.ok) {
    // 非 2xx 是 JSON 错误体不是 SSE 流(如 404/503;M2 起对话轮锁 409),吞掉会静默变空流。
    const body = await r.text().catch(() => "");
    throw apiError("streamMessage", r.status, body || undefined);
  }
  if (!r.body) throw new Error("后端未返回响应内容，请稍后重试。", { cause: "no response body" });
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let completed = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) { completed = true; break; }
      buf += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const block = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const parsed = parseSSEBlock(block);
        // SSE 注释心跳不进入事件缓冲和 rAF 状态投影。
        if (parsed.event) yield parsed;
      }
    }
  } finally {
    if (!completed) await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

function parseSSEBlock(block: string): SSEEvent {
  const lines = block.split("\n");
  let id = "";
  let event = "";
  let dataStr = "";
  for (const line of lines) {
    if (line.startsWith("id: ")) id = line.slice(4);
    else if (line.startsWith("event: ")) event = line.slice(7);
    else if (line.startsWith("data: ")) dataStr += line.slice(6);
  }
  let data: unknown = dataStr;
  try {
    data = JSON.parse(dataStr);
  } catch {
    /* keep raw */
  }
  return { id, event, data };
}

/** 幂等停止当前 Run，保留会话与项目文件。 */
export async function cancelRun(sessionId: string, runId: string): Promise<void> {
  const response = await fetch(`/api/hagent/sessions/${encodeURIComponent(sessionId)}/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" });
  if (!response.ok) throw new Error("停止请求未送达，请检查连接后再次点击停止。");
}
