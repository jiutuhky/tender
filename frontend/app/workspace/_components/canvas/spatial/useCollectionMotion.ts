"use client";

import { useCallback, useLayoutEffect, useRef, type RefObject } from "react";
import { gsap } from "gsap";
import type { Camera } from "@/lib/canvas/model";

interface Pose {
  x: number;
  y: number;
  w: number;
  h: number;
  a: number;
  b: number;
  c: number;
  d: number;
}
interface Flight {
  shell: HTMLElement;
  target: HTMLElement;
  animation: Animation;
  inline?: boolean;
}

/** 将缩略纸片与真实卡片按稳定实例标识连接，反向操作从当前画面接续。 */
export function useCollectionMotion(
  world: RefObject<HTMLDivElement | null>,
  camera: RefObject<Camera>,
) {
  const before = useRef<Map<string, Pose> | null>(null),
    flights = useRef(new Map<string, Flight>());
  const measure = useCallback(
    (element: HTMLElement): Pose => {
      const rect = element.getBoundingClientRect(),
        origin = world.current?.parentElement?.getBoundingClientRect();
      const style = getComputedStyle(element);
      // 包围框已经包含旋转，不能把它的宽高再次旋转。保留纸张的
      // 原始尺寸与两条变换后的边，并由包围框反求实际左上角。
      let matrix = new DOMMatrix();
      for (
        let node: HTMLElement | null = element;
        node && node !== world.current;
        node = node.parentElement
      )
        matrix = new DOMMatrix(getComputedStyle(node).transform).multiply(
          matrix,
        );
      const extra = (properties: string[]) =>
        style.boxSizing === "border-box"
          ? 0
          : properties.reduce(
              (sum, property) =>
                sum + (parseFloat(style.getPropertyValue(property)) || 0),
              0,
            );
      const w =
          (parseFloat(style.width) || element.offsetWidth) +
          extra([
            "padding-left",
            "padding-right",
            "border-left-width",
            "border-right-width",
          ]),
        h =
          (parseFloat(style.height) || element.offsetHeight) +
          extra([
            "padding-top",
            "padding-bottom",
            "border-top-width",
            "border-bottom-width",
          ]);
      return {
        x:
          (rect.left - (origin?.left ?? 0) - camera.current.x) /
            camera.current.z -
          Math.min(0, matrix.a * w, matrix.c * h, matrix.a * w + matrix.c * h),
        y:
          (rect.top - (origin?.top ?? 0) - camera.current.y) /
            camera.current.z -
          Math.min(0, matrix.b * w, matrix.d * h, matrix.b * w + matrix.d * h),
        w,
        h,
        a: matrix.a,
        b: matrix.b,
        c: matrix.c,
        d: matrix.d,
      };
    },
    [camera, world],
  );
  const clear = useCallback(() => {
    for (const flight of flights.current.values()) {
      flight.animation.cancel();
      flight.target.style.visibility = "";
      if (!flight.inline) flight.shell.remove();
    }
    flights.current.clear();
  }, []);
  const capture = useCallback(() => {
    const poses = new Map<string, Pose>();
    world.current
      ?.querySelectorAll<HTMLElement>("[data-motion-id]")
      .forEach((el) => poses.set(el.dataset.motionId!, measure(el)));
    for (const [id, flight] of flights.current)
      poses.set(id, measure(flight.shell));
    clear();
    before.current = poses;
  }, [world, measure, clear]);
  useLayoutEffect(() => {
    const poses = before.current;
    before.current = null;
    if (
      !poses ||
      !world.current ||
      matchMedia("(prefers-reduced-motion: reduce)").matches
    )
      return;
    // 收回时集合外壳会重新挂载。缩略片已有空间迁移接管反馈，
    // 取消外壳额外的 6px 入场，避免把临时位置采样成飞行终点。
    world.current
      .querySelectorAll<HTMLElement>("[data-placement]")
      .forEach((card) => {
        if (poses.has(card.dataset.placement!)) return;
        const matched = [
          ...card.querySelectorAll<HTMLElement>("[data-motion-id]"),
        ].some((child) => poses.has(child.dataset.motionId!));
        const material = card.querySelector<HTMLElement>(".sp-card-material");
        if (matched && material) {
          gsap.killTweensOf(material);
          gsap.set(material, { clearProps: "transform,opacity,visibility" });
        }
      });
    let order = 0;
    world.current
      .querySelectorAll<HTMLElement>("[data-motion-id]")
      .forEach((target) => {
        const id = target.dataset.motionId!,
          from = poses.get(id),
          to = measure(target);
        if (
          !from ||
          !to.w ||
          !to.h ||
          Math.abs(from.x - to.x) +
            Math.abs(from.y - to.y) +
            Math.abs(from.w - to.w) +
            Math.abs(from.h - to.h) <
            1
        )
          return;
        const transform = (p: Pose) =>
          `matrix(${(p.a * p.w) / to.w},${(p.b * p.w) / to.w},${(p.c * p.h) / to.h},${(p.d * p.h) / to.h},${p.x},${p.y})`;
        // 展开后的卡片直接参与动画，整个飞行过程仍可被指针抓住。
        if (target.dataset.placement) {
          const animation = target.animate(
            [{ transform: transform(from) }, { transform: transform(to) }],
            {
              duration: 340 + Math.min(order++, 4) * 14,
              easing: "cubic-bezier(.22,.75,.2,1)",
              fill: "both",
            },
          );
          const flight: Flight = {
            shell: target,
            target,
            animation,
            inline: true,
          };
          flights.current.set(id, flight);
          const finish = () => {
            if (flights.current.get(id) !== flight) return;
            animation.cancel();
            flights.current.delete(id);
          };
          void animation.finished.then(finish).catch(finish);
          return;
        }
        const shell = document.createElement("div"),
          copy = target.cloneNode(true) as HTMLElement;
        shell.className = "sp-motion-flight";
        shell.setAttribute("aria-hidden", "true");
        shell.inert = true;
        shell.style.width = `${to.w}px`;
        shell.style.height = `${to.h}px`;
        for (const el of [copy, ...copy.querySelectorAll<HTMLElement>("*")])
          for (const attr of [
            "id",
            "data-placement",
            "data-motion-id",
            "tabindex",
          ])
            el.removeAttribute(attr);
        copy.classList.remove("is-selected", "is-dimmed", "is-moving");
        Object.assign(copy.style, {
          transform: "none",
          position: "absolute",
          inset: "0",
          width: "100%",
          height: "100%",
          visibility: "visible",
          transition: "none",
        });
        shell.appendChild(copy);
        world.current!.appendChild(shell);
        target.style.visibility = "hidden";
        const animation = shell.animate(
          [
            { transform: transform(from), opacity: 0.85 },
            { transform: transform(to), opacity: 1 },
          ],
          {
            duration: 340 + Math.min(order++, 4) * 14,
            easing: "cubic-bezier(.22,.75,.2,1)",
            fill: "both",
          },
        );
        const flight = { shell, target, animation };
        flights.current.set(id, flight);
        void animation.finished
          .then(() => {
            if (flights.current.get(id) !== flight) return;
            target.style.visibility = "";
            shell.remove();
            flights.current.delete(id);
          })
          .catch(() => {});
      });
  });
  useLayoutEffect(() => clear, [clear]);
  return { capture, clear };
}
