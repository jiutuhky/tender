"use client";

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import "./reading-detail.css";
import { CardDetail, type DetailType } from "./CardDetail";
import { META, isMatrixCardType, type CardType } from "./cardMeta";
import { TraceContext, useTraceState } from "./traceContext";
import { TraceModal } from "./TraceModal";
import {
  DUR_FLOAT,
  DUR_MICRO,
  DUR_PANEL,
  TRACE_EASE_ENTER,
  TRACE_EASE_EXIT,
  prefersReducedMotion,
} from "./traceMotion";
import type { CardBadge } from "./ArtifactCard";
import { FrameIcon, XIcon } from "@/components/ui/icons";

// 右侧抽屉：点击制品卡 / 主轴行后从右滑入，承载完整详情 + 制品动作。
// 滑入 / 遮罩淡入走 gsap（不手写 keyframes）。遮罩点击、关闭钮、Esc 同走快速镜像退出。
// 真实矩阵卡的人工动作(确认/应答状态标注)在详情条目行内(detailShared.ItemActions),
// 核验操作仅在展开的条目中呈现；演示卡沿用展示内容。
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
  children?: ReactNode;
  spatial?: boolean;
  origin?: { x: number; y: number; w: number; h: number };
  subtitle?: string;
}

/** 固定标题与阅读提示；事实摘要留在正文，避免重复。 */
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
  const sub =
    badge && badge.tone !== "done"
      ? badge.label
      : type === "basic_info"
        ? "采购事实与关键时间"
        : type === "scoring"
          ? "评审标准与计分依据"
          : "招标要求与原文依据";
  return (
    <>
      <div className="cv-drawer-titlebox">
        <div className="cv-drawer-title" id={titleId}>
          {title}
        </div>
        {sub && <div className="cv-drawer-sub">{sub}</div>}
      </div>
    </>
  );
}

/** 收窄 CardType → MatrixType 的类型出口(调用点已用 isMatrixCardType 守卫过) */
function matrixTypeOf(t: CardType) {
  return t as Extract<
    CardType,
    "basic_info" | "business" | "technical" | "scoring"
  >;
}

export function CanvasDrawer({
  type,
  cardType,
  title,
  onClose,
  badge,
  skipEntrance = false,
  children,
  spatial = false,
  origin,
  subtitle,
}: CanvasDrawerProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [focused, setFocused] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const closingRef = useRef(false);
  const onCloseRef = useRef(onClose);
  const originRef = useRef(origin);
  const titleId = useId();
  const m = META[cardType];
  const { ctx: traceCtx, activeDoc } = useTraceState(
    isMatrixCardType(cardType),
  );

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
      gsap.from(".cv-drawer-scrim", {
        autoAlpha: 0,
        duration: DUR_MICRO,
        ease: TRACE_EASE_ENTER,
      });
      const panel =
        rootRef.current?.querySelector<HTMLElement>(".cv-drawer-panel");
      const rect = panel?.getBoundingClientRect(),
        from = originRef.current;
      if (spatial && panel && rect && from)
        gsap.from(panel, {
          x: from.x + from.w / 2 - rect.left - rect.width / 2,
          y: from.y + from.h / 2 - rect.top - rect.height / 2,
          scaleX: from.w / rect.width,
          scaleY: from.h / rect.height,
          autoAlpha: 0.35,
          duration: 0.4,
          ease: "power3.out",
          clearProps: "transform,opacity,visibility",
        });
      else
        gsap.from(".cv-drawer-panel", {
          xPercent: spatial ? 0 : 100,
          autoAlpha: 0,
          duration: DUR_PANEL,
          ease: TRACE_EASE_ENTER,
        });
    },
    { scope: rootRef, dependencies: [skipEntrance, spatial] },
  );

  // 预览层关闭后焦点回发起签:卸载会让焦点散落到 body,焦点圈断裂
  const prevTraceShownRef = useRef(false);
  useEffect(() => {
    if (!traceShown && prevTraceShownRef.current) {
      const active = document.activeElement;
      if (
        active === document.body ||
        (active instanceof HTMLElement &&
          rootRef.current?.contains(active) === false)
      ) {
        const key = lastChipKeyRef.current;
        const chip = key
          ? rootRef.current?.querySelector<HTMLElement>(
              `[data-chip-key="${CSS.escape(key)}"]`,
            )
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
    if (scrim)
      gsap.to(scrim, {
        autoAlpha: 0,
        duration: DUR_MICRO,
        ease: TRACE_EASE_EXIT,
      });
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
    const from = originRef.current;
    const rect = panel.getBoundingClientRect();
    // 入场可能尚未结束：屏幕矩形包含当前位移和缩放，退场目标须
    // 换回同一个 transform 坐标系，才能从当前画面准确收回来源卡片。
    const currentX = Number(gsap.getProperty(panel, "x")) || 0;
    const currentY = Number(gsap.getProperty(panel, "y")) || 0;
    const currentScaleX = Number(gsap.getProperty(panel, "scaleX")) || 1;
    const currentScaleY = Number(gsap.getProperty(panel, "scaleY")) || 1;
    gsap.to(scrim, {
      autoAlpha: 0,
      duration: DUR_MICRO,
      ease: TRACE_EASE_EXIT,
    });
    gsap.to(panel, {
      ...(spatial && from
        ? {
            x: currentX + from.x + from.w / 2 - rect.left - rect.width / 2,
            y: currentY + from.y + from.h / 2 - rect.top - rect.height / 2,
            scaleX: (from.w / rect.width) * currentScaleX,
            scaleY: (from.h / rect.height) * currentScaleY,
            autoAlpha: 0,
          }
        : spatial
          ? { scale: 0.97, autoAlpha: 0 }
          : { xPercent: 100 }),
      duration: spatial ? DUR_PANEL : DUR_FLOAT,
      ease: TRACE_EASE_EXIT,
      overwrite: true,
      onComplete: () => onCloseRef.current(),
    });
  }, [spatial]);

  useEffect(() => {
    previousFocusRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
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
          'button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), summary, [tabindex]:not([tabindex="-1"])',
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

  const toggleReading = () => {
    const body = bodyRef.current;
    const top = body?.getBoundingClientRect().top ?? 0;
    const anchor = Array.from(
      body?.querySelectorAll<HTMLElement>("[data-reading-item]") ?? [],
    ).find((el) => el.getBoundingClientRect().bottom > top + 100);
    const offset = anchor ? anchor.getBoundingClientRect().top - top : 0;
    const scrollTop = body?.scrollTop ?? 0;
    setFocused((v) => !v);
    requestAnimationFrame(() => {
      if (!body) return;
      body.scrollTop = anchor
        ? body.scrollTop +
          anchor.getBoundingClientRect().top -
          body.getBoundingClientRect().top -
          offset
        : scrollTop;
    });
  };

  return (
    <div
      ref={rootRef}
      className={`cv-drawer${spatial ? " sp-reader-host" : ""}`}
      data-no-gesture
    >
      {/* 遮罩只做纯色调光:下方画布上浮着玻璃面(消息窗/看板/药丸),scrim 再上
          backdrop blur 就是「玻璃叠玻璃」。调光色走 CSS 的 token 派生(--label 24%)。 */}
      <div className="cv-drawer-scrim" onPointerDown={requestClose} />
      <TraceContext.Provider value={providedCtx}>
        <div
          className={`cv-drawer-panel${focused ? " is-focused" : ""}`}
          inert={traceShown}
          aria-hidden={traceShown || undefined}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
        >
          <div className="cv-drawer-main">
            <div className="cv-drawer-head">
              {isMatrixCardType(cardType) ? (
                <MatrixDrawerHead
                  type={matrixTypeOf(cardType)}
                  title={title}
                  titleId={titleId}
                  badge={badge}
                />
              ) : (
                <>
                  <div className="cv-drawer-titlebox">
                    <div className="cv-drawer-title" id={titleId}>
                      {title}
                    </div>
                    <div className="cv-drawer-sub">
                      {children
                        ? subtitle
                        : `${m.stage} · ${badge?.label ?? m.status}`}
                    </div>
                  </div>
                </>
              )}
              <button
                type="button"
                className="cv-drawer-focus"
                aria-pressed={focused}
                onClick={toggleReading}
              >
                <FrameIcon width={16} height={16} />
                <span>{focused ? "收起阅读" : "展开阅读"}</span>
              </button>
              <button
                ref={closeRef}
                type="button"
                className="cv-drawer-close"
                aria-label="关闭"
                onClick={requestClose}
              >
                <XIcon width={16} height={16} />
              </button>
            </div>

            <div className="cv-drawer-body" ref={bodyRef}>
              {traceCtx.registryStatus === "failed" &&
                isMatrixCardType(cardType) && (
                  <div className="cv-review-error" role="alert">
                    原文索引加载失败，条目仍可阅读。
                    <button type="button" onClick={traceCtx.retryRegistry}>
                      重新加载原文
                    </button>
                  </div>
                )}
              {children ?? <CardDetail type={type} />}
            </div>

            {!isMatrixCardType(cardType) && !children && (
              <div className="cv-drawer-foot">
                演示产物 · 展示信息结构，不写入真实项目。
              </div>
            )}
          </div>
        </div>
        {activeDoc && (
          <TraceModal doc={activeDoc} onRequestClose={requestTraceClose} />
        )}
      </TraceContext.Provider>
    </div>
  );
}
