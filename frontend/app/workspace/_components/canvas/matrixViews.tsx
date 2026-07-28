"use client";

import { useId, useRef, useState, type ReactNode } from "react";
import { useWorkspaceStore, type MatrixSlot } from "@/lib/store/workspace";
import { MatrixWriteConflictError } from "@/lib/hagent/api";
import {
  asRec,
  asSourceRefs,
  fmtLineSpan,
  fmtMoney,
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
import { SecTitle, Table, type Col } from "./CardDetail";
import { isSlotInterrupted } from "./cardMeta";
import { useTrace } from "./traceContext";
import { bidDeadline, calendarDaysBetween, deadlineCountdown, parseDeadline } from "./deadline";

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

/** 载入中卡面的骨架条:形状呼应就绪后的行式内容,静态呈现(Frost 禁无限循环动效),
 *  进行感由卡顶蓝色进度条与「解析中」徽标承担。 */
function FaceSkeleton() {
  return (
    <div className="cv-skel" aria-hidden>
      {[0.92, 0.64, 0.8, 0.48].map((w, i) => (
        <i key={i} style={{ width: `${w * 100}%` }} />
      ))}
    </div>
  );
}

/** 非 ready 槽位的占位(预览与详情共用):正在… / 等待 / 失败 / 中断。
 *  失败与中断的详情视图附「对话重试」引导——本迭代不做定向重试,恢复走对话。 */
function SlotFallback({ slot, compact }: { slot: MatrixSlot<unknown>; compact?: boolean }) {
  const aborted = useWorkspaceStore((s) => s.phase === "error");
  const parsing = useWorkspaceStore(
    (s) => s.phase === "creating" || s.phase === "uploading" || s.phase === "running",
  );
  const fs = compact ? 11.5 : 13;
  const retryHint = (
    <div style={{ color: "var(--label-3)", marginTop: 6 }}>可在对话中要求智能体重新解析。</div>
  );
  if (slot.status === "error") {
    return (
      <div style={{ fontSize: fs, lineHeight: 1.7 }}>
        <div style={{ color: "var(--orange-text)" }}>
          解析失败{compact ? "" : `：${slot.error ?? "未知错误"}`}
        </div>
        {!compact && retryHint}
      </div>
    );
  }
  // 流整体中断且本槽位未终态:如实定格为「解析中断」,不再假装进行中
  if (isSlotInterrupted(slot.status, aborted)) {
    return (
      <div style={{ fontSize: fs, lineHeight: 1.7 }}>
        <div style={{ color: "var(--label-2)" }}>解析中断，未获得本矩阵结果</div>
        {!compact && retryHint}
      </div>
    );
  }
  // 卡面在「解析中」(徽标同语义:载入中,或解析流进行中的待命槽)呈骨架条,不再是一行灰字
  if (compact && (slot.status === "loading" || (slot.status === "empty" && parsing)))
    return <FaceSkeleton />;
  const text = slot.status === "loading" ? "正在载入矩阵数据…" : "等待智能体完成解析";
  return <div style={{ fontSize: fs, color: "var(--label-3)", lineHeight: 1.7 }}>{text}</div>;
}

/** extraction_summary 非 complete 时的黄条提示 */
function SummaryStrip({ data }: { data: { extraction_summary?: { status?: string; warnings?: string[] } } }) {
  const s = data.extraction_summary;
  if (!s || s.status === "complete") return null;
  const label = s.status === "needs_review" ? "待复核" : "部分提取";
  return (
    <div
      style={{
        fontSize: 12,
        color: "var(--orange-text)",
        background: "rgba(255,149,0,.12)",
        borderRadius: 8,
        padding: "7px 10px",
        marginBottom: 12,
      }}
    >
      {label}
      {s.warnings?.length ? ` · ${s.warnings[0]}` : " · 提取结果可能不完整，请对照原文核验"}
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
}: {
  refs: SourceRef[];
  /** 签身份命名空间:条目用业务 id,评分项/否决项加 score:/veto: 前缀防同抽屉撞键 */
  itemKey: string;
  compact?: boolean;
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
            onClick={usability.usable ? () => trace.openTrace(ref, chipKey) : undefined}
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
function SourceRow({ refs, itemKey }: { refs: SourceRef[]; itemKey: string }) {
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
      <SourceChips refs={refs} itemKey={itemKey} />
    </div>
  );
}

/** 条目底部来源行:签身份取条目业务 id,缺 id 回退 useId 稳定实例键 */
function SourceLine({ item }: { item: RequirementItem }) {
  const fallbackId = useId();
  return <SourceRow refs={item.source_refs ?? []} itemKey={item.id ?? fallbackId} />;
}

/** ★ 实质性徽标:与卡面 .cv-face-badge 同皮(票3评审遗留③,橙=实质性、红=高风险统一口径) */
function MandatoryBadge() {
  return <span className="cv-face-badge is-mand">★ 实质性</span>;
}

/** 分组卡外壳:商务/技术条目分组与评分分组共用 */
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
    <div
      id={id}
      style={{ border: "1px solid var(--separator)", borderRadius: 12, padding: "12px 14px", background: "var(--surface)" }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--label)" }}>{title}</span>
        <span style={{ fontSize: 11, color: "var(--label-3)" }}>
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
    <div style={{ fontSize: 11.5, color: "var(--label-3)", marginTop: 10 }}>
      其余 {rest} {unit}未展示，可在对话中让智能体检索
    </div>
  );
}

/** 详情空态短句(未提取到 / 过滤无匹配) */
function EmptyNote({ text }: { text: string }) {
  return <div style={{ fontSize: 12.5, color: "var(--label-3)", padding: "6px 0" }}>{text}</div>;
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

function Bar({ fill }: { fill: number }) {
  return (
    <div style={{ flex: 1, height: 6, borderRadius: 999, background: "var(--surface-2)", overflow: "hidden" }}>
      <div style={{ width: `${Math.min(1, fill) * 100}%`, height: "100%", background: "var(--blue)", borderRadius: 999 }} />
    </div>
  );
}

/** 概要卡决策触发器:投标截止时间 + 剩余天数倒计时,全卡最醒目一行(临近截止翻警示色) */
function DeadlineHero({ data }: { data: BasicInfoMatrix }) {
  const dl = bidDeadline(data.timeline);
  const cd = deadlineCountdown(dl?.daysLeft ?? null);
  const tone = cd?.tone ?? "normal";
  const cls =
    tone === "warn" ? "cv-face-deadline is-warn" : tone === "past" ? "cv-face-deadline is-past" : "cv-face-deadline";
  return (
    <div className={cls}>
      <div className="cv-face-deadline-top">
        <span>投标截止</span>
        {cd && <span className="cv-face-deadline-count">{cd.label}</span>}
      </div>
      <div className="cv-face-deadline-date">{dl?.text || "—"}</div>
    </div>
  );
}

function BasicInfoPreview({ slot }: { slot: MatrixSlot<BasicInfoMatrix> }) {
  if (slot.status !== "ready" || !slot.data) return <SlotFallback slot={slot} compact />;
  const p = slot.data.project ?? {};
  const kv: Array<[string, string]> = [
    ["项目预算", fmtMoney(p.budget)],
    ["采购方式", p.procurement_method || "—"],
    ["评标方法", p.evaluation_method || "—"],
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
      <DeadlineHero data={slot.data} />
      <div
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: "var(--label)",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {p.name || slot.data.project_name || "未识别项目名称"}
      </div>
      {kv.map(([k, v]) => (
        <div key={k} style={{ display: "flex", gap: 8, fontSize: 11.5 }}>
          <span style={{ width: 52, color: "var(--label-3)" }}>{k}</span>
          <span
            style={{
              flex: 1,
              color: "var(--label)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {v}
          </span>
        </div>
      ))}
    </div>
  );
}

function RequirementPreview({
  slot,
  categoryMap,
  showRisk,
}: {
  slot: MatrixSlot<BusinessMatrix | TechnicalMatrix>;
  categoryMap: Record<string, string>;
  /** 技术卡专属:存在高风险条目时追加「高风险 N」徽标 */
  showRisk?: boolean;
}) {
  if (slot.status !== "ready" || !slot.data) return <SlotFallback slot={slot} compact />;
  const items = slot.data.items ?? [];
  const groups = groupByCategory(items).slice(0, 4);
  const max = groups[0]?.[1].length ?? 1;
  const mand = mandatoryCount(items);
  const risk = showRisk ? items.filter((i) => i.risk_level === "high").length : 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
      {/* 决策触发器:实质性计数升格为★橙色徽标(漏一条即废标);为 0 时中性呈现不误报 */}
      <div className="cv-face-badges">
        <span className={mand > 0 ? "cv-face-badge is-mand" : "cv-face-badge"}>
          {mand > 0 ? `★ 实质性 ${mand} 项` : "实质性 0 项"}
        </span>
        {risk > 0 && <span className="cv-face-badge is-risk">高风险 {risk}</span>}
      </div>
      {groups.map(([cat, arr]) => (
        <div key={cat} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{ width: 44, fontSize: 11, color: "var(--label-2)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
          >
            {zh(categoryMap, cat)}
          </span>
          <Bar fill={arr.length / max} />
          <span style={{ width: 20, textAlign: "right", fontSize: 11, fontVariantNumeric: "tabular-nums", color: "var(--label-3)" }}>
            {arr.length}
          </span>
        </div>
      ))}
      <div style={{ marginTop: 1, fontSize: 11, color: "var(--label-3)", fontVariantNumeric: "tabular-nums" }}>
        共 {items.length} 条
      </div>
    </div>
  );
}

function ScoringPreview({ slot }: { slot: MatrixSlot<ScoringMatrix> }) {
  if (slot.status !== "ready" || !slot.data) return <SlotFallback slot={slot} compact />;
  const ev = slot.data.evaluation ?? {};
  const subs: Array<[string, number | null | undefined]> = [
    ["价格", ev.price_score],
    ["商务", ev.business_score],
    ["技术", ev.technical_score],
  ];
  // 权重基数:优先总分,缺失时退化为三格分值之和(仍能比出价格标/技术标)
  const base =
    typeof ev.total_score === "number" && ev.total_score > 0
      ? ev.total_score
      : subs.reduce((acc, [, v]) => acc + (typeof v === "number" && v > 0 ? v : 0), 0);
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 7, marginBottom: 8 }}>
        <span style={{ fontSize: 24, fontWeight: 700, color: "var(--label)", fontVariantNumeric: "tabular-nums" }}>
          {ev.total_score ?? "—"}
        </span>
        <span style={{ fontSize: 11, color: "var(--label-3)" }}>
          {ev.method || "综合评分法"} · {slot.data.items?.length ?? 0} 项
        </span>
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        {subs.map(([k, v]) => {
          const fill = base > 0 && typeof v === "number" && v > 0 ? Math.min(1, v / base) : 0;
          return (
            <div
              key={k}
              style={{ flex: 1, background: "var(--surface-2)", borderRadius: 8, padding: "6px 0 7px", textAlign: "center" }}
            >
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--label)", fontVariantNumeric: "tabular-nums" }}>
                {v ?? "—"}
              </div>
              <div style={{ fontSize: 10.5, color: "var(--label-3)" }}>{k}</div>
              {/* 权重占比微条(分值/总分):一眼可辨价格标还是技术标;分值缺失的格不画空轨道 */}
              {base > 0 && typeof v === "number" && v > 0 && (
                <div className="cv-face-weight">
                  <i style={{ width: `${fill * 100}%` }} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** 卡面预览统一入口 */
export function MatrixCardPreview({ type }: { type: MatrixType }) {
  const slot = useWorkspaceStore((s) => s.matrices[type]);
  switch (type) {
    case "basic_info":
      return <BasicInfoPreview slot={slot as MatrixSlot<BasicInfoMatrix>} />;
    case "business":
      return <RequirementPreview slot={slot as MatrixSlot<BusinessMatrix>} categoryMap={BIZ_CATEGORY} />;
    case "technical":
      return <RequirementPreview slot={slot as MatrixSlot<TechnicalMatrix>} categoryMap={TECH_CATEGORY} showRisk />;
    case "scoring":
      return <ScoringPreview slot={slot as MatrixSlot<ScoringMatrix>} />;
  }
}

/* ---------- 详情:抽屉完整视图 ---------- */

function KvGrid({ rows }: { rows: Array<[string, string]> }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px 18px", marginBottom: 14 }}>
      {rows.map(([k, v]) => (
        <div key={k}>
          <div style={{ fontSize: 11, color: "var(--label-3)", marginBottom: 2 }}>{k}</div>
          <div style={{ fontSize: 13, color: "var(--label)", lineHeight: 1.55, overflowWrap: "anywhere" }}>{v || "—"}</div>
        </div>
      ))}
    </div>
  );
}

function BasicInfoDetail({ slot }: { slot: MatrixSlot<BasicInfoMatrix> }) {
  if (slot.status !== "ready" || !slot.data) {
    return (
      <div>
        <SecTitle t="项目概要" />
        <SlotFallback slot={slot} />
      </div>
    );
  }
  const d = slot.data;
  const p = d.project ?? {};
  const timeline = d.timeline ?? [];
  const packages = p.packages ?? [];
  return (
    <div>
      <SecTitle t="项目概要" sub={p.number ? `项目编号 ${p.number}` : undefined} />
      <SummaryStrip data={d} />
      <KvGrid
        rows={[
          ["项目名称", p.name || d.project_name || ""],
          ["项目预算", fmtMoney(p.budget)],
          ["采购方式", p.procurement_method || ""],
          ["评标方法", p.evaluation_method || ""],
          ["采购人", p.purchaser?.name || ""],
          ["代理机构", p.agency?.name || ""],
          ["服务期 / 工期", p.delivery_or_service_period || ""],
          ["交付地点", p.delivery_location || ""],
        ]}
      />
      {p.scope && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, color: "var(--label-3)", marginBottom: 3 }}>采购范围</div>
          <p style={{ fontSize: 13, lineHeight: 1.8, color: "var(--label)", margin: 0 }}>{p.scope}</p>
        </div>
      )}
      {packages.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>分包 · {packages.length} 个</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {packages.map((pkg, i) => (
              <div
                key={pkg.package_id ?? i}
                style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 11px", background: "var(--surface-2)", borderRadius: 10 }}
              >
                <span style={{ flex: 1, fontSize: 12.5, color: "var(--label)" }}>
                  {pkg.package_name || pkg.package_id || `包 ${i + 1}`}
                </span>
                <span style={{ fontSize: 11.5, color: "var(--label-3)", fontVariantNumeric: "tabular-nums" }}>
                  {fmtMoney(pkg.budget)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      {timeline.length > 0 && (
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>关键时间节点</div>
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
                {cd && (
                  <span className={cd.tone === "warn" ? "cv-face-badge is-warn" : "cv-face-badge"}>
                    {cd.label}
                  </span>
                )}
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

function ItemActions({
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
        {row.confirmed ? "✓ 已确认" : "确认"}
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

/** business / technical 共用的条目详情:顶部过滤签(全部/★实质性/高风险)与
 *  分类锚点计数签吸顶,几百条逐条响应中快速聚焦致命条款;条目按 category 分组,渲染上限 300 条。
 *  条目行带人工动作(确认/应答状态),经 store 写 REST 端点落对象库。 */
function RequirementDetail({
  type,
  slot,
  title,
  categoryMap,
}: {
  type: MatrixType;
  slot: MatrixSlot<BusinessMatrix | TechnicalMatrix>;
  title: string;
  categoryMap: Record<string, string>;
}) {
  const [filter, setFilter] = useState<ReqFilter>("all");
  const anchorBase = useId();
  const headRef = useRef<HTMLDivElement>(null);
  const confirmItem = useWorkspaceStore((s) => s.confirmItem);
  const setItemResponseStatus = useWorkspaceStore((s) => s.setItemResponseStatus);
  // 人工动作在途/失败态按条目局部呈现,不打扰其余条目
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
  if (slot.status !== "ready" || !slot.data) {
    return (
      <div>
        <SecTitle t={title} />
        <SlotFallback slot={slot} />
      </div>
    );
  }
  const d = slot.data;
  const all = d.items ?? [];
  // 行级管理状态(确认/应答状态/乐观锁版本)按业务 id 对齐条目 payload
  const rowsById = new Map((slot.itemRows ?? []).map((r) => [r.item_id, r]));
  const mand = mandatoryCount(all);
  const conf = d.extraction_summary?.confidence;
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
      <SecTitle
        t={title}
        sub={`共 ${all.length} 条 · 实质性 ${mand} 项${conf ? ` · 置信度 ${conf}` : ""}`}
      />
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
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {groups.map(([cat, arr]) => (
            <GroupCard
              key={cat}
              id={gid(cat)}
              title={zh(categoryMap, cat)}
              count={arr.length}
              unit="条"
              extra={
                mandatoryCount(arr) > 0 ? (
                  <span style={{ marginLeft: "auto", fontSize: 10.5, color: "var(--orange-text)" }}>
                    实质性 {mandatoryCount(arr)}
                  </span>
                ) : undefined
              }
            >
              {arr.map((it, i) => {
                const row = it.id ? rowsById.get(it.id) : undefined;
                return (
                  <div
                    key={it.id ?? i}
                    style={{ padding: "9px 0", borderTop: i ? "1px solid var(--separator)" : "none" }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 11, color: "var(--label-3)", fontVariantNumeric: "tabular-nums" }}>
                        {it.id ?? `#${i + 1}`}
                      </span>
                      <span style={{ flex: 1, fontSize: 12.5, fontWeight: 600, color: "var(--label)" }}>
                        {it.title || "未命名条目"}
                      </span>
                      {it.mandatory && <MandatoryBadge />}
                      {isHighRisk(it) && !it.mandatory && (
                        <span className="cv-face-badge is-risk">高风险</span>
                      )}
                    </div>
                    {it.requirement_text && (
                      <p style={{ fontSize: 12.5, lineHeight: 1.75, color: "var(--label-2)", margin: "4px 0 0" }}>
                        {it.requirement_text}
                      </p>
                    )}
                    <SourceLine item={it} />
                    {row && (
                      <ItemActions
                        row={row}
                        busy={busyItemId === row.item_id}
                        error={actionErr?.id === row.item_id ? actionErr.msg : null}
                        onConfirm={() => runItemAction(row.item_id, confirmItem(type, row.item_id))}
                        onSetStatus={(status) =>
                          runItemAction(row.item_id, setItemResponseStatus(type, row.item_id, status))
                        }
                      />
                    )}
                  </div>
                );
              })}
            </GroupCard>
          ))}
        </div>
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
  if (slot.status !== "ready" || !slot.data) {
    return (
      <div>
        <SecTitle t="评分办法" />
        <SlotFallback slot={slot} />
      </div>
    );
  }
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
  // 段色由 .cv-det-scorebar/.cv-det-scorelegend 的修饰类承载,TSX 不写色值
  const parts: Array<{ label: string; score: number; cls: string }> = [];
  const raw: Array<[string, number | null | undefined, string]> = [
    ["价格", ev.price_score, "is-price"],
    ["商务", ev.business_score, "is-business"],
    ["技术", ev.technical_score, "is-technical"],
  ];
  for (const [label, v, cls] of raw) {
    if (typeof v === "number" && v > 0) parts.push({ label, score: v, cls });
  }
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
  const head: Col[] = [
    { t: "评分项", f: "1.6" },
    { t: "分值", f: "0 0 48px" },
    { t: "评分规则", f: "2.4" },
    { t: "来源", f: "0 0 96px" },
  ];
  // 「来源」列升级为来源签(票04):多条 ref 全部成签(修复旧版只显示第一条的
  // 信息丢失),点击行为与条目签一致;窄列用 compact 签面(行号),章节进悬停。
  const groupRows = (groupKey: string, arr: ScoringItem[]): ReactNode[][] => {
    const rows: ReactNode[][] = arr.map((it, i) => [
      <span key="t" style={{ display: "inline-flex", alignItems: "center", gap: 6, minWidth: 0 }}>
        {it.title || `评分项 ${i + 1}`}
        {it.mandatory_gate && <span className="cv-face-badge is-risk">否决</span>}
      </span>,
      <span key="s" style={{ fontVariantNumeric: "tabular-nums" }}>{it.max_score ?? "—"}</span>,
      <span key="r" style={{ color: "var(--label-2)", lineHeight: 1.6 }}>{it.scoring_rule || "—"}</span>,
      <span key="l" className="cv-src-row is-cell">
        <SourceChips
          refs={it.source_refs ?? []}
          itemKey={`score:${it.id ?? `${groupKey}#${i}`}`}
          compact
        />
      </span>,
    ]);
    const subtotal = arr.reduce((acc, it) => acc + (typeof it.max_score === "number" ? it.max_score : 0), 0);
    rows.push([
      <span key="t" style={{ fontWeight: 700 }}>小计</span>,
      <span key="s" style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{fmtScore(subtotal)}</span>,
      "",
      "",
    ]);
    return rows;
  };

  return (
    <div>
      <SecTitle t="评分办法" sub={ev.method || undefined} />
      <SummaryStrip data={d} />
      {vetoRules.length > 0 && (
        <div className="cv-det-veto">
          <div className="cv-det-veto-title">
            否决项 / 通过性条款
            <span className="cv-det-veto-count">{vetoRules.length} 条</span>
          </div>
          {vetoRules.map((v, i) => (
            <div key={i} className="cv-det-veto-row">
              <span className="cv-det-veto-bullet" aria-hidden />
              <div style={{ minWidth: 0 }}>
                <span>{v.text}</span>
                <SourceRow refs={v.refs} itemKey={`veto:${v.id ?? i}`} />
              </div>
            </div>
          ))}
        </div>
      )}
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 28, fontWeight: 700, color: "var(--label)", fontVariantNumeric: "tabular-nums" }}>
          {total ?? "—"}
        </span>
        <span style={{ fontSize: 12, color: "var(--label-3)" }}>总分 · {itemsAll.length} 项评分项</span>
      </div>
      {base > 0 && parts.length > 0 && (
        <div style={{ marginBottom: 16 }}>
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
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {orderedKeys.map((key) => {
            const arr = gmap.get(key) ?? [];
            return (
              <GroupCard key={key} title={zh(SCORE_GROUP, key)} count={arr.length} unit="项">
                <Table head={head} rows={groupRows(key, arr)} />
              </GroupCard>
            );
          })}
        </div>
      ) : (
        <EmptyNote text="未提取到评分项" />
      )}
      <TruncNote rest={itemsAll.length - items.length} unit="项" />
    </div>
  );
}

/** 抽屉详情统一入口 */
export function MatrixCardDetail({ type }: { type: MatrixType }) {
  const slot = useWorkspaceStore((s) => s.matrices[type]);
  switch (type) {
    case "basic_info":
      return <BasicInfoDetail slot={slot as MatrixSlot<BasicInfoMatrix>} />;
    case "business":
      return (
        <RequirementDetail type={type} slot={slot as MatrixSlot<BusinessMatrix>} title="商务应答矩阵" categoryMap={BIZ_CATEGORY} />
      );
    case "technical":
      return (
        <RequirementDetail type={type} slot={slot as MatrixSlot<TechnicalMatrix>} title="技术应答矩阵" categoryMap={TECH_CATEGORY} />
      );
    case "scoring":
      return <ScoringDetail slot={slot as MatrixSlot<ScoringMatrix>} />;
  }
}
