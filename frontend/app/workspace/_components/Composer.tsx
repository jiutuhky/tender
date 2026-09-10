"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { FileIcon, ListDashesIcon, PaperPlaneTiltIcon, PaperclipIcon, StopIcon, UploadIcon } from "@/components/ui/icons";
import { useWorkspaceStore } from "@/lib/store/workspace";
import { listSamples, type SampleInfo } from "@/lib/hagent/api";
import { prettyLabel } from "@/lib/hagent/naming";
import "./composer.css";

const BUSY = new Set(["creating", "uploading", "running", "loading_results"]);
type Attachment = { label: string; file: File; sampleName?: never } | { label: string; sampleName: string; file?: never };

/** 首页与项目内共用提交行为：先暂存附件，明确提交后才开始解析。 */
export function Composer({ entry = false, onStart }: { entry?: boolean; onStart?: () => void }) {
  const taRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const sampleButtonRef = useRef<HTMLButtonElement>(null);
  const hintId = useId();
  const menuId = useId();
  const draft = useWorkspaceStore((s) => s.composerDraft);
  const setDraft = useWorkspaceStore((s) => s.setComposerDraft);
  const startParse = useWorkspaceStore((s) => s.startParse);
  const sendMessage = useWorkspaceStore((s) => s.sendMessage);
  const projectId = useWorkspaceStore((s) => s.projectId);
  const phase = useWorkspaceStore((s) => s.phase);
  const runId = useWorkspaceStore((s) => s.botSignals.runId);
  const runEnded = useWorkspaceStore((s) => s.botSignals.ended);
  const cancelling = useWorkspaceStore((s) => s.cancelling);
  const cancelRun = useWorkspaceStore((s) => s.cancelRun);
  const busy = BUSY.has(phase);
  const showStop = phase === "running" && !runEnded;
  const canChat = !entry && Boolean(projectId) && !busy;
  const [attachment, setAttachment] = useState<Attachment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [samples, setSamples] = useState<SampleInfo[]>([]);
  const [sampleState, setSampleState] = useState<"loading" | "ready" | "error">("loading");
  const [open, setOpen] = useState(false);
  const [sampleRevision, setSampleRevision] = useState(0);

  const acceptFile = useCallback((file: File) => {
    if (busy) return;
    if (!/\.(md|pdf)$/i.test(file.name)) { setError("请选择 PDF 或 Markdown（.md）招标文件。"); return; }
    if (!file.size) { setError("这份文件没有内容，请选择其他文件。"); return; }
    setError(null);
    setAttachment({ file, label: file.name });
    taRef.current?.focus();
  }, [busy]);

  useEffect(() => {
    if (!entry) return;
    let depth = 0;
    const enter = (e: DragEvent) => {
      if (!e.dataTransfer?.types.includes("Files")) return;
      e.preventDefault(); depth += 1; if (!busy) setDragging(true);
    };
    const over = (e: DragEvent) => { if (e.dataTransfer?.types.includes("Files")) e.preventDefault(); };
    const leave = () => { depth = Math.max(0, depth - 1); if (!depth) setDragging(false); };
    const drop = (e: DragEvent) => {
      if (!e.dataTransfer?.types.includes("Files")) return;
      e.preventDefault(); depth = 0; setDragging(false);
      if (e.dataTransfer.files.length > 1) { setError("每个新项目选择一份招标文件，请逐份添加。"); return; }
      const file = e.dataTransfer.files[0]; if (file) acceptFile(file);
    };
    window.addEventListener("dragenter", enter); window.addEventListener("dragover", over);
    window.addEventListener("dragleave", leave); window.addEventListener("drop", drop);
    return () => { window.removeEventListener("dragenter", enter); window.removeEventListener("dragover", over); window.removeEventListener("dragleave", leave); window.removeEventListener("drop", drop); };
  }, [entry, acceptFile, busy]);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    listSamples().then((items) => { if (alive) { setSamples(items); setSampleState("ready"); } }).catch(() => { if (alive) setSampleState("error"); });
    return () => { alive = false; };
  }, [open, sampleRevision]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!menuRef.current?.contains(e.target as Node) && !sampleButtonRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); setOpen(false); sampleButtonRef.current?.focus(); return; }
      if (e.key === "Tab") { setOpen(false); return; }
      if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
      if (!menuRef.current?.contains(document.activeElement) && document.activeElement !== sampleButtonRef.current) return;
      const items = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>("button") ?? []);
      if (!items.length) return;
      e.preventDefault();
      const current = items.indexOf(document.activeElement as HTMLButtonElement);
      const next = e.key === "Home" ? 0 : e.key === "End" ? items.length - 1 : e.key === "ArrowDown" ? (current + 1) % items.length : (current - 1 + items.length) % items.length;
      items[next]?.focus();
    };
    window.addEventListener("pointerdown", onPointerDown); window.addEventListener("keydown", onKeyDown);
    return () => { window.removeEventListener("pointerdown", onPointerDown); window.removeEventListener("keydown", onKeyDown); };
  }, [open]);

  useEffect(() => {
    const ta = taRef.current;
    if (ta) { ta.style.height = "auto"; ta.style.height = `${Math.min(ta.scrollHeight, 140)}px`; }
  }, [draft]);

  const fire = () => {
    if (busy) return;
    if (attachment) {
      void startParse({ file: attachment.file, sampleName: attachment.sampleName, sampleLabel: attachment.file ? undefined : attachment.label, projectName: prettyLabel(attachment.label), instruction: draft.trim() || undefined });
      setAttachment(null); setDraft(""); setError(null); onStart?.();
    } else if (canChat && draft.trim()) { void sendMessage(draft.trim()); setDraft(""); }
  };
  const actionLabel = attachment && projectId && !entry ? "解析新项目" : attachment || entry || !projectId ? "开始解析" : "发送";

  return (
    <div className={`composer${entry ? " composer-entry" : ""}`}>
      {attachment && <div className="composer-selection" role="status">
        <span className="composer-selection-icon" aria-hidden="true"><FileIcon width={18} height={18} /></span>
        <span className="composer-selection-copy"><strong>{attachment.label}</strong><span>{attachment.file ? `${Math.max(1, Math.round(attachment.file.size / 1024))} KB · 已添加，提交后创建新项目` : "示例文件 · 将创建独立项目"}</span></span>
        <button type="button" onClick={() => { setAttachment(null); taRef.current?.focus(); }} disabled={busy} aria-label={`移除 ${attachment.label}`}>移除</button>
      </div>}
      <div className="composer-input">
        <textarea ref={taRef} aria-label="补充要求或向智能体发送指令" aria-describedby={hintId}
          placeholder={attachment ? "补充解析要求，例如：优先标出实质性条款和需要准备的证明材料…" : canChat ? "继续核验、补充说明，或让智能体修改本项目的应答…" : "添加一份招标文件，或先写下本次解析的重点…"}
          value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => {
            if (e.nativeEvent.isComposing || e.keyCode === 229) return;
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); fire(); }
          }} />
        <div className="composer-actions">
          <input ref={fileRef} type="file" accept=".pdf,application/pdf,.md,text/markdown" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) acceptFile(f); e.target.value = ""; }} />
          <button className="icon-btn" type="button" disabled={busy} onClick={() => fileRef.current?.click()}><PaperclipIcon /><span>{projectId && !entry ? "新项目文件" : "添加文件"}</span></button>
          <div className="composer-sample-control">
            <button ref={sampleButtonRef} className="icon-btn" type="button" disabled={busy} aria-haspopup="menu" aria-expanded={open} aria-controls={open ? menuId : undefined} onClick={() => setOpen((v) => !v)}><ListDashesIcon /><span>试用样本</span></button>
            {open && <div id={menuId} ref={menuRef} className="composer-sample-menu" role="menu" aria-label="选择示例招标文件">
              <div className="composer-sample-heading">示例招标文件</div>
              {sampleState === "loading" && <div className="composer-sample-empty" role="status">正在加载样本…</div>}
              {sampleState === "error" && <div className="composer-sample-empty">样本加载失败。<button type="button" className="prose-text-button" onClick={() => { setSampleState("loading"); setSampleRevision((v) => v + 1); }}>重试</button></div>}
              {sampleState === "ready" && samples.length === 0 && <div className="composer-sample-empty">暂无样本，请添加自己的文件。</div>}
              {samples.map((s) => <button key={s.filename} type="button" role="menuitem" className="composer-sample-item" onClick={() => { setAttachment({ sampleName: s.filename, label: prettyLabel(s.filename) }); setError(null); setOpen(false); taRef.current?.focus(); }}>{prettyLabel(s.filename)}</button>)}
            </div>}
          </div>
          {showStop ? (
            <button className="composer-send composer-stop" type="button"
              aria-label={cancelling ? "正在停止本轮" : "停止本轮"}
              title={cancelling ? "正在停止本轮" : "停止本轮"}
              aria-busy={cancelling} disabled={cancelling || !runId}
              onClick={() => void cancelRun()}>
              <StopIcon aria-hidden="true" />
            </button>
          ) : (
            <button className="composer-send" type="button" disabled={busy || (!attachment && !(canChat && draft.trim()))} onClick={fire}><PaperPlaneTiltIcon aria-hidden="true" /><span>{busy ? "处理中" : actionLabel}</span></button>
          )}
        </div>
      </div>
      {error && <p className="composer-error" role="alert">{error}</p>}
      <div className="composer-hint" id={hintId}>{entry || attachment || !projectId ? "支持 PDF、Markdown 招标文件 · " : ""}{busy ? "任务进行中，可以先写下下一条要求" : "Ctrl / ⌘ + Enter 提交，Enter 换行"}</div>
      {dragging && <div className="composer-drop-overlay" aria-hidden="true"><div><UploadIcon width={32} height={32} /><strong>松手，添加招标文件</strong><span>核对文件和要求后，点击「开始解析」</span></div></div>}
    </div>
  );
}
