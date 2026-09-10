"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import {
  bounds,
  clamp,
  intersects,
  handoffAnchorOffset,
  resizeRect,
  worldPoint,
  type Camera,
  type CanvasPlacement,
  type Point,
  type Rect,
  type CardTransform,
} from "@/lib/canvas/model";

type Gesture = {
  pointer: number;
  kind: "pan" | "move" | "resize" | "select";
  start: Point;
  last: Point;
  camera: Camera;
  moved: boolean;
  time: number;
  velocity: number;
  items: CanvasPlacement[];
  corner: string;
  additive: boolean;
  initialSelection: string[];
  originals: CanvasPlacement[];
  elements: Map<string, HTMLElement>;
  handoffs: Map<string, { matrix: CardTransform; offset: Point }>;
};
interface Options {
  items: CanvasPlacement[];
  selection: string[];
  setSelection: (ids: string[]) => void;
  isMedia: (id: string) => boolean;
  canDrop: (ids: string[], targetId: string) => boolean;
  onCommit: (items: CanvasPlacement[], dropId: string | null) => void;
  onCamera: (camera: Camera) => void;
  interactive: boolean;
}
const reduced = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** 相机与手势逐帧直接写 DOM；React 只接收完成的布局和低频裁剪窗口。 */
export function useSpatialGestures(options: Options) {
  const viewport = useRef<HTMLDivElement>(null),
    world = useRef<HTMLDivElement>(null),
    marquee = useRef<HTMLDivElement>(null);
  const camera = useRef<Camera>({ x: 60, y: 85, z: 0.75 });
  const [view, setView] = useState({
    ...camera.current,
    width: 1200,
    height: 700,
  });
  const latest = useRef(options),
    active = useRef<Gesture | null>(null),
    raf = useRef(0),
    space = useRef(false);
  const tween = useRef<gsap.core.Tween | null>(null),
    cullTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pending = useRef<CanvasPlacement[]>([]),
    drop = useRef<string | null>(null),
    pointers = useRef(new Map<number, Point>());
  const pinch = useRef<{
    distance: number;
    anchor: Point;
    camera: Camera;
  } | null>(null);
  const suppress = useRef(false);
  useEffect(() => {
    latest.current = options;
  });
  const refreshView = useCallback(() => {
    const rect = viewport.current?.getBoundingClientRect();
    if (rect)
      setView((previous) => {
        const c = camera.current;
        return previous.x === c.x &&
          previous.y === c.y &&
          previous.z === c.z &&
          previous.width === rect.width &&
          previous.height === rect.height
          ? previous
          : { ...c, width: rect.width, height: rect.height };
      });
  }, []);
  const paintCamera = useCallback(() => {
    const c = camera.current;
    if (world.current)
      world.current.style.transform = `translate(${c.x}px,${c.y}px) scale(${c.z})`;
    if (viewport.current) {
      const gap = 28 * c.z * (c.z < 0.45 ? 2 : 1);
      viewport.current.style.backgroundSize = `${gap}px ${gap}px`;
      viewport.current.style.backgroundPosition = `${c.x}px ${c.y}px`;
    }
    if (!cullTimer.current)
      cullTimer.current = setTimeout(() => {
        cullTimer.current = null;
        refreshView();
      }, 100);
  }, [refreshView]);
  const moveCamera = useCallback(
    (target: Camera, animate = true, duration = 0.38) => {
      tween.current?.kill();
      if (!animate || reduced()) {
        camera.current = { ...target };
        paintCamera();
        refreshView();
        latest.current.onCamera(camera.current);
        return;
      }
      // GSAP 给目标对象附加缓存；用代理承接，持久化相机保持纯数值。
      const proxy = {
        x: camera.current.x,
        y: camera.current.y,
        z: camera.current.z,
      };
      tween.current = gsap.to(proxy, {
        ...target,
        duration,
        ease: "power3.out",
        onUpdate: () => {
          camera.current = { x: proxy.x, y: proxy.y, z: proxy.z };
          paintCamera();
        },
        onComplete: () => {
          refreshView();
          latest.current.onCamera({ ...camera.current });
        },
      });
    },
    [paintCamera, refreshView],
  );
  const usableRect = useCallback((): Rect => {
    const vp = viewport.current;
    if (!vp) return { x: 30, y: 70, w: 1100, h: 600 };
    const r = vp.getBoundingClientRect();
    const host = vp.closest(".sp-workspace");
    const message = host?.querySelector<HTMLElement>(".cv-msgwin"),
      board = host?.querySelector<HTMLElement>(".cv-agentboard");
    const opened = host?.getAttribute("data-stream") === "open";
    const left =
      opened && r.width > 860 && message
        ? Math.max(32, message.getBoundingClientRect().right - r.left + 28)
        : 40;
    const right =
      board && r.width > 1150
        ? Math.max(40, r.right - board.getBoundingClientRect().left + 28)
        : 40;
    const dock = host
      ?.querySelector<HTMLElement>(".cv-dock")
      ?.getBoundingClientRect();
    const bottom = dock ? Math.max(170, r.bottom - dock.top + 90) : 120;
    return {
      x: left,
      y: 65,
      w: Math.max(240, r.width - left - right),
      h: Math.max(240, r.height - bottom - 65),
    };
  }, []);
  const fit = useCallback(
    (items?: Rect[], animate = true) => {
      const b = bounds(items ?? latest.current.items),
        area = usableRect();
      const z = clamp(
        Math.min(area.w / (b.w + 40), area.h / (b.h + 40)),
        0.15,
        1,
      );
      moveCamera(
        {
          x: area.x + (area.w - b.w * z) / 2 - b.x * z,
          y: area.y + (area.h - b.h * z) / 2 - b.y * z,
          z,
        },
        animate,
      );
    },
    [moveCamera, usableRect],
  );
  const zoom = useCallback(
    (factor: number, absolute = false) => {
      const area = usableRect(),
        c = camera.current,
        anchor = { x: area.x + area.w / 2, y: area.y + area.h / 2 };
      const z = clamp(absolute ? factor : c.z * factor, 0.15, 2.5);
      moveCamera({
        x: anchor.x - ((anchor.x - c.x) * z) / c.z,
        y: anchor.y - ((anchor.y - c.y) * z) / c.z,
        z,
      });
    },
    [moveCamera, usableRect],
  );

  useEffect(() => {
    const vp = viewport.current;
    if (!vp) return;
    const observer = new ResizeObserver(refreshView);
    observer.observe(vp);
    paintCamera();
    let saveCameraTimer: ReturnType<typeof setTimeout> | undefined;
    let suppressTimer: ReturnType<typeof setTimeout> | undefined;
    const local = (e: PointerEvent): Point => {
      const r = vp.getBoundingClientRect();
      return { x: e.clientX - r.left, y: e.clientY - r.top };
    };
    const node = (id: string) =>
      world.current?.querySelector<HTMLElement>(
        `[data-placement="${CSS.escape(id)}"]`,
      );
    const clearDrop = () => {
      if (drop.current) node(drop.current)?.classList.remove("is-drop-target");
      drop.current = null;
    };
    const cleanupGesture = () => {
      const g = active.current;
      cancelAnimationFrame(raf.current);
      raf.current = 0;
      for (const item of g?.originals ?? []) {
        const el = g?.elements.get(item.id);
        if (!el) continue;
        el.classList.remove("is-moving");
        el.style.transform = `translate(${item.x}px,${item.y}px)`;
        el.style.width = `${item.w}px`;
        el.style.height = `${item.h}px`;
      }
      active.current = null;
      pending.current = [];
      clearDrop();
      vp.classList.remove("is-gesturing", "is-panning");
      if (marquee.current) marquee.current.style.display = "none";
    };
    const itemTransform = (p: CanvasPlacement, g: Gesture) => {
      const handoff = g.handoffs.get(p.id);
      const matrix = handoff?.matrix;
      return `translate(${p.x}px,${p.y}px)${matrix ? ` matrix(${matrix.a},${matrix.b},${matrix.c},${matrix.d},0,0)` : ""}`;
    };
    const settleHandoffs = (
      g: Gesture,
      from: CanvasPlacement[],
      to: CanvasPlacement[],
    ) => {
      if (reduced()) return;
      const destinations = new Map(to.map((p) => [p.id, p]));
      for (const item of from) {
        const el = g.elements.get(item.id),
          target = destinations.get(item.id);
        if (!el || !target || !g.handoffs.has(item.id)) continue;
        const animation = el.animate(
          [
            { transform: itemTransform(item, g) },
            { transform: `translate(${target.x}px,${target.y}px)` },
          ],
          { duration: 220, easing: "cubic-bezier(.22,.75,.2,1)", fill: "both" },
        );
        void animation.finished.then(() => animation.cancel()).catch(() => {});
      }
    };
    const paint = () => {
      raf.current = 0;
      const g = active.current;
      if (!g) return;
      const dx = g.last.x - g.start.x,
        dy = g.last.y - g.start.y;
      if (!g.moved) return;
      if (g.kind === "pan") {
        camera.current = {
          ...g.camera,
          x: g.camera.x + dx,
          y: g.camera.y + dy,
        };
        paintCamera();
        return;
      }
      if (g.kind === "select") {
        const rect = {
          x: Math.min(g.start.x, g.last.x),
          y: Math.min(g.start.y, g.last.y),
          w: Math.abs(dx),
          h: Math.abs(dy),
        };
        if (marquee.current)
          Object.assign(marquee.current.style, {
            display: "block",
            transform: `translate(${rect.x}px,${rect.y}px)`,
            width: `${rect.w}px`,
            height: `${rect.h}px`,
          });
        return;
      }
      const delta = { x: dx / camera.current.z, y: dy / camera.current.z };
      pending.current = g.items.map((p) =>
        g.kind === "resize"
          ? {
              ...p,
              ...resizeRect(p, g.corner, delta, latest.current.isMedia(p.id)),
            }
          : { ...p, x: p.x + delta.x, y: p.y + delta.y },
      );
      for (const item of pending.current) {
        const el = g.elements.get(item.id);
        if (!el) continue;
        el.classList.add("is-moving");
        el.style.transform = itemTransform(item, g);
        if (g.kind === "resize") {
          el.style.width = `${item.w}px`;
          el.style.height = `${item.h}px`;
        }
      }
      if (g.kind === "move") {
        const point = worldPoint(g.last, camera.current);
        const target = [...latest.current.items].reverse().find(
          (p) =>
            point.x >= p.x &&
            point.x <= p.x + p.w &&
            point.y >= p.y &&
            point.y <= p.y + p.h &&
            latest.current.canDrop(
              g.items.map((i) => i.id),
              p.id,
            ),
        );
        clearDrop();
        if (target) {
          drop.current = target.id;
          node(target.id)?.classList.add("is-drop-target");
        }
      }
    };
    const down = (event: PointerEvent) => {
      if (
        !latest.current.interactive ||
        (event.button !== 0 && event.button !== 1)
      )
        return;
      const target = event.target as HTMLElement;
      if (
        target.closest("[data-no-gesture],button,input,textarea,a,select,video")
      )
        return;
      pointers.current.set(event.pointerId, local(event));
      vp.setPointerCapture(event.pointerId);
      tween.current?.kill();
      if (pointers.current.size === 2) {
        cleanupGesture();
        const [a, b] = [...pointers.current.values()];
        if (a && b)
          pinch.current = {
            distance: Math.hypot(a.x - b.x, a.y - b.y),
            anchor: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 },
            camera: { ...camera.current },
          };
        return;
      }
      const element = target.closest<HTMLElement>("[data-placement]"),
        id = element?.dataset.placement;
      const item = latest.current.items.find((p) => p.id === id);
      const corner = target.dataset.corner ?? "";
      const pan =
        space.current ||
        event.button === 1 ||
        (!item && event.pointerType === "touch");
      let selected = latest.current.selection;
      if (item && !pan) {
        selected = event.shiftKey
          ? selected.includes(item.id)
            ? selected.filter((i) => i !== item.id)
            : [...selected, item.id]
          : selected.includes(item.id)
            ? selected
            : [item.id];
        latest.current.setSelection(selected);
        if (selected.includes(item.id)) element?.focus({ preventScroll: true });
      }
      const point = local(event);
      const handoffs: Gesture["handoffs"] = new Map();
      const elements: Gesture["elements"] = new Map();
      const originals = item
        ? latest.current.items.filter((p) =>
            corner ? p.id === item.id : selected.includes(p.id),
          )
        : [];
      const moving = item
        ? originals.map((p) => {
            const element = node(p.id),
              animations = element?.getAnimations() ?? [];
            if (element) elements.set(p.id, element);
            if (!element || !animations.length) return p;
            const matrix = new DOMMatrix(getComputedStyle(element).transform);
            handoffs.set(p.id, {
              matrix,
              offset: handoffAnchorOffset(
                matrix,
                worldPoint(point, camera.current),
              ),
            });
            const actual = {
              ...p,
              x: matrix.e,
              y: matrix.f,
            };
            animations.forEach((animation) => animation.cancel());
            element.style.transform = matrix.toString();
            return actual;
          })
        : [];
      active.current = {
        pointer: event.pointerId,
        kind: pan
          ? "pan"
          : corner && item
            ? "resize"
            : item
              ? "move"
              : "select",
        start: point,
        last: point,
        camera: { ...camera.current },
        moved: false,
        time: performance.now(),
        velocity: 0,
        items: moving,
        corner,
        additive: event.shiftKey,
        initialSelection: [...latest.current.selection],
        originals,
        elements,
        handoffs,
      };
      pending.current = [];
      suppress.current = false;
      event.preventDefault();
    };
    const move = (event: PointerEvent) => {
      if (!pointers.current.has(event.pointerId)) return;
      const point = local(event);
      pointers.current.set(event.pointerId, point);
      if (pinch.current && pointers.current.size >= 2) {
        const [a, b] = [...pointers.current.values()];
        if (!a || !b) return;
        const p = pinch.current,
          z = clamp(
            (p.camera.z * Math.hypot(a.x - b.x, a.y - b.y)) /
              Math.max(1, p.distance),
            0.15,
            2.5,
          );
        camera.current = {
          x: (a.x + b.x) / 2 - ((p.anchor.x - p.camera.x) * z) / p.camera.z,
          y: (a.y + b.y) / 2 - ((p.anchor.y - p.camera.y) * z) / p.camera.z,
          z,
        };
        paintCamera();
        return;
      }
      const g = active.current;
      if (!g || g.pointer !== event.pointerId) return;
      const now = performance.now();
      g.velocity = (point.x - g.last.x) / Math.max(8, now - g.time);
      g.time = now;
      g.last = point;
      if (Math.hypot(point.x - g.start.x, point.y - g.start.y) > 5)
        g.moved = true;
      if (g.moved) {
        vp.classList.add("is-gesturing");
        if (g.kind === "pan") vp.classList.add("is-panning");
      }
      if (!raf.current) raf.current = requestAnimationFrame(paint);
    };
    const up = (event: PointerEvent) => {
      pointers.current.delete(event.pointerId);
      if (vp.hasPointerCapture(event.pointerId))
        vp.releasePointerCapture(event.pointerId);
      if (pinch.current) {
        if (pointers.current.size < 2) pinch.current = null;
        refreshView();
        latest.current.onCamera({ ...camera.current });
        return;
      }
      const g = active.current;
      if (!g || g.pointer !== event.pointerId) return;
      if (event.type === "pointercancel") {
        cleanupGesture();
        return;
      }
      paint();
      suppress.current = g.moved;
      clearTimeout(suppressTimer);
      // 只拦截本次释放产生的点击，后续按钮和键盘操作立即可用。
      suppressTimer = setTimeout(() => {
        suppress.current = false;
      }, 0);
      if (g.kind === "select") {
        const a = worldPoint(g.start, camera.current),
          b = worldPoint(g.last, camera.current);
        const rect = {
          x: Math.min(a.x, b.x),
          y: Math.min(a.y, b.y),
          w: Math.abs(a.x - b.x),
          h: Math.abs(a.y - b.y),
        };
        const ids = g.moved
          ? latest.current.items
              .filter((p) => intersects(p, rect))
              .map((p) => p.id)
          : [];
        latest.current.setSelection([
          ...new Set([...(g.additive ? g.initialSelection : []), ...ids]),
        ]);
      } else if ((g.kind === "move" || g.kind === "resize") && g.moved) {
        const presented = pending.current;
        const finalItems = presented.map((p) => {
            const offset = g.handoffs.get(p.id)?.offset;
            return offset ? { ...p, x: p.x + offset.x, y: p.y + offset.y } : p;
          }),
          target = drop.current;
        cleanupGesture();
        latest.current.onCommit(finalItems, target);
        if (!target) settleHandoffs(g, presented, finalItems);
        if (!target && !reduced())
          for (const p of finalItems) {
            const face = g.elements
              .get(p.id)
              ?.querySelector(".sp-card-material");
            if (face)
              gsap.fromTo(
                face,
                { rotation: clamp(g.velocity * 1.4, -2, 2) },
                {
                  rotation: 0,
                  duration: 0.42,
                  ease: "elastic.out(1, 0.65)",
                  overwrite: true,
                },
              );
          }
      }
      cleanupGesture();
      if (!g.moved && g.handoffs.size) settleHandoffs(g, g.items, g.originals);
      refreshView();
      if (g.kind === "pan") latest.current.onCamera({ ...camera.current });
    };
    const wheel = (event: WheelEvent) => {
      if (
        !latest.current.interactive ||
        active.current ||
        (event.target as HTMLElement).closest(
          "[data-no-gesture],textarea,input,video",
        )
      )
        return;
      event.preventDefault();
      tween.current?.kill();
      const c = camera.current;
      if (event.ctrlKey || event.metaKey) {
        const r = vp.getBoundingClientRect(),
          x = event.clientX - r.left,
          y = event.clientY - r.top;
        const z = clamp(c.z * Math.exp(-event.deltaY * 0.003), 0.15, 2.5);
        camera.current = {
          x: x - ((x - c.x) * z) / c.z,
          y: y - ((y - c.y) * z) / c.z,
          z,
        };
      } else
        camera.current = { ...c, x: c.x - event.deltaX, y: c.y - event.deltaY };
      paintCamera();
      clearTimeout(saveCameraTimer);
      saveCameraTimer = setTimeout(
        () => latest.current.onCamera({ ...camera.current }),
        180,
      );
    };
    const keydown = (event: KeyboardEvent) => {
      if (
        (event.target as HTMLElement).closest(
          "button,a,input,textarea,select,[contenteditable=true]",
        )
      )
        return;
      if (event.code === "Space" && latest.current.interactive) {
        space.current = true;
        vp.classList.add("hand-mode");
        event.preventDefault();
      }
    };
    const keyup = (event: KeyboardEvent) => {
      if (event.code === "Space") {
        space.current = false;
        vp.classList.remove("hand-mode");
      }
    };
    const blur = () => {
      space.current = false;
      vp.classList.remove("hand-mode");
      pointers.current.clear();
      pinch.current = null;
      cleanupGesture();
    };
    vp.addEventListener("pointerdown", down);
    vp.addEventListener("pointermove", move);
    vp.addEventListener("pointerup", up);
    vp.addEventListener("pointercancel", up);
    vp.addEventListener("wheel", wheel, { passive: false });
    window.addEventListener("keydown", keydown);
    window.addEventListener("keyup", keyup);
    window.addEventListener("blur", blur);
    return () => {
      observer.disconnect();
      cleanupGesture();
      tween.current?.kill();
      clearTimeout(saveCameraTimer);
      if (cullTimer.current) clearTimeout(cullTimer.current);
      clearTimeout(suppressTimer);
      cullTimer.current = null;
      vp.removeEventListener("pointerdown", down);
      vp.removeEventListener("pointermove", move);
      vp.removeEventListener("pointerup", up);
      vp.removeEventListener("pointercancel", up);
      vp.removeEventListener("wheel", wheel);
      window.removeEventListener("keydown", keydown);
      window.removeEventListener("keyup", keyup);
      window.removeEventListener("blur", blur);
    };
  }, [paintCamera, refreshView]);
  return {
    viewport,
    world,
    marquee,
    camera,
    view,
    fit,
    zoom,
    moveCamera,
    suppress,
  };
}
