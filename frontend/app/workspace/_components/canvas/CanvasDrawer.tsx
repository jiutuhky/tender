"use client";

import { useCallback, useEffect, useId, useMemo, useRef } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { IconTile, StatusBadge } from "./bits";
import { CardDetail, type DetailType } from "./CardDetail";
import { META, isMatrixCardType, type CardType } from "./cardMeta";
import { useMatrixDetailSummary } from "./matrixViews";
import { TraceContext, useTraceState } from "./traceContext";
import { TraceModal } from "./TraceModal";
import { DUR_FLOAT, DUR_MICRO, DUR_PANEL, TRACE_EASE_ENTER, TRACE_EASE_EXIT, prefersReducedMotion } from "./traceMotion";
import type { CardBadge } from "./ArtifactCard";
import { DotsThreeIcon, DownloadIcon, RefreshIcon, XIcon } from "@/components/ui/icons";

// 右侧抽屉：点击制品卡 / 主轴行后从右滑入，承载完整详情 + 制品动作。
// 滑入 / 遮罩淡入走 gsap（不手写 keyframes）。遮罩点击、关闭钮、Esc 同走快速镜像退出。
// 真实矩阵卡的人工动作(确认/应答状态标注)在详情条目行内(matrixViews.ItemActions),
// 不设底部动作条;mock 卡沿用原型的静态按钮组(演示面,不动)。
//
// 溯源预览:矩阵卡详情点来源签后,打开盖满画布的原文预览层(TraceModal)。
// 抽屉留在层后不卸载,退层即回到条目列表原样(含滚动位置)。
// 溯源状态挂本组件,关抽屉即整体重置。
//
// 键盘归属(两层浮层,必须写明):
//   Esc —— 逐层退。判定收在本组件的单一 window 处理器里:预览层开着就先退层,
//          否则关抽屉。不拆成两个监听器,因为同节点上 stopPropagation 拦不住彼此。
//   Tab —— 同一时刻只允许一个焦点陷阱。预览层开着时本组件的陷阱短路让位,
//          由 TraceModal 装自己的;否则焦点会在被浮层盖住的抽屉按钮上打转。

interface CanvasDrawerProps {
  type: DetailType;
  cardType: CardType;
  title: string;
  onClose: () => void;
  badge?: CardBadge;
  skipEntrance?: boolean;
}

/** 矩阵抽屉的标题栏:线性图标 + 标题 + 摘要,不发终态徽标。
 *  摘要(共 26 条 · 实质性 11 项)由详情正文上提到头里 —— 正文再写一遍矩阵名与摘要
 *  就是同一件事说两遍。非终态时副标题让位给状态文案。 */
function MatrixDrawerHead({
  type,
  title,
  titleId,
  badge,
}: {
  type: ReturnType<typeof matrixTypeOf>;
  title: string;
  titleId: string;
  badge?: CardBadge;
}) {
  const summary = useMatrixDetailSummary(type);
  const m = META[type];
  const Icon = m.icon;
  const sub = badge && badge.tone !== "done" ? badge.label : summary;
  return (
    <>
      <Icon width={17} height={17} style={{ color: "var(--label-3)", flex: "0 0 auto" }} />
      <div className="cv-drawer-titlebox">
        <div className="cv-drawer-title" id={titleId}>{title}</div>
        {sub && <div className="cv-drawer-sub">{sub}</div>}
      </div>
    </>
  );
}

/** 收窄 CardType → MatrixType 的类型出口(调用点已用 isMatrixCardType 守卫过) */
function matrixTypeOf(t: CardType) {
  return t as Extract<CardType, "basic_info" | "business" | "technical" | "scoring">;
}

export function CanvasDrawer({ type, cardType, title, onClose, badge, skipEntrance = false }: CanvasDrawerProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const closingRef = useRef(false);
  const onCloseRef = useRef(onClose);
  const titleId = useId();
  const m = META[cardType];
  const { ctx: traceCtx, activeDoc } = useTraceState(isMatrixCardType(cardType));

  const traceShown = activeDoc !== null;
  /** Esc / Tab 处理器读的是 ref(监听器只装一次,不随开合重挂) */
  const traceShownRef = useRef(false);
  /** 最近一次活跃签身份:预览层关闭后焦点回到发起签,焦点圈不因卸载散落 */
  const lastChipKeyRef = useRef<string | null>(null);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);
  useEffect(() => {
    traceShownRef.current = traceShown;
  }, [traceShown]);
  useEffect(() => {
    if (traceCtx.activeKey) lastChipKeyRef.current = traceCtx.activeKey;
  }, [traceCtx.activeKey]);

  useGSAP(
    () => {
      if (skipEntrance || prefersReducedMotion()) return;
      gsap.from(".cv-drawer-scrim", { autoAlpha: 0, duration: DUR_MICRO, ease: TRACE_EASE_ENTER });
      gsap.from(".cv-drawer-panel", { xPercent: 100, duration: DUR_PANEL, ease: TRACE_EASE_ENTER });
    },
    { scope: rootRef, dependencies: [skipEntrance] },
  );

  // 预览层关闭后焦点回发起签:卸载会让焦点散落到 body,焦点圈断裂
  const prevTraceShownRef = useRef(false);
  useEffect(() => {
    if (!traceShown && prevTraceShownRef.current) {
      const active = document.activeElement;
      if (active === document.body || (active instanceof HTMLElement && rootRef.current?.contains(active) === false)) {
        const key = lastChipKeyRef.current;
        const chip = key
          ? rootRef.current?.querySelector<HTMLElement>(`[data-chip-key="${CSS.escape(key)}"]`)
          : null;
        (chip ?? closeRef.current)?.focus({ preventScroll: true });
      }
    }
    prevTraceShownRef.current = traceShown;
  }, [traceShown]);

  /** 预览层关闭收口:先演退场(与入场镜像)再清溯源状态;reduced-motion 即时。
   *  经 context 覆盖 closeTrace 下发,浮层头 X、遮罩点击、Esc 走的都是这一条。 */
  const closeTraceRef = useRef(traceCtx.closeTrace);
  useEffect(() => {
    closeTraceRef.current = traceCtx.closeTrace;
  }, [traceCtx.closeTrace]);
  const requestTraceClose = useCallback(() => {
    const root = rootRef.current;
    if (prefersReducedMotion()) {
      closeTraceRef.current();
      return;
    }
    const panel = root?.querySelector<HTMLElement>(".cv-trace-modal-panel");
    const scrim = root?.querySelector<HTMLElement>(".cv-trace-modal-scrim");
    if (!panel) {
      closeTraceRef.current();
      return;
    }
    if (scrim) gsap.to(scrim, { autoAlpha: 0, duration: DUR_MICRO, ease: TRACE_EASE_EXIT });
    gsap.to(panel, {
      autoAlpha: 0,
      scale: 0.98,
      duration: DUR_FLOAT,
      ease: TRACE_EASE_EXIT,
      overwrite: "auto",
      onComplete: () => closeTraceRef.current(),
    });
  }, []);

  const providedCtx = useMemo(
    () => ({ ...traceCtx, closeTrace: requestTraceClose }),
    [traceCtx, requestTraceClose],
  );

  /** 整抽屉退场:scrim 点击、关闭钮、Esc 三个入口共用同一次快速镜像退出 */
  const requestClose = useCallback(() => {
    if (closingRef.current) return;
    if (prefersReducedMotion()) {
      onCloseRef.current();
      return;
    }
    const root = rootRef.current;
    const scrim = root?.querySelector<HTMLElement>(".cv-drawer-scrim");
    const panel = root?.querySelector<HTMLElement>(".cv-drawer-panel");
    if (!scrim || !panel) {
      onCloseRef.current();
      return;
    }
    closingRef.current = true;
    gsap.to(scrim, { autoAlpha: 0, duration: DUR_MICRO, ease: TRACE_EASE_EXIT });
    gsap.to(panel, {
      xPercent: 100,
      duration: DUR_FLOAT,
      ease: TRACE_EASE_EXIT,
      onComplete: () => onCloseRef.current(),
    });
  }, []);

  useEffect(() => {
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus({ preventScroll: true });

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        // 逐层退:预览层开着先退层,再按一次才关抽屉
        if (traceShownRef.current) {
          requestTraceClose();
          return;
        }
        requestClose();
        return;
      }
      if (event.key !== "Tab") return;
      // 预览层开着时把 Tab 让给它自己的陷阱,否则焦点会落到被盖住的抽屉按钮上
      if (traceShownRef.current) return;
      const focusable = Array.from(
        rootRef.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
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
      previousFocusRef.current?.focus({ preventScroll: true });
    };
  }, [requestClose, requestTraceClose]);

  return (
    <div ref={rootRef} className="cv-drawer">
      {/* 遮罩只做纯色调光:下方画布上浮着玻璃面(消息窗/看板/药丸),scrim 再上
          backdrop blur 就是「玻璃叠玻璃」。调光色走 CSS 的 token 派生(--label 24%)。 */}
      <div className="cv-drawer-scrim" onPointerDown={requestClose} />
      <TraceContext.Provider value={providedCtx}>
        <div
          className="cv-drawer-panel"
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
        >
          <div className="cv-drawer-main">
            <div className="cv-drawer-head">
              {isMatrixCardType(cardType) ? (
                <MatrixDrawerHead type={matrixTypeOf(cardType)} title={title} titleId={titleId} badge={badge} />
              ) : (
                <>
                  <IconTile icon={m.icon} />
                  <div className="cv-drawer-titlebox">
                    <div className="cv-drawer-title" id={titleId}>{title}</div>
                    <div className="cv-drawer-sub">{m.stage} · 产物</div>
                  </div>
                  <StatusBadge sc={badge?.sc ?? m.sc} label={badge?.label ?? m.status} />
                </>
              )}
              <button ref={closeRef} type="button" className="cv-drawer-close" aria-label="关闭" onClick={requestClose}>
                <XIcon width={16} height={16} />
              </button>
            </div>

            <div className="cv-drawer-body" ref={bodyRef}>
              <CardDetail type={type} />
            </div>

            {!isMatrixCardType(cardType) && (
              <div className="cv-drawer-foot">
                <button type="button" className="cv-drawer-btn primary">
                  <DownloadIcon width={15} height={15} />
                  插入到文档
                </button>
                <button type="button" className="cv-drawer-btn">
                  <RefreshIcon width={15} height={15} />
                  重新生成
                </button>
                <span style={{ flex: 1 }} />
                <button type="button" className="cv-drawer-btn icon" aria-label="更多">
                  <DotsThreeIcon width={17} height={17} />
                </button>
              </div>
            )}
          </div>
        </div>
        {activeDoc && <TraceModal doc={activeDoc} onRequestClose={requestTraceClose} />}
      </TraceContext.Provider>
    </div>
  );
}
