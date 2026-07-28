// bid-response-matrix skill 输出的四张应答矩阵的类型契约与防御式读取工具。
// 数据源是 hagent 对象库 REST 读端点(票08,契约见 hagent/src/hagent/assets/schemas.py):
// meta(envelope+固定标量)+ 区段行由 assembleMatrixDocument 拼回旧 final JSON 形状,
// 视图契约不变。数据由 LLM 产出:所有字段按可缺失防御性读取,只 type UI 会渲染的部分,
// 其余走 index signature。

export type MatrixType = "basic_info" | "business" | "technical" | "scoring";

export const MATRIX_TYPES: readonly MatrixType[] = [
  "basic_info",
  "business",
  "technical",
  "scoring",
];

/* ---------- 公共 envelope ---------- */

export interface SourceRef {
  document_id?: string;
  /** 1-based 闭区间 Markdown 行号 [start, end] */
  line_span?: number[];
  section?: string | null;
}

export interface ExtractionSummary {
  status?: string; // complete | partial | needs_review
  confidence?: string; // high | medium | low
  warnings?: string[];
}

export interface MatrixEnvelope {
  schema_version?: string;
  matrix_type?: string;
  project_id?: string | null;
  project_name?: string | null;
  generated_at?: string | null;
  source_documents?: unknown[];
  extraction_summary?: ExtractionSummary;
  [k: string]: unknown;
}

/* ---------- basic_info ---------- */

export interface Money {
  amount?: number | null;
  currency?: string;
  text?: string | null;
}

export interface ContactParty {
  name?: string | null;
  contact?: string | null;
  phone?: string | null;
  address?: string | null;
}

export interface PackageInfo {
  package_id?: string | null;
  package_name?: string | null;
  budget?: Money;
  scope?: string | null;
  source_refs?: SourceRef[];
}

export interface TimelineEvent {
  event?: string;
  datetime?: string | null;
  timezone?: string | null;
  location?: string | null;
  source_refs?: SourceRef[];
}

export interface BasicInfoMatrix extends MatrixEnvelope {
  project?: {
    name?: string | null;
    number?: string | null;
    procurement_method?: string | null;
    evaluation_method?: string | null;
    purchaser?: ContactParty;
    agency?: ContactParty;
    packages?: PackageInfo[];
    budget?: Money;
    scope?: string | null;
    delivery_or_service_period?: string | null;
    delivery_location?: string | null;
  };
  timeline?: TimelineEvent[];
  contacts?: unknown[];
}

/* ---------- business / technical ---------- */

export interface RequirementItem {
  id?: string;
  category?: string;
  title?: string;
  requirement_text?: string;
  mandatory?: boolean;
  response_required?: boolean;
  evidence_required?: string[];
  acceptance_criteria?: string[];
  related_forms?: string[];
  related_deliverables?: string[];
  risk_level?: string;
  deadline_or_period?: string | null;
  source_refs?: SourceRef[];
  confidence?: string;
  notes?: string | null;
}

export interface BusinessMatrix extends MatrixEnvelope {
  items?: RequirementItem[];
  compliance_overview?: {
    qualification_review?: unknown[];
    conformity_review?: unknown[];
    invalid_bid_triggers?: unknown[];
  };
}

export interface TechnicalMatrix extends MatrixEnvelope {
  items?: RequirementItem[];
  deliverables?: unknown[];
  acceptance_requirements?: unknown[];
}

/* ---------- scoring ---------- */

export interface ScoringItem {
  id?: string;
  group?: string; // price | business | technical | ...
  title?: string;
  max_score?: number | null;
  scoring_rule?: string;
  /** 通过性门槛项:不满足即否决,与 pass_fail_rules 同级致命 */
  mandatory_gate?: boolean;
  source_refs?: SourceRef[];
  confidence?: string;
  notes?: string | null;
}

export interface ScoringMatrix extends MatrixEnvelope {
  evaluation?: {
    method?: string | null;
    total_score?: number | null;
    price_score?: number | null;
    business_score?: number | null;
    technical_score?: number | null;
    pass_fail_rules?: unknown[];
    tie_break_rules?: unknown[];
  };
  items?: ScoringItem[];
}

/* ---------- 防御式取值(自原 ResultView 移植) ---------- */

export type Rec = Record<string, unknown>;

export const asRec = (v: unknown): Rec | null =>
  typeof v === "object" && v !== null && !Array.isArray(v) ? (v as Rec) : null;
export const asArr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
export const str = (v: unknown): string => (typeof v === "string" ? v : "");
export const num = (v: unknown): number | null =>
  typeof v === "number" && Number.isFinite(v) ? v : null;

/** unknown → SourceRef 列表(pass_fail_rules 等无形状约束区段用):错型字段丢弃,
 *  非空的坏条目(字段全坏的对象、字符串等)退化为空壳 ref——签走置灰 + 悬停原因分层,
 *  坏数据可见不静默吞掉;只有 null/undefined 条目与空数组才是「不显示」。 */
export function asSourceRefs(v: unknown): SourceRef[] {
  return asArr(v).flatMap((e): SourceRef[] => {
    if (e == null) return [];
    const rec = asRec(e);
    const ref: SourceRef = {};
    if (rec) {
      if (typeof rec.document_id === "string") ref.document_id = rec.document_id;
      if (Array.isArray(rec.line_span) && rec.line_span.every((n): n is number => typeof n === "number"))
        ref.line_span = rec.line_span;
      if (typeof rec.section === "string") ref.section = rec.section;
    }
    return [ref];
  });
}

/** 金额:优先 Money.text 原文,否则「2,700,000 元」;缺失显示「—」 */
export function fmtMoney(money: Money | undefined | null): string {
  if (!money) return "—";
  if (money.text) return money.text;
  const n = num(money.amount);
  if (n === null || n <= 0) return "—";
  return `${n.toLocaleString("zh-CN")} 元`;
}

/** line_span [12, 34] → 「L12-34」;单点 → 「L12」;缺失 → "" */
export function fmtLineSpan(ls: number[] | undefined): string {
  const [a, b] = ls ?? [];
  if (a == null) return "";
  if (b == null || b === a) return `L${a}`;
  return `L${a}-${b}`;
}

/** 单条 source_ref → 「L12-34 · 投标人须知前附表」;两段皆缺 → "" */
export function fmtSourceRef(ref: SourceRef): string {
  return [fmtLineSpan(ref.line_span), ref.section ?? ""].filter(Boolean).join(" · ");
}

/** source_refs → 多条展示串(最多前 3 条) */
export function fmtSourceRefs(refs: SourceRef[] | undefined): string {
  if (!refs?.length) return "";
  return refs.slice(0, 3).map(fmtSourceRef).filter(Boolean).join(";");
}

/* ---------- 对象库 REST 契约(与 hagent assets/schemas.py 输出模型对齐) ---------- */

export type ResponseStatus = "pending" | "compliant" | "positive_deviation" | "negative_deviation";

export type MatrixLifecycle = "empty" | "drafting" | "published" | "published_drafting";

/** 对象库条目行:payload 是源 schema 的 item shape,应答状态/确认/乐观锁版本挂行级 */
export interface MatrixItemRow {
  matrix_type: string;
  stage: string;
  item_id: string;
  section: string;
  payload: Rec;
  response_status: ResponseStatus | null;
  response_note: string | null;
  confirmed: boolean;
  version: number;
}

export interface MatrixStats {
  stage: string;
  total: number;
  by_section: Record<string, number>;
  by_response_status: Record<string, number>;
  confirmed_count: number;
  mandatory_count: number;
  by_category: Record<string, number>;
}

export interface MatrixOverview {
  matrix_type: string;
  state: MatrixLifecycle;
  current_rev: number;
  updated_at: string | null;
  meta: Rec;
  stats: MatrixStats;
}

export interface MatrixItemsPage {
  items: MatrixItemRow[];
  total_count: number;
  limit: number;
  offset: number;
  has_more: boolean;
  next_offset: number | null;
}

export interface MatrixStatusEntry {
  matrix_type: string;
  state: MatrixLifecycle;
  current_rev: number;
  updated_at: string | null;
  draft_count: number;
  current_count: number;
  last_validation: Rec | null;
}

export interface ProjectMatrixStatus {
  project_id: string;
  matrices: MatrixStatusEntry[];
}

/** 已发布(含逃生门重抽中)的矩阵才作为前端呈现的数据源 */
export const isPublishedState = (state: string): boolean =>
  state === "published" || state === "published_drafting";

/** 区段 dot-path(镜像服务端 projection._section_path):unresolved_items 归 validation 下 */
const sectionPath = (section: string): string[] =>
  section === "unresolved_items" ? ["validation", "unresolved_items"] : section.split(".");

/** 把 REST 读端点数据拼回旧 final JSON 形状(对拍服务端 projection.build_matrix_document):
 *  meta = envelope + 固定标量(project / evaluation),区段行 payload 按 dot-path 嵌回原位置。
 *  视图全程防御式读取,缺省区段不强造空桶。 */
export function assembleMatrixDocument<T extends MatrixEnvelope>(
  meta: Rec,
  rows: MatrixItemRow[],
): T {
  const body: Rec = structuredClone(meta);
  for (const row of rows) {
    const path = sectionPath(row.section);
    let node: Rec = body;
    for (const key of path.slice(0, -1)) {
      const child = asRec(node[key]);
      if (child) {
        node = child;
      } else {
        const fresh: Rec = {};
        node[key] = fresh;
        node = fresh;
      }
    }
    const leaf = path[path.length - 1] ?? row.section;
    const bucket = node[leaf];
    if (Array.isArray(bucket)) bucket.push(row.payload);
    else node[leaf] = [row.payload];
  }
  return body as T;
}
