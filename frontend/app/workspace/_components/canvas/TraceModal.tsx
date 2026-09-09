"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { prettyLabel } from "@/lib/hagent/naming";
import type { DocumentRecord } from "@/lib/hagent/documents";
import { TracePanel } from "./TracePanel";
import { useTrace } from "./traceContext";
import {
  DUR_FLOAT,
  DUR_PANEL,
  TRACE_EASE_ENTER,
  prefersReducedMotion,
} from "./traceMotion";
import {
  ChevronIcon,
  DownloadIcon,
  SidebarSimpleIcon,
  XIcon,
} from "@/components/ui/icons";

import { TraceInspector } from "./TraceInspector";
import { documentAssetUrl } from "@/lib/trace/pdf-runtime";
import "./trace-preview.css";

/** 焦点陷阱作用域内的可聚焦元素;offsetParent 过滤掉隐藏节点(与抽屉同口径) */
const FOCUSABLE =
  'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])';

/** 原文阅读与条目核验共用一个工作面，关闭后回到矩阵条目的原位置。 */
export function TraceModal({
  doc,
  onRequestClose,
}: {
  doc: DocumentRecord;
  onRequestClose: () => void;
}) {
  const trace = useTrace();
  const claim = trace?.activeClaim ?? null;
  const rootRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const inspectorId = useId();
  const [inspectorOpen, setInspectorOpen] = useState(() => typeof window === "undefined" || window.innerWidth >= 1000);
  const [locationsTarget, setLocationsTarget] = useState<HTMLDivElement | null>(null);
  const documents = [...new Set(claim?.refs.map((ref) => ref.document_id).filter((id): id is string => !!id && !!trace?.registry?.has(id)))];
  const downloadUrl = trace?.projectId ? doc.has_preview
    ? documentAssetUrl(trace.projectId, doc.id, "original")
    : `/api/hagent/projects/${encodeURIComponent(trace.projectId)}/workspace/files/${doc.path.split("/").map(encodeURIComponent).join("/")}` : null;

  // 入场:遮罩淡入 + 面板轻缩放到位,只动 transform / opacity。
  // 退场镜像编排在 CanvasDrawer.requestTraceClose(与抽屉退场同一处收口)。
  //
  // 必须走 useGSAP 而不是裸 useEffect + gsap.from:StrictMode 会双跑 effect,
  // 而 gsap.from 的「终点」取的是调用那一刻的当前值——第一次把 opacity 打到 0 并
  // 开始动,第二次跑时读到的当前值还是动画中途的 0.16,于是终点变成 0.16,
  // 面板永久停在半透明(实测 opacity 0.1648 / scale 0.9833,遮罩 0)。
  // useGSAP 在清理时 revert 掉上一轮 tween,第二次才是从干净状态重来。
  useGSAP(
    () => {
      if (prefersReducedMotion()) return;
      gsap.from(".cv-trace-modal-scrim", {
        autoAlpha: 0,
        duration: DUR_FLOAT,
        ease: TRACE_EASE_ENTER,
      });
      gsap.from(".cv-trace-modal-panel", {
        autoAlpha: 0,
        scale: 0.98,
        duration: DUR_PANEL,
        ease: TRACE_EASE_ENTER,
      });
    },
    { scope: rootRef },
  );

  // 焦点陷阱归本层所有:抽屉那份在预览层打开时短路让位(同一时刻只允许一个陷阱)。
  // Esc 不在这里处理 —— 两个 window 监听器会互抢且 stopPropagation 对同节点无效,
  // 所以「逐层退」的判定统一收在 CanvasDrawer 的单一处理器里。
  useEffect(() => {
    const previous =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    closeRef.current?.focus({ preventScroll: true });
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        rootRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [],
      ).filter((el) => el.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!rootRef.current?.contains(document.activeElement)) {
        event.preventDefault();
        first?.focus();
        return;
      }
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      previous?.focus({ preventScroll: true });
    };
  }, []);

  const onScrimDown = useCallback(() => onRequestClose(), [onRequestClose]);

  return (
    <div ref={rootRef} className="cv-trace-modal trace-workspace" data-inspector-open={inspectorOpen && !!claim}>
      <div className="cv-trace-modal-scrim" onPointerDown={onScrimDown} />
      <div className="cv-trace-modal-panel" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="cv-trace-modal-head">
          <div className="trace-document-title">
            <span className="cv-trace-title" id={titleId} title={doc.path}>{prettyLabel(doc.path.split("/").pop() ?? doc.path)}</span>
            {documents.length > 1 && <>
              <ChevronIcon width={14} height={14} aria-hidden />
              <select aria-label="来源文件" value={doc.id} onChange={(e) => {
                const index = claim?.refs.findIndex((ref) => ref.document_id === e.target.value) ?? -1;
                const ref = claim?.refs[index];
                if (claim && ref) trace?.openTrace(ref, `${claim.itemKey}:${index}`, { ...claim, refIndex: index });
              }}>{documents.map((id) => <option key={id} value={id}>{prettyLabel(trace?.registry?.get(id)?.path.split("/").pop() ?? id)}</option>)}</select>
            </>}
          </div>
          <div className="trace-window-actions">
            {downloadUrl && <a className="trace-icon-button" href={downloadUrl} download title="下载原件" aria-label="下载原件"><DownloadIcon width={18} height={18} /></a>}
            {claim && <button type="button" className="trace-inspector-toggle" aria-label="对照条目" title="对照条目" aria-expanded={inspectorOpen} aria-controls={inspectorId}
              onClick={() => setInspectorOpen((value) => !value)}><SidebarSimpleIcon width={18} height={18} /><span>对照</span></button>}
            <button ref={closeRef} type="button" className="trace-icon-button" title="返回条目" aria-label="关闭原文预览" onClick={onRequestClose}><XIcon width={18} height={18} /></button>
          </div>
        </div>
        <div className="trace-workspace-body">
          <div className="trace-document"><TracePanel doc={doc} arrival={DUR_PANEL} locationsTarget={locationsTarget} /></div>
          {claim && <aside className="trace-inspector" id={inspectorId} aria-label="条目核验" hidden={!inspectorOpen}>
            <TraceInspector key={`${claim.matrixType}:${claim.itemKey}`} claim={claim} locationsRef={setLocationsTarget} hasPdf={!!doc.has_preview} />
          </aside>}
        </div>
      </div>
    </div>
  );
}
