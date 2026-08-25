"use client";

import { useRef, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { IconTile, StatusBadge } from "./bits";
import { CardPreview } from "./CardPreview";
import { META, isMatrixCardType, type CardInst, type FaceTone, type StatusColor } from "./cardMeta";
import { ArrowRightIcon } from "@/components/ui/icons";
import { DUR_FLOAT, TRACE_EASE_ENTER } from "./traceMotion";

// 画布上的制品卡：可拖拽（startDrag 由视口逻辑接管），未拖动即视为点击 → 打开抽屉。
// 进场（新增卡）pop 动画走 gsap，遵循「不手写 CSS keyframes」约定。
// 两种卡壳：真实矩阵卡走 2026-08 重做的四行语法（题名 / 主指标 / 结构条 / 信号行，
// 无卡脚、无阶段签）；mock 卡（演示模式）沿用头/身/脚三段式。

/** 动态状态徽标(真实矩阵卡由 store 槽位派生,覆盖 META 的静态值) */
export interface CardBadge {
  label: string;
  sc: StatusColor;
  inProgress: boolean;
  tone: FaceTone;
}

interface ArtifactCardProps {
  card: CardInst;
  onStartDrag: (e: ReactPointerEvent) => void;
  onOpen: (source?: "pointer" | "keyboard") => void;
  badge?: CardBadge;
}

/** 卡壳基调 → 附加类名:失败立橙条、中断立灰条,其余无 */
function toneClass(tone: FaceTone | undefined): string {
  if (tone === "failed") return " is-failed";
  if (tone === "stalled") return " is-stalled";
  return "";
}

export function ArtifactCard({ card, onStartDrag, onOpen, badge }: ArtifactCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const m = META[card.type];
  const isFace = isMatrixCardType(card.type);
  const inProgress = badge ? badge.inProgress : m.status === "进行中";
  // 状态文字只在偏离常态时出现:进行中报「正在解析」、待命报「等待解析」;
  // 终态与失败态都不报——前者无信息量,后者由卡面直陈 + 卡壳色条承担。
  const stateText = badge && (badge.tone === "progress" || badge.tone === "idle") ? badge.label : null;

  useGSAP(
    () => {
      if (!card.isNew) return;
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      gsap.from(ref.current, { autoAlpha: 0, y: 8, scale: 0.97, duration: DUR_FLOAT, ease: TRACE_EASE_ENTER });
    },
    { scope: ref },
  );

  const shell = {
    ref,
    "data-card-id": card.id,
    style: { left: card.x, top: card.y, width: m.w },
    role: "button" as const,
    tabIndex: 0,
    "aria-label": `打开${card.title || m.title}`,
    onPointerDown: onStartDrag,
    onKeyDown: (e: ReactKeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onOpen("keyboard");
      }
    },
  };

  if (isFace) {
    const Icon = m.icon;
    return (
      <div {...shell} className={`cv-card is-face${toneClass(badge?.tone)}`}>
        {inProgress && <div className="cv-face-thread" />}
        <div className="cv-face-head">
          <Icon width={14} height={14} />
          <span className="cv-face-name">{card.title || m.title}</span>
          {stateText && <span className="cv-face-state">{stateText}</span>}
        </div>
        <CardPreview type={card.type} />
      </div>
    );
  }

  return (
    <div {...shell} className="cv-card">
      {inProgress && <div className="cv-card-prog" />}
      <div className="cv-card-head">
        <IconTile icon={m.icon} />
        <span className="cv-card-title">{card.title || m.title}</span>
        <span className="cv-card-stage">{m.stage}</span>
      </div>
      <div className="cv-card-body">
        <CardPreview type={card.type} />
      </div>
      <div className="cv-card-foot">
        <StatusBadge sc={badge?.sc ?? m.sc} label={badge?.label ?? m.status} />
        <span className="cv-card-expand">
          展开
          <ArrowRightIcon width={13} height={13} />
        </span>
      </div>
    </div>
  );
}
