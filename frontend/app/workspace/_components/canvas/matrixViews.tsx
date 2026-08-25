"use client";

import { Fragment, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useWorkspaceStore, type MatrixSlot } from "@/lib/store/workspace";
import { MatrixWriteConflictError } from "@/lib/hagent/api";
import {
  asRec,
  asSourceRefs,
  fmtLineSpan,
  fmtMoney,
  fmtMoneyCompact,
  fmtSourceRef,
  fmtSourceRefs,
  type BasicInfoMatrix,
  type BusinessMatrix,
  type MatrixItemRow,
  type MatrixType,
  type RequirementItem,
  type ResponseStatus,
  type ScoringItem,
  type ScoringMatrix,
  type SourceRef,
  type TechnicalMatrix,
  type TimelineEvent,
} from "@/lib/hagent/matrix";
import { assessSourceRef } from "@/lib/trace/refs";
import { CheckIcon, ClockIcon, ProhibitIcon, WarningIcon } from "@/components/ui/icons";
import { isSlotInterrupted } from "./cardMeta";
import { useTrace, type TraceClaim } from "./traceContext";
import {
  DEADLINE_WARN_DAYS,
  bidDeadline,
  bidWindow,
  calendarDaysBetween,
  deadlineCountdown,
  fmtShortDeadline,
  parseDeadline,
  type DeadlineInfo,
} from "./deadline";

/** 来源签处要填的对照条数据。itemKey / refs / refIndex 由 SourceChips 就地补齐
 *  (它本来就持有这三样),调用点只描述「被核验的是什么」。 */
type ClaimInfo = Omit<TraceClaim, "itemKey" | "refs" | "refIndex">;

// 四张真实应答矩阵卡的卡面预览与抽屉详情。
// 数据订阅自 workspace store(store 为唯一事实来源,不经 CardInst 传递);
// 全部字段防御式读取,缺失一律「—」。视觉延续画布内联微版式 + 语义色对。

/* ---------- 中文化映射 ---------- */

const BIZ_CATEGORY: Record<string, string> = {
  qualification: "资格",
  conformity: "符合性",
  bid_document: "投标文件",
  pricing: "报价",
  guarantee: "保证金",
  contract: "合同",
  payment: "付款",
  delivery: "交付",
  acceptance: "验收",
  confidentiality: "保密",
  service: "服务",
  invalid_bid: "废标条款",
  other: "其他",
};

const TECH_CATEGORY: Record<string, string> = {
  scope: "范围",
  function: "功能",
  performance: "性能",
  architecture: "架构",
  environment: "环境",
  security: "安全",
  data: "数据",
  integration: "集成",
  testing: "测试",
  deliverable: "交付物",
  acceptance: "验收",
  training: "培训",
  maintenance: "运维",
  service: "服务",
  other: "其他",
};

const SCORE_GROUP: Record<string, string> = {
  price: "价格",
  business: "商务",
  technical: "技术",
  service: "服务",
  policy: "政策",
  other: "其他",
};

const TIMELINE_EVENT: Record<string, string> = {
  doc_sale: "标书发售",
  qa_deadline: "质疑截止",
  site_survey: "现场踏勘",
  bid_deadline: "投标截止",
  bid_opening: "开标",
  announcement: "结果公告",
};

const zh = (map: Record<string, string>, key: string | undefined): string =>
  (key && map[key]) || key || "其他";

/* ---------- 通用小态 ---------- */

/** 载入中卡面的骨架:形状呼应就绪后的四行语法(主指标块 → 结构条 → 注释行),
 *  静态呈现(Frost 禁无限循环动效),进行感由卡顶发丝线与题名行的「正在解析」承担。 */
function FaceSkeleton() {
  return (
    <div className="cv-skel" aria-hidden>
      <i className="hero" style={{ width: "46%" }} />
      <i style={{ width: "100%" }} />
      <i style={{ width: "72%" }} />
    </div>
  );
}

/** 非 ready 槽位的占位(预览与详情共用):正在… / 等待 / 失败 / 中断。
 *  卡面不发状态药丸——失败与中断由卡壳左缘色条(ArtifactCard 按 tone 挂类)加这里
 *  的一句直陈承担。失败与中断的详情视图附「对话重试」引导:本迭代不做定向重试,恢复走对话。 */
function SlotFallback({ slot, compact }: { slot: MatrixSlot<unknown>; compact?: boolean }) {
  const aborted = useWorkspaceStore((s) => s.phase === "error");
  const parsing = useWorkspaceStore(
    (s) => s.phase === "creating" || s.phase === "uploading" || s.phase === "running",
  );
  const retryHint = (
    <div style={{ color: "var(--label-3)", marginTop: 6 }}>可在对话中要求智能体重新解析。</div>
  );
  if (slot.status === "error") {
    const reason = slot.error ?? "未知错误";
    if (compact) {
      return (
        <div className="cv-face-fail">
          <b>
            <WarningIcon width={13} height={13} />
            未取到解析结果
          </b>
          {reason}
        </div>
      );
    }
    return (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <div style={{ color: "var(--orange-text)" }}>解析失败：{reason}</div>
        {retryHint}
      </div>
    );
  }
  // 流整体中断且本槽位未终态:如实定格为「解析中断」,不再假装进行中
  if (isSlotInterrupted(slot.status, aborted)) {
    if (compact) {
      return (
        <div className="cv-face-fail">
          <b>
            <ClockIcon width={13} height={13} />
            解析中断
          </b>
          未获得本矩阵结果
        </div>
      );
    }
    return (
      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        <div style={{ color: "var(--label-2)" }}>解析中断，未获得本矩阵结果</div>
        {retryHint}
      </div>
    );
  }
  // 卡面在「解析中」(载入中,或解析流进行中的待命槽)呈骨架,不再是一行灰字
  if (compact && (slot.status === "loading" || (slot.status === "empty" && parsing)))
    return <FaceSkeleton />;
  const text = slot.status === "loading" ? "正在载入矩阵数据……" : "等待智能体完成解析";
  return (
    <div style={{ fontSize: compact ? 12 : 13, color: "var(--label-3)", lineHeight: 1.7 }}>{text}</div>
  );
}

/** extraction_summary 非 complete 时的提示:一枚橙图标 + 一行字。
 *  不做黄块——语义色只落在图标上,文案照常读。 */
function SummaryStrip({ data }: { data: { extraction_summary?: { status?: string; warnings?: string[] } } }) {
  const s = data.extraction_summary;
  if (!s || s.status === "complete") return null;
  const label = s.status === "needs_review" ? "待复核" : "部分提取";
  return (
    <div className="cv-det-notice" role="status">
      <WarningIcon width={14} height={14} />
      <span>
        <b>{label}</b>
        {s.warnings?.length ? ` · ${s.warnings[0]}` : " · 提取结果可能不完整，请对照原文核验"}
      </span>
    </div>
  );
}

/** 来源签组:条目底部来源行、评分表「来源」列、否决项红区共用(票04)——
 *  每条 ref 一签,点签打开溯源预览(抽屉加宽对照双栏),点击行为三处完全一致。
 *  可用性分层判定收 lib/trace/refs:不可用置灰 + 悬停原因说明——用 aria-disabled
 *  而非 disabled,置灰签保持可悬停/可聚焦,原因说明才到得了用户。
 *  活跃签按签身份(itemKey + ref 序号)点亮:值相同的重复 ref 只亮被点的那枚,
 *  「活跃签点亮、其余保持常态」取字面语义。compact 用于表格窄列:签面只留行号,
 *  完整来源(含章节)转入悬停说明。无 Provider 场景(mock 详情)回退纯文本。 */
function SourceChips({
  refs,
  itemKey,
  compact,
  claim,
}: {
  refs: SourceRef[];
  /** 签身份命名空间:条目用业务 id,评分项/否决项加 score:/veto: 前缀防同抽屉撞键 */
  itemKey: string;
  compact?: boolean;
  /** 被核验条目的描述数据,随签带进预览层的对照条;itemKey/refs/refIndex 在此就地补齐 */
  claim?: ClaimInfo;
}) {
  const trace = useTrace();
  if (refs.length === 0) return null;
  if (!trace) {
    const text = compact ? fmtLineSpan(refs[0]?.line_span) : fmtSourceRefs(refs);
    if (!text) return null;
    return <span style={{ fontSize: 11, color: "var(--label-3)" }}>{text}</span>;
  }
  return (
    <>
      {refs.map((ref, i) => {
        const label = (compact ? fmtLineSpan(ref.line_span) : fmtSourceRef(ref)) || "原文";
        const usability = assessSourceRef(ref, trace.registryStatus, trace.registry);
        const chipKey = `${itemKey}:${i}`;
        const active = trace.activeKey === chipKey;
        const hoverText = compact ? fmtSourceRef(ref) || undefined : undefined;
        return (
          <button
            key={i}
            type="button"
            className={`cv-src-chip${active ? " is-active" : ""}${usability.usable ? "" : " is-disabled"}`}
            data-chip-key={chipKey}
            aria-disabled={usability.usable ? undefined : true}
            aria-pressed={active || undefined}
            title={usability.usable ? hoverText : usability.reason}
            onClick={
              usability.usable
                ? () =>
                    trace.openTrace(
                      ref,
                      chipKey,
                      claim ? { ...claim, itemKey, refs, refIndex: i } : undefined,
                    )
                : undefined
            }
          >
            {label}
          </button>
        );
      })}
    </>
  );
}

/** 「来源」标签行:条目底部与否决项红区共用。无 Provider 场景(mock 详情)回退
 *  纯文本行;refs 为空或文本拼不出时整行不渲染,不留孤立「来源」标签。 */
function SourceRow({
  refs,
  itemKey,
  claim,
}: {
  refs: SourceRef[];
  itemKey: string;
  claim?: ClaimInfo;
}) {
  const trace = useTrace();
  if (refs.length === 0) return null;
  if (!trace) {
    const text = fmtSourceRefs(refs);
    if (!text) return null;
    return <div style={{ fontSize: 11, color: "var(--label-3)", marginTop: 4 }}>来源 {text}</div>;
  }
  return (
    <div className="cv-src-row">
      <span className="cv-src-label">来源</span>
      <SourceChips refs={refs} itemKey={itemKey} claim={claim} />
    </div>
  );
}

/** 条目底部来源行:签身份取条目业务 id,缺 id 回退 useId 稳定实例键 */
function SourceLine({
  item,
  type,
  index,
}: {
  item: RequirementItem;
  type: MatrixType;
  index: number;
}) {
  const fallbackId = useId();
  if ((item.source_refs?.length ?? 0) === 0) return null;
  return (
    <SourceChips
      refs={item.source_refs ?? []}
      itemKey={item.id ?? fallbackId}
      compact
      claim={{
        matrixType: type,
        itemId: item.id ?? null,
        label: item.id ?? `#${index + 1}`,
        title: item.title || "未命名条目",
        requirementText: item.requirement_text ?? "",
        mandatory: !!item.mandatory,
        highRisk: isHighRisk(item),
      }}
    />
  );
}

/** 实质性标记:沿用招标文件的原生记号 ★,不另造图形;窄处只留符号,悬停给全称。 */
export function MandatoryMark({ full }: { full?: boolean }) {
  return (
    <span className="cv-star" title={full ? undefined : "实质性条款"}>
      {full ? "★ 实质性" : "★"}
    </span>
  );
}

/** 高风险标记:一枚红点 + 两个字,替代此前的红底药丸。 */
export function RiskMark({ label = "高风险" }: { label?: string }) {
  return <span className="cv-mark is-risk">{label}</span>;
}

/** 分组外壳:商务/技术条目分组与评分分组共用。
 *  抽屉自身已是一个面,里面再套边框卡就成了三层盒子 —— 改用一条分组眉 + hairline 列表。 */
function GroupCard({
  id,
  title,
  count,
  unit,
  extra,
  children,
}: {
  id?: string;
  title: string;
  count: number;
  unit: string;
  extra?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div id={id} className="cv-det-group">
      <div className="cv-det-group-head">
        <b>{title}</b>
        <span>
          {count} {unit}
        </span>
        {extra}
      </div>
      {children}
    </div>
  );
}

/** 渲染截断尾注:超出上限的条目可在对话中让智能体检索 */
function TruncNote({ rest, unit }: { rest: number; unit: string }) {
  if (rest <= 0) return null;
  return (
    <div style={{ fontSize: 12, color: "var(--label-3)", marginTop: 10 }}>
      其余 {rest} {unit}未展示，可在对话中让智能体检索
    </div>
  );
}

/** 详情空态短句(未提取到 / 过滤无匹配) */
function EmptyNote({ text }: { text: string }) {
  return <div style={{ fontSize: 13, color: "var(--label-3)", padding: "6px 0" }}>{text}</div>;
}

/* ---------- 聚合工具 ---------- */

function groupByCategory(items: RequirementItem[]): Array<[string, RequirementItem[]]> {
  const m = new Map<string, RequirementItem[]>();
  for (const it of items) {
    const key = it.category || "other";
    const arr = m.get(key);
    if (arr) arr.push(it);
    else m.set(key, [it]);
  }
  return [...m.entries()].sort((a, b) => b[1].length - a[1].length);
}

const mandatoryCount = (items: RequirementItem[]): number =>
  items.filter((i) => i.mandatory).length;

/* ---------- 预览:卡面紧凑视图 ---------- */
/* 四张卡共用一套四行语法:题名(卡壳给) / 主指标 / 结构条 / 信号行。
   卡面只回答一个问题,其余交给抽屉详情。信号行至多两项,风险信号优先于分类注释。 */

/** 结构条:分类构成压成一条 4px 堆叠条。段色走中性灰阶(深→浅 = 多→少),
 *  第五类及以后并成一段浅色尾;段数为 0 时整条不渲染。 */
function FaceStack({ parts }: { parts: number[] }) {
  const total = parts.reduce((a, b) => a + b, 0);
  if (parts.length === 0 || total <= 0) return null;
  const cls = ["s1", "s2", "s3", "s4"];
  return (
    <div className="cv-face-stack" aria-hidden>
      {parts.map((v, i) => (
        <i key={i} className={cls[i] ?? "rest"} style={{ flex: Math.max(v, 0) }} />
      ))}
    </div>
  );
}

/** 概要卡主指标:剩余天数。无从推导时由调用方降级到预算。 */
function deadlineHero(dl: DeadlineInfo): { value: string; unit: string; tone: string } | null {
  const d = dl.daysLeft;
  if (d === null) return null;
  if (d > 0)
    return { value: String(d), unit: "天后投标截止", tone: d <= DEADLINE_WARN_DAYS ? " is-warn" : "" };
  if (d === 0) return { value: "今日", unit: "投标截止", tone: " is-warn" };
  return { value: "已截止", unit: `已过 ${-d} 天`, tone: " is-past" };
}

function BasicInfoPreview({ slot }: { slot: MatrixSlot<BasicInfoMatrix> }) {
  if (slot.status !== "ready" || !slot.data) return <SlotFallback slot={slot} compact />;
  const d = slot.data;
  const p = d.project ?? {};
  const dl = bidDeadline(d.timeline);
  const hero = dl ? deadlineHero(dl) : null;
  const win = bidWindow(d.timeline);
  // 卡面金额一律走紧凑格式(「270 万元」):原文 text 可能带小数、大写与最高限价整句,
  // 放进 27px 大字会撑爆四行语法、把下面的卡顶到重叠。完整原文在抽屉里。
  const budget = fmtMoneyCompact(p.budget);
  // 招标文件没写明投标截止时,主指标顺位降到预算;两者都缺就如实说一句
  const fallbackHero = budget
    ? { value: budget.value, unit: `${budget.unit} · 项目预算`, tone: "" }
    : { value: "—", unit: p.name || d.project_name || "未识别关键信息", tone: "" };
  const h = hero ?? fallbackHero;
  // 信号行:主指标是截止时补「截止时刻 · 预算」;主指标已是预算时,说清截止缺席,
  // 再带一个采购方式——信号行总得有一条对下游决策有用的事实。
  const deadlineNote = hero
    ? dl?.at
      ? `${fmtShortDeadline(dl.at)} 截止`
      : ""
    : dl
      ? "投标截止时间无法解析"
      : "未写明投标截止时间";
  const note = [
    deadlineNote,
    hero && budget ? `预算 ${budget.value} ${budget.unit}` : "",
    !hero ? p.procurement_method || "" : "",
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <>
      <div className={`cv-face-hero${h.tone}`}>
        <b>{h.value}</b>
        <span>{h.unit}</span>
      </div>
      {win ? <FaceStack parts={[win.elapsed, win.left]} /> : null}
      <div className="cv-face-sig" style={win ? undefined : { marginTop: 13 }}>
        <span className="is-note">{note}</span>
      </div>
    </>
  );
}

function RequirementPreview({
  slot,
  unit,
  categoryMap,
  showRisk,
}: {
  slot: MatrixSlot<BusinessMatrix | TechnicalMatrix>;
  /** 主指标后缀:「条商务要求」/「条技术要求」 */
  unit: string;
  categoryMap: Record<string, string>;
  /** 技术卡专属:存在高风险条目时追加信号 */
  showRisk?: boolean;
}) {
  if (slot.status !== "ready" || !slot.data) return <SlotFallback slot={slot} compact />;
  const items = slot.data.items ?? [];
  const groups = groupByCategory(items);
  const top = groups.slice(0, 4);
  const rest = items.length - top.reduce((acc, [, arr]) => acc + arr.length, 0);
  const parts = [...top.map(([, arr]) => arr.length), ...(rest > 0 ? [rest] : [])];
  const mand = mandatoryCount(items);
  const risk = showRisk ? items.filter(isHighRisk).length : 0;
  // 信号行至多两项:实质性 > 高风险 > 分类注释。两个风险信号都在时不再挤注释
  const catNote = top
    .slice(0, 2)
    .map(([cat, arr]) => `${zh(categoryMap, cat)} ${arr.length}`)
    .join(" · ");
  return (
    <>
      <div className="cv-face-hero">
        <b>{items.length}</b>
        <span>{unit}</span>
      </div>
      <FaceStack parts={parts} />
      <div className="cv-face-sig">
        {mand > 0 && (
          <span className="is-mand">
            实质性 <b>{mand}</b> 项
          </span>
        )}
        {risk > 0 && (
          <span className="is-fatal">
            高风险 <b>{risk}</b>
          </span>
        )}
        {!(mand > 0 && risk > 0) && (
          <span className="is-note">{mand > 0 ? catNote : `无实质性条款${catNote ? ` · ${catNote}` : ""}`}</span>
        )}
      </div>
    </>
  );
}

/** 否决项计数:与详情红区同口径(文本拼得出来的 pass_fail_rules 才算数) */
function countVetoRules(ev: NonNullable<ScoringMatrix["evaluation"]>): number {
  return (ev.pass_fail_rules ?? []).filter((r) => vetoRuleText(r)).length;
}

function ScoringPreview({ slot }: { slot: MatrixSlot<ScoringMatrix> }) {
  if (slot.status !== "ready" || !slot.data) return <SlotFallback slot={slot} compact />;
  const ev = slot.data.evaluation ?? {};
  const dims: Array<[string, number | null | undefined]> = [
    ["技术", ev.technical_score],
    ["价格", ev.price_score],
    ["商务", ev.business_score],
  ];
  // 分值降序:结构条的灰阶按名次给(最重的一维最深),注释行也只报前两名
  const ranked = dims
    .filter((x): x is [string, number] => typeof x[1] === "number" && x[1] > 0)
    .sort((a, b) => b[1] - a[1]);
  const total = typeof ev.total_score === "number" && ev.total_score > 0 ? ev.total_score : null;
  const known = ranked.reduce((acc, [, v]) => acc + v, 0);
  const other = total !== null && total - known > 0 ? total - known : 0;
  const veto = countVetoRules(ev);
  const count = slot.data.items?.length ?? 0;
  const dimNote = ranked
    .slice(0, 2)
    .map(([k, v]) => `${k} ${fmtScore(v)}`)
    .join(" · ");
  return (
    <>
      <div className="cv-face-hero">
        <b>{total ?? "—"}</b>
        <span>{count > 0 ? `分 · ${count} 项` : "分"}</span>
      </div>
      <FaceStack parts={[...ranked.map(([, v]) => v), ...(other > 0 ? [other] : [])]} />
      <div className="cv-face-sig">
        {veto > 0 && (
          <span className="is-fatal">
            否决项 <b>{veto}</b> 条
          </span>
        )}
        <span className="is-note">{dimNote || ev.method || "综合评分法"}</span>
      </div>
    </>
  );
}

/** 卡面预览统一入口 */
export function MatrixCardPreview({ type }: { type: MatrixType }) {
  const slot = useWorkspaceStore((s) => s.matrices[type]);
  switch (type) {
    case "basic_info":
      return <BasicInfoPreview slot={slot as MatrixSlot<BasicInfoMatrix>} />;
    case "business":
      return (
        <RequirementPreview
          slot={slot as MatrixSlot<BusinessMatrix>}
          unit="条商务要求"
          categoryMap={BIZ_CATEGORY}
        />
      );
    case "technical":
      return (
        <RequirementPreview
          slot={slot as MatrixSlot<TechnicalMatrix>}
          unit="条技术要求"
          categoryMap={TECH_CATEGORY}
          showRisk
        />
      );
    case "scoring":
      return <ScoringPreview slot={slot as MatrixSlot<ScoringMatrix>} />;
  }
}

/* ---------- 详情:抽屉完整视图 ---------- */

/** 字段定义列表:八格键值网格里一半是空值时格线感最重,改成有值才列的 dt/dd。 */
function FieldList({ rows }: { rows: Array<[string, string]> }) {
  const filled = rows.filter(([, v]) => v && v !== "—");
  if (filled.length === 0) return null;
  return (
    <dl className="cv-det-dl">
      {filled.map(([k, v]) => (
        <Fragment key={k}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </Fragment>
      ))}
    </dl>
  );
}

function BasicInfoDetail({ slot }: { slot: MatrixSlot<BasicInfoMatrix> }) {
  if (slot.status !== "ready" || !slot.data) return <SlotFallback slot={slot} />;
  const d = slot.data;
  const p = d.project ?? {};
  const timeline = d.timeline ?? [];
  const packages = p.packages ?? [];
  const dl = bidDeadline(timeline);
  const hero = dl ? deadlineHero(dl) : null;
  const budget = fmtMoney(p.budget);
  return (
    <div>
      <SummaryStrip data={d} />
      {(hero || budget !== "—") && (
        <div className="cv-det-hero">
          {hero && (
            <div className={`cv-det-hero-cell${hero.tone}`}>
              <b>{hero.value}</b>
              <span>{hero.unit}</span>
            </div>
          )}
          {budget !== "—" && (
            <div className="cv-det-hero-cell">
              <b>{budget}</b>
              <span>项目预算</span>
            </div>
          )}
        </div>
      )}
      <FieldList
        rows={[
          // 项目编号不在此列:抽屉标题栏的副标题已经写着它
          ["项目名称", p.name || d.project_name || ""],
          ["采购方式", p.procurement_method || ""],
          ["评标方法", p.evaluation_method || ""],
          ["服务期 / 工期", p.delivery_or_service_period || ""],
          ["交付地点", p.delivery_location || ""],
          ["采购人", p.purchaser?.name || ""],
          ["代理机构", p.agency?.name || ""],
        ]}
      />
      {p.scope && (
        <div style={{ marginBottom: 16 }}>
          <div className="cv-det-sub">采购范围</div>
          <p style={{ fontSize: 13, lineHeight: 1.8, color: "var(--label-2)", margin: 0 }}>{p.scope}</p>
        </div>
      )}
      {packages.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div className="cv-det-sub">分包 · {packages.length} 个</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {packages.map((pkg, i) => (
              <div
                key={pkg.package_id ?? i}
                style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 11px", background: "var(--surface-2)", borderRadius: "var(--r-window)" }}
              >
                <span style={{ flex: 1, fontSize: 13, color: "var(--label)" }}>
                  {pkg.package_name || pkg.package_id || `包 ${i + 1}`}
                </span>
                <span style={{ fontSize: 12, color: "var(--label-3)", fontVariantNumeric: "tabular-nums" }}>
                  {fmtMoney(pkg.budget)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      {timeline.length > 0 && (
        <div>
          <div className="cv-det-sub">关键时间节点</div>
          <DetailTimeline timeline={timeline} />
        </div>
      )}
    </div>
  );
}

/** 时间线节点推导:解析时间并升序排布(不可解析的节点保持原序垫底)。
 *  now 走默认参收口(与 bidDeadline 同式),组件 render 保持纯净。 */
function timelineNodes(timeline: TimelineEvent[], now: number = Date.now()) {
  return timeline
    .map((ev, i) => {
      const t = ev.datetime ? parseDeadline(ev.datetime) : null;
      return { ev, i, t, days: t === null ? null : calendarDaysBetween(now, t) };
    })
    .sort((a, b) => (a.t ?? Number.MAX_SAFE_INTEGER) - (b.t ?? Number.MAX_SAFE_INTEGER) || a.i - b.i);
}

/** 概要详情纵向时间线:投标截止节点高亮并挂倒计时徽标,已过期节点整体淡化。 */
function DetailTimeline({ timeline }: { timeline: TimelineEvent[] }) {
  const nodes = timelineNodes(timeline);
  return (
    <div className="cv-det-timeline">
      {nodes.map(({ ev, i, days }) => {
        const isDeadline = ev.event === "bid_deadline";
        const past = days !== null && days < 0;
        const cd = isDeadline ? deadlineCountdown(days) : null;
        const cls = [
          "cv-det-tl-node",
          isDeadline ? "is-deadline" : "",
          past ? "is-past" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <div key={`${ev.event}-${i}`} className={cls}>
            <span className="cv-det-tl-dot" aria-hidden />
            <div style={{ minWidth: 0 }}>
              <div className="cv-det-tl-title">
                {zh(TIMELINE_EVENT, ev.event)}
                {cd && <span className="cv-det-tl-count">{cd.label}</span>}
              </div>
              <div className="cv-det-tl-meta">
                {ev.datetime || "—"}
                {ev.location ? ` · ${ev.location}` : ""}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ---------- 条目行人工动作(确认 / 应答状态标注,REST 落对象库) ---------- */

/** 签面文案与语义色修饰类同源:与状态徽标口径一致(绿=合规、蓝=正偏离、橙=负偏离) */
const RESPONSE_STATUS_OPTS: Array<{ k: ResponseStatus; label: string; cls: string }> = [
  { k: "compliant", label: "合规", cls: "is-compliant" },
  { k: "positive_deviation", label: "正偏离", cls: "is-positive" },
  { k: "negative_deviation", label: "负偏离", cls: "is-negative" },
];

/** 人工动作的在途/失败态 + 落库调用,按条目局部呈现不打扰其余条目。
 *  条目行与预览层对照条共用同一份 —— 冲突提示等口径只写一遍。 */
export function useItemAction(type: MatrixType) {
  const confirmItem = useWorkspaceStore((s) => s.confirmItem);
  const setItemResponseStatus = useWorkspaceStore((s) => s.setItemResponseStatus);
  const [busyItemId, setBusyItemId] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<{ id: string; msg: string } | null>(null);
  const runItemAction = (id: string, action: Promise<void>) => {
    setBusyItemId(id);
    setActionErr(null);
    action
      .catch((e: unknown) => {
        const msg =
          e instanceof MatrixWriteConflictError
            ? "该条目已被其他会话更新，已刷新为最新版本，请核对后重试"
            : e instanceof Error
              ? e.message
              : String(e);
        setActionErr({ id, msg });
      })
      .finally(() => setBusyItemId((cur) => (cur === id ? null : cur)));
  };
  return {
    busyItemId,
    actionErr,
    confirm: (itemId: string) => runItemAction(itemId, confirmItem(type, itemId)),
    setStatus: (itemId: string, status: ResponseStatus) =>
      runItemAction(itemId, setItemResponseStatus(type, itemId, status)),
  };
}

export function ItemActions({
  row,
  busy,
  error,
  onConfirm,
  onSetStatus,
}: {
  row: MatrixItemRow;
  busy: boolean;
  error: string | null;
  onConfirm: () => void;
  onSetStatus: (status: ResponseStatus) => void;
}) {
  return (
    <div className="cv-item-actions">
      <div className="cv-det-seg" role="group" aria-label="应答状态标注">
        {RESPONSE_STATUS_OPTS.map((o) => {
          const active = row.response_status === o.k;
          return (
            <button
              key={o.k}
              type="button"
              className={active ? `is-active ${o.cls}` : o.cls}
              aria-pressed={active}
              disabled={busy}
              onClick={() => {
                if (!active) onSetStatus(o.k);
              }}
            >
              {o.label}
            </button>
          );
        })}
      </div>
      <button
        type="button"
        className={row.confirmed ? "cv-item-confirm is-on" : "cv-item-confirm"}
        disabled={busy || row.confirmed}
        onClick={onConfirm}
      >
        {/* 勾号走 Phosphor 图标,不用 Unicode 图形字符 ✓ */}
        {row.confirmed ? (
          <>
            <CheckIcon width={12} height={12} aria-hidden="true" />
            已确认
          </>
        ) : (
          "确认"
        )}
      </button>
      {row.response_note && <span className="cv-item-note">备注 {row.response_note}</span>}
      {error && (
        <span className="cv-item-action-err" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

type ReqFilter = "all" | "mand" | "risk";

const isHighRisk = (it: RequirementItem): boolean => it.risk_level === "high";

/** 过滤签定义:签面文案与筛选谓词同源,计数与筛选不会漂移 */
const REQ_FILTERS: Array<{ k: ReqFilter; label: string; pred: (it: RequirementItem) => boolean }> = [
  { k: "all", label: "全部", pred: () => true },
  { k: "mand", label: "★ 实质性", pred: (it) => !!it.mandatory },
  { k: "risk", label: "高风险", pred: isHighRisk },
];

/** 条目行状态标记:常驻的是状态(读),按需的是操作(点)。两者共用行尾同一个槽,悬停互斥切换。 */
function rowState(row: MatrixItemRow | undefined): { text: string; cls: string } | null {
  if (!row) return null;
  const opt = RESPONSE_STATUS_OPTS.find((o) => o.k === row.response_status);
  if (row.confirmed) return { text: opt ? `已确认 · ${opt.label}` : "已确认", cls: opt?.cls ?? "is-compliant" };
  if (opt) return { text: opt.label, cls: opt.cls };
  return { text: "待应答", cls: "is-idle" };
}


function RequirementRow({
  item,
  index,
  type,
  row,
  action,
}: {
  item: RequirementItem;
  index: number;
  type: MatrixType;
  row: MatrixItemRow | undefined;
  action: ReturnType<typeof useItemAction>;
}) {
  const [open, setOpen] = useState(false);
  // 「展开原文」按实际是否被截断决定,不按字数猜:中英数混排的行宽差一倍,
  // 猜出来的阈值必然在一部分条目上给出没用的按钮或漏掉该给的按钮。
  const [clampable, setClampable] = useState(false);
  const textRef = useRef<HTMLParagraphElement>(null);
  const text = item.requirement_text ?? "";
  useLayoutEffect(() => {
    const el = textRef.current;
    if (!el) return;
    setClampable(el.scrollHeight - el.clientHeight > 1);
  }, [text]);
  const state = rowState(row);
  return (
    <div className="cv-det-item">
      <div className="cv-det-item-top">
        {item.mandatory && <MandatoryMark />}
        {isHighRisk(item) && !item.mandatory && <RiskMark />}
        <span className="cv-det-item-title">{item.title || "未命名条目"}</span>
      </div>
      {text && (
        <p ref={textRef} className={open ? "cv-det-item-text" : "cv-det-item-text is-clamped"}>
          {text}
        </p>
      )}
      <div className="cv-det-foot">
        <span className="cv-det-id">{item.id ?? `#${index + 1}`}</span>
        <SourceLine item={item} type={type} index={index} />
        {clampable && (
          <button type="button" className="cv-det-more" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
            {open ? "收起" : "展开原文"}
          </button>
        )}
        {state && <span className={`cv-det-state ${state.cls}`}>{state.text}</span>}
      </div>
      {row && (
        <div className="cv-det-act">
          <ItemActions
            row={row}
            busy={action.busyItemId === row.item_id}
            error={action.actionErr?.id === row.item_id ? action.actionErr.msg : null}
            onConfirm={() => action.confirm(row.item_id)}
            onSetStatus={(status) => action.setStatus(row.item_id, status)}
          />
        </div>
      )}
    </div>
  );
}

/** business / technical 共用的条目详情:过滤段控与分类锚点同行吸顶(锚点自身横滚),
 *  几百条逐条响应中快速聚焦致命条款;条目按 category 分组,渲染上限 300 条。
 *  条目行的人工动作(确认/应答状态)悬停浮现,经 store 写 REST 端点落对象库。 */
function RequirementDetail({
  type,
  slot,
  categoryMap,
}: {
  type: MatrixType;
  slot: MatrixSlot<BusinessMatrix | TechnicalMatrix>;
  categoryMap: Record<string, string>;
}) {
  const [filter, setFilter] = useState<ReqFilter>("all");
  const anchorBase = useId();
  const headRef = useRef<HTMLDivElement>(null);
  const action = useItemAction(type);
  if (slot.status !== "ready" || !slot.data) return <SlotFallback slot={slot} />;
  const d = slot.data;
  const all = d.items ?? [];
  // 行级管理状态(确认/应答状态/乐观锁版本)按业务 id 对齐条目 payload
  const rowsById = new Map((slot.itemRows ?? []).map((r) => [r.item_id, r]));
  const filters = REQ_FILTERS.map((f) => ({ ...f, n: all.filter(f.pred).length }));
  const active = REQ_FILTERS.find((f) => f.k === filter) ?? REQ_FILTERS[0]!;
  const filtered = all.filter(active.pred);
  const items = filtered.slice(0, 300);
  const groups = groupByCategory(items);
  const gid = (cat: string) => `${anchorBase}-${cat}`;
  // 锚点跳转:抽屉体自滚动,并抵消吸顶过滤头的遮挡高度(scrollIntoView 会把分组顶进头下面)
  const jumpTo = (cat: string) => {
    const el = document.getElementById(gid(cat));
    const body = el?.closest(".cv-drawer-body");
    if (!el || !body) return;
    const offset = (headRef.current?.offsetHeight ?? 0) + 8;
    const delta = el.getBoundingClientRect().top - body.getBoundingClientRect().top - offset;
    body.scrollBy({
      top: delta,
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
  };
  return (
    <div>
      <SummaryStrip data={d} />
      <div ref={headRef} className="cv-det-head">
        <div className="cv-det-seg" role="group" aria-label="条目过滤">
          {filters.map((f) => (
            <button
              key={f.k}
              type="button"
              className={filter === f.k ? "is-active" : undefined}
              aria-pressed={filter === f.k}
              onClick={() => setFilter(f.k)}
            >
              {f.label} {f.n}
            </button>
          ))}
        </div>
        {groups.length > 1 && (
          <div className="cv-det-anchors">
            {groups.map(([cat, arr]) => (
              <button key={cat} type="button" className="cv-det-anchor" onClick={() => jumpTo(cat)}>
                {zh(categoryMap, cat)}
                <span className="cv-det-anchor-n">{arr.length}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      {items.length === 0 ? (
        <EmptyNote text={all.length === 0 ? "未提取到条目" : "当前过滤下无匹配条目"} />
      ) : (
        groups.map(([cat, arr]) => (
          <GroupCard
            key={cat}
            id={gid(cat)}
            title={zh(categoryMap, cat)}
            count={arr.length}
            unit="条"
            extra={
              mandatoryCount(arr) > 0 ? (
                <span className="cv-det-group-mand">实质性 {mandatoryCount(arr)}</span>
              ) : undefined
            }
          >
            {arr.map((it, i) => (
              <RequirementRow
                key={it.id ?? i}
                item={it}
                index={i}
                type={type}
                row={it.id ? rowsById.get(it.id) : undefined}
                action={action}
              />
            ))}
          </GroupCard>
        ))
      )}
      <TruncNote rest={filtered.length - items.length} unit="条" />
    </div>
  );
}

/** 分组固定排序:与招标文件评分办法的常见叙述顺序一致,未知分组按出现序垫底 */
const SCORE_GROUP_ORDER: readonly string[] = ["price", "business", "technical", "service", "policy", "other"];

/** 分值展示:整数原样,小数保留一位(「其他」由总分差值推得,可能带小数) */
const fmtScore = (n: number): string => (Number.isInteger(n) ? String(n) : n.toFixed(1));

/** pass_fail_rules 记录无形状约束(LLM 产出):字符串原样,对象取常见文案字段,兜底 JSON 串如实呈现 */
function vetoRuleText(r: unknown): string {
  if (typeof r === "string") return r;
  const rec = asRec(r);
  if (rec) {
    for (const k of ["rule_text", "rule", "text", "description", "title", "condition", "requirement"]) {
      const v = rec[k];
      if (typeof v === "string" && v.trim()) return v;
    }
    return JSON.stringify(r);
  }
  return r == null ? "" : String(r);
}

function ScoringDetail({ slot }: { slot: MatrixSlot<ScoringMatrix> }) {
  if (slot.status !== "ready" || !slot.data) return <SlotFallback slot={slot} />;
  const d = slot.data;
  const ev = d.evaluation ?? {};

  // 否决项红区:与实质性条款同级致命,置于详情最顶部。
  // 带合法 source_refs 的条目给来源签(票04,同一套签组件);无 refs 的无签、无兜底。
  const vetoRules = (ev.pass_fail_rules ?? [])
    .map((r) => {
      const rec = asRec(r);
      return {
        text: vetoRuleText(r),
        refs: asSourceRefs(rec?.source_refs),
        // 签身份优先业务 id(如 PFR-005),与条目/评分项同口径;缺 id 回退渲染序
        id: typeof rec?.id === "string" && rec.id ? rec.id : null,
      };
    })
    .filter((v) => v.text);

  // 分值结构:价格/商务/技术取评分办法标称分,其他 = 总分与三格之和的差值(>0 才画);
  // 段色按名次走中性灰阶(.is-rank1..3 / .is-other),TSX 不写色值
  const ranked = ([
    ["价格", ev.price_score],
    ["商务", ev.business_score],
    ["技术", ev.technical_score],
  ] as Array<[string, number | null | undefined]>)
    .filter((x): x is [string, number] => typeof x[1] === "number" && x[1] > 0)
    .sort((a, b) => b[1] - a[1]);
  const parts: Array<{ label: string; score: number; cls: string }> = ranked.map(([label, score], i) => ({
    label,
    score,
    cls: `is-rank${i + 1}`,
  }));
  const known = parts.reduce((acc, p) => acc + p.score, 0);
  const total = typeof ev.total_score === "number" && ev.total_score > 0 ? ev.total_score : null;
  if (total !== null && total - known > 0) parts.push({ label: "其他", score: total - known, cls: "is-other" });
  const base = total ?? known;

  // 评分项分组 + 小计
  const itemsAll = d.items ?? [];
  const items = itemsAll.slice(0, 300);
  const gmap = new Map<string, ScoringItem[]>();
  for (const it of items) {
    const k = it.group || "other";
    const arr = gmap.get(k);
    if (arr) arr.push(it);
    else gmap.set(k, [it]);
  }
  const orderedKeys = [
    ...SCORE_GROUP_ORDER.filter((k) => gmap.has(k)),
    ...[...gmap.keys()].filter((k) => !SCORE_GROUP_ORDER.includes(k)),
  ];

  return (
    <div>
      <SummaryStrip data={d} />
      {vetoRules.length > 0 && (
        <section className="cv-det-veto">
          <div className="cv-det-veto-title">
            <ProhibitIcon width={15} height={15} />
            否决项 / 通过性条款
            <span className="cv-det-veto-count">{vetoRules.length} 条</span>
          </div>
          {vetoRules.map((v, i) => (
            <div key={i} className="cv-det-veto-row">
              <span className="cv-det-veto-no" aria-hidden>
                {String(i + 1).padStart(2, "0")}
              </span>
              <div style={{ minWidth: 0 }}>
                <span>{v.text}</span>
                <SourceRow
                  refs={v.refs}
                  itemKey={`veto:${v.id ?? i}`}
                  claim={{
                    matrixType: "scoring",
                    itemId: null,
                    label: `否决项 ${v.id ?? i + 1}`,
                    title: "否决项 / 通过性条款",
                    requirementText: v.text,
                    highRisk: true,
                  }}
                />
              </div>
            </div>
          ))}
        </section>
      )}
      {base > 0 && parts.length > 0 && (
        <div style={{ marginBottom: 18 }}>
          <div className="cv-det-scorebar">
            {parts.map((p) => (
              <i key={p.label} className={p.cls} style={{ width: `${(p.score / base) * 100}%` }} />
            ))}
          </div>
          <div className="cv-det-scorelegend">
            {parts.map((p) => (
              <span key={p.label}>
                <i className={p.cls} aria-hidden />
                {p.label} {fmtScore(p.score)} · {Math.round((p.score / base) * 100)}%
              </span>
            ))}
          </div>
        </div>
      )}
      {orderedKeys.length > 0 ? (
        orderedKeys.map((key) => {
          const arr = gmap.get(key) ?? [];
          const subtotal = arr.reduce((acc, it) => acc + (typeof it.max_score === "number" ? it.max_score : 0), 0);
          return (
            <GroupCard
              key={key}
              title={zh(SCORE_GROUP, key)}
              count={arr.length}
              unit="项"
              extra={<span className="cv-det-group-note">{fmtScore(subtotal)} 分</span>}
            >
              {arr.map((it, i) => (
                <div key={it.id ?? i} className="cv-det-srow">
                  <div className="cv-det-srow-main">
                    <div className="cv-det-srow-title">
                      {it.mandatory_gate && <RiskMark label="否决" />}
                      {it.title || `评分项 ${i + 1}`}
                    </div>
                    {it.scoring_rule && <p className="cv-det-srow-rule">{it.scoring_rule}</p>}
                    {(it.source_refs?.length ?? 0) > 0 && (
                      <div className="cv-det-foot">
                        <SourceChips
                          refs={it.source_refs ?? []}
                          itemKey={`score:${it.id ?? `${key}#${i}`}`}
                          compact
                          claim={{
                            matrixType: "scoring",
                            itemId: null,
                            label: `评分项 ${it.id ?? i + 1}`,
                            title: it.title || `评分项 ${i + 1}`,
                            requirementText: it.scoring_rule || "",
                            highRisk: !!it.mandatory_gate,
                          }}
                        />
                      </div>
                    )}
                  </div>
                  <span className="cv-det-srow-score">{it.max_score ?? "—"}</span>
                </div>
              ))}
            </GroupCard>
          );
        })
      ) : (
        <EmptyNote text="未提取到评分项" />
      )}
      <TruncNote rest={itemsAll.length - items.length} unit="项" />
    </div>
  );
}

/** 抽屉标题栏的副标题:详情正文不再自带一遍矩阵名与摘要(抽屉头已经写着标题,
 *  正文再来一行 SecTitle 就是同一件事说两遍)。摘要上提到头里,正文直接从内容开始。 */
export function useMatrixDetailSummary(type: MatrixType): string | null {
  const slot = useWorkspaceStore((s) => s.matrices[type]);
  if (slot.status !== "ready" || !slot.data) return null;
  if (type === "basic_info") {
    const p = (slot.data as BasicInfoMatrix).project ?? {};
    return p.number ? `项目编号 ${p.number}` : p.procurement_method || null;
  }
  if (type === "scoring") {
    const sc = slot.data as ScoringMatrix;
    const total = sc.evaluation?.total_score;
    const n = sc.items?.length ?? 0;
    return [typeof total === "number" ? `总分 ${fmtScore(total)}` : "", n > 0 ? `${n} 项评分项` : ""]
      .filter(Boolean)
      .join(" · ") || null;
  }
  const items = (slot.data as BusinessMatrix | TechnicalMatrix).items ?? [];
  const mand = mandatoryCount(items);
  return `共 ${items.length} 条${mand > 0 ? ` · 实质性 ${mand} 项` : ""}`;
}

/** 抽屉详情统一入口 */
export function MatrixCardDetail({ type }: { type: MatrixType }) {
  const slot = useWorkspaceStore((s) => s.matrices[type]);
  switch (type) {
    case "basic_info":
      return <BasicInfoDetail slot={slot as MatrixSlot<BasicInfoMatrix>} />;
    case "business":
      return <RequirementDetail type={type} slot={slot as MatrixSlot<BusinessMatrix>} categoryMap={BIZ_CATEGORY} />;
    case "technical":
      return <RequirementDetail type={type} slot={slot as MatrixSlot<TechnicalMatrix>} categoryMap={TECH_CATEGORY} />;
    case "scoring":
      return <ScoringDetail slot={slot as MatrixSlot<ScoringMatrix>} />;
  }
}
