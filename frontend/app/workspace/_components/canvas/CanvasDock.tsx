"use client";

import { useLayoutEffect, useRef } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { DUR_PANEL, TRACE_EASE_ENTER, prefersReducedMotion } from "./traceMotion";
import { Composer } from "../Composer";

// 画布底部的输入坞：输入与运行控制集成在 Composer 内。

export function CanvasDock() {
  const dockRef = useRef<HTMLDivElement>(null);

  // 坞占用的底部带宽实测，供展开态浮窗的 height: calc(100% - --cv-dock-band) 让位。
  // 坞高真的会变（待提交附件、自增高 textarea），写死会让长起来的
  // 输入框滑到浮窗下面。
  useLayoutEffect(() => {
    const el = dockRef.current;
    const vp = el?.parentElement;
    if (!el || !vp) return;
    const write = () =>
      vp.style.setProperty("--cv-dock-band", `${Math.round(el.offsetHeight + 32)}px`);
    write();
    const ro = new ResizeObserver(write);
    ro.observe(el);
    return () => {
      ro.disconnect();
      vp.style.removeProperty("--cv-dock-band");
    };
  }, []);

  // 坞的首次到场：Composer 淡入并上浮 8px。
  useGSAP(
    () => {
      if (prefersReducedMotion()) return;
      const targets = gsap.utils.toArray<HTMLElement>(".cv-dock .composer");
      if (!targets.length) return;
      gsap.from(targets, {
        autoAlpha: 0,
        y: 8,
        duration: DUR_PANEL,
        ease: TRACE_EASE_ENTER,
        clearProps: "transform,opacity,visibility",
      });
    },
    { scope: dockRef },
  );

  return (
    <div className="cv-dock" ref={dockRef}>
      <Composer />
    </div>
  );
}
