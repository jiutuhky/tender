"use client";

import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { IconTile, StatusBadge } from "./bits";
import { CardDetail, type DetailType } from "./CardDetail";
import { META, isMatrixCardType, type CardType } from "./cardMeta";
import { TraceContext, useTraceState } from "./traceContext";
import { TracePanel } from "./TracePanel";
import { DUR_FLOAT, DUR_PANEL, TRACE_EASE_ENTER, TRACE_EASE_EXIT, prefersReducedMotion } from "./traceMotion";
import type { CardBadge } from "./ArtifactCard";
import { ChevronLeftIcon, DotsThreeIcon, DownloadIcon, RefreshIcon, XIcon } from "@/components/ui/icons";

// 右侧抽屉：点击制品卡 / 主轴行后从右滑入，承载完整详情 + 制品动作。
// 滑入 / 遮罩淡入走 gsap（不手写 keyframes）。遮罩点击、关闭钮、Esc 同走快速镜像退出。
// 真实矩阵卡的人工动作(确认/应答状态标注)在详情条目行内(matrixViews.ItemActions),
// 不设底部动作条;mock 卡沿用原型的静态按钮组(演示面,不动)。
//
// 溯源预览(票02-05):矩阵卡详情点来源签后抽屉加宽为对照双栏(左原文面板/右条目列表)。
// 「加宽 + 滑入」的 transform-only 编排(票05):主列(.cv-drawer-main,头+列表)恒定
// 548px 不重排,panel 容器本身透明无投影;原文面板自带表面材质与左投影,从主列
// 后方(z 序更低)滑出到位——投影随面板左缘行进,视觉上即「抽屉左缘连续生长」,
// 加宽与滑入天然是同一次连续到场,全程只动 transform。退出走原路、缓动互为镜像。
// 动画不锁输入:动画中点其他签只切换定位;退出中重开从当前呈现值滑回(gsap
// overwrite 覆盖旧 tween),无跳变。窄屏(抽屉容器实测 <1000px,含分隔条拖窄画布)
// 降级为抽屉内二级视图:返回条 + 原文面板,返回时恢复列表滚动位置。
// 溯源状态挂本组件,关抽屉即整体重置。Esc 语义定稿:一步关抽屉(不分层退面板),
// 面板关闭走显式按钮(双栏为面板头 X,窄屏为「返回条目」)。

/** 双栏可用的最小容器宽:低于此宽度双栏各剩 <500px,对照阅读双输,降级二级视图 */
const DUAL_MIN_WIDTH = 1000;

/** 双栏模式的原文面板(panel 直接子级;窄屏二级视图内的面板不参与滑入编排) */
const DUAL_PANE_SELECTOR = ".cv-drawer-panel > .cv-trace-pane";

interface CanvasDrawerProps {
  type: DetailType;
  cardType: CardType;
  title: string;
  onClose: () => void;
  badge?: CardBadge;
  skipEntrance?: boolean;
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

  const [narrow, setNarrow] = useState(false);
  const narrowRef = useRef(false);
  /** 面板退场动画进行中:此窗口内再点签要从当前呈现值滑回(重定向),而非重新入场 */
  const traceClosingRef = useRef(false);
  /** 最近一次活跃签身份:面板关闭后焦点回到发起签,焦点圈不因卸载散落 */
  const lastChipKeyRef = useRef<string | null>(null);
  const listScrollRef = useRef(0);

  const dualShown = !narrow && activeDoc !== null;
  const secondaryShown = narrow && activeDoc !== null;

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);
  useEffect(() => {
    if (traceCtx.activeKey) lastChipKeyRef.current = traceCtx.activeKey;
  }, [traceCtx.activeKey]);

  // 窄屏判定按抽屉容器实测宽度(非全局视口):分隔条把画布拖窄同样触发降级
  useLayoutEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const update = () => {
      const isNarrow = root.clientWidth < DUAL_MIN_WIDTH;
      narrowRef.current = isNarrow;
      setNarrow(isNarrow);
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(root);
    return () => ro.disconnect();
  }, []);

  useGSAP(
    () => {
      if (skipEntrance || prefersReducedMotion()) return;
      gsap.from(".cv-drawer-scrim", { autoAlpha: 0, duration: 0.16, ease: "power2.out" });
      gsap.from(".cv-drawer-panel", { xPercent: 100, duration: 0.26, ease: "power3.out" });
    },
    { scope: rootRef, dependencies: [skipEntrance] },
  );

  // 面板/二级视图到场:仅在「未呈现 → 呈现」沿触发一次;之后切签/跨文档面板常驻不重演。
  // 双栏面板从主列后方滑出(x: 面板宽 → 0),窄屏二级视图用 float 档轻浮入(位移 ≤8px)。
  const prevDualRef = useRef(false);
  const prevSecondaryRef = useRef(false);
  useGSAP(
    () => {
      const root = rootRef.current;
      if (dualShown && !prevDualRef.current) {
        const pane = root?.querySelector<HTMLElement>(DUAL_PANE_SELECTOR);
        if (pane && !prefersReducedMotion()) {
          gsap.fromTo(
            pane,
            { x: pane.offsetWidth },
            { x: 0, duration: DUR_PANEL, ease: TRACE_EASE_ENTER, overwrite: "auto" },
          );
        }
      }
      if (secondaryShown && !prevSecondaryRef.current) {
        const secondary = root?.querySelector<HTMLElement>(".cv-trace-secondary");
        if (secondary && !prefersReducedMotion()) {
          gsap.fromTo(
            secondary,
            { x: 8, autoAlpha: 0 },
            { x: 0, autoAlpha: 1, duration: DUR_FLOAT, ease: TRACE_EASE_ENTER, overwrite: "auto" },
          );
        }
      }
      prevDualRef.current = dualShown;
      prevSecondaryRef.current = secondaryShown;
    },
    { scope: rootRef, dependencies: [dualShown, secondaryShown] },
  );

  // 可打断重定向:面板退场中用户再点签(activeSeq 递增),杀退场 tween、
  // 从当前呈现值滑回到位——动画从 presentation value 出发,无跳变(apple-design)。
  useEffect(() => {
    if (!traceClosingRef.current) return;
    traceClosingRef.current = false;
    const pane = rootRef.current?.querySelector<HTMLElement>(DUAL_PANE_SELECTOR);
    if (pane) gsap.to(pane, { x: 0, duration: DUR_PANEL, ease: TRACE_EASE_ENTER, overwrite: "auto" });
  }, [traceCtx.activeSeq]);

  // 窄屏二级视图接管抽屉体时列表隐藏:隐藏前存滚动位置,返回后原位恢复。
  // 用 layout effect 直改 display(而非渲染态):读 scrollTop 必须发生在隐藏之前。
  useLayoutEffect(() => {
    const body = bodyRef.current;
    if (!body) return;
    if (secondaryShown) {
      listScrollRef.current = body.scrollTop;
      body.style.display = "none";
    } else if (body.style.display === "none") {
      body.style.display = "";
      body.scrollTop = listScrollRef.current;
    }
  }, [secondaryShown]);

  // 面板关闭(显式按钮/返回条)后焦点回发起签:卸载会让焦点散落到 body,焦点圈断裂
  const prevTraceShownRef = useRef(false);
  useEffect(() => {
    const shown = activeDoc !== null;
    if (!shown && prevTraceShownRef.current) {
      const active = document.activeElement;
      if (active === document.body || (active instanceof HTMLElement && rootRef.current?.contains(active) === false)) {
        const key = lastChipKeyRef.current;
        const chip = key
          ? rootRef.current?.querySelector<HTMLElement>(`[data-chip-key="${CSS.escape(key)}"]`)
          : null;
        // preventScroll:窄屏返回刚恢复完列表滚动位置,聚焦的默认滚动会把它再次拉走
        (chip ?? closeRef.current)?.focus({ preventScroll: true });
      }
    }
    prevTraceShownRef.current = shown;
  }, [activeDoc]);

  /** 面板关闭收口:先演退场(路径与缓动为入场镜像)再清溯源状态;reduced-motion 即时。
   *  经 context 覆盖 closeTrace 下发,面板头 X 与窄屏返回条走的都是这一条。 */
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
    if (narrowRef.current) {
      const secondary = root?.querySelector<HTMLElement>(".cv-trace-secondary");
      if (!secondary) {
        closeTraceRef.current();
        return;
      }
      // 与入场同为 float 档:窄屏二级视图的进出节奏也保持镜像对称
      gsap.to(secondary, {
        x: 8,
        autoAlpha: 0,
        duration: DUR_FLOAT,
        ease: TRACE_EASE_EXIT,
        overwrite: "auto",
        onComplete: () => closeTraceRef.current(),
      });
      return;
    }
    const pane = root?.querySelector<HTMLElement>(DUAL_PANE_SELECTOR);
    if (!pane) {
      closeTraceRef.current();
      return;
    }
    traceClosingRef.current = true;
    gsap.to(pane, {
      x: pane.offsetWidth,
      duration: DUR_PANEL,
      ease: TRACE_EASE_EXIT,
      overwrite: "auto",
      onComplete: () => {
        traceClosingRef.current = false;
        closeTraceRef.current();
      },
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
    gsap.to(scrim, { autoAlpha: 0, duration: 0.12, ease: "power2.out" });
    gsap.to(panel, {
      xPercent: 100,
      duration: 0.18,
      ease: "power2.out",
      onComplete: () => onCloseRef.current(),
    });
  }, []);

  useEffect(() => {
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus({ preventScroll: true });

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        // Esc 与鼠标关同走退场动画:出口路径一致(语义仍是一步关抽屉)
        requestClose();
        return;
      }
      if (event.key !== "Tab") return;
      // 只计可见元素:窄屏二级视图把条目列表 display:none(签仍在 DOM),
      // 不过滤则 first/last 可能落在不可聚焦节点上,Tab 在边界处逃出抽屉
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
  }, [requestClose]);

  return (
    <div ref={rootRef} className="cv-drawer">
      {/* 背景模糊随原型走内联（构建期 Lightning CSS 会剥离样式表里的 backdrop-filter，内联可保留） */}
      <div
        className="cv-drawer-scrim"
        onPointerDown={requestClose}
        style={{ backdropFilter: "blur(2px)", WebkitBackdropFilter: "blur(2px)" }}
      />
      <div
        className={dualShown ? "cv-drawer-panel is-trace" : "cv-drawer-panel"}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <TraceContext.Provider value={providedCtx}>
          {dualShown && activeDoc && <TracePanel doc={activeDoc} arrival={DUR_PANEL} />}
          <div className="cv-drawer-main">
            <div className="cv-drawer-head">
              <IconTile icon={m.icon} />
              <div className="cv-drawer-titlebox">
                <div className="cv-drawer-title" id={titleId}>{title}</div>
                <div className="cv-drawer-sub">{m.stage} · 产物</div>
              </div>
              <StatusBadge sc={badge?.sc ?? m.sc} label={badge?.label ?? m.status} />
              <button ref={closeRef} type="button" className="cv-drawer-close" aria-label="关闭" onClick={requestClose}>
                <XIcon width={16} height={16} />
              </button>
            </div>

            <div className="cv-drawer-body" ref={bodyRef}>
              <CardDetail type={type} />
            </div>

            {secondaryShown && activeDoc && (
              <div className="cv-trace-secondary">
                <button type="button" className="cv-trace-back" onClick={requestTraceClose}>
                  <ChevronLeftIcon width={14} height={14} />
                  返回条目
                </button>
                <TracePanel doc={activeDoc} arrival={DUR_FLOAT} />
              </div>
            )}

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
        </TraceContext.Provider>
      </div>
    </div>
  );
}
