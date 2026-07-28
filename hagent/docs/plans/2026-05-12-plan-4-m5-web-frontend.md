# Plan 4 — M5 最小 Web 前端（Next.js + 自定义 SSE 消费）

> **存档说明**：本 plan 产出自已退役的 superpowers 工作流，仅作历史参考；新工作一律走仓根 tickets.md（Matt 契约）。

**Goal**: 在 `web/` 子目录搭一个 Next.js 15 单页应用，通过 Plan 3 的 Agent Server HTTP/SSE 接口，让用户能在浏览器里：(1) 发消息并看到流式回复 + tool 调用 + todo 更新；(2) 看到沙箱 workspace 文件树并下载；(3) 拖文件上传到沙箱；(4) HITL 弹窗用浏览器 `confirm()` 兜底。

**Architecture**:
- 单一 App Router 路由 `/`，三列布局（chat | todo | files），用 Tailwind 排版
- API 客户端是 vanilla `fetch`——**不引入 `@langchain/langgraph-sdk`**，因为我们的 server 是自定义 FastAPI（spec §5 自定义事件名），不是 LangGraph 部署；spec D2 提到 langgraph-sdk 时假设了 LangGraph 标准部署，事实修正
- SSE 消费用 `fetch` + `ReadableStream` 解码（`EventSource` 不支持 POST 不可用）
- 状态：React useState + useReducer，不引入 Redux/Zustand
- 鉴权：把 `HAGENT_API_KEY` 放到 `.env.local` 里，server 端 fetch 用 Bearer 头；这是 MVP 单租户单用户，浏览器持有 key 是可接受的

**Tech Stack**: Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS 4, pnpm（或 npm）。**前端不引入 langgraph-sdk**——理由见 Architecture。

**Spec reference**: §3 / §4 M5 / §5（HTTP API 表面，由前端消费）。

**Depends on**: Plan 3 完成；Agent Server 可在本地 8000 端口跑起来；`/healthz` 返回 200。

**Spec deviation note**: 原 spec §3 / D2 说 "Next.js 15 + @langchain/langgraph-sdk"，本 plan 改用 vanilla fetch + ReadableStream。理由：自定义 server 的 SSE 事件名是 spec §5 表里的 9 种（`message.delta` 等），不是 LangGraph SDK 期望的 LangGraph 标准事件，sdk 反而是阻力。本变更已在执行前在 spec doc 上记录。

---

### Task 1: spec 修补（更新 D2 决策）

**Files:**
- Modify: `docs/specs/2026-05-12-hagent-backend-design.md`

- [ ] **Step 1: 找到 spec D2 那行并改写**

```bash
grep -n "langgraph-sdk" docs/specs/2026-05-12-hagent-backend-design.md
```

把 `D2` 决策行修改为：

```
| D2 | 前端：单页 Next.js + vanilla fetch/SSE（**不**引入 langgraph-sdk，因 server 用自定义 SSE 事件名），无 Monaco/xterm，HITL 用浏览器 confirm() | §3 |
```

把 §3 架构图里的 `Next.js 15 + @langchain/langgraph-sdk` 改为：
```
Next.js 15 + 自定义 fetch/SSE 客户端
```

把 §4 M5 模块的"单页 Next.js + `@langchain/langgraph-sdk`"改为：
```
单页 Next.js + 自定义 fetch/SSE 客户端
```

把 §12 Dependencies 里的 `Next.js 15 / @langchain/langgraph-sdk（前端）` 改为：
```
Next.js 15（前端）
```

- [ ] **Step 2: 提交**

```bash
git add docs/specs/2026-05-12-hagent-backend-design.md
git commit -m "docs(spec): drop langgraph-sdk from frontend stack

Server uses custom SSE events (spec §5 named events), not LangGraph
standard events; sdk would be an impediment rather than helper.
Plan 4 uses vanilla fetch + ReadableStream."
```

---

### Task 2: bootstrap Next.js + Tailwind

**Files:**
- Create: `web/`（整个子目录通过 create-next-app 生成）
- Modify: `.gitignore`（确认 `node_modules` 已忽略，否则补）
- Modify: `web/package.json`

- [ ] **Step 1: 确认 node 可用**

```bash
node --version  # 期望 v20+
npm --version
```

如果没装 node，向用户报告 BLOCKED，让用户先装 node 20+ 再继续。

- [ ] **Step 2: bootstrap**

```bash
cd /home/han/workplace/Hagent && npx --yes create-next-app@latest web \
  --typescript --tailwind --app --src-dir --import-alias '@/*' --no-eslint --turbopack --use-npm
```

create-next-app 交互式，如果还问问题（如 ESLint / Tailwind），全选默认/yes。

- [ ] **Step 3: 验证开发 server 能起**

```bash
cd web && npm run dev
```
开几秒确认端口 3000 上跑了 Next.js，然后 Ctrl+C 退出。

- [ ] **Step 4: 改 .gitignore**

确认根 `.gitignore` 已经有 `node_modules/`；如果没有，追加：
```
node_modules/
.next/
```

- [ ] **Step 5: 提交**

```bash
git add web/ .gitignore
git commit -m "feat(web): bootstrap Next.js 15 app with Tailwind in web/"
```

注意：commit 体积会比较大（lock file + boilerplate）。这是 boilerplate 不是手写代码，记成一个 commit 即可。

---

### Task 3: API 客户端 lib

**Files:**
- Create: `web/src/lib/hagent_api.ts`

- [ ] **Step 1: 写客户端**

```typescript
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
```

- [ ] **Step 2: 提交**

```bash
git add web/src/lib/hagent_api.ts
git commit -m "feat(web): add Hagent API client with SSE consumer"
```

---

### Task 4: 主页面三列布局

**Files:**
- Modify: `web/src/app/page.tsx`
- Modify: `web/src/app/layout.tsx`（清理 boilerplate）

- [ ] **Step 1: 清理 layout.tsx**

把 `web/src/app/layout.tsx` 改为：

```typescript
import "./globals.css";

export const metadata = {
  title: "Hagent",
  description: "Hagent — Web-based agent harness",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="h-screen bg-gray-50 text-gray-900">
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 2: 重写 page.tsx**

```typescript
"use client";

import { useEffect, useRef, useState } from "react";
import {
  SSEEvent,
  createSession,
  downloadFile,
  getTodos,
  listFiles,
  postInterrupt,
  streamMessage,
  uploadFile,
} from "@/lib/hagent_api";

type ChatMsg = { id: string; role: "user" | "assistant" | "tool"; content: string };
type Todo = { content: string; status: string };
type FileEntry = { path: string; type: "file" | "dir"; size: number | null };

export default function Home() {
  const [sid, setSid] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [todos, setTodos] = useState<Todo[]>([]);
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 启动时自动创建 session
  useEffect(() => {
    (async () => {
      const r = await createSession();
      setSid(r.session_id);
    })().catch((e) => console.error("createSession", e));
  }, []);

  // 周期性刷新 files + todos
  useEffect(() => {
    if (!sid) return;
    const tick = async () => {
      try {
        setFiles((await listFiles(sid)) as FileEntry[]);
        setTodos((await getTodos(sid)) as Todo[]);
      } catch (e) {
        console.error(e);
      }
    };
    tick();
    const id = setInterval(tick, 2500);
    return () => clearInterval(id);
  }, [sid]);

  async function send() {
    if (!sid || !input.trim()) return;
    const userMsgId = `u-${Date.now()}`;
    setMsgs((m) => [...m, { id: userMsgId, role: "user", content: input }]);
    const userInput = input;
    setInput("");
    setStreaming(true);
    let assistantBuf = "";
    const assistantId = `a-${Date.now()}`;
    setMsgs((m) => [...m, { id: assistantId, role: "assistant", content: "" }]);
    try {
      for await (const ev of streamMessage(sid, userInput)) {
        handleEvent(ev, (chunk) => {
          assistantBuf += chunk;
          setMsgs((m) => m.map((x) => (x.id === assistantId ? { ...x, content: assistantBuf } : x)));
        });
      }
    } catch (e) {
      console.error("stream error", e);
    } finally {
      setStreaming(false);
    }
  }

  function handleEvent(ev: SSEEvent, appendDelta: (s: string) => void) {
    if (ev.event === "message.delta") {
      const d = ev.data as { content_chunk?: string };
      if (d.content_chunk) appendDelta(d.content_chunk);
    } else if (ev.event === "tool_call.started") {
      const d = ev.data as { tool_name?: string; args_chunk?: string };
      setMsgs((m) => [
        ...m,
        { id: `t-${Date.now()}-${Math.random()}`, role: "tool", content: `→ ${d.tool_name}(${d.args_chunk ?? ""})` },
      ]);
    } else if (ev.event === "tool_call.completed") {
      const d = ev.data as { tool_name?: string; result_summary?: string };
      setMsgs((m) => [
        ...m,
        { id: `t-${Date.now()}-${Math.random()}`, role: "tool", content: `✓ ${d.tool_name}: ${d.result_summary ?? ""}` },
      ]);
    } else if (ev.event === "interrupt.requested") {
      const d = ev.data as { interrupt_id?: string; payload?: unknown };
      const ok = window.confirm(`HITL: ${JSON.stringify(ev.data)}\n\n点确认=approve / 取消=reject`);
      if (sid && d.interrupt_id) {
        // 把决策回传给 server；不 await，不阻塞 SSE 流处理
        postInterrupt(sid, d.interrupt_id, ok ? "approve" : "reject").catch((e) =>
          console.error("postInterrupt", e),
        );
      }
    } else if (ev.event === "error") {
      const d = ev.data as { message?: string };
      setMsgs((m) => [...m, { id: `e-${Date.now()}`, role: "tool", content: `[error] ${d.message ?? ""}` }]);
    }
  }

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    if (!sid) return;
    const f = e.target.files?.[0];
    if (!f) return;
    await uploadFile(sid, f);
    e.target.value = "";
  }

  async function onDownload(path: string) {
    if (!sid) return;
    // downloadFile 现在返回 Blob（二进制安全），直接走浏览器下载流程
    const blob = await downloadFile(sid, path);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = path.split("/").pop() || path;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="grid grid-cols-12 gap-4 p-4 h-full">
      {/* Chat */}
      <section className="col-span-7 flex flex-col rounded border bg-white">
        <header className="px-4 py-2 border-b text-sm font-medium text-gray-700">
          Chat {sid && <span className="ml-2 text-gray-400 font-mono text-xs">{sid}</span>}
        </header>
        <div className="flex-1 overflow-y-auto px-4 py-2 space-y-2 text-sm">
          {msgs.map((m) => (
            <div key={m.id} className={
              m.role === "user" ? "text-right" :
              m.role === "tool" ? "text-xs text-gray-500 font-mono" :
              ""
            }>
              <span className={
                m.role === "user" ? "inline-block bg-blue-100 px-3 py-1 rounded" :
                m.role === "tool" ? "" :
                "inline-block bg-gray-100 px-3 py-1 rounded whitespace-pre-wrap"
              }>{m.content}</span>
            </div>
          ))}
        </div>
        <footer className="border-t p-2 flex gap-2">
          <input
            type="text"
            className="flex-1 border rounded px-3 py-1 text-sm"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            placeholder={streaming ? "agent is thinking…" : "输入消息，回车发送"}
            disabled={streaming || !sid}
          />
          <button
            className="px-3 py-1 bg-blue-600 text-white rounded text-sm disabled:opacity-50"
            onClick={send}
            disabled={streaming || !sid || !input.trim()}
          >
            发送
          </button>
        </footer>
      </section>

      {/* Todos */}
      <section className="col-span-2 flex flex-col rounded border bg-white">
        <header className="px-3 py-2 border-b text-sm font-medium text-gray-700">Todos</header>
        <ul className="flex-1 overflow-y-auto px-3 py-2 text-xs space-y-1">
          {todos.length === 0 ? (
            <li className="text-gray-400">no todos</li>
          ) : (
            todos.map((t, i) => (
              <li key={i} className="flex gap-2">
                <span>{t.status === "completed" ? "✓" : "•"}</span>
                <span>{t.content}</span>
              </li>
            ))
          )}
        </ul>
      </section>

      {/* Files */}
      <section className="col-span-3 flex flex-col rounded border bg-white">
        <header className="px-3 py-2 border-b text-sm font-medium text-gray-700 flex justify-between items-center">
          <span>Workspace</span>
          <label className="text-xs text-blue-600 cursor-pointer">
            upload
            <input ref={fileInputRef} type="file" className="hidden" onChange={onUpload} />
          </label>
        </header>
        <ul className="flex-1 overflow-y-auto px-3 py-2 text-xs space-y-1">
          {files.length === 0 ? (
            <li className="text-gray-400">empty</li>
          ) : (
            files.map((f) => (
              <li key={f.path} className="flex justify-between">
                <span className={f.type === "dir" ? "font-medium" : ""}>
                  {f.type === "dir" ? "📁" : "📄"} {f.path}
                </span>
                {f.type === "file" && (
                  <button
                    className="text-blue-600 hover:underline"
                    onClick={() => onDownload(f.path)}
                  >
                    ↓
                  </button>
                )}
              </li>
            ))
          )}
        </ul>
      </section>
    </main>
  );
}
```

- [ ] **Step 3: 起 dev server 验证**

```bash
cd /home/han/workplace/Hagent/web && npm run dev
```

打开 http://localhost:3000；如果 Agent Server 没起，页面会显示创建 session 失败（开发者工具控制台报错）——这是预期。

- [ ] **Step 4: 提交**

```bash
cd /home/han/workplace/Hagent && git add web/src/app/page.tsx web/src/app/layout.tsx
git commit -m "feat(web): add three-column layout (chat / todos / files) with SSE streaming"
```

---

### Task 5: 端到端浏览器 dogfood（手动）

- [ ] **Step 1: 起 server**

shell A:
```bash
source .venv/bin/activate && uvicorn hagent.server.app:create_app --factory --port 8000
```

- [ ] **Step 2: 起 web**

shell B:
```bash
cd web && npm run dev
```

- [ ] **Step 3: 浏览器开 http://localhost:3000**

Expected:
- 页面三列布局正常
- 顶部 Chat header 显示 session_id
- Workspace 列显示 "empty"
- Todos 列显示 "no todos"

- [ ] **Step 4: 跑一个真实 demo（需 ANTHROPIC_API_KEY）**

在 server 的 shell A 设：
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```
重启 server。

在 chat 输入框输入：
```
在 workspace 创建一个 hello.py，内容是 print("hello hagent")，然后用 execute 跑它
```
回车发送。

Expected:
- chat 区流式出现 assistant 文本
- chat 区出现 `→ write_todos(...)` 等 tool 调用消息
- chat 区出现 `→ write_file(...)` 然后 `✓ write_file: ...`
- chat 区出现 `→ execute(...)` 然后 `✓ execute: ...` 包含 "hello hagent"
- Workspace 列 ~2.5 秒后出现 `hello.py`
- Todos 列出现已写入的任务（可能空，因 deepagents 并非每次都用 write_todos）

- [ ] **Step 5: 测上传**

点 Workspace header 的 "upload"，选一个本地小文件（如 sample.csv）。Expected: 几秒后 Workspace 列显示该文件。

- [ ] **Step 6: 测下载**

点任意文件后面的 ↓，浏览器下载文件，内容与原文件一致。

- [ ] **Step 7: 用户 review**

把浏览器截图（或文字描述）给用户。用户回"通过"才进 Task 6。

---

### Task 6: Plan 4 收口

- [ ] **Step 1: 跑后端单元测试确认没回归**

```bash
source .venv/bin/activate && pytest -v
```

- [ ] **Step 2: 提交 README 增补**

修改根 `README.md`，加一节"运行 Web 前端"：

```markdown
## 运行 Web 前端

```bash
cd web
npm install   # 首次
npm run dev
```

打开 http://localhost:3000。需要 Agent Server 已在 8000 端口跑（见上一节）。

可选环境变量（`.env.local`）：
- `NEXT_PUBLIC_HAGENT_API_BASE`（默认 `http://localhost:8000`）
- `NEXT_PUBLIC_HAGENT_API_KEY`（与 server 的 `HAGENT_API_KEY` 一致）
```

提交：
```bash
git add README.md
git commit -m "docs: add web frontend section to README"
```

- [ ] **Step 3: 通知用户**

> "Plan 4 完成：Web 前端 ready，三列布局 + SSE 流式 + 文件上传/下载 + HITL confirm() 兜底。所有后端 pytest 仍过。准备合 main + 进 Plan 5（DockerBackend + Session Manager + M3-swap）。"

---

## Plan 4 完整 Done 标准（对应 spec §4 M5 修正后）

- ✅ `web/` 子目录是 Next.js 15 App Router 项目（TypeScript + Tailwind）
- ✅ `web/src/lib/hagent_api.ts` 提供完整 API + SSE 消费
- ✅ `web/src/app/page.tsx` 单页三列布局
- ✅ 浏览器可对话、看 todo / 文件树更新、上传/下载文件
- ✅ HITL interrupt.requested 触发浏览器 `confirm()`
- ✅ spec D2 / §3 / §4 / §12 关于"langgraph-sdk"的描述已更新为"自定义 fetch/SSE"
- ✅ 后端 pytest 没有 regression
- ✅ README 含 web 启动指令
