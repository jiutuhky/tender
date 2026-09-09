"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import type { PDFDocumentProxy, PDFPageProxy, RenderTask, TextLayer } from "pdfjs-dist";
import { ChevronIcon, ChevronLeftIcon, ChevronRightIcon, MinusIcon, PlusIcon, RefreshIcon, WarningIcon } from "@/components/ui/icons";
import { getDocumentMapping, resetDocumentCaches, type DocumentRecord } from "@/lib/hagent/documents";
import { documentAssetUrl, getPdfEngine, PDFJS_ASSETS } from "@/lib/trace/pdf-runtime";
import { locatePdfReferences, locatePdfRegions, regionPixels, validateMapping, visiblePageRange, type PageSize, type Region } from "@/lib/trace/pdf-mapping";
import { useTrace } from "./traceContext";
import "./pdf-trace.css";

const GAP = 24;
type LoadedPdf = { pdf: PDFDocumentProxy; pages: PageSize[]; mapping: unknown; mappingError: string | null };
type Zoom = "auto" | "width" | "page" | number;
const ZOOM_STEPS = [25, 50, 75, 100, 125, 150, 175, 200, 250, 300];

/** 单页渲染任务与 Canvas 同生命周期；旧任务取消后才可复用节点。 */
function PdfPage({ pdf, index, size, regions, selected }: {
  pdf: PDFDocumentProxy; index: number; size: PageSize; regions: Region[]; selected: Region | undefined;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let cancelled = false;
    let render: RenderTask | undefined;
    let text: TextLayer | undefined;
    let page: PDFPageProxy | undefined;
    const canvas = canvasRef.current;
    const container = textRef.current;
    if (!canvas || !container) return;
    const draw = async () => {
      const engine = await getPdfEngine();
      page = await pdf.getPage(index + 1);
      if (cancelled) return;
      const viewport = page.getViewport({ scale: size.width / page.getViewport({ scale: 1 }).width });
      // 限制单页位图内存；覆盖层与文本层仍使用精确的 CSS 尺寸。
      const dpr = Math.min(window.devicePixelRatio || 1, 2, Math.sqrt(16_000_000 / (viewport.width * viewport.height)));
      canvas.width = Math.floor(viewport.width * dpr);
      canvas.height = Math.floor(viewport.height * dpr);
      container.replaceChildren();
      container.style.setProperty("--scale-factor", String(viewport.scale));
      container.style.setProperty("--total-scale-factor", String(viewport.scale * page.userUnit));
      render = page.render({ canvas, viewport, transform: [dpr, 0, 0, dpr, 0, 0] });
      await render.promise;
      if (cancelled) return;
      setReady(true);
      text = new engine.TextLayer({ textContentSource: page.streamTextContent(), container, viewport });
      // 文本层失败时保留已成功渲染的原页与高亮。
      await text.render().catch(() => undefined);
    };
    void draw().catch((reason: unknown) => {
      if (!cancelled) { console.warn("原文页面渲染失败", reason); setError(true); }
    });
    return () => {
      cancelled = true;
      render?.cancel();
      text?.cancel();
      container.replaceChildren();
      const clean = () => { canvas.width = 0; canvas.height = 0; page?.cleanup(); };
      if (render) void render.promise.then(clean, clean); else clean();
    };
  }, [pdf, index, size.width, size.height, retry]);

  return <>
    {!ready && !error && <span className="pdf-page-loading">正在载入第 {index + 1} 页</span>}
    <canvas ref={canvasRef} data-rendered={ready} style={{ width: size.width, height: size.height }} aria-label={`原文第 ${index + 1} 页`} />
    <div ref={textRef} className="pdf-text-layer" />
    <svg className="pdf-regions" width={size.width} height={size.height} viewBox={`0 0 ${size.width} ${size.height}`} aria-label={`第 ${index + 1} 页的 ${regions.length} 处来源区域`}>
      {regions.map((region, i) => <rect key={i} {...regionPixels(region, size)} className={region === selected ? "pdf-region is-selected" : "pdf-region"} data-source-region />)}
    </svg>
    {error && <div className="pdf-page-error" role="alert">第 {index + 1} 页加载失败
      <button type="button" onClick={() => { setError(false); setReady(false); setRetry((v) => v + 1); }}>重试本页</button>
    </div>}
  </>;
}

function PdfReader({ loaded, doc, locationsTarget, onRetry }: { loaded: LoadedPdf; doc: DocumentRecord; locationsTarget: HTMLElement | null; onRetry: () => void }) {
  const trace = useTrace();
  const stageRef = useRef<HTMLDivElement>(null);
  const raf = useRef(0);
  const [view, setView] = useState({ width: 800, height: 600, top: 0 });
  const [zoom, setZoom] = useState<Zoom>("auto");
  const [pageInput, setPageInput] = useState<string | null>(null);
  const [selection, setSelection] = useState({ key: "", index: 0 });
  const active = trace?.activeRef;
  const activation = `${trace?.activeSeq ?? 0}:${active?.document_id}:${active?.line_span?.join(",")}`;
  const checked = useMemo(() => validateMapping(loaded.mapping, doc, loaded.pages), [loaded.mapping, doc, loaded.pages]);
  const refs = trace?.activeClaim?.refs;
  const regions = useMemo(() => checked.mapping ? locatePdfReferences(checked.mapping,
    (refs ?? (active ? [active] : [])).filter((ref) => ref.document_id === doc.id).map((ref) => ref.line_span)) : [],
    [checked.mapping, refs, active, doc.id]);
  const activeRegions = useMemo(() => checked.mapping && active?.document_id === doc.id ? locatePdfRegions(checked.mapping, active.line_span) : [], [checked.mapping, active, doc.id]);
  const initialRegion = activeRegions[0];
  const initialIndex = initialRegion ? Math.max(0, regions.findIndex((region) => region.page === initialRegion.page && region.bbox.every((v, i) => v === initialRegion.bbox[i]))) : -1;
  const selectedIndex = selection.key === activation ? Math.min(selection.index, Math.max(0, regions.length - 1)) : initialIndex;
  const selected = regions[selectedIndex];
  const sourcePages = useMemo(() => [...new Set(regions.map((region) => region.page))], [regions]);
  const warning = loaded.mappingError ?? checked.reason ?? (selected ? null : "该来源没有可用的原文位置。");
  const unlocatedCount = useMemo(() => {
    const mapping = checked.mapping;
    return mapping ? (refs ?? []).filter((ref) => ref.document_id === doc.id && locatePdfRegions(mapping, ref.line_span).length === 0).length : 0;
  }, [checked.mapping, refs, doc.id]);
  const grouped = useMemo(() => {
    const map = new Map<number, Region[]>();
    for (const region of regions) map.set(region.page, [...(map.get(region.page) ?? []), region]);
    return map;
  }, [regions]);
  const layout = useMemo(() => {
    let offset = GAP;
    const tops: number[] = [];
    const sizes = loaded.pages.map((p) => {
      const fitWidth = Math.max(160, view.width - 56) / p.width;
      const scale = zoom === "auto" ? Math.min(fitWidth, 880 / p.width) : zoom === "width" ? fitWidth : zoom === "page" ? Math.min(fitWidth, Math.max(100, view.height - 104) / p.height) : zoom / 100;
      const size = { width: p.width * scale, height: p.height * scale };
      tops.push(offset); offset += size.height + GAP;
      return size;
    });
    return { tops, sizes, height: offset + 72, width: Math.max(view.width, ...sizes.map((p) => p.width + 48)) };
  }, [loaded.pages, view.width, view.height, zoom]);
  const [first, last] = visiblePageRange(layout.tops, layout.sizes, view.top, view.height);
  const currentPage = useMemo(() => {
    let page = 0;
    for (let i = 0; i < layout.tops.length; i++) {
      if ((layout.tops[i] ?? Infinity) > view.top + Math.min(view.height / 2, 180)) break;
      page = i;
    }
    return page;
  }, [layout, view.top, view.height]);

  const measure = useCallback(() => {
    const stage = stageRef.current;
    if (!stage) return;
    setView({ width: stage.clientWidth, height: stage.clientHeight, top: stage.scrollTop });
  }, []);
  useLayoutEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const observer = new ResizeObserver(measure);
    observer.observe(stage); measure();
    return () => { observer.disconnect(); cancelAnimationFrame(raf.current); };
  }, [measure]);
  const scheduleMeasure = () => {
    cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(measure);
  };

  // 缩放和容器变化保持当前阅读位置；来源激活则随后精确定位到矩形。
  const previousLayout = useRef(layout);
  useLayoutEffect(() => {
    const old = previousLayout.current;
    previousLayout.current = layout;
    const stage = stageRef.current;
    if (!stage || old === layout) return;
    let index = 0;
    for (let i = 0; i < old.tops.length; i++) if ((old.tops[i] ?? Infinity) <= view.top) index = i;
    const fraction = (view.top - (old.tops[index] ?? 0)) / (old.sizes[index]?.height ?? 1);
    stage.scrollTop = (layout.tops[index] ?? 0) + fraction * (layout.sizes[index]?.height ?? 1);
    measure();
  }, [layout, measure, view.top]);
  const jumpToRegion = useCallback((region: Region) => {
    const stage = stageRef.current, size = layout.sizes[region.page];
    if (!stage || !size) return;
    const rect = regionPixels(region, size);
    const top = (layout.tops[region.page] ?? 0) + rect.y;
    stage.scrollTo({ top: Math.max(0, rect.height > stage.clientHeight - 100 ? top - 24 : top + rect.height / 2 - (stage.clientHeight - 72) / 2),
      left: Math.max(0, (layout.width - size.width) / 2 + rect.x + rect.width / 2 - stage.clientWidth / 2), behavior: "instant" });
    measure();
  }, [layout, measure]);
  // 用 ref 读取最新几何，缩放不重新触发来源激活。
  const jumpRef = useRef(jumpToRegion);
  useLayoutEffect(() => { jumpRef.current = jumpToRegion; }, [jumpToRegion]);
  useEffect(() => { if (selected) jumpRef.current(selected); }, [activation, selected]);

  const goPage = (index: number) => {
    const target = Math.max(0, Math.min(loaded.pages.length - 1, index));
    stageRef.current?.scrollTo({ top: (layout.tops[target] ?? 0) - 12, behavior: "instant" });
    setPageInput(null); measure();
  };
  const currentZoom = Math.round((layout.sizes[currentPage]?.width ?? 1) / (loaded.pages[currentPage]?.width ?? 1) * 100);
  const changeZoom = (delta: number) => setZoom(delta > 0 ? ZOOM_STEPS.find((level) => level >= currentZoom + 12) ?? 300 : [...ZOOM_STEPS].reverse().find((level) => level <= currentZoom - 12) ?? 25);
  const visibleSource = regions.some((region) => {
    const size = layout.sizes[region.page];
    if (!size) return false;
    const rect = regionPixels(region, size);
    const top = (layout.tops[region.page] ?? 0) + rect.y;
    return top < view.top + view.height - 72 && top + rect.height > view.top;
  });
  const chooseSourcePage = (page: number) => {
    const index = regions.findIndex((region) => region.page === page);
    const region = regions[index];
    if (!region) return;
    setSelection({ key: activation, index });
    jumpToRegion(region);
  };

  return <div className="pdf-reader">
    {locationsTarget && createPortal(<>{sourcePages.map((page) => <button key={page} type="button" className="trace-location" aria-pressed={currentPage === page} aria-label={`定位原文第 ${page + 1} 页`} onClick={() => chooseSourcePage(page)}>第 {page + 1} 页</button>)}{unlocatedCount > 0 && <span className="trace-location-missing"><WarningIcon width={12} height={12} />{unlocatedCount} 处未定位</span>}</>, locationsTarget)}
    {warning && <div className="pdf-warning" role="status" title={warning}><WarningIcon width={14} height={14} /><span>未能定位原文</span><button type="button" aria-label="重试原文定位" title="重试" onClick={onRetry}><RefreshIcon width={14} height={14} /></button></div>}
    <div ref={stageRef} className="pdf-stage" onScroll={scheduleMeasure} tabIndex={0} aria-label="招标文件原文">
      <div className="pdf-page-list" style={{ height: layout.height, width: layout.width }}>
        {layout.sizes.map((size, i) => <div key={i} className="pdf-page" data-pdf-page={i + 1} style={{ top: layout.tops[i], left: (layout.width - size.width) / 2, width: size.width, height: size.height } as CSSProperties}>
          {i >= first && i <= last && <PdfPage key={`${i}:${size.width}:${size.height}`} pdf={loaded.pdf} index={i} size={size} regions={grouped.get(i) ?? []} selected={selected} />}
          <span className="pdf-page-number" aria-hidden>{i + 1}</span>
        </div>)}
      </div>
    </div>
    <div className="pdf-controls-position">
      <div className="pdf-control-dock">
        {selected && !visibleSource && <button type="button" className="pdf-return" onClick={() => selected && jumpToRegion(selected)}>回到引用</button>}
        <div className="pdf-toolbar" role="toolbar" aria-label="原文阅读工具">
          <div className="pdf-controls">
            <button type="button" aria-label="上一页" title="上一页" disabled={currentPage === 0} onClick={() => goPage(currentPage - 1)}><ChevronLeftIcon width={16} height={16} /></button>
            <form onSubmit={(e) => { e.preventDefault(); const n = Number(pageInput); if (Number.isInteger(n) && n >= 1 && n <= loaded.pages.length) goPage(n - 1); }}>
              <input aria-label="跳转页码" inputMode="numeric" value={pageInput ?? String(currentPage + 1)} onChange={(e) => setPageInput(e.target.value)} onBlur={() => setPageInput(null)} /><span>/ {loaded.pages.length}</span>
            </form>
            <button type="button" aria-label="下一页" title="下一页" disabled={currentPage === loaded.pages.length - 1} onClick={() => goPage(currentPage + 1)}><ChevronRightIcon width={16} height={16} /></button>
          </div>
          <span className="pdf-control-divider" aria-hidden />
          <div className="pdf-controls">
            <button type="button" aria-label="缩小原文" title="缩小" disabled={currentZoom <= 25} onClick={() => changeZoom(-1)}><MinusIcon width={15} height={15} /></button>
            <label className="pdf-zoom-picker">
              <span aria-hidden>{currentZoom}%<ChevronIcon width={10} height={10} /></span>
              <select aria-label="缩放比例" value={String(zoom)} onChange={(e) => {
                const value = e.target.value;
                setZoom(value === "auto" || value === "width" || value === "page" ? value : Number(value));
              }}>
                <option value="auto">自动</option><option value="width">适应宽度</option><option value="page">适应页面</option>
                {ZOOM_STEPS.map((level) => <option key={level} value={level}>{level}%</option>)}
              </select>
            </label>
            <button type="button" aria-label="放大原文" title="放大" disabled={currentZoom >= 300} onClick={() => changeZoom(1)}><PlusIcon width={15} height={15} /></button>
          </div>
        </div>
      </div>
    </div>
    <span className="pdf-sr-only" role="status" aria-live="polite">原文第 {currentPage + 1} 页，共 {loaded.pages.length} 页。{regions.length ? `来源共有 ${regions.length} 处区域。` : ""}</span>
  </div>;
}

function PdfSession({ doc, projectId, locationsTarget, onRetry }: { doc: DocumentRecord; projectId: string; locationsTarget: HTMLElement | null; onRetry: () => void }) {
  const [loaded, setLoaded] = useState<LoadedPdf | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    let task: ReturnType<Awaited<ReturnType<typeof getPdfEngine>>["getDocument"]> | undefined;
    const load = async () => {
      const mappingRequest = getDocumentMapping(projectId, doc).then((mapping) => ({ mapping, mappingError: null }), () => ({ mapping: null, mappingError: "原文映射暂不可用，请重试或重新解析文档。" }));
      const engine = await getPdfEngine();
      if (cancelled) return;
      task = engine.getDocument({ url: documentAssetUrl(projectId, doc.id, "preview"),
        cMapUrl: `${PDFJS_ASSETS}cmaps/`, cMapPacked: true,
        standardFontDataUrl: `${PDFJS_ASSETS}standard_fonts/`, wasmUrl: `${PDFJS_ASSETS}wasm/`,
        disableAutoFetch: true, disableStream: true });
      const pdf = await task.promise;
      if (cancelled) return;
      const pages: PageSize[] = new Array(pdf.numPages);
      let cursor = 0;
      await Promise.all(Array.from({ length: Math.min(4, pdf.numPages) }, async () => {
        while (cursor < pdf.numPages && !cancelled) {
          const index = cursor++;
          const page = await pdf.getPage(index + 1);
          const viewport = page.getViewport({ scale: 1 });
          pages[index] = { width: viewport.width, height: viewport.height };
        }
      }));
      const mapping = await mappingRequest;
      if (!cancelled) setLoaded({ pdf, pages, ...mapping });
    };
    void load().catch((reason: unknown) => {
      if (!cancelled) {
        console.warn("原文 PDF 加载失败", reason);
        setError("原文加载失败");
      }
    });
    return () => { cancelled = true; if (task) void task.destroy().catch(() => undefined); };
  }, [doc, projectId]);
  if (loaded) return <PdfReader loaded={loaded} doc={doc} locationsTarget={locationsTarget} onRetry={onRetry} />;
  return <div className="pdf-loading" role={error ? "alert" : "status"}>
    {error ? <><WarningIcon width={22} height={22} /><p>{error}</p><button type="button" onClick={onRetry}><RefreshIcon width={15} height={15} />重试</button></> : <div className="pdf-loading-sheet" aria-label="正在加载原文"><i /><i /><i /><i /><i /></div>}
  </div>;
}

export default function PdfTracePanel({ doc, locationsTarget }: { doc: DocumentRecord; locationsTarget: HTMLElement | null }) {
  const trace = useTrace();
  const [retry, setRetry] = useState(0);
  if (!trace?.projectId) return null;
  return <PdfSession key={`${doc.id}:${doc.sha256}:${doc.preview_sha256}:${retry}`} doc={doc} projectId={trace.projectId} locationsTarget={locationsTarget} onRetry={() => { resetDocumentCaches(); setRetry((n) => n + 1); }} />;
}
