"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { useWorkspaceStore } from "@/lib/store/workspace";
import { prettyLabel } from "@/lib/hagent/naming";
import type { DocumentRecord } from "@/lib/hagent/documents";
import { ItemActions, MandatoryMark, RiskMark, useItemAction } from "./matrixViews";
import { TracePanel } from "./TracePanel";
import { useTrace, type TraceClaim } from "./traceContext";
import { DUR_FLOAT, DUR_PANEL, TRACE_EASE_ENTER, prefersReducedMotion } from "./traceMotion";
import { ChevronLeftIcon, ChevronRightIcon, FileIcon, XIcon } from "@/components/ui/icons";

// 溯源预览层:点来源签后盖满画布的阅读层(取代早期「抽屉加宽对照双栏」)。
// 形态决策:旧双栏留给原文的版心只有 ~503px,而公文排版的纸面版心要 720px 以上,
// 招标文件的宽表格(前附表 4 列长中文)同样放不下 —— 版心不够是排版做不出来的硬原因。
// 工作台是单列布局(对话是画布上的浮层),所以画布级浮层几乎能拿到满窗宽度。
//
// 挂载位置是 .cv-drawer 的子级而非 .canvas-viewport 的兄弟:
// .cv-drawer 已是 absolute inset:0 / z-30 铺满画布,子级天然盖住抽屉面板并继承既有裁剪,
// 不需要 portal、不需要越过 .ds-return(z-99) 之类的页面级 fixed 层。
//
// 对照条(cv-trace-claim)是这次形态改动的关键补偿:预览层盖住条目列表后,
// 「对照原文核验 + 就地落应答状态」(PRD 故事 5)会断掉,所以把被核验条目连同
// 人工动作一起钉在标题栏下方,并提供层内来源步进走完同一条目的多条来源(故事 6)。

/** 焦点陷阱作用域内的可聚焦元素;offsetParent 过滤掉隐藏节点(与抽屉同口径) */
const FOCUSABLE =
  'button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])';

/** 对照条:被核验条目 + 人工动作 + 来源步进。
 *  行级管理状态按 matrixType + itemId 从 store 读实时值 —— 不能用快照,
 *  否则层内点完「确认」对照条自己不刷新。 */
function ClaimBar({ claim }: { claim: TraceClaim }) {
  const trace = useTrace();
  const [expanded, setExpanded] = useState(false);
  const { busyItemId, actionErr, confirm, setStatus } = useItemAction(claim.matrixType);
  const row = useWorkspaceStore((s) => {
    if (!claim.itemId) return null;
    return s.matrices[claim.matrixType].itemRows?.find((r) => r.item_id === claim.itemId) ?? null;
  });

  const total = claim.refs.length;
  const text = claim.requirementText.trim();

  return (
    <div className="cv-trace-claim">
      <div className="cv-trace-claim-head">
        <span className="cv-trace-claim-label">核验条目 · {claim.label}</span>
        {claim.mandatory && <MandatoryMark full />}
        {claim.highRisk && !claim.mandatory && <RiskMark />}
        <span className="cv-trace-claim-title">{claim.title}</span>
      </div>

      {text && (
        <p className={expanded ? "cv-trace-claim-text is-open" : "cv-trace-claim-text"}>
          {text}
          <button
            type="button"
            className="cv-trace-claim-toggle"
            aria-expanded={expanded}
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? "收起" : "展开"}
          </button>
        </p>
      )}

      <div className="cv-trace-claim-foot">
        {row && (
          <ItemActions
            row={row}
            busy={busyItemId === row.item_id}
            error={actionErr?.id === row.item_id ? actionErr.msg : null}
            onConfirm={() => confirm(row.item_id)}
            onSetStatus={(status) => setStatus(row.item_id, status)}
          />
        )}
        {total > 1 && (
          <div className="cv-trace-step" role="group" aria-label="来源步进">
            <span>
              第 {claim.refIndex + 1}/{total} 条来源
            </span>
            <button type="button" aria-label="上一条来源" onClick={() => trace?.stepSource(-1)}>
              <ChevronLeftIcon width={13} height={13} />
            </button>
            <button type="button" aria-label="下一条来源" onClick={() => trace?.stepSource(1)}>
              <ChevronRightIcon width={13} height={13} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/** 预览层外壳:遮罩 + 标题栏 + 对照条 + 正文舞台。
 *  onRequestClose 由抽屉下发(退场动画 + 清溯源状态在那边收口)。 */
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
      gsap.from(".cv-trace-modal-scrim", { autoAlpha: 0, duration: DUR_FLOAT, ease: TRACE_EASE_ENTER });
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
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus({ preventScroll: true });
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        rootRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [],
      ).filter((el) => el.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
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
    <div ref={rootRef} className="cv-trace-modal">
      {/* 遮罩只做纯色调光:下方是玻璃浮件,scrim 再做 backdrop blur 即「玻璃叠玻璃」。
          调光色走 CSS 的 token 派生(--label 24%),暗色下随外观换挡。 */}
      <div className="cv-trace-modal-scrim" onPointerDown={onScrimDown} />
      <div
        className="cv-trace-modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className="cv-trace-modal-head">
          <FileIcon width={15} height={15} aria-hidden />
          <span className="cv-trace-title" id={titleId} title={doc.path}>
            {prettyLabel(doc.path.split("/").pop() ?? doc.path)}
          </span>
          <button
            ref={closeRef}
            type="button"
            className="cv-trace-close"
            aria-label="关闭原文预览"
            onClick={onRequestClose}
          >
            <XIcon width={15} height={15} />
          </button>
        </div>
        {claim && <ClaimBar claim={claim} />}
        <TracePanel doc={doc} arrival={DUR_PANEL} />
      </div>
    </div>
  );
}
