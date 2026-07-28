// 溯源预览纯逻辑:招标文件 Markdown(MinerU OCR 产物)的块级分段。
// 每块携带 1-based 闭区间源行号,与 source_ref.line_span 同一坐标系——
// 票03 的「源行号→渲染块映射」直接以 startLine/endLine 相交判定,本模块零 DOM 依赖。
//
// 语料画像(data/ 真语料实测):ATX 标题、纯文本段落、单行内联 HTML 大表格、
// 少量 $…$ 公式噪声(如实按文本呈现);列表/管道表格语料暂无,但按验收口径支持。

export type DocBlock =
  | { kind: "heading"; level: number; text: string; startLine: number; endLine: number }
  | { kind: "paragraph"; text: string; startLine: number; endLine: number }
  | { kind: "list"; ordered: boolean; items: string[]; startLine: number; endLine: number }
  | { kind: "table"; headRow: string[]; rows: string[][]; startLine: number; endLine: number }
  | { kind: "html"; html: string; startLine: number; endLine: number };

const HEADING_RE = /^(#{1,6})\s+(.*)$/;
const LIST_ITEM_RE = /^\s*(?:([-*+])|(\d+)[.、])\s+(.*)$/;
const TABLE_ROW_RE = /^\s*\|.*\|\s*$/;
// 分隔行至少两列(单列管道行按段落如实呈现,避免把普通竖线文本误判成表格)
const TABLE_DELIM_RE = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/;
const HTML_OPEN_RE = /^</;

/** 管道表格行 → 单元格数组(去首尾空管道,单元格 trim)。 */
function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim());
}

/** 整篇 Markdown → 顺序块序列。空行分隔;未知构造一律落段落,不吞内容。 */
export function segmentMarkdown(md: string): DocBlock[] {
  const lines = md.split("\n");
  const blocks: DocBlock[] = [];
  let i = 0;

  while (i < lines.length) {
    const raw = lines[i] ?? "";
    const line = raw.trim();
    const lineNo = i + 1;

    if (!line) {
      i++;
      continue;
    }

    const heading = HEADING_RE.exec(line);
    if (heading) {
      blocks.push({
        kind: "heading",
        level: heading[1]?.length ?? 1,
        text: (heading[2] ?? "").trim(),
        startLine: lineNo,
        endLine: lineNo,
      });
      i++;
      continue;
    }

    // HTML 块:以 < 开头的连续行(语料为单行 <table>…</table>,兼容偶发跨行)
    if (HTML_OPEN_RE.test(line)) {
      const start = i;
      while (i < lines.length && HTML_OPEN_RE.test((lines[i] ?? "").trim())) i++;
      blocks.push({
        kind: "html",
        html: lines.slice(start, i).join("\n"),
        startLine: start + 1,
        endLine: i,
      });
      continue;
    }

    // 管道表格:表头 + 分隔行起手的连续 | 行;缺分隔行的孤立 | 行落段落
    if (TABLE_ROW_RE.test(line) && TABLE_DELIM_RE.test((lines[i + 1] ?? "").trim())) {
      const start = i;
      const headRow = splitTableRow(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && TABLE_ROW_RE.test((lines[i] ?? "").trim())) {
        rows.push(splitTableRow((lines[i] ?? "").trim()));
        i++;
      }
      blocks.push({ kind: "table", headRow, rows, startLine: start + 1, endLine: i });
      continue;
    }

    const listItem = LIST_ITEM_RE.exec(raw);
    if (listItem) {
      const start = i;
      const ordered = listItem[2] !== undefined;
      const items: string[] = [];
      while (i < lines.length) {
        const m = LIST_ITEM_RE.exec(lines[i] ?? "");
        if (!m || (m[2] !== undefined) !== ordered) break;
        items.push((m[3] ?? "").trim());
        i++;
      }
      blocks.push({ kind: "list", ordered, items, startLine: start + 1, endLine: i });
      continue;
    }

    // 段落:至下一空行或下一结构性构造为止的连续文本行
    const start = i;
    const text: string[] = [line];
    i++;
    while (i < lines.length) {
      const next = (lines[i] ?? "").trim();
      if (
        !next ||
        HEADING_RE.test(next) ||
        HTML_OPEN_RE.test(next) ||
        LIST_ITEM_RE.test(lines[i] ?? "") ||
        TABLE_ROW_RE.test(next)
      )
        break;
      text.push(next);
      i++;
    }
    blocks.push({ kind: "paragraph", text: text.join("\n"), startLine: start + 1, endLine: i });
  }

  return blocks;
}
