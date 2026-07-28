import { OUTLINE } from "@/lib/mock/outline";

export function Outline() {
  return (
    <aside className="outline">
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
