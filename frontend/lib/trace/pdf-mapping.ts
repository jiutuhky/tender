// 溯源坐标始终以原页显示空间为基准；本模块不依赖 DOM 或 PDF 引擎。
export interface PageSize { width: number; height: number }
export interface Region { page: number; bbox: [number, number, number, number] }
export interface LayoutBlock { mdStart: number; mdEnd: number; label: string; rects: Region[] }
export interface PdfMapping {
  schema: 2;
  coordinateSpace: "page-display-normalized";
  mdSha256: string;
  originSha256: string;
  previewSha256: string;
  mdLineCount: number;
  pages: (PageSize & { index: number })[];
  blocks: LayoutBlock[];
}
export interface DocumentVersion { sha256: string; origin_sha256?: string | null; preview_sha256?: string | null }
export type MappingResult = { mapping: PdfMapping; reason: null } | { mapping: null; reason: string };
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const positive = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v) && v > 0;
const integer = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v);
const digest = (v: unknown): v is string => typeof v === "string" && /^[a-f0-9]{64}$/.test(v);

export function validateMapping(raw: unknown, doc: DocumentVersion, pages: readonly PageSize[]): MappingResult {
  const fail = (reason: string): MappingResult => ({ mapping: null, reason });
  if (!object(raw)) return fail("原文映射暂不可用，请重试或在原文中核对。");
  if (raw.schema !== 2) return fail("该文档需要重新解析，才能定位原文区域。");
  if (raw.coordinateSpace !== "page-display-normalized" || !digest(raw.mdSha256) || !digest(raw.originSha256) || !digest(raw.previewSha256)
    || raw.mdSha256 !== doc.sha256 || raw.originSha256 !== doc.origin_sha256 || raw.previewSha256 !== doc.preview_sha256) {
    return fail("原文与映射版本不一致，请重新解析文档。");
  }
  if (!integer(raw.mdLineCount) || raw.mdLineCount < 1 || !Array.isArray(raw.pages) || raw.pages.length !== pages.length || !Array.isArray(raw.blocks)) {
    return fail("原文映射的页数或行号信息不完整。");
  }
  for (const [i, p] of raw.pages.entries()) {
    const actual = pages[i];
    if (!object(p) || p.index !== i || !positive(p.width) || !positive(p.height) || !actual
      || Math.abs((p.width / p.height) / (actual.width / actual.height) - 1) > 0.005) {
      return fail("原文页面尺寸与映射不一致，请重新解析文档。");
    }
  }
  for (const b of raw.blocks) {
    if (!object(b) || !integer(b.mdStart) || !integer(b.mdEnd) || b.mdStart < 1 || b.mdEnd < b.mdStart || b.mdEnd > raw.mdLineCount
      || typeof b.label !== "string" || !Array.isArray(b.rects) || b.rects.length === 0) return fail("原文映射的行号或区域信息无效。");
    for (const r of b.rects) {
      if (!object(r) || !integer(r.page) || r.page < 0 || r.page >= pages.length || !Array.isArray(r.bbox) || r.bbox.length !== 4
        || !r.bbox.every((n: unknown) => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= 1)
        || r.bbox[0] >= r.bbox[2] || r.bbox[1] >= r.bbox[3]) return fail("原文映射包含无效区域。");
    }
  }
  return { mapping: raw as unknown as PdfMapping, reason: null };
}

export function locatePdfRegions(mapping: PdfMapping, span: readonly number[] | undefined): Region[] {
  if (!span || span.length !== 2 || !span.every(integer)) return [];
  const [start, end] = span;
  if (start === undefined || end === undefined || start < 1 || end < start || end > mapping.mdLineCount) return [];
  const unique = new Map<string, Region>();
  for (const block of mapping.blocks) {
    if (block.mdStart > end || block.mdEnd < start) continue;
    for (const rect of block.rects) unique.set(`${rect.page}:${rect.bbox.join(",")}`, rect);
  }
  return [...unique.values()].sort((a, b) => a.page - b.page || a.bbox[1] - b.bbox[1] || a.bbox[0] - b.bbox[0]);
}

export function regionPixels(region: Region, page: PageSize) {
  const [l, t, r, b] = region.bbox;
  return { x: l * page.width, y: t * page.height, width: (r - l) * page.width, height: (b - t) * page.height };
}

/** 占位保留全部页的几何，Canvas 仅在可见页前后各一页内分配。 */
export function visiblePageRange(tops: readonly number[], sizes: readonly PageSize[], top: number, height: number): [number, number] {
  let lo = 0, hi = tops.length - 1;
  while (lo < hi) {
    const mid = Math.floor((lo + hi + 1) / 2);
    if ((tops[mid] ?? 0) <= top) lo = mid; else hi = mid - 1;
  }
  let end = lo;
  while (end + 1 < tops.length && (tops[end + 1] ?? Infinity) < top + height) end++;
  return [Math.max(0, lo - 1), Math.min(sizes.length - 1, end + 1)];
}

/** 同一条目可在同一原件中引用多段正文，将可定位区域合并后按页展示。 */
export function locatePdfReferences(mapping: PdfMapping, spans: readonly (readonly number[] | undefined)[]): Region[] {
  const unique = new Map<string, Region>();
  for (const span of spans) for (const region of locatePdfRegions(mapping, span)) {
    unique.set(`${region.page}:${region.bbox.join(",")}`, region);
  }
  return [...unique.values()].sort((a, b) => a.page - b.page || a.bbox[1] - b.bbox[1] || a.bbox[0] - b.bbox[0]);
}
