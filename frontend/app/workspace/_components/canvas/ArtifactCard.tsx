"use client";

import { useRef, type PointerEvent as ReactPointerEvent } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { IconTile, StatusBadge } from "./bits";
import { CardPreview } from "./CardPreview";
import { META, type CardInst, type StatusColor } from "./cardMeta";
import { ArrowRightIcon } from "@/components/ui/icons";

// 画布上的制品卡：可拖拽（startDrag 由视口逻辑接管），未拖动即视为点击 → 打开抽屉。
// 进场（新增卡）pop 动画走 gsap，遵循「不手写 CSS keyframes」约定。

/** 动态状态徽标(真实矩阵卡由 store 槽位派生,覆盖 META 的静态值) */
export interface CardBadge {
  label: string;
  sc: StatusColor;
  inProgress: boolean;
}

interface ArtifactCardProps {
  card: CardInst;
  onStartDrag: (e: ReactPointerEvent) => void;
  onOpen: (source?: "pointer" | "keyboard") => void;
  badge?: CardBadge;
}

export function ArtifactCard({ card, onStartDrag, onOpen, badge }: ArtifactCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const m = META[card.type];
  const inProgress = badge ? badge.inProgress : m.status === "进行中";

  useGSAP(
    () => {
      if (!card.isNew) return;
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      gsap.from(ref.current, { autoAlpha: 0, y: 8, scale: 0.97, duration: 0.22, ease: "power3.out" });
    },
    { scope: ref },
  );

  return (
    <div
      ref={ref}
      className="cv-card"
      data-card-id={card.id}
      style={{ left: card.x, top: card.y, width: m.w }}
      role="button"
      tabIndex={0}
      aria-label={`打开${card.title || m.title}`}
      onPointerDown={onStartDrag}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen("keyboard");
        }
      }}
    >
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
