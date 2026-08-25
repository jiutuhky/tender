import { OUTLINE } from "@/lib/mock/outline";

export function Outline() {
  // 霜玻璃嵌入式 chrome（放置矩阵：sidebar = 霜 thick flush）；
  // 与内容交界的 .5px 接触边写在 styles.css 的 .outline 上。
  return (
    <aside className="outline frost-glass frost-glass--soft frost-glass--flush" data-thick="thick">
      <div className="outline-title">目录 · 共 6 章 78 页</div>
      {OUTLINE.map((ch) => (
        <div key={ch.idx}>
          <div className={`outline-item${ch.active ? " active" : ""}`}>
            <span className="idx">{ch.idx}</span>
            <span className="name">{ch.name}</span>
            <span className="stat">{ch.stat}</span>
          </div>
          {ch.subs.map((s) => (
            <div key={s.name} className={`outline-sub ${s.status}`}>
              <span className="dot" />
              {s.name}
            </div>
          ))}
        </div>
      ))}
    </aside>
  );
}
