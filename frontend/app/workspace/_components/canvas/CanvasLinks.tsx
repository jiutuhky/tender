import { LINK_DEFS, META, SPINE, spineNodeY, type CardInst } from "./cardMeta";

// 制品卡 ↔ 主轴的连线层（world 坐标 SVG，随世界一起平移缩放，不拦截指针）。
// 曲线样式（cubic）；卡片拖动时随 cards 状态重算 path。

interface Seg {
  sx: number;
  sy: number;
  tx: number;
  ty: number;
}

function pathD(s: Seg): string {
  const co = Math.max(40, Math.abs(s.tx - s.sx) * 0.45);
  return `M ${s.sx} ${s.sy} C ${s.sx + co} ${s.sy}, ${s.tx - co} ${s.ty}, ${s.tx} ${s.ty}`;
}

export function CanvasLinks({
  cards,
  links = LINK_DEFS,
}: {
  cards: CardInst[];
  links?: Array<{ a: string; n: number }>;
}) {
  const by = new Map(cards.map((c) => [c.id, c]));
  const segs: Seg[] = [];

  for (const def of links) {
    const c = by.get(def.a);
    if (!c) continue;
    const m = META[c.type];
    const ny = spineNodeY(def.n);
    if (c.x < SPINE.x) {
      segs.push({ sx: c.x + m.w, sy: c.y + m.h / 2, tx: SPINE.x, ty: ny });
    } else {
      segs.push({ sx: SPINE.x + SPINE.w, sy: ny, tx: c.x, ty: c.y + m.h / 2 });
    }
  }

  const asm = by.get("assemble");
  if (asm) {
    const m = META[asm.type];
    const spineBottom = SPINE.y + SPINE.headerH + SPINE.nodes.length * SPINE.rowH;
    segs.push({ sx: SPINE.x + SPINE.w / 2, sy: spineBottom, tx: asm.x + m.w / 2, ty: asm.y });
  }

  return (
    <svg className="cv-links" width={10} height={10}>
      {segs.map((s, i) => (
        <path key={`p${i}`} d={pathD(s)} fill="none" stroke="var(--label-3)" strokeWidth={1.6} strokeOpacity={0.45} strokeLinecap="round" />
      ))}
      {segs.map((s, i) => (
        <g key={`d${i}`}>
          <circle cx={s.sx} cy={s.sy} r={3} fill="var(--label-3)" fillOpacity={0.7} />
          <circle cx={s.tx} cy={s.ty} r={3} fill="var(--label-3)" fillOpacity={0.7} />
        </g>
      ))}
    </svg>
  );
}
