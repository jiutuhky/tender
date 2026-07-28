import { Dot } from "./bits";
import { SPINE } from "./cardMeta";
import { TreeStructureIcon } from "@/components/ui/icons";

// 主轴：投标文件大纲（背景骨架卡）。不参与拖拽（cv-spine 被视口平移忽略）；
// 点击任意章节行打开「投标大纲」抽屉。

export function SpineCard({
  onOpenOutline,
}: {
  onOpenOutline: (source?: "pointer" | "keyboard") => void;
}) {
  return (
    <div className="cv-spine" style={{ left: SPINE.x, top: SPINE.y, width: SPINE.w }}>
      <div className="cv-spine-head" style={{ height: SPINE.headerH }}>
        <TreeStructureIcon width={15} height={15} style={{ color: "var(--blue)" }} />
        <span className="cv-spine-title">投标文件大纲</span>
        <span className="cv-spine-tag">主轴</span>
      </div>
      {SPINE.nodes.map((n, i) => (
        <div
          key={i}
          className={`cv-spine-row${n.s === "blue" ? " is-active" : ""}${n.ind ? " is-sub" : ""}`}
          style={{ height: SPINE.rowH, paddingLeft: 13 + n.ind * 16 }}
          role="button"
          tabIndex={0}
          aria-label={`打开大纲章节：${n.t}`}
          onClick={() => onOpenOutline("pointer")}
          onKeyDown={(event) => {
            if (event.key !== "Enter" && event.key !== " ") return;
            event.preventDefault();
            onOpenOutline("keyboard");
          }}
        >
          <Dot sc={n.s} />
          <span className="cv-spine-row-text">{n.t}</span>
        </div>
      ))}
    </div>
  );
}
