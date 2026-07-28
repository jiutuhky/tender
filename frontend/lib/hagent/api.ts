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

const BASE = "/api/hagent";

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
  revision: string;
  /** 租约活跃时是否已同步注入 VM(无租约为 false,由下一轮追平) */
  sandbox_synced: boolean;
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
  if (!r.ok) throw new Error(`createProject failed: ${r.status}`);
  return r.json();
}

export async function listProjects(): Promise<ProjectInfo[]> {
  const r = await fetch(`${BASE}/projects`);
  if (!r.ok) throw new Error(`listProjects failed: ${r.status}`);
  return r.json();
}

export async function getProject(pid: string): Promise<ProjectInfo> {
  const r = await fetch(`${BASE}/projects/${pid}`);
  if (!r.ok) throw new Error(`getProject failed: ${r.status}`);
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
  if (!r.ok) throw new Error(`patchProject failed: ${r.status}`);
  return r.json();
}

/** 创建会话。会话只是项目内的对话容器,后端要求必须归属项目(spec §4.4)。 */
export async function createSession(opts: { projectId: string }): Promise<SessionInfo> {
  const r = await fetch(`${BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: opts.projectId }),
  });
  if (!r.ok) throw new Error(`createSession failed: ${r.status}`);
  return r.json();
}

export async function listSamples(): Promise<SampleInfo[]> {
  const r = await fetch(`${BASE}/samples`);
  if (!r.ok) throw new Error(`listSamples failed: ${r.status}`);
  return r.json();
}

/** 把 data/ 下的样本（服务端读盘）上传到项目 workspace 的 sources/。 */
export async function uploadProjectSample(pid: string, filename: string): Promise<ProjectUploadResult> {
  const r = await fetch(`${BASE}/projects/${pid}/upload-sample`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  });
  if (!r.ok) throw new Error(`uploadProjectSample failed: ${r.status}`);
  return r.json();
}

/** 用户上传本地 .md 到项目 workspace(落 sources/ 并形成提交)。 */
export async function uploadProjectFile(pid: string, file: File): Promise<ProjectUploadResult> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("path", `sources/${file.name}`);
  const r = await fetch(`${BASE}/projects/${pid}/files`, { method: "POST", body: fd });
  if (!r.ok) throw new Error(`uploadProjectFile failed: ${r.status}`);
  return r.json();
}

/* ---------- 结构化资产(应答矩阵)REST 端点,契约见 hagent assets/router.py ---------- */

/** 四矩阵状态汇总(恢复/刷新路径的入口查询)。 */
export async function getMatrixStatus(pid: string): Promise<ProjectMatrixStatus> {
  const r = await fetch(`${BASE}/projects/${pid}/matrices`);
  if (!r.ok) throw new Error(`getMatrixStatus failed: ${r.status}`);
  return r.json();
}

/** 矩阵总览:envelope(meta)+ 分组统计,不含条目本体。 */
export async function getMatrixOverview(pid: string, type: MatrixType): Promise<MatrixOverview> {
  const r = await fetch(`${BASE}/projects/${pid}/matrices/${type}`);
  if (!r.ok) throw new Error(`getMatrixOverview failed: ${r.status}`);
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
  if (!r.ok) throw new Error(`queryMatrixItems failed: ${r.status}`);
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
): Promise<DocumentsPage> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) qs.set(k, String(v));
  }
  const search = qs.size ? `?${qs}` : "";
  const r = await fetch(`${BASE}/projects/${pid}/documents${search}`);
  if (!r.ok) throw new Error(`listDocuments failed: ${r.status}`);
  return r.json();
}

/** 拉取项目全部注册文档(按服务端上限逐页翻完,护栏同 fetchAllMatrixItems)。 */
export async function fetchAllDocuments(pid: string): Promise<DocumentRecord[]> {
  const records: DocumentRecord[] = [];
  let offset: number | null = 0;
  for (let page = 0; offset !== null && page < PAGE_CAP; page++) {
    const batch: DocumentsPage = await listDocuments(pid, {
      limit: PAGE_LIMIT,
      offset,
    });
    records.push(...batch.documents);
    offset = batch.has_more ? batch.next_offset : null;
  }
  return records;
}

/** 读 project workspace 文件文本(招标文件 OCR Markdown 原文)。 */
export async function getWorkspaceFileText(pid: string, path: string): Promise<string> {
  const encoded = path.split("/").map(encodeURIComponent).join("/");
  const r = await fetch(`${BASE}/projects/${pid}/workspace/files/${encoded}`);
  if (!r.ok) throw new Error(`getWorkspaceFileText failed: ${r.status}`);
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

async function matrixWriteError(r: Response, action: string): Promise<Error> {
  let detail: { code?: string; message?: string; current_version?: number } = {};
  try {
    detail = ((await r.json()) as { detail?: typeof detail }).detail ?? {};
  } catch {
    /* 非 JSON 错误体,用状态码兜底 */
  }
  const message = detail.message || `${action} failed: ${r.status}`;
  if (r.status === 409) return new MatrixWriteConflictError(message, detail.current_version ?? null);
  return new Error(message);
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

export async function getTodos(sid: string): Promise<unknown[]> {
  const r = await fetch(`${BASE}/sessions/${sid}/todos`);
  if (!r.ok) throw new Error(`getTodos failed: ${r.status}`);
  return r.json();
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
    throw new Error(`streamMessage failed: ${r.status}${body ? ` ${body.slice(0, 200)}` : ""}`);
  }
  if (!r.body) throw new Error("no response body");
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      yield parseSSEBlock(block);
    }
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
