"use client";

import { useEffect, useState } from "react";
import { useWorkspaceStore, type MatrixSlot } from "@/lib/store/workspace";
import {
  asRec,
  fmtMoneyCompact,
  type BasicInfoMatrix,
  type BusinessMatrix,
  type MatrixType,
  type RequirementItem,
  type ScoringMatrix,
  type TechnicalMatrix,
} from "@/lib/hagent/matrix";
import {
  ClockIcon,
  WarningIcon,
} from "@/components/ui/icons";
import { isSlotInterrupted } from "./cardMeta";
import {
  DEADLINE_WARN_DAYS,
  bidDeadline,
  bidWindow,
  fmtShortDeadline,
  type DeadlineInfo,
} from "./deadline";


// 四张真实应答矩阵卡的卡面预览与抽屉详情。
// 数据订阅自 workspace store(store 为唯一事实来源,不经 CardInst 传递);
// 全部字段防御式读取,缺失一律「—」。视觉延续画布内联微版式 + 语义色对。

/* ---------- 中文化映射 ---------- */

export const BIZ_CATEGORY: Record<string, string> = {
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

export const TECH_CATEGORY: Record<string, string> = {
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

export const SCORE_GROUP: Record<string, string> = {
  price: "价格",
  business: "商务",
  technical: "技术",
  service: "服务",
  policy: "政策",
  other: "其他",
};

export const TIMELINE_EVENT: Record<string, string> = {
  doc_sale: "标书发售",
  qa_deadline: "质疑截止",
  site_survey: "现场踏勘",
  bid_deadline: "投标截止",
  bid_opening: "开标",
  announcement: "结果公告",
};

export const zh = (map: Record<string, string>, key: string | undefined): string =>
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
export function SlotFallback({ slot, compact }: { slot: MatrixSlot<unknown>; compact?: boolean }) {
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
export function SummaryStrip({ data }: { data: { extraction_summary?: { status?: string; warnings?: string[] } } }) {
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

/** 实质性标记:沿用招标文件的原生记号 ★,不另造图形;窄处只留符号,悬停给全称。 */
export function MandatoryMark({ full }: { full?: boolean }) {
  return (
    <span className="cv-star" title={full ? undefined : "实质性条款"}>
      {full ? "★ 实质性" : "★"}
    </span>
  );
}

/** 重要参数标记:同样沿用原生记号 ▲。它比一般条款重、又不致命 ——
 *  故走中性刻度而非第二种语义色:★ 的橙已经占住「致命」,再上一色只会稀释它。 */
export function ImportantMark({ full }: { full?: boolean }) {
  return (
    <span className="cv-tri" title={full ? undefined : "重要参数"}>
      {full ? "▲ 重要" : "▲"}
    </span>
  );
}

/** 高风险标记:一枚红点 + 两个字,替代此前的红底药丸。 */
export function RiskMark({ label = "高风险" }: { label?: string }) {
  return <span className="cv-mark is-risk">{label}</span>;
}

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

export const mandatoryCount = (items: RequirementItem[]): number =>
  items.filter((i) => i.mandatory).length;

/** ▲ 重要参数计数:只认 param_nature,不与 mandatory 混算 —— 两者是并列的两档,不是包含关系 */
export const importantCount = (items: RequirementItem[]): number =>
  items.filter((i) => i.param_nature === "▲").length;

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
  if (dl.expired) return { value: "已截止", unit: d === 0 ? "今日截止时间已过" : `已过 ${-d} 天`, tone: " is-past" };
  if (d > 0)
    return { value: String(d), unit: "天后投标截止", tone: d <= DEADLINE_WARN_DAYS ? " is-warn" : "" };
  if (d === 0) return { value: "今日", unit: "投标截止", tone: " is-warn" };
  return { value: "已截止", unit: `已过 ${-d} 天`, tone: " is-past" };
}

export function useDeadlineClock() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const tick = () => setNow(Date.now());
    const timer = window.setInterval(tick, 30_000);
    window.addEventListener("focus", tick);
    return () => { window.clearInterval(timer); window.removeEventListener("focus", tick); };
  }, []);
  return now;
}

function BasicInfoPreview({ slot }: { slot: MatrixSlot<BasicInfoMatrix> }) {
  const now = useDeadlineClock();
  if (slot.status !== "ready" || !slot.data) return <SlotFallback slot={slot} compact />;
  const d = slot.data;
  const p = d.project ?? {};
  const dl = bidDeadline(d.timeline, now);
  const hero = dl ? deadlineHero(dl) : null;
  const win = bidWindow(d.timeline, now);
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
      ? `${fmtShortDeadline(dl.at, dl.timezone, dl.precise)} · ${dl.zoneLabel}`
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
  const imp = importantCount(items);
  const risk = showRisk ? items.filter(isHighRisk).length : 0;
  // 信号行至多两项:实质性 > ▲ 重要 > 高风险 > 分类注释。前两项占满时不再挤注释
  const catNote = top
    .slice(0, 2)
    .map(([cat, arr]) => `${zh(categoryMap, cat)} ${arr.length}`)
    .join(" · ");
  // 第二枚信号:▲ 优先于高风险(它来自招标文件的原生记号,高风险是抽取侧的判定)
  const second: "imp" | "risk" | null = imp > 0 ? "imp" : risk > 0 ? "risk" : null;
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
        {second === "imp" && (
          <span className="is-imp">
            ▲ 重要 <b>{imp}</b>
          </span>
        )}
        {second === "risk" && (
          <span className="is-fatal">
            高风险 <b>{risk}</b>
          </span>
        )}
        {!(mand > 0 && second) && (
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


export const fmtScore = (n: number): string => (Number.isInteger(n) ? String(n) : n.toFixed(1));

/** pass_fail_rules 记录无形状约束(LLM 产出):字符串原样,对象取常见文案字段,兜底 JSON 串如实呈现 */
export function vetoRuleText(r: unknown): string {
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


export const isHighRisk = (it: RequirementItem): boolean => it.risk_level === "high";
