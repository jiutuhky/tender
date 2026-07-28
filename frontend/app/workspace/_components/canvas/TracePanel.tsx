"use client";

import { Component, Suspense, use, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { gsap } from "gsap";
import { Newsreader, Noto_Serif_SC } from "next/font/google";
import { getDocumentContent, type DocumentRecord } from "@/lib/hagent/documents";
import { segmentMarkdown, type DocBlock } from "@/lib/trace/blocks";
import { locateSpan, type SpanAnchor } from "@/lib/trace/refs";
import { sanitizeDocHtml } from "@/lib/trace/sanitize";
import { prettyLabel } from "@/lib/hagent/naming";
import { useTrace } from "./traceContext";
import { DUR_MICRO, DUR_PANEL, TRACE_EASE_ENTER, prefersReducedMotion } from "./traceMotion";
import { FileIcon, RefreshIcon, XIcon } from "@/components/ui/icons";

// 溯源预览左栏:招标文件原文的渲染态面板。
// 排版对齐 .design/prototype/archive/preview.html(文档预览与导出)的层级密度,
// 颜色映射 Frost token(样式在 globals.css .cv-trace-*)。
// 取数走 use() + Suspense:数据层按 document_id + sha256 缓存 promise(身份稳定),
// 载入占位 = fallback,读取失败抛给错误边界,重试即换 key 重挂发新请求。

// 「零 Web 字体」全局硬约束在此有一处有意破例(PRD 决策,CLAUDE.md 与 frost-design skill 已注记):
// 公文式衬线排版在简体环境没有可靠的系统衬线栈,经 next/font 自托管引入
// Newsreader(拉丁)+ Noto Serif SC(简体),构建期下载、零运行时外链;
// CSS 变量类只挂在面板文档根节点(.cv-trace-doc),站点其余部分不受影响。
const serifLatin = Newsreader({
  weight: ["400", "600"],
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--trace-serif-latin",
});
const serifCJK = Noto_Serif_SC({
  weight: ["400", "600"],
  display: "swap",
  preload: false,
  variable: "--trace-serif-cjk",
});

/** 载入占位:静态骨架行(Frost 禁无限循环动效),形状呼应成稿后的标题 + 段落 */
function TraceSkeleton() {
  return (
    <div className="cv-trace-skel" aria-hidden>
      {[0.46, 0.9, 0.84, 0.62, 1, 0.72, 0.88, 0.4].map((w, i) => (
        <i key={i} style={{ width: `${w * 100}%` }} />
      ))}
    </div>
  );
}

const HEADING_TAGS = ["h1", "h2", "h3", "h4"] as const;

/** 单块渲染:块级元素钉 1-based 源行号锚点;hit = 与活跃 ref 行区相交,整块高亮 */
function BlockView({ block, hit }: { block: DocBlock; hit: boolean }) {
  const lineAttrs = { "data-line-start": block.startLine, "data-line-end": block.endLine };
  const cls = hit ? "cv-trace-hit" : undefined;
  const html = useMemo(
    () => (block.kind === "html" ? sanitizeDocHtml(block.html) : ""),
    [block],
  );
  switch (block.kind) {
    case "heading": {
      const Tag = HEADING_TAGS[Math.min(block.level, 4) - 1] ?? "h4";
      return <Tag {...lineAttrs} className={cls}>{block.text}</Tag>;
    }
    case "paragraph":
      return <p {...lineAttrs} className={cls}>{block.text}</p>;
    case "list": {
      const items = block.items.map((it, i) => <li key={i}>{it}</li>);
      return block.ordered ? (
        <ol {...lineAttrs} className={cls}>{items}</ol>
      ) : (
        <ul {...lineAttrs} className={cls}>{items}</ul>
      );
    }
    case "table":
      return (
        <table {...lineAttrs} className={cls}>
          <thead>
            <tr>
              {block.headRow.map((c, i) => (
                <th key={i}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.rows.map((r, i) => (
              <tr key={i}>
                {r.map((c, j) => (
                  <td key={j}>{c}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      );
    case "html":
      // 净化后无白名单内容时按纯文本如实呈现,坏数据可见、不静默吞掉
      if (!html.trim()) return <p {...lineAttrs} className={cls}>{block.html}</p>;
      return (
        <div
          {...lineAttrs}
          className={cls ? `cv-trace-html ${cls}` : "cv-trace-html"}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      );
  }
}

/** 文档正文:use() 挂起至原文就绪(promise 由数据层缓存,重渲染身份稳定)。
 *  活跃 ref → 块映射走 lib/trace/refs.locateSpan;命中块高亮并滚动进入视野中部,
 *  未能定位(行号缺失/越界/落空行)照常呈现全文 + 顶部黄条,不滚动不高亮。 */
function DocView({ projectId, doc }: { projectId: string; doc: DocumentRecord }) {
  const trace = useTrace();
  const activeRef = trace?.activeRef ?? null;
  const activeSeq = trace?.activeSeq ?? 0;
  const md = use(getDocumentContent(projectId, doc));
  const blocks = useMemo(() => segmentMarkdown(md), [md]);
  // activation = 一次点签动作:seq 随每次 openTrace 递增,已活跃的签重点一次也重新定位
  const activation = useMemo<{ anchor: SpanAnchor; seq: number } | null>(() => {
    if (!activeRef || activeRef.document_id !== doc.id) return null;
    return { anchor: locateSpan(blocks, activeRef.line_span, md.split("\n").length), seq: activeSeq };
  }, [activeRef, activeSeq, doc.id, blocks, md]);
  const anchor = activation?.anchor ?? null;
  const hits = useMemo(
    () => new Set(anchor?.status === "located" ? anchor.blockIndices : []),
    [anchor],
  );

  // 定位滚动:高亮区整体进入视野中部;区比视口高时退化为首块顶部留白对齐。
  // reduced-motion 即时跳转(与抽屉动效同一判定)。
  const rootRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (activation?.anchor.status !== "located") return;
    const hitEls = rootRef.current?.querySelectorAll<HTMLElement>(".cv-trace-hit");
    const first = hitEls?.[0];
    const last = hitEls?.[hitEls.length - 1];
    const body = first?.closest<HTMLElement>(".cv-trace-body");
    if (!first || !last || !body) return;
    const br = body.getBoundingClientRect();
    const top = first.getBoundingClientRect().top;
    const bottom = last.getBoundingClientRect().bottom;
    const delta =
      bottom - top > br.height
        ? top - br.top - 24
        : (top + bottom) / 2 - (br.top + br.height / 2);
    const instant = prefersReducedMotion();
    body.scrollTo({ top: body.scrollTop + delta, behavior: instant ? "auto" : "smooth" });
    // 高亮出现的一次性短暂强调(票05):染色淡入 micro 档,只动覆盖层 opacity。
    // 每次点签(seq 递增)重播一次;之后保持常亮,无循环。reduced-motion 直接呈现。
    if (!instant) {
      gsap.fromTo(
        hitEls,
        { "--cv-hit-in": 0 },
        { "--cv-hit-in": 1, duration: DUR_MICRO, ease: TRACE_EASE_ENTER, overwrite: "auto" },
      );
    }
  }, [activation]);

  return (
    <>
      {anchor?.status === "unlocatable" && (
        <div className="cv-trace-banner" role="status">
          未能定位：来源行号缺失、越界或未指向正文内容，请在原文中人工查找
        </div>
      )}
      <article ref={rootRef} className={`cv-trace-doc ${serifLatin.variable} ${serifCJK.variable}`}>
        {blocks.map((b, i) => (
          <BlockView key={b.startLine} block={b} hit={hits.has(i)} />
        ))}
      </article>
    </>
  );
}

/** 面板内错误边界:读取失败呈错误态 + 重试入口(数据层不缓存失败,重试即新请求) */
class DocErrorBoundary extends Component<
  { onRetry: () => void; children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="cv-trace-error" role="alert">
        <div>原文读取失败：{this.state.error.message}</div>
        <button type="button" onClick={this.props.onRetry}>
          <RefreshIcon width={13} height={13} />
          重试
        </button>
      </div>
    );
  }
}

/** 原文面板:标题头 + 关闭按钮(显式关闭回单栏),正文取数 → 分段 → 渲染。
 *  arrival = 挂载处的到场动画时长(秒):双栏滑入 panel 档,窄屏二级视图 float 档 */
export function TracePanel({ doc, arrival = DUR_PANEL }: { doc: DocumentRecord; arrival?: number }) {
  const trace = useTrace();
  const projectId = trace?.projectId ?? null;
  const [retryTick, setRetryTick] = useState(0);

  // 到场让位(票05):缓存命中时整篇文档会在面板滑入途中 commit,长帧冻结动画。
  // 面板落位前持骨架、之后才挂 DocView;取数在此并行预热,不因此推迟网络往返。
  // 只门控首挂:之后切签/跨文档(边界 key 换)走 Suspense 正常换内容,无二次延迟。
  const [arrived, setArrived] = useState(() => typeof window !== "undefined" && prefersReducedMotion());
  useEffect(() => {
    const id = setTimeout(() => setArrived(true), arrival * 1000 + 30);
    return () => clearTimeout(id);
  }, [arrival]);
  useEffect(() => {
    if (projectId) getDocumentContent(projectId, doc).catch(() => undefined);
  }, [projectId, doc]);

  return (
    <aside className="cv-trace-pane" aria-label="招标文件原文对照">
      <div className="cv-trace-head">
        <FileIcon width={14} height={14} aria-hidden />
        <span className="cv-trace-title" title={doc.path}>
          {prettyLabel(doc.path.split("/").pop() ?? doc.path)}
        </span>
        <button
          type="button"
          className="cv-trace-close"
          aria-label="关闭原文面板"
          onClick={trace?.closeTrace}
        >
          <XIcon width={14} height={14} />
        </button>
      </div>
      <div className="cv-trace-body">
        {projectId && !arrived && <TraceSkeleton />}
        {projectId && arrived && (
          <DocErrorBoundary
            key={`${doc.id}:${doc.sha256}:${retryTick}`}
            onRetry={() => setRetryTick((t) => t + 1)}
          >
            <Suspense fallback={<TraceSkeleton />}>
              <DocView projectId={projectId} doc={doc} />
            </Suspense>
          </DocErrorBoundary>
        )}
      </div>
    </aside>
  );
}
