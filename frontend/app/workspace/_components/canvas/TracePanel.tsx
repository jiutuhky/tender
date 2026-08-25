"use client";

import {
  Component,
  Suspense,
  cloneElement,
  isValidElement,
  use,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { gsap } from "gsap";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { toJsxRuntime } from "hast-util-to-jsx-runtime";
import { Newsreader, Noto_Serif_SC } from "next/font/google";
// KaTeX 结构样式必须引入:它把 .katex-mathml 裁剪成 1px 隐藏起来,
// 不引入的话 MathML 会和 HTML 两套一起显示(同一个公式渲染两遍)。
// 它带的 20 个 KaTeX_* Web 字体在 globals.css 里被字族覆盖掉,一个都不会被请求。
import "katex/dist/katex.min.css";
import { getDocumentContent, type DocumentRecord } from "@/lib/hagent/documents";
import { parseTenderMarkdown, type LineRange } from "@/lib/trace/pipeline";
import { locateSpan, type SpanAnchor } from "@/lib/trace/refs";
import { useTrace } from "./traceContext";
import { DUR_MICRO, DUR_PANEL, TRACE_EASE_ENTER, prefersReducedMotion } from "./traceMotion";
import { RefreshIcon, WarningIcon } from "@/components/ui/icons";

// 溯源预览正文:招标文件原文的渲染态文档纸面(外壳与标题栏在 TraceModal)。
// 排版对齐 .design/prototype/archive/preview.html(文档预览与导出)的层级密度,
// 颜色映射 Frost token(样式在 globals.css .cv-trace-*)。
// 渲染走 lib/trace/pipeline 的 unified 管线(remark/rehype + KaTeX),
// 块级源行号由管线打在 root 层子节点上,与 source_ref.line_span 同坐标系。
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

/** 「解析 + 元素化」的结果按文档身份跨挂载缓存。
 *
 *  为什么必须缓存:整篇 ~1700 行语料跑管线 + 生成 5000+ React 元素实测是一次
 *  ~330ms 的主线程长任务(dev + StrictMode 双跑)。而预览层每次关闭都会卸载
 *  DocView,不缓存的话「关掉再开同一文档」要重新付一整遍——PRD 故事 23
 *  「重复打开同一文档时内容即时呈现」讲的就是这里。数据层只缓存了原文文本,
 *  解析结果不缓存等于把那条故事丢掉一半。缓存后重开命中即零成本,
 *  StrictMode 的第二次调用也直接命中,首开也省掉一半。
 *
 *  键取 document_id + sha256(与数据层同一套内容版本口径,原文变了自然失效)。
 *  只留最近 3 篇:跨文档核验够用,又不至于把整个语料常驻内存。 */
const RENDER_CACHE = new Map<string, { nodes: ReactNode[]; blocks: LineRange[] }>();
const RENDER_CACHE_MAX = 3;

function renderDocument(cacheKey: string, md: string): { nodes: ReactNode[]; blocks: LineRange[] } {
  const cached = RENDER_CACHE.get(cacheKey);
  if (cached) return cached;

  const { root, blocks } = parseTenderMarkdown(md);
  const nodes = root.children
    .filter((n) => n.type === "element")
    .map((el, i) => {
      const node = toJsxRuntime(el, { Fragment, jsx, jsxs, development: false });
      // toJsxRuntime 不接受 key,列表键在此补一次(整篇只做一次;
      // 后续命中克隆不传 key,cloneElement 会保留原键)
      return isValidElement(node) ? cloneElement(node, { key: `b${i}` }) : node;
    });

  const value = { nodes, blocks };
  RENDER_CACHE.set(cacheKey, value);
  if (RENDER_CACHE.size > RENDER_CACHE_MAX) {
    const oldest = RENDER_CACHE.keys().next();
    if (!oldest.done) RENDER_CACHE.delete(oldest.value);
  }
  return value;
}

/** 文档正文:use() 挂起至原文就绪(promise 由数据层缓存,重渲染身份稳定)。
 *  活跃 ref → 块映射走 lib/trace/refs.locateSpan;命中块高亮并滚动进入视野中部,
 *  未能定位(行号缺失/越界/落空行)照常呈现全文 + 顶部黄条,不滚动不高亮。 */
function DocView({ projectId, doc }: { projectId: string; doc: DocumentRecord }) {
  const trace = useTrace();
  const activeRef = trace?.activeRef ?? null;
  const activeSeq = trace?.activeSeq ?? 0;
  const md = use(getDocumentContent(projectId, doc));

  // 点签只重算命中集合,不重跑 remark/rehype,也不重建元素
  const { nodes, blocks } = useMemo(
    () => renderDocument(`${doc.id}:${doc.sha256}`, md),
    [doc.id, doc.sha256, md],
  );

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

  // 命中块加高亮类:浅克隆已渲染好的元素,不动子树(子节点引用不变,React 对账极廉价)
  const body = useMemo(
    () =>
      nodes.map((node, i) => {
        if (!hits.has(i) || !isValidElement<{ className?: string }>(node)) return node;
        const cls = node.props.className;
        return cloneElement(node, { className: cls ? `${cls} cv-trace-hit` : "cv-trace-hit" });
      }),
    [nodes, hits],
  );

  // 定位滚动:高亮区整体进入视野中部;区比视口高时退化为首块顶部留白对齐。
  // reduced-motion 即时跳转(与浮层动效同一判定)。
  //
  /** 超过这个位移就直接跳,不做平滑滚动(约两屏) */
  const SMOOTH_MAX_DELTA_RATIO = 2;

  // 定位滚动:高亮区整体进入视野中部;区比视口高时退化为首块顶部留白对齐。
  //
  // 远距离必须直接跳,不能平滑滚:真语料整篇约 6 万 px,命中块常在 4 万 px 处。
  // 实测 behavior:"smooth" 滚这种距离不收敛——Chrome 的平滑滚动有时长上限,
  // 动画跑满 2 秒后停在离目标 524-743px 的地方,命中块正好落在视野外,
  // 看起来就是「点了来源签但没定位」。而且拿 2 秒滚过 4 万 px 正文本身也很难受。
  // 平滑只在近距离(同屏附近换签)才有空间连续性的意义,远距离直接跳更准也更快。
  const rootRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (activation?.anchor.status !== "located") return;
    const hitEls = rootRef.current?.querySelectorAll<HTMLElement>(".cv-trace-hit");
    const first = hitEls?.[0];
    const last = hitEls?.[hitEls.length - 1];
    // 滚动容器是舞台(纸面在其中居中),不是文档根
    const stage = first?.closest<HTMLElement>(".cv-trace-stage");
    if (!first || !last || !stage) return;
    const br = stage.getBoundingClientRect();
    const top = first.getBoundingClientRect().top;
    const bottom = last.getBoundingClientRect().bottom;
    const delta =
      bottom - top > br.height
        ? top - br.top - 24
        : (top + bottom) / 2 - (br.top + br.height / 2);
    const instant = prefersReducedMotion() || Math.abs(delta) > br.height * SMOOTH_MAX_DELTA_RATIO;
    stage.scrollTo({ top: stage.scrollTop + delta, behavior: instant ? "auto" : "smooth" });
    // 高亮出现的一次性短暂强调(票05):染色淡入 micro 档,只动覆盖层 opacity。
    // 每次点签(seq 递增)重播一次;之后保持常亮,无循环。reduced-motion 直接呈现。
    if (!prefersReducedMotion()) {
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
          <WarningIcon width={14} height={14} />
          <span>未能定位：来源行号缺失、越界或未指向正文内容，请在原文中人工查找</span>
        </div>
      )}
      <article ref={rootRef} className={`cv-trace-doc ${serifLatin.variable} ${serifCJK.variable}`}>
        {body}
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
        <p>
          <b>原文读取失败</b> · {this.state.error.message}
        </p>
        <button type="button" onClick={this.props.onRetry}>
          <RefreshIcon width={13} height={13} />
          重试
        </button>
      </div>
    );
  }
}

/** 原文正文:舞台(滚动容器)→ 纸面 → 文档。标题栏与关闭钮由 TraceModal 承担。
 *  arrival = 挂载处的到场动画时长(秒),浮层入场期间持骨架,避免长帧冻住动画 */
export function TracePanel({ doc, arrival = DUR_PANEL }: { doc: DocumentRecord; arrival?: number }) {
  const trace = useTrace();
  const projectId = trace?.projectId ?? null;
  const [retryTick, setRetryTick] = useState(0);

  // 到场让位(票05):缓存命中时整篇文档会在浮层入场途中 commit,长帧冻结动画。
  // 浮层落位前持骨架、之后才挂 DocView;取数在此并行预热,不因此推迟网络往返。
  // 只门控首挂:之后切签/跨文档(边界 key 换)走 Suspense 正常换内容,无二次延迟。
  //
  // 放行前顺带把公文衬线抓下来,让正文只按最终字体排一次版。字体请求本来要等正文
  // 布局才发起,而正文正等着放行,于是默认时序是「先按回退字体排、随后换入重排」;
  // 整篇约 6 万 px,重排会把定位落点挤走。字体名即上面 next/font 的构造名。
  //
  // 说明:这是预防,不是已发生故障的修复。定位偏移的实测根因是长距离平滑滚动不收敛
  // (见下方 SMOOTH_MAX_DELTA_RATIO),多轮采样中 .cv-trace-doc 高度始终恒定、
  // 未观察到字体重排。之所以仍保留,是因为字体已缓存时代价接近零(load 立即 resolve),
  // 而一旦真发生重排,症状是命中块定位错位,排查成本远高于此处这几行。
  // 加载超时(1.5s)照常放行:内容呈现绝不吊死在字体上。
  const [arrived, setArrived] = useState(() => typeof window !== "undefined" && prefersReducedMotion());
  useEffect(() => {
    let alive = true;
    const gate = new Promise<void>((r) => setTimeout(r, arrival * 1000 + 30));
    const serif = document.fonts
      ? Promise.all(
          (["400", "600"] as const).flatMap((w) => [
            document.fonts.load(`${w} 1em Newsreader`),
            document.fonts.load(`${w} 1em "Noto Serif SC"`),
          ]),
        ).then(() => undefined, () => undefined)
      : Promise.resolve();
    const capped = Promise.race([serif, new Promise<void>((r) => setTimeout(r, 1500))]);
    void Promise.all([gate, capped]).then(() => {
      if (alive) setArrived(true);
    });
    return () => {
      alive = false;
    };
  }, [arrival]);
  useEffect(() => {
    if (projectId) getDocumentContent(projectId, doc).catch(() => undefined);
  }, [projectId, doc]);

  return (
    <div className="cv-trace-stage">
      <div className="cv-trace-sheet">
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
    </div>
  );
}
