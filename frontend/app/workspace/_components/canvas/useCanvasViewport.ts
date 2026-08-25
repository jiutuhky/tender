"use client";

import { useCallback, useEffect, useRef, type MutableRefObject, type PointerEvent as ReactPointerEvent } from "react";
import { gsap } from "gsap";
import { DUR_FLOAT, TRACE_EASE_ENTER } from "./traceMotion";

// 画布视口：背景拖拽=平移；卡片拖拽=移动该卡（startCardDrag 由卡片 onPointerDown 触发）；
// 滚轮=以光标为锚缩放；缩放按钮/适应/重置=gsap 平滑过渡。
// 平移/缩放写在 worldRef.transform（命令式、不进 React state）；卡片位移上抛宿主写入 cards state。

export interface WorldRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** 相机运镜节拍覆盖(与卡片编排动画同拍时传入,缺省为 float 档 + 品牌标准缓动) */
export interface CameraMotion {
  duration?: number;
  /** gsap 缓动:字符串名或 CustomEase 产出的缓动函数(traceMotion 的品牌曲线) */
  ease?: string | gsap.EaseFunction;
}

interface ViewportOpts {
  /** 取卡片当前 world 坐标（拖拽起点基准） */
  getCard: (id: string) => { x: number; y: number } | undefined;
  /** 卡片拖动中持续上抛新坐标 */
  onCardMove: (id: string, x: number, y: number) => void;
  /** 卡片按下未拖动 → 视为点击（打开抽屉） */
  onCardClick: (id: string) => void;
  /** 空白处点击（未拖动） */
  onBackgroundClick?: () => void;
  /** 内容包围盒（world 坐标），供「适应」计算 */
  boundsRef?: MutableRefObject<WorldRect>;
}

// 下限 0.2:停靠列 world 高约 1024px,矮视口(≥333px)也要保证「适应」能整列放下。
// 手动缩放与适应共用同一下限——若手动下限更高,适应到更小比例后首次滚轮会被 clamp 强行跳档。
const MIN_SCALE = 0.2;
const MAX_SCALE = 1.4;
const DEFAULT_VIEW = { tx: 30, ty: 50, scale: 0.72 };
/** pointerdown 不视作「拖背景平移」：卡片/主轴自处理拖拽，浮层是 chrome。 */
const PAN_IGNORE = ".cv-card, .cv-spine, .cv-zoom, .cv-dock, .cv-drawer, .cv-msgwin, .cv-agentboard";
/** wheel 不视作「缩放画布」：只有自带滚动容器/输入的浮层。卡片与主轴仍属画布世界，
 *  悬停其上滚轮照常缩放——所以这两张名单不能合并。 */
const WHEEL_IGNORE = ".cv-zoom, .cv-dock, .cv-drawer, .cv-msgwin, .cv-agentboard";

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const prefersReduced = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

type Drag =
  | { type: "pan"; sx: number; sy: number; ox: number; oy: number; moved: boolean }
  | { type: "card"; id: string; sx: number; sy: number; ox: number; oy: number; moved: boolean };

export function useCanvasViewport(opts: ViewportOpts) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const worldRef = useRef<HTMLDivElement>(null);
  const zoomLabelRef = useRef<HTMLSpanElement>(null);

  const view = useRef({ ...DEFAULT_VIEW });
  const drag = useRef<Drag | null>(null);
  // 用户是否已主动操作过视图（平移/缩放/拖卡）。在此之前自动适应，之后不再打扰。
  const touchedRef = useRef(false);
  const tweenRef = useRef<gsap.core.Tween | null>(null);
  const optsRef = useRef(opts);
  useEffect(() => {
    optsRef.current = opts;
  });

  const apply = useCallback(() => {
    const w = worldRef.current;
    if (w) {
      const { tx, ty, scale } = view.current;
      w.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
    }
    // 视口的网格点背景跟随平移/缩放（见 globals.css .canvas-viewport 注释）
    const vp = viewportRef.current;
    if (vp) {
      const { tx, ty, scale } = view.current;
      // 点阵间距随缩放；缩得太小时间距翻倍，避免密成一片
      let gap = 24 * scale;
      while (gap < 12) gap *= 2;
      vp.style.setProperty("--cv-grid-size", `${gap}px`);
      vp.style.setProperty("--cv-grid-x", `${tx}px`);
      vp.style.setProperty("--cv-grid-y", `${ty}px`);
    }
    if (zoomLabelRef.current) zoomLabelRef.current.textContent = `${Math.round(view.current.scale * 100)}%`;
  }, []);

  const setScaleAnchored = useCallback(
    (next: number, ax: number, ay: number) => {
      const ns = clamp(next, MIN_SCALE, MAX_SCALE);
      const { tx, ty, scale } = view.current;
      view.current = { scale: ns, tx: ax - (ax - tx) * (ns / scale), ty: ay - (ay - ty) * (ns / scale) };
      apply();
    },
    [apply],
  );

  const animateTo = useCallback(
    (target: { tx: number; ty: number; scale: number }, instant = false, motion?: CameraMotion) => {
      tweenRef.current?.kill();
      if (instant || prefersReduced()) {
        view.current = { ...target };
        apply();
        return;
      }
      const proxy = { ...view.current };
      tweenRef.current = gsap.to(proxy, {
        ...target,
        duration: motion?.duration ?? DUR_FLOAT,
        ease: motion?.ease ?? TRACE_EASE_ENTER,
        onUpdate: () => {
          view.current = { tx: proxy.tx, ty: proxy.ty, scale: proxy.scale };
          apply();
        },
      });
    },
    [apply],
  );

  const zoomByCenter = useCallback(
    (factor: number, instant = false) => {
      touchedRef.current = true;
      const vp = viewportRef.current;
      if (!vp) return;
      const r = vp.getBoundingClientRect();
      const ax = r.width / 2;
      const ay = r.height / 2;
      const { tx, ty, scale } = view.current;
      const ns = clamp(scale * factor, MIN_SCALE, MAX_SCALE);
      animateTo({ scale: ns, tx: ax - (ax - tx) * (ns / scale), ty: ay - (ay - ty) * (ns / scale) }, instant);
    },
    [animateTo],
  );

  const zoomIn = useCallback((instant = false) => zoomByCenter(1.2, instant), [zoomByCenter]);
  const zoomOut = useCallback((instant = false) => zoomByCenter(1 / 1.2, instant), [zoomByCenter]);

  const fit = useCallback((instant = false, motion?: CameraMotion) => {
    touchedRef.current = false;
    const vp = viewportRef.current;
    if (!vp) return;
    const r = vp.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return;
    const b = optsRef.current.boundsRef?.current ?? { x: 0, y: 0, w: 800, h: 600 };
    const pad = 64;
    const w = Math.max(b.w, 1);
    const h = Math.max(b.h, 1);
    const s = clamp(Math.min((r.width - pad * 2) / w, (r.height - pad * 2) / h), MIN_SCALE, 1);
    animateTo({ scale: s, tx: (r.width - w * s) / 2 - b.x * s, ty: (r.height - h * s) / 2 - b.y * s }, instant, motion);
  }, [animateTo]);

  const resetView = useCallback((instant = false) => {
    touchedRef.current = false;
    animateTo({ ...DEFAULT_VIEW }, instant);
  }, [animateTo]);

  /** 当前视口中心对应的 world 坐标（新卡落点用） */
  const centerWorld = useCallback((): { x: number; y: number } => {
    const vp = viewportRef.current;
    const { tx, ty, scale } = view.current;
    if (!vp) return { x: (-tx + 400) / scale, y: (-ty + 200) / scale };
    const r = vp.getBoundingClientRect();
    return { x: (r.width / 2 - tx) / scale, y: (r.height / 2 - ty) / scale };
  }, []);

  const startCardDrag = useCallback((id: string, e: ReactPointerEvent) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    const c = optsRef.current.getCard(id);
    if (!c) return;
    touchedRef.current = true;
    // 相机 tween 让位于手:不打断则 onUpdate 每帧覆写 view,拖卡期间画布仍在自走
    tweenRef.current?.kill();
    drag.current = { type: "card", id, sx: e.clientX, sy: e.clientY, ox: c.x, oy: c.y, moved: false };
    document.body.style.cursor = "grabbing";
    document.body.style.userSelect = "none";
  }, []);

  // 全局指针监听（卡片拖出视口也能跟手）+ 视口平移/缩放
  useEffect(() => {
    const vp = viewportRef.current;
    if (!vp) return;
    apply();

    const onViewportDown = (e: PointerEvent) => {
      if (e.button !== 0) return;
      const target = e.target as HTMLElement;
      if (target.closest(PAN_IGNORE)) return;
      touchedRef.current = true;
      // 平移起手即打断进行中的相机 tween,否则 onUpdate 每帧覆写用户输入
      tweenRef.current?.kill();
      drag.current = { type: "pan", sx: e.clientX, sy: e.clientY, ox: view.current.tx, oy: view.current.ty, moved: false };
      vp.classList.add("is-panning");
      document.body.style.userSelect = "none";
    };

    const onMove = (e: PointerEvent) => {
      const d = drag.current;
      if (!d) return;
      const dx = e.clientX - d.sx;
      const dy = e.clientY - d.sy;
      if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
      if (d.type === "pan") {
        view.current.tx = d.ox + dx;
        view.current.ty = d.oy + dy;
        apply();
      } else {
        const s = view.current.scale;
        optsRef.current.onCardMove(d.id, d.ox + dx / s, d.oy + dy / s);
      }
    };

    const onUp = () => {
      const d = drag.current;
      drag.current = null;
      vp.classList.remove("is-panning");
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      if (!d) return;
      if (!d.moved) {
        if (d.type === "card") optsRef.current.onCardClick(d.id);
        else optsRef.current.onBackgroundClick?.();
      }
    };

    const onWheel = (e: WheelEvent) => {
      // 浮层（消息浮窗 / 底部坞输入区 / 抽屉正文）自带滚动：放行原生滚动，既不
      // preventDefault 也不缩放。此前无条件 preventDefault，导致抽屉正文根本滚不动、
      // 反而把画布缩了。用 instanceof Element 而非断言：SVG 子节点是 SVGElement，同样有 closest。
      const t = e.target;
      if (t instanceof Element && t.closest(WHEEL_IGNORE)) return;
      e.preventDefault();
      touchedRef.current = true;
      tweenRef.current?.kill();
      const r = vp.getBoundingClientRect();
      const factor = 1 - e.deltaY * 0.0012;
      setScaleAnchored(view.current.scale * factor, e.clientX - r.left, e.clientY - r.top);
    };

    vp.addEventListener("pointerdown", onViewportDown);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    vp.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      vp.removeEventListener("pointerdown", onViewportDown);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      vp.removeEventListener("wheel", onWheel);
      tweenRef.current?.kill();
    };
  }, [apply, setScaleAnchored]);

  // 自动适应：视口尺寸变化时（含挂载首测、分隔条拖拽）适应内容——直到用户主动操作视图为止。
  useEffect(() => {
    const vp = viewportRef.current;
    if (!vp || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => {
      if (!touchedRef.current) fit(true);
    });
    ro.observe(vp);
    return () => ro.disconnect();
  }, [fit]);

  return { viewportRef, worldRef, zoomLabelRef, startCardDrag, zoomIn, zoomOut, fit, resetView, centerWorld };
}
