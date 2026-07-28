const BASE = process.env.NEXT_PUBLIC_HAGENT_API_BASE || "http://localhost:8000";
const KEY = process.env.NEXT_PUBLIC_HAGENT_API_KEY || "";

function authHeaders(): HeadersInit {
  return KEY ? { Authorization: `Bearer ${KEY}` } : {};
}

export interface SessionInfo {
  id: string;
  workspace_dir: string;
  status: string;
  created_at: number;
  last_active: number;
}

export interface FileNode {
  path: string;
  type: "file" | "dir";
  size: number | null;
}

export async function createSession(): Promise<{ session_id: string; workspace_dir: string; status: string }> {
  const r = await fetch(`${BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({}),
  });
  if (!r.ok) throw new Error(`createSession failed: ${r.status}`);
  return r.json();
}

export async function listFiles(sid: string, path: string = ""): Promise<FileNode[]> {
  const u = new URL(`${BASE}/sessions/${sid}/files`);
  if (path) u.searchParams.set("path", path);
  const r = await fetch(u.toString(), { headers: authHeaders() });
  if (!r.ok) throw new Error(`listFiles failed: ${r.status}`);
  return r.json();
}

export async function downloadFile(sid: string, filePath: string): Promise<Blob> {
  // 用 Blob 而不是 text，避免二进制（如 PNG）被 utf-8 decode 损坏。
  // spec §11 要求 plot.png 可下载，必须走 binary-safe 路径。
  const r = await fetch(`${BASE}/sessions/${sid}/files/${encodeURIComponent(filePath)}`, {
    headers: authHeaders(),
  });
  if (!r.ok) throw new Error(`downloadFile failed: ${r.status}`);
  return r.blob();
}

export async function uploadFile(sid: string, file: File, targetPath?: string): Promise<{ path: string; size: number }> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("path", targetPath || file.name);
  const r = await fetch(`${BASE}/sessions/${sid}/files`, {
    method: "POST",
    headers: authHeaders(),
    body: fd,
  });
  if (!r.ok) throw new Error(`uploadFile failed: ${r.status}`);
  return r.json();
}

export async function getTodos(sid: string): Promise<unknown[]> {
  const r = await fetch(`${BASE}/sessions/${sid}/todos`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`getTodos failed: ${r.status}`);
  return r.json();
}

export interface SSEEvent {
  id: string;
  event: string;
  data: unknown;
}

export async function* streamMessage(sid: string, content: string): AsyncIterable<SSEEvent> {
  const r = await fetch(`${BASE}/sessions/${sid}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ content }),
  });
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
  try { data = JSON.parse(dataStr); } catch { /* keep raw */ }
  return { id, event, data };
}

export async function deleteSession(sid: string): Promise<void> {
  const r = await fetch(`${BASE}/sessions/${sid}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!r.ok) throw new Error(`deleteSession failed: ${r.status}`);
}

export async function postInterrupt(
  sid: string,
  interrupt_id: string,
  decision: "approve" | "reject" | "edit" | "respond",
  reason?: string,
): Promise<{ ok: boolean }> {
  const r = await fetch(`${BASE}/sessions/${sid}/interrupt`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ interrupt_id, decision, reason }),
  });
  if (!r.ok) throw new Error(`postInterrupt failed: ${r.status}`);
  return r.json();
}
