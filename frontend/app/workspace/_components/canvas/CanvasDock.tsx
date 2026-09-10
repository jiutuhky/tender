"use client";

import { useLayoutEffect, useRef } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { PenIcon, TableIcon, TreeStructureIcon } from "@/components/ui/icons";
import { useWorkspaceStore } from "@/lib/store/workspace";
import { DUR_FLOAT, DUR_PANEL, TRACE_EASE_ENTER, prefersReducedMotion } from "./traceMotion";
import { isRunning } from "../runStatus";
import { Composer } from "../Composer";

// 画布底部的输入坞：项目空闲时提供快捷指令，运行控制集成在 Composer 内。

const CHIPS: Array<{ label: string; icon: React.ReactNode; prompt: string }> = [
  {
    label: "核查实质性条款",
    icon: <TableIcon width={14} height={14} />,
    prompt: "请核查已解析的实质性条款，列出还需要人工确认的问题，并附上原文依据。",
  },
  {
    label: "整理证明材料",
    icon: <TreeStructureIcon width={14} height={14} />,
    prompt: "请根据当前应答矩阵，整理需要准备的证明材料清单，注明对应条目。",
  },
  {
    label: "检查负偏离",
    icon: <PenIcon width={14} height={14} />,
    prompt: "请检查当前应答中的负偏离，说明影响及需要核实的事项。",
  },
];

export function CanvasDock() {
  const dockRef = useRef<HTMLDivElement>(null);
  const phase = useWorkspaceStore((s) => s.phase);
  const projectId = useWorkspaceStore((s) => s.projectId);
  const setDraft = useWorkspaceStore((s) => s.setComposerDraft);
  const running = isRunning(phase);

  // 坞占用的底部带宽实测，供展开态浮窗的 height: calc(100% - --cv-dock-band) 让位。
  // 坞高真的会变（armed 文件 chip、自增高 textarea、chips 换行），写死会让长起来的
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

  // 坞的首次到场：快捷指令先、Composer 后，各自淡入 + 8px 上浮。
  useGSAP(
    () => {
      if (prefersReducedMotion()) return;
      // 玻璃约束:autoAlpha 会给元素设 opacity,而 opacity<1 的**祖先**会切断玻璃的
      // backdrop——所以补间只落在玻璃元素自身(各 chip,自身 opacity 不切断)与
      // 实底 composer 上,绝不作用于 .cv-dockbar / .cv-dock-chips 这类玻璃祖先容器。
      const targets = [
        ...gsap.utils.toArray<HTMLElement>(".cv-dockbar .cv-dock-chip"),
        ...gsap.utils.toArray<HTMLElement>(".cv-dock .composer"),
      ];
      if (!targets.length) return;
      gsap.from(targets, {
        autoAlpha: 0,
        y: 8,
        duration: DUR_PANEL,
        ease: TRACE_EASE_ENTER,
        stagger: 0.05,
        clearProps: "transform,opacity,visibility",
      });
    },
    { scope: dockRef },
  );

  // 运行结束后，快捷指令从原位置淡入；补间只作用于玻璃元素自身。
  useGSAP(
    () => {
      if (prefersReducedMotion()) return;
      const items = gsap.utils.toArray<HTMLElement>(".cv-dockbar .cv-dock-chip");
      if (!items.length) return;
      gsap.from(items, {
        autoAlpha: 0,
        y: 4,
        duration: DUR_FLOAT,
        ease: TRACE_EASE_ENTER,
        clearProps: "transform,opacity,visibility",
      });
    },
    { scope: dockRef, dependencies: [running] },
  );

  // 快捷指令只是「给你起个头」，填进输入框由用户过目后再发，不代发。
  const prefill = (prompt: string) => {
    setDraft(prompt);
    document.querySelector<HTMLTextAreaElement>(".composer-input textarea")?.focus();
  };

  return (
    <div className="cv-dock" ref={dockRef}>
      {!running && projectId && (
        <div className="cv-dockbar">
            <div className="cv-dock-chips">
              {CHIPS.map((c) => (
                <button
                  key={c.label}
                  type="button"
                  // 快捷 chips:放置矩阵为 lens thin,lens 预算已满,降级 霜 soft·thin
                  className="cv-dock-chip frost-glass frost-glass--soft frost-glass--interactive"
                  data-thick="thin"
                  onClick={() => prefill(c.prompt)}
                >
                  {c.icon}
                  {c.label}
                </button>
              ))}
            </div>
        </div>
      )}
      <Composer />
    </div>
  );
}
