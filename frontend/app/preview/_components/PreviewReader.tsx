"use client";

import { useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { MagnifyingGlassMinusIcon, MagnifyingGlassPlusIcon, ChevronLeftIcon } from "@/components/ui/icons";

export function PreviewReader({ children }: { children: ReactNode }) {
  const [zoom, setZoom] = useState<number | null>(null);
  const viewport = useRef<HTMLDivElement>(null);
  return <main className="preview-reader" id="main-content" tabIndex={-1}>
    <div className="preview-toolbar">
      <Link href="/projects" className="preview-back"><ChevronLeftIcon width={16} height={16} /><span>返回项目</span></Link>
      <div className="preview-zoom" role="group" aria-label="文档显示比例">
        <button type="button" aria-label="缩小文档" disabled={zoom !== null && zoom <= 0.5} onClick={() => setZoom(Math.max(0.5,(zoom ?? 1) - 0.1))}><MagnifyingGlassMinusIcon width={18} height={18} /></button>
        <button type="button" className="preview-fit" onClick={() => setZoom(null)} title="适应阅读区域">{zoom === null ? "适应宽度" : `${Math.round(zoom * 100)}%`}</button>
        <button type="button" aria-label="放大文档" disabled={zoom !== null && zoom >= 1.5} onClick={() => setZoom(Math.min(1.5,(zoom ?? 1) + 0.1))}><MagnifyingGlassPlusIcon width={18} height={18} /></button>
      </div>
      <button className="prose-button" type="button" onClick={() => window.print()}>打印示例</button>
    </div>
    <div className="preview-layout">
      <aside className="preview-outline" aria-label="示例目录"><h1>文档排版示例</h1><p>绿色技术方案 · 2 页</p><nav>{[["p42","4.1 总体技术路线"],["p43","4.2 液冷子系统"]].map(([id,title]) => <a key={id} href={`#${id}`} onClick={(e) => { e.preventDefault(); viewport.current?.querySelector(`#${id}`)?.scrollIntoView({ block: "start" }); }}>{title}</a>)}</nav><span>示例内容不代表已生成的投标文件。实际项目目前支持招标解析与矩阵核验。</span></aside>
      <div ref={viewport} className="preview-viewport" tabIndex={0} aria-label="示例文档，可滚动阅读">
        <div className="preview-disclosure">排版示例 · 内容、引用与数据均为演示，正式投标前需另行编制与核验。</div>
        <div className={`preview-pages${zoom === null ? " is-fit" : ""}`} style={zoom === null ? undefined : { width: 760, zoom }}>{children}</div>
      </div>
    </div>
  </main>;
}
