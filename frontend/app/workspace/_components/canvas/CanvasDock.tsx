"use client";

import { useLayoutEffect, useRef } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { PenIcon, TableIcon, TreeStructureIcon } from "@/components/ui/icons";
import { useWorkspaceStore } from "@/lib/store/workspace";
import { DUR_FLOAT, DUR_PANEL, TRACE_EASE_ENTER, prefersReducedMotion } from "./traceMotion";
import { isRunning } from "../runStatus";
import { ActivityBar } from "../ActivityBar";
import { Composer } from "../Composer";

// 画布底部居中的输入坞：一行快捷指令（运行期由活动条顶替）+ 真 Composer。
// 活动条**顶替** chips 的槽位而不是加第三行：chips 在 busy 期本就无效
// （startParse / sendMessage 遇 BUSY 直接返回），同一槽位两个状态，交叉淡入。

const CHIPS: Array<{ label: string; icon: React.ReactNode; prompt: string }> = [
  {
    label: "合成应答矩阵",
    icon: <TableIcon width={14} height={14} />,
    prompt: "请基于已解析的招标文件，合成一张完整的应答矩阵。",
  },
  {
    label: "生成大纲",
    icon: <TreeStructureIcon width={14} height={14} />,
    prompt: "请根据应答矩阵生成投标文件大纲，标注每章对应的实质性条款。",
  },
  {
    label: "起草章节",
    icon: <PenIcon width={14} height={14} />,
    prompt: "请起草技术方案章节，覆盖技术应答矩阵中的高风险条目。",
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

  // 坞的首次到场：活动条/chips 先、Composer 后，各自淡入 + 8px 上浮。
  useGSAP(
    () => {
      if (prefersReducedMotion()) return;
      // 玻璃约束:autoAlpha 会给元素设 opacity,而 opacity<1 的**祖先**会切断玻璃的
      // backdrop——所以补间只落在玻璃元素自身(活动条/各 chip,自身 opacity 不切断)与
      // 实底 composer 上,绝不作用于 .cv-dockbar / .cv-dock-chips 这类玻璃祖先容器。
      const targets = [
        ...gsap.utils.toArray<HTMLElement>(".cv-dockbar .cv-actbar, .cv-dockbar .cv-dock-chip"),
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

  // chips ⇄ 活动条换位：只给到场的一方做进场（两者在 DOM 里互斥，为一条 32px
  // 状态胶囊维持双挂载不值当）。运行状态翻转每次解析只发生一回。
  // 先取元素再判空：idle 且无项目时这一行是空的（chips 与活动条都不渲染），
  // 直接传选择器会让 gsap 每次挂载都往控制台丢一条 target not found。
  // 同上:目标是玻璃元素自身,不动 .cv-dock-chips 之类玻璃祖先。
  useGSAP(
    () => {
      if (prefersReducedMotion()) return;
      const items = gsap.utils.toArray<HTMLElement>(".cv-dockbar .cv-actbar, .cv-dockbar .cv-dock-chip");
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
      <div className="cv-dockbar">
        {running ? (
          <ActivityBar />
        ) : (
          projectId && (
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
          )
        )}
      </div>
      <Composer />
    </div>
  );
}
