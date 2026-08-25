"use client";

import { useEffect, useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { FileIcon, ListDashesIcon, PaperPlaneTiltIcon, PaperclipIcon } from "@/components/ui/icons";
import { DUR_MICRO, TRACE_EASE_ENTER } from "./canvas/traceMotion";
import { useWorkspaceStore } from "@/lib/store/workspace";
import { listSamples, type SampleInfo } from "@/lib/hagent/api";
import { prettyLabel } from "@/lib/hagent/naming";

const BUSY = new Set(["creating", "uploading", "running", "loading_results"]);

export function Composer() {
  const rootRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const sampleButtonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const skipMenuAnimationRef = useRef(false);
  const draft = useWorkspaceStore((s) => s.composerDraft);
  const setDraft = useWorkspaceStore((s) => s.setComposerDraft);
  const startParse = useWorkspaceStore((s) => s.startParse);
  const sendMessage = useWorkspaceStore((s) => s.sendMessage);
  const projectId = useWorkspaceStore((s) => s.projectId);
  const phase = useWorkspaceStore((s) => s.phase);
  const busy = BUSY.has(phase);
  // 项目已就位时,composer 兼作自由对话入口:续写/修改同一工作区的产物。
  const canChat = Boolean(projectId) && !busy;

  const [samples, setSamples] = useState<SampleInfo[]>([]);
  const [sampleState, setSampleState] = useState<"loading" | "ready" | "error">("loading");
  const [open, setOpen] = useState(false);
  const [armed, setArmed] = useState<{ name: string; label: string } | null>(null);

  useEffect(() => {
    listSamples()
      .then((items) => {
        setSamples(items);
        setSampleState("ready");
      })
      .catch(() => {
        setSamples([]);
        setSampleState("error");
      });
  }, []);

  useEffect(() => {
    if (!open) return;
    if (skipMenuAnimationRef.current) {
      requestAnimationFrame(() => menuRef.current?.querySelector<HTMLButtonElement>("button")?.focus());
    }
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (menuRef.current?.contains(target) || sampleButtonRef.current?.contains(target)) return;
      setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        sampleButtonRef.current?.focus();
        return;
      }
      if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
      const items = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>("button") ?? []);
      if (!items.length) return;
      event.preventDefault();
      const current = items.indexOf(document.activeElement as HTMLButtonElement);
      const next =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? items.length - 1
            : event.key === "ArrowDown"
              ? (current + 1 + items.length) % items.length
              : (current - 1 + items.length) % items.length;
      items[next]?.focus();
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  useGSAP(
    () => {
      if (!open || !menuRef.current || skipMenuAnimationRef.current) return;
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      gsap.fromTo(
        menuRef.current,
        { autoAlpha: 0, transform: "translateY(4px) scale(0.98)" },
        { autoAlpha: 1, transform: "translateY(0) scale(1)", duration: DUR_MICRO, ease: TRACE_EASE_ENTER },
      );
    },
    { scope: rootRef, dependencies: [open] },
  );

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 140)}px`;
  }, [draft]);

  const fire = () => {
    if (busy) return;
    if (armed) {
      startParse({
        sampleName: armed.name,
        sampleLabel: armed.label,
        instruction: draft.trim() || undefined,
      });
      setArmed(null);
      setDraft("");
      return;
    }
    const text = draft.trim();
    if (!text || !canChat) return;
    void sendMessage(text);
    setDraft("");
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      fire();
    }
  };

  const onPickFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f && !busy) {
      startParse({ file: f, instruction: draft.trim() || undefined });
      setDraft("");
    }
    e.target.value = "";
  };

  return (
    <div className="composer" ref={rootRef}>
      {armed && (
        <div className="composer-selection" role="status">
          <span className="composer-selection-icon" aria-hidden="true">
            <FileIcon width={15} height={15} />
          </span>
          <span className="composer-selection-copy">
            <strong>已选招标文件</strong>
            <span title={armed.label}>{armed.label}</span>
          </span>
          <button type="button" onClick={() => setArmed(null)} disabled={busy}>
            移除
          </button>
        </div>
      )}
      <div className="composer-input">
        <textarea
          ref={taRef}
          aria-label="向智能体输入指令"
          placeholder={
            armed
              ? "补充本次解析要求（可选）……"
              : projectId
                ? "向智能体发送指令，续写或修改本项目的产物……"
                : "先选择招标文件，再补充解析要求……"
          }
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="composer-actions">
          <input
            ref={fileRef}
            type="file"
            accept=".md,text/markdown"
            style={{ display: "none" }}
            onChange={onPickFile}
          />
          <button
            className="icon-btn"
            title="上传 .md 招标文件"
            type="button"
            disabled={busy}
            onClick={() => fileRef.current?.click()}
          >
            <PaperclipIcon />
            <span>上传</span>
          </button>

          <div className="composer-sample-control">
            <button
              ref={sampleButtonRef}
              className="icon-btn"
              title="选择招标文件样本"
              type="button"
              disabled={busy}
              aria-haspopup="menu"
              aria-expanded={open}
              aria-controls="composer-sample-menu"
              onClick={(event) => {
                skipMenuAnimationRef.current = event.detail === 0;
                setOpen((v) => !v);
              }}
            >
              <ListDashesIcon />
              <span>样本</span>
            </button>
            {open && (
              /* 样本菜单:瞬态浮层,凝 lens·regular——单屏第 3 张 lens 面
                 (前两张为消息浮窗与 agent 看板,菜单开合短暂,预算内) */
              <div
                className="composer-sample-menu frost-glass frost-glass--lens"
                data-thick="regular"
                id="composer-sample-menu"
                ref={menuRef}
                role="menu"
                aria-label="招标文件样本"
              >
                <div className="composer-sample-heading">选择招标文件</div>
                {sampleState === "loading" && <div className="composer-sample-empty">正在载入样本……</div>}
                {sampleState === "error" && <div className="composer-sample-empty">样本载入失败，请上传文件</div>}
                {sampleState === "ready" && samples.length === 0 && (
                  <div className="composer-sample-empty">暂无可用样本</div>
                )}
                {samples.map((s) => {
                  const label = prettyLabel(s.filename);
                  return (
                    <button
                      key={s.filename}
                      type="button"
                      className="composer-sample-item"
                      role="menuitem"
                      onClick={() => {
                        setArmed({ name: s.filename, label });
                        setOpen(false);
                      }}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <button
            className="composer-send"
            aria-label="发送"
            type="button"
            disabled={busy || (!armed && !(canChat && draft.trim()))}
            onClick={fire}
          >
            <PaperPlaneTiltIcon aria-hidden="true" />
            <span>发送</span>
          </button>
        </div>
      </div>
      <div className="composer-hint" aria-hidden="true">
        {armed
          ? "⌘ / Ctrl + Enter 开始解析"
          : projectId
            ? "⌘ / Ctrl + Enter 发送"
            : "支持 Markdown 招标文件"}
      </div>
    </div>
  );
}
