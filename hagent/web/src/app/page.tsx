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
import { reduceChatEvent, type ChatMsg, type SubagentRun, type ToolCall } from "@/lib/chat_timeline";

type Todo = { content: string; status: string };
type FileEntry = { path: string; type: "file" | "dir"; size: number | null };

export default function Home() {
  const [sid, setSid] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [todos, setTodos] = useState<Todo[]>([]);
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [creating, setCreating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  async function newSession() {
    if (creating || streaming) return;
    setCreating(true);
    try {
      const r = await createSession();
      setSid(r.session_id);
      setMsgs([]);
      setTodos([]);
      setFiles([]);
    } catch (e) {
      console.error("createSession", e);
    } finally {
      setCreating(false);
    }
  }

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

  // 新消息自动滚到底
  useEffect(() => {
    const el = chatScrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [msgs]);

  async function send() {
    if (!sid || !input.trim()) return;
    setMsgs((m) => [...m, { id: `u-${Date.now()}`, role: "user", content: input }]);
    const userInput = input;
    setInput("");
    setStreaming(true);
    try {
      for await (const ev of streamMessage(sid, userInput)) {
        handleEvent(ev);
      }
    } catch (e) {
      console.error("stream error", e);
    } finally {
      setStreaming(false);
    }
  }

  function handleEvent(ev: SSEEvent) {
    if (
      ev.event === "message.delta" ||
      ev.event === "tool_call.started" ||
      ev.event === "tool_call.completed" ||
      ev.event === "error"
    ) {
      setMsgs((m) => reduceChatEvent(m, ev));
    } else if (ev.event === "interrupt.requested") {
      const d = ev.data as { interrupt_id?: string };
      const ok = window.confirm(`HITL: ${JSON.stringify(ev.data)}\n\n点确认=approve / 取消=reject`);
      if (sid && d.interrupt_id) {
        postInterrupt(sid, d.interrupt_id, ok ? "approve" : "reject").catch((e) =>
          console.error("postInterrupt", e),
        );
      }
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
    const blob = await downloadFile(sid, path);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = path.split("/").pop() || path;
    a.click();
    URL.revokeObjectURL(url);
  }

  const lastIdx = msgs.length - 1;
  const lastIsUser = lastIdx >= 0 && msgs[lastIdx].role === "user";

  return (
    <main className="grid grid-cols-12 gap-4 p-4 h-full">
      {/* Chat */}
      <section className="col-span-7 flex flex-col rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
        <header className="px-4 py-2.5 border-b border-gray-200 text-sm font-medium text-gray-700 bg-gray-50 flex items-center justify-between">
          <span>Chat</span>
          <div className="flex items-center gap-2">
            {sid && <span className="text-gray-400 font-mono text-[10px]">{sid}</span>}
            <button
              onClick={newSession}
              disabled={creating || streaming}
              title={sid ? "新建会话（丢弃当前对话）" : "新建会话以开始"}
              className="text-xs px-2 py-1 rounded border border-gray-300 bg-white hover:bg-gray-100 active:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {creating ? "创建中…" : sid ? "+ 新会话" : "+ 新建会话"}
            </button>
          </div>
        </header>
        <div ref={chatScrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3 text-sm">
          {msgs.length === 0 && (
            <div className="text-center text-gray-400 text-xs pt-8">
              {sid ? "输入消息开始对话" : "点击右上角\"新建会话\"开始"}
            </div>
          )}
          {msgs.map((m, i) => {
            // 只有最后一条 thinking + 全局还在 streaming，才算"正在思考"
            // 一旦后面有新 ChatMsg 进来 (text / tool / 新 thinking)，自动 streaming=false → 收起
            const isStreamingThisMsg = i === lastIdx && streaming;
            return renderMessage(m, isStreamingThisMsg);
          })}
          {/* 第一个 event 还没到、user 是 last 时的等待状态 */}
          {streaming && lastIsUser && (
            <div className="flex"><PulsingDot /></div>
          )}
        </div>
        <footer className="border-t border-gray-200 p-2.5 flex gap-2 bg-gray-50">
          <input
            type="text"
            className="flex-1 border border-gray-300 rounded-md px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
            className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded-md text-sm font-medium disabled:opacity-50 disabled:hover:bg-blue-600 transition-colors"
            onClick={send}
            disabled={streaming || !sid || !input.trim()}
          >
            发送
          </button>
        </footer>
      </section>

      {/* Todos */}
      <section className="col-span-2 flex flex-col rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
        <header className="px-3 py-2.5 border-b border-gray-200 text-sm font-medium text-gray-700 bg-gray-50">Todos</header>
        <ul className="flex-1 overflow-y-auto px-3 py-2 text-xs space-y-1.5">
          {todos.length === 0 ? (
            <li className="text-gray-400 italic">no todos</li>
          ) : (
            todos.map((t, i) => (
              <li key={i} className="flex gap-2 items-start">
                <span className={t.status === "completed" ? "text-green-600" : "text-gray-400"}>
                  {t.status === "completed" ? "✓" : "○"}
                </span>
                <span className={t.status === "completed" ? "line-through text-gray-400" : "text-gray-800"}>
                  {t.content}
                </span>
              </li>
            ))
          )}
        </ul>
      </section>

      {/* Files */}
      <section className="col-span-3 flex flex-col rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
        <header className="px-3 py-2.5 border-b border-gray-200 text-sm font-medium text-gray-700 bg-gray-50 flex justify-between items-center">
          <span>Workspace</span>
          <label className="text-xs text-blue-600 hover:text-blue-800 cursor-pointer font-medium">
            ↑ upload
            <input ref={fileInputRef} type="file" className="hidden" onChange={onUpload} />
          </label>
        </header>
        <ul className="flex-1 overflow-y-auto px-3 py-2 text-xs space-y-1">
          {files.length === 0 ? (
            <li className="text-gray-400 italic">empty</li>
          ) : (
            files.map((f) => (
              <li key={f.path} className="flex justify-between items-center hover:bg-gray-50 px-1 rounded">
                <span className={`truncate ${f.type === "dir" ? "font-medium text-gray-800" : "text-gray-700"}`}>
                  {f.type === "dir" ? "📁" : "📄"} {f.path}
                </span>
                {f.type === "file" && (
                  <button
                    className="text-blue-600 hover:text-blue-800 ml-2 shrink-0"
                    onClick={() => onDownload(f.path)}
                    title="下载"
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

function renderMessage(m: ChatMsg, isStreamingThisMsg: boolean) {
  if (m.role === "user") {
    return (
      <div key={m.id} className="flex justify-end">
        <span className="inline-block max-w-[80%] bg-blue-600 text-white px-3.5 py-2 rounded-2xl rounded-br-md whitespace-pre-wrap shadow-sm text-sm">
          {m.content}
        </span>
      </div>
    );
  }
  if (m.role === "assistant_text") {
    return (
      <div key={m.id} className="flex">
        <span className="inline-block max-w-[85%] bg-white border border-gray-200 px-3.5 py-2 rounded-2xl rounded-bl-md whitespace-pre-wrap shadow-sm text-sm text-gray-900 leading-relaxed">
          {m.content}
        </span>
      </div>
    );
  }
  if (m.role === "thinking") {
    return <ThinkingBlock key={m.id} text={m.content} streaming={isStreamingThisMsg} />;
  }
  if (m.role === "tool") {
    return <ToolCallView key={m.id} call={m.call} />;
  }
  if (m.role === "subagent") {
    return <SubagentRunView key={m.id} run={m.run} streaming={isStreamingThisMsg} />;
  }
  if (m.role === "error") {
    return (
      <div key={m.id} className="text-xs text-red-700 font-mono px-3 py-2 bg-red-50 border border-red-200 rounded-md">
        [error] {m.content}
      </div>
    );
  }
  return null;
}

function ThinkingBlock({ text, streaming }: { text: string; streaming: boolean }) {
  // 初始：streaming 时展开（让用户看到思考过程），历史消息默认收起
  const [open, setOpen] = useState(streaming);
  const prevStreaming = useRef(streaming);
  // streaming=true → false 转换时自动收起（thinking 输出完毕）
  // 之后用户手动 toggle 不再被覆盖（因为 prev/cur 都是 false，不触发）
  useEffect(() => {
    if (prevStreaming.current && !streaming) {
      setOpen(false);
    }
    prevStreaming.current = streaming;
  }, [streaming]);
  return (
    <details
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      className="bg-amber-50 border border-amber-200 rounded-lg overflow-hidden max-w-full"
    >
      <summary className="px-3 py-1.5 text-xs text-amber-800 cursor-pointer select-none flex items-center gap-1.5 hover:bg-amber-100">
        <span>💭</span>
        <span className="font-medium">thinking</span>
        {streaming && <span className="text-amber-600 text-[10px] italic">streaming…</span>}
        <span className="text-amber-600 text-[10px] ml-auto">{open ? "收起" : "展开"}</span>
      </summary>
      <div className="px-3 py-2 text-xs text-amber-900 whitespace-pre-wrap font-mono leading-relaxed border-t border-amber-200 bg-amber-50/50">
        {text}
      </div>
    </details>
  );
}

function truncateText(text: string, max = 160): string {
  const compact = text.replace(/\s+/g, " ").trim();
  if (compact.length <= max) return compact;
  return `${compact.slice(0, max - 1)}…`;
}

function SubagentRunView({ run, streaming }: { run: SubagentRun; streaming: boolean }) {
  const running = run.status === "running";
  const [open, setOpen] = useState(running);
  const prevRunning = useRef(running);
  useEffect(() => {
    if (running) setOpen(true);
    if (prevRunning.current && !running) setOpen(false);
    prevRunning.current = running;
  }, [running]);

  const toolCount = run.children.filter((child) => child.role === "tool" || child.role === "subagent").length;
  const childCount = run.children.length;
  const resultPreview = run.call.result ? truncateText(run.call.result, 180) : "";

  return (
    <details
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
      className="group max-w-full overflow-hidden rounded-lg border border-zinc-200 bg-zinc-50 shadow-sm"
    >
      <summary className="grid cursor-pointer select-none grid-cols-[auto_1fr_auto] items-start gap-3 px-3 py-2.5 hover:bg-zinc-100">
        <span
          className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border text-[11px] font-semibold ${
            running
              ? "border-amber-300 bg-amber-100 text-amber-800"
              : "border-emerald-300 bg-emerald-50 text-emerald-700"
          }`}
        >
          {running ? "..." : "OK"}
        </span>
        <span className="min-w-0 space-y-1">
          <span className="flex min-w-0 items-center gap-2">
            <span className="truncate text-sm font-semibold text-zinc-900">{run.description}</span>
            <span className="shrink-0 rounded border border-zinc-300 bg-white px-1.5 py-0.5 font-mono text-[10px] text-zinc-600">
              {run.subagentType}
            </span>
          </span>
          <span className="block truncate text-xs text-zinc-500">
            {running ? "子代理运行中" : resultPreview || "子代理已完成"}
            {childCount > 0 && ` · ${childCount} 条内部事件`}
            {toolCount > 0 && ` · ${toolCount} 个工具调用`}
          </span>
        </span>
        <span className="pt-1 text-[10px] font-medium text-zinc-500">{open ? "收起" : "展开"}</span>
      </summary>
      <div className="border-t border-zinc-200 bg-white px-3 py-3">
        <div className="mb-3 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Task</span>
            {streaming && running && (
              <span className="text-[11px] font-medium text-amber-700">streaming</span>
            )}
          </div>
          <div className="text-xs leading-relaxed text-zinc-800">{run.prompt ? truncateText(run.prompt, 420) : run.description}</div>
        </div>

        {run.children.length > 0 ? (
          <div className="space-y-2 border-l border-zinc-200 pl-3">
            {run.children.map((child, i) => (
              <SubagentChildView
                key={child.id}
                msg={child}
                streaming={running && i === run.children.length - 1}
              />
            ))}
          </div>
        ) : (
          <div className="border-l border-zinc-200 pl-3 text-xs text-zinc-400">
            {running ? "等待子代理输出…" : "没有捕获到子代理内部事件"}
          </div>
        )}

        {run.call.result && (
          <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2">
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-emerald-700">Result</div>
            <div className="whitespace-pre-wrap text-xs leading-relaxed text-emerald-950">{run.call.result}</div>
          </div>
        )}
      </div>
    </details>
  );
}

function SubagentChildView({ msg, streaming }: { msg: ChatMsg; streaming: boolean }) {
  if (msg.role === "assistant_text") {
    return (
      <div className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-xs leading-relaxed text-zinc-800 shadow-sm">
        {msg.content}
      </div>
    );
  }
  if (msg.role === "thinking") {
    return <ThinkingBlock text={msg.content} streaming={streaming} />;
  }
  if (msg.role === "tool") {
    return <ToolCallView call={msg.call} compact />;
  }
  if (msg.role === "subagent") {
    return <SubagentRunView run={msg.run} streaming={streaming} />;
  }
  if (msg.role === "error") {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 font-mono text-xs text-red-700">
        [error] {msg.content}
      </div>
    );
  }
  return null;
}

function compactToolArgValue(value: unknown): string {
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number" || typeof value === "boolean" || value === null) return String(value);
  if (Array.isArray(value)) return `[${value.length} items]`;
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatToolArgsPreview(rawArgs: string): string {
  const trimmed = rawArgs.trim();
  if (!trimmed) return "";

  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      const entries = Object.entries(parsed);
      if (entries.length > 0) {
        return entries
          .map(([key, value]) => `${key}=${compactToolArgValue(value)}`)
          .join(", ");
      }
    }
  } catch {
    // Streaming tool args can be partial JSON; fall back to the raw chunk.
  }

  return trimmed.replace(/\s+/g, " ");
}

function ToolCallView({ call, compact = false }: { call: ToolCall; compact?: boolean }) {
  const argsSummary = formatToolArgsPreview(call.args);
  const previewLength = compact ? 90 : 120;
  const argsPreview = argsSummary.length > previewLength ? argsSummary.slice(0, previewLength) + "…" : argsSummary;
  const done = call.status === "done";
  return (
    <details className={`bg-slate-50 border border-slate-200 overflow-hidden max-w-full ${compact ? "rounded-md" : "rounded-lg"}`}>
      <summary className={`${compact ? "px-2.5 py-1.5" : "px-3 py-1.5"} text-xs cursor-pointer select-none flex items-center gap-2 hover:bg-slate-100`}>
        <span className={done ? "text-green-600" : "text-amber-500 animate-pulse"}>
          {done ? "✓" : "●"}
        </span>
        <span className="font-mono font-semibold text-slate-800 shrink-0">{call.tool_name}</span>
        {argsPreview && (
          <span className="font-mono text-slate-500 truncate flex-1 min-w-0">
            {argsPreview}
          </span>
        )}
      </summary>
      <div className="px-3 py-2 text-xs space-y-2 border-t border-slate-200 bg-white">
        {call.args && (
          <div>
            <div className="text-slate-500 mb-1 font-medium">args</div>
            <pre className="bg-slate-50 border border-slate-200 rounded px-2 py-1.5 overflow-x-auto whitespace-pre-wrap text-slate-800 font-mono">
              {call.args}
            </pre>
          </div>
        )}
        {call.result !== undefined && (
          <div>
            <div className="text-slate-500 mb-1 font-medium">result</div>
            <pre className="bg-slate-50 border border-slate-200 rounded px-2 py-1.5 overflow-x-auto whitespace-pre-wrap text-slate-800 font-mono max-h-64">
              {call.result}
            </pre>
          </div>
        )}
        {!done && call.result === undefined && (
          <div className="text-slate-400 italic">running…</div>
        )}
      </div>
    </details>
  );
}

function PulsingDot() {
  return (
    <div className="flex gap-1 items-center px-3.5 py-2 bg-white border border-gray-200 rounded-2xl rounded-bl-md shadow-sm">
      <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
      <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
      <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
    </div>
  );
}
