// 溯源预览纯逻辑:招标文件 Markdown(MinerU OCR 产物)→ hast 渲染树 + 块级源行号。
// 零 DOM 依赖(同构),取代早期手写的 blocks.ts 分段器与 sanitize.ts 的 DOMParser 白名单。
//
// 语料画像(data/ 真语料实测):ATX 标题、纯文本段落、**单元格正文含硬换行的内联 HTML 大表格**、
// 行内 $…$ 公式;列表/管道表格语料暂无,块级 $$…$$ 语料为 0(按验收口径一并支持)。
//
// 管线顺序有三处是刻意的,改动前先读注释:
//   1. rehype-raw 必须在 remark-rehype 之后 —— 用真 HTML 解析器接管 MinerU 表格。
//      旧分段器按「每行以 < 开头」吞 HTML 块,单元格里的硬换行会把一张表切碎成
//      未闭合残片 + 一堆带字面量 </td><td> 的段落(全语料 69 张表破 17 张、泄漏 52 行)。
//   2. rehype-sanitize 必须在 rehype-katex 之前 —— 净化的对象是「语料里的 HTML」,
//      KaTeX 自己生成的 MathML/span 是可信产物,不该被洗掉(否则 MathML 无障碍标注全丢)。
//   3. stampLineAnchors 必须最后 —— 只给 root 层子节点打行号,保住块级高亮的粒度契约。

import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import remarkRehype from "remark-rehype";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import rehypeKatex from "rehype-katex";
import type { Element, Root, RootContent } from "hast";

/** 块级源行号区间(1-based 闭区间),与 source_ref.line_span 同一坐标系 */
export interface LineRange {
  startLine: number;
  endLine: number;
}

/** 净化白名单:以 hast-util-sanitize 默认 schema 为基,只做两处加固。
 *
 *  表格属性无需额外放行 —— 默认 schema 的 attributes["*"] 已含 colSpan/rowSpan(实测)。
 *
 *  math 类名要显式放行:remark-math 产出 <code class="language-math math-inline">,
 *  默认 schema 只按 /^language-./ 放行,math-inline / math-display 会被剥掉。
 *  rehype-katex 目前认 language-math 所以「碰巧」还能工作,但块级公式靠 math-display
 *  区分行内/行间 —— 剥掉就会把行间公式渲染成行内。不赌上游实现,显式留住这两个类名。 */
const SCHEMA: typeof defaultSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [
      ...(defaultSchema.attributes?.code ?? []),
      ["className", "language-math", "math-inline", "math-display"],
    ],
  },
};

/** root 层子节点里,能承载行号锚点的元素节点(text/comment 等不打) */
function isStampable(node: RootContent): node is Element {
  return node.type === "element";
}

/** 宽表兜底:root 层的 <table> 套一层可横滚的容器,宽表在纸面内自己滚,
 *  绝不让纸面本身横向溢出(语料最宽 9 列,版心勉强放得下,但不赌上游)。
 *  必须跑在 stampLineAnchors 之前 —— 包完容器才是 root 子节点,行号要打在容器上,
 *  命中时整个容器染色 = 「命中大表格即整表高亮」。position 从表格原样继承。 */
function wrapTables() {
  return (tree: Root): void => {
    tree.children = tree.children.map((node) => {
      if (node.type !== "element" || node.tagName !== "table") return node;
      const wrapper: Element = {
        type: "element",
        tagName: "div",
        properties: { className: ["cv-trace-html"], tabIndex: 0, role: "region", ariaLabel: "原文表格，可横向滚动" },
        children: [node],
      };
      if (node.position) wrapper.position = node.position;
      return wrapper;
    });
  };
}

/** 行号锚点:mdast/hast 节点原生带 position(1-based),正是 line_span 的坐标系。
 *  只打 root 层子节点 —— 高亮契约是「与 line_span 相交的块整块高亮」,
 *  嵌套节点也打会让 locateSpan 命中一堆子节点,把整块高亮碎成片。
 *
 *  实测(unified 11 / rehype-raw 7)root 层 position 完整穿过 rehype-raw,无缺失。
 *  仍留一道廉价防御:缺 position 时顺延上一块的 endLine,并保证行号单调不倒退——
 *  语料没触发,但上游 OCR 产物换了未必。 */
function stampLineAnchors(collected: LineRange[]) {
  return (tree: Root): void => {
    let cursor = 1;
    for (const node of tree.children) {
      if (!isStampable(node)) continue;
      const pos = node.position;
      const rawStart = pos?.start.line ?? cursor;
      const rawEnd = pos?.end.line ?? rawStart;
      const startLine = Math.max(rawStart, 1);
      const endLine = Math.max(rawEnd, startLine);
      cursor = endLine + 1;
      node.properties = {
        ...node.properties,
        "data-line-start": startLine,
        "data-line-end": endLine,
      };
      collected.push({ startLine, endLine });
    }
  };
}

/** 整篇 Markdown → hast 渲染树 + 与之顺序对齐的块级行号表。
 *  blocks[i] 对应 root.children 里第 i 个元素节点(非元素节点不计),
 *  这条对齐关系是 locateSpan 的 blockIndices → 渲染块映射的依据,不要打破。 */
export function parseTenderMarkdown(md: string): { root: Root; blocks: LineRange[] } {
  const blocks: LineRange[] = [];
  const processor = unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkMath)
    .use(remarkRehype, { allowDangerousHtml: true })
    .use(rehypeRaw)
    .use(rehypeSanitize, SCHEMA)
    // strict: "ignore" —— 语料是 OCR 产物,\textcircled 用在数学模式、‰ 无字形之类的
    // 告警每次渲染都会刷控制台,而源头修不了;渲染结果本身不受影响。
    // 解析失败无需配置:rehype-katex 7 固定内部兜底(其 Options 显式 Omit 掉了
    // throwOnError),坏公式降级成 .katex-error 节点,不会炸掉整篇渲染。
    // output 用默认的 htmlAndMathml:只要 html 的话整段公式会被 aria-hidden 吃掉,
    // 「20%」这类内容对读屏用户直接消失。
    .use(rehypeKatex, { strict: "ignore" })
    .use(wrapTables)
    .use(() => stampLineAnchors(blocks));

  const root = processor.runSync(processor.parse(md)) as Root;
  return { root, blocks };
}
