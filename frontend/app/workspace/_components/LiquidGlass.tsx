"use client";

import { useEffect, useRef, type ReactNode } from "react";

export interface LiquidGlassProps {
  cornerRadius?: number;
  className?: string;
  children?: ReactNode;
}

/** 单层毛玻璃承托正文，高光与阴影提供层次，正文放在独立内容层。 */
export function LiquidGlass({
  cornerRadius = 28,
  className = "",
  children,
}: LiquidGlassProps) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const target = root.closest(".cv-msgwin") ?? root;
    const responsive = window.matchMedia(
      "(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)",
    );
    let frame = 0;
    let pointerX = 0;
    let pointerY = 0;
    const reset = () => {
      cancelAnimationFrame(frame);
      frame = 0;
      root.style.removeProperty("--lg-light-x");
      root.style.removeProperty("--lg-light-y");
    };
    const move = (event: Event) => {
      if (!responsive.matches || !(event instanceof PointerEvent) || event.pointerType !== "mouse") return;
      pointerX = event.clientX;
      pointerY = event.clientY;
      if (frame) return;
      // 光位随指针小幅偏移，每帧合并更新装饰层的 transform。
      frame = requestAnimationFrame(() => {
        frame = 0;
        const box = root.getBoundingClientRect();
        if (!box.width || !box.height) return;
        const x = Math.max(-1, Math.min(1, (pointerX - box.left) / box.width * 2 - 1));
        const y = Math.max(-1, Math.min(1, (pointerY - box.top) / box.height * 2 - 1));
        root.style.setProperty("--lg-light-x", `${x * 24}px`);
        root.style.setProperty("--lg-light-y", `${y * 18}px`);
      });
    };
    target.addEventListener("pointermove", move, { passive: true });
    target.addEventListener("pointerleave", reset);
    responsive.addEventListener("change", reset);
    return () => {
      reset();
      target.removeEventListener("pointermove", move);
      target.removeEventListener("pointerleave", reset);
      responsive.removeEventListener("change", reset);
    };
  }, []);

  const radius = `${cornerRadius}px`;

  return (
    <div
      ref={rootRef}
      className={`lg-root ${className}`}
      style={{ position: "absolute", inset: 0 }}
    >
      <div
        className="lg-glass"
        style={{ position: "absolute", inset: 0, borderRadius: radius, overflow: "hidden" }}
      >
        {/* 中央散射承托文字，渐变遮罩向边缘淡出。滤镜内联保留标准属性。 */}
        <span
          className="lg-diffusion"
          aria-hidden="true"
          style={{ backdropFilter: "blur(8px) saturate(125%)", WebkitBackdropFilter: "blur(8px) saturate(125%)" }}
        />
        <span className="lg-illum" aria-hidden="true" />
        <span className="lg-sheen" aria-hidden="true" />
        <div
          className="lg-content"
          style={{ position: "relative", zIndex: 1, height: "100%", borderRadius: radius }}
        >
          {children}
        </div>
      </div>
      <span className="lg-rim" aria-hidden="true" style={{ borderRadius: radius }} />
    </div>
  );
}
