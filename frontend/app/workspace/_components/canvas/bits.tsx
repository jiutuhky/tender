import type { ComponentType, ReactNode, SVGProps } from "react";
import { dotColor, scPair, type StatusColor } from "./cardMeta";

// 画布卡片 / 抽屉里复用的细粒度视觉原子。结构走 className，动态色值走 inline（与卡位同款）。

/** 状态连点（实色小圆） */
export function Dot({ sc }: { sc: StatusColor }) {
  return <span className="cv-dot" style={{ background: dotColor(sc) }} />;
}

/** 蓝底引用 chip（业绩 / 资质等） */
export function Chip({ children }: { children: ReactNode }) {
  return <span className="cv-chip">{children}</span>;
}

/** 状态徽标：前点 + 文案，底/前景由状态色决定 */
export function StatusBadge({ sc, label }: { sc: StatusColor; label: string }) {
  const [bg, fg] = scPair(sc);
  return (
    <span className="cv-badge" style={{ background: bg, color: fg }}>
      <span className="cv-badge-dot" style={{ background: fg }} />
      {label}
    </span>
  );
}

/** 蓝底图标方砖（卡头 / 抽屉头） */
export function IconTile({ icon: Icon }: { icon: ComponentType<SVGProps<SVGSVGElement>> }) {
  return (
    <span className="cv-icon-tile">
      <Icon width={15} height={15} />
    </span>
  );
}
