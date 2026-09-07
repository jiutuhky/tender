"use client";

import { Fragment, useId, useRef, useState } from "react";
import { useWorkspaceStore, type MatrixSlot } from "@/lib/store/workspace";
import {
  asRec,
  asSourceRefs,
  fmtMoney,
  fmtMoneyCompact,
  type BasicInfoMatrix,
  type BusinessMatrix,
  type MatrixItemRow,
  type MatrixType,
  type Rec,
  type RequirementItem,
  type ScoringItem,
  type ScoringMatrix,
  type SourceRef,
  type TechnicalMatrix,
  type TimelineEvent,
} from "@/lib/hagent/matrix";
import {
  ArrowsDownUpIcon,
  ChevronIcon,
  ProhibitIcon,
} from "@/components/ui/icons";
import {
  SourceChips,
  SourceRow,
  SourceLine,
  ItemActions,
  useItemAction,
  RESPONSE_STATUS_OPTS,
} from "./detailShared";
import {
  fmtScore,
  vetoRuleText,
  isHighRisk,
  BIZ_CATEGORY,
  TECH_CATEGORY,
  SCORE_GROUP,
  TIMELINE_EVENT,
  zh,
  SlotFallback,
  SummaryStrip,
  useDeadlineClock,
} from "./matrixViews";
import {
  bidDeadline,
  calendarDaysBetween,
  deadlineCountdown,
  parseDeadline,
  deadlineZone,
  deadlineZoneLabel,
} from "./deadline";

/* ---------- 详情:抽屉完整视图 ---------- */

/** 关键事实显式留空提示，可选信息由调用方决定是否显示。 */
function FieldList({ rows }: { rows: Array<[string, string]> }) {
  return (
    <dl className="rd-facts">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>
            {v && v !== "—" ? v : <span className="rd-muted">未提取</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function BasicInfoDetail({ slot }: { slot: MatrixSlot<BasicInfoMatrix> }) {
  const now = useDeadlineClock();
  if (slot.status !== "ready" || !slot.data)
    return <SlotFallback slot={slot} />;
  const d = slot.data;
  const p = d.project ?? {};
  const timeline = d.timeline ?? [];
  const packages = p.packages ?? [];
  const deadline = bidDeadline(timeline, now);
  const countdown = deadlineCountdown(
    deadline?.daysLeft ?? null,
    deadline?.expired,
  );
  const money = fmtMoneyCompact(p.budget);
  const parties = [
    ["采购人", p.purchaser],
    ["代理机构", p.agency],
  ] as const;
  return (
    <div className="rd-overview">
      <SummaryStrip data={d} />
      <div className="rd-project-intro">
        <h2>{p.name || d.project_name || "项目名称未提取"}</h2>
        <p>项目编号 · {p.number || "未提取"}</p>
      </div>
      <div className="rd-key-facts">
        <section>
          <h3>项目预算</h3>
          <div className="rd-budget">
            {money ? (
              <>
                <b>{money.value}</b>
                <span>{money.unit}</span>
              </>
            ) : (
              <span className="rd-muted">未提取</span>
            )}
          </div>
          {fmtMoney(p.budget) !== "—" && <p>{fmtMoney(p.budget)}</p>}
        </section>
        <section>
          <h3>投标截止</h3>
          <div className="rd-deadline">
            {deadline?.text.replace("T", " ") || "未提取"}
          </div>
          {deadline && (
            <p>
              {deadline.zoneLabel}
              {countdown && (
                <span className={countdown.tone === "warn" ? "rd-warning" : ""}>
                  {" "}
                  · {countdown.label}
                </span>
              )}
            </p>
          )}
        </section>
      </div>
      <section className="rd-overview-section">
        <h2>采购与交付</h2>
        <FieldList
          rows={[
            ["采购方式", p.procurement_method || ""],
            ["评标方法", p.evaluation_method || ""],
            ["服务期 / 工期", p.delivery_or_service_period || ""],
            ["交付地点", p.delivery_location || ""],
          ]}
        />
        {p.scope && (
          <div className="rd-detail-section">
            <h4>采购范围</h4>
            <p>{p.scope}</p>
          </div>
        )}
      </section>
      {parties.some(
        ([, party]) => party && Object.values(party).some(Boolean),
      ) && (
        <section className="rd-overview-section">
          <h2>相关单位</h2>
          {parties.map(([label, party]) =>
            party && Object.values(party).some(Boolean) ? (
              <div className="rd-party" key={label}>
                <h3>{label}</h3>
                <FieldList
                  rows={(
                    [
                      ["名称", party.name || ""],
                      ["联系人", party.contact || ""],
                      ["电话", party.phone || ""],
                      ["地址", party.address || ""],
                    ] as Array<[string, string]>
                  ).filter(([k, v]) => k === "名称" || v)}
                />
              </div>
            ) : null,
          )}
        </section>
      )}
      {!!packages.length && (
        <section className="rd-overview-section">
          <h2>
            分包 <span>{packages.length} 个</span>
          </h2>
          {packages.map((pkg, i) => (
            <div className="rd-package" key={pkg.package_id ?? i}>
              <div>
                <h3>{pkg.package_name || pkg.package_id || `包 ${i + 1}`}</h3>
                <span>
                  {fmtMoney(pkg.budget) === "—"
                    ? "预算未提取"
                    : fmtMoney(pkg.budget)}
                </span>
              </div>
              {pkg.scope && <p>{pkg.scope}</p>}
              {!!pkg.source_refs?.length && (
                <SourceRow
                  refs={pkg.source_refs}
                  itemKey={`package:${pkg.package_id ?? i}`}
                />
              )}
            </div>
          ))}
        </section>
      )}
      {!!timeline.length && (
        <section className="rd-overview-section">
          <h2>关键时间</h2>
          <DetailTimeline timeline={timeline} />
        </section>
      )}
    </div>
  );
}

/** 时间线节点推导:解析时间并升序排布(不可解析的节点保持原序垫底)。
 *  now 走默认参收口(与 bidDeadline 同式),组件 render 保持纯净。 */
function timelineNodes(timeline: TimelineEvent[], now: number = Date.now()) {
  return timeline
    .map((ev, i) => {
      const t = ev.datetime ? parseDeadline(ev.datetime, ev.timezone) : null;
      let days: number | null = null;
      try {
        if (t !== null)
          days = calendarDaysBetween(
            now,
            t,
            deadlineZone(ev.datetime ?? "", ev.timezone),
          );
      } catch {
        /* 无效时区仅展示原文。 */
      }
      return { ev, i, t, days };
    })
    .sort(
      (a, b) =>
        (a.t ?? Number.MAX_SAFE_INTEGER) - (b.t ?? Number.MAX_SAFE_INTEGER) ||
        a.i - b.i,
    );
}

/** 概要详情纵向时间线:投标截止节点高亮并挂倒计时徽标,已过期节点整体淡化。 */
function DetailTimeline({ timeline }: { timeline: TimelineEvent[] }) {
  const now = useDeadlineClock();
  const nodes = timelineNodes(timeline, now);
  return (
    <div className="cv-det-timeline">
      {nodes.map(({ ev, i, days }) => {
        const isDeadline = ev.event === "bid_deadline";
        const past = days !== null && days < 0;
        const deadline = isDeadline ? bidDeadline([ev], now) : null;
        const cd = isDeadline
          ? deadlineCountdown(deadline?.daysLeft ?? null, deadline?.expired)
          : null;
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
                {ev.datetime
                  ? ` · ${deadlineZoneLabel(ev.datetime, ev.timezone)}`
                  : ""}
                {ev.location ? ` · ${ev.location}` : ""}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

type ReqFilter = "all" | "mand" | "imp" | "risk";

const REQ_FILTERS: Array<{
  k: ReqFilter;
  label: string;
  pred: (it: RequirementItem) => boolean;
}> = [
  { k: "all", label: "全部重要性", pred: () => true },
  { k: "mand", label: "实质性要求", pred: (it) => !!it.mandatory },
  { k: "imp", label: "重要参数", pred: (it) => it.param_nature === "▲" },
  { k: "risk", label: "高风险", pred: isHighRisk },
];

function RequirementRow({
  item,
  index,
  type,
  row,
  action,
  open,
  onToggle,
}: {
  item: RequirementItem;
  index: number;
  type: MatrixType;
  row?: MatrixItemRow;
  action: ReturnType<typeof useItemAction>;
  open: boolean;
  onToggle: () => void;
}) {
  const contentId = useId();
  const titleRef = useRef<HTMLButtonElement>(null);
  const toggle = () => {
    const current = titleRef.current;
    const body = current?.closest(".cv-drawer-body");
    const titles = Array.from(
      body?.querySelectorAll<HTMLButtonElement>(".rd-item-title button") ?? [],
    );
    const index = current ? titles.indexOf(current) : -1;
    const neighbor = titles[index + 1] ?? titles[index - 1];
    onToggle();
    if (open)
      requestAnimationFrame(() => {
        // 待核验过滤中，收起刚确认的条目会卸载它，焦点交给相邻条目。
        const target =
          titleRef.current ??
          (neighbor?.isConnected
            ? neighbor
            : body?.querySelector<HTMLInputElement>("input[type=search]"));
        target?.focus({ preventScroll: true });
        const toolbar = body?.querySelector(".rd-toolbar");
        if (
          target &&
          body &&
          toolbar &&
          target.getBoundingClientRect().top <
            toolbar.getBoundingClientRect().bottom
        ) {
          body.scrollBy({
            top:
              target.getBoundingClientRect().top -
              toolbar.getBoundingClientRect().bottom -
              24,
          });
        }
      });
  };
  const response = RESPONSE_STATUS_OPTS.find(
    (o) => o.k === row?.response_status,
  );
  const importance = item.mandatory
    ? "实质性要求"
    : item.param_nature === "▲"
      ? "重要参数"
      : isHighRisk(item)
        ? "高风险"
        : null;
  return (
    <article
      className={`rd-item${open ? " is-open" : ""}`}
      data-reading-item={item.id ?? index}
    >
      <div className="rd-item-eyebrow">
        <span>{item.id ?? `条目 ${index + 1}`}</span>
        {importance && (
          <span
            className={item.mandatory || isHighRisk(item) ? "rd-warning" : ""}
          >
            {importance}
          </span>
        )}
      </div>
      <h3 className="rd-item-title">
        <button
          ref={titleRef}
          type="button"
          onClick={toggle}
          aria-expanded={open}
          aria-controls={contentId}
        >
          {item.title || "未命名条目"}
          <ChevronIcon width={16} height={16} aria-hidden="true" />
        </button>
      </h3>
      {!open && (
        <>
          <p className="rd-excerpt">
            {item.requirement_text || "未提取具体要求"}
          </p>
          <div className="rd-item-meta">
            <span>
              {row ? (row.confirmed ? "已核验" : "待核验") : "仅供阅读"}
            </span>
            {response && (
              <span
                className={
                  response.cls === "is-negative" ? "rd-warning" : undefined
                }
              >
                {response.label}
              </span>
            )}
            {!!item.evidence_required?.length && (
              <span>证明材料 {item.evidence_required.length} 项</span>
            )}
            <button
              type="button"
              className="rd-text-button"
              onClick={toggle}
              aria-expanded={open}
              aria-controls={contentId}
            >
              查看详情
            </button>
          </div>
        </>
      )}
      <div id={contentId} hidden={!open} className="rd-item-content">
        <section className="rd-detail-section">
          <h4>具体要求</h4>
          <p>{item.requirement_text || "未提取具体要求"}</p>
        </section>
        {!!item.evidence_required?.length && (
          <section className="rd-detail-section">
            <h4>
              证明材料 <span>{item.evidence_required.length} 项</span>
            </h4>
            <ul>
              {item.evidence_required.map((v, i) => (
                <li key={i}>{v}</li>
              ))}
            </ul>
          </section>
        )}
        {!!item.acceptance_criteria?.length && (
          <section className="rd-detail-section">
            <h4>验收要求</h4>
            <ul>
              {item.acceptance_criteria.map((v, i) => (
                <li key={i}>{v}</li>
              ))}
            </ul>
          </section>
        )}
        {item.notes ||
        item.deadline_or_period ||
        item.related_forms?.length ||
        item.related_deliverables?.length ? (
          <section className="rd-detail-section">
            <h4>补充说明</h4>
            {item.deadline_or_period && <p>期限：{item.deadline_or_period}</p>}
            {!!item.related_forms?.length && (
              <p>关联表单：{item.related_forms.join("、")}</p>
            )}
            {!!item.related_deliverables?.length && (
              <p>关联交付物：{item.related_deliverables.join("、")}</p>
            )}
            {item.notes && <p>{item.notes}</p>}
          </section>
        ) : null}
        <section className="rd-detail-section">
          <h4>原文依据</h4>
          <SourceLine item={item} type={type} index={index} />
        </section>
        {row && (
          <section className="rd-review">
            <h4>
              核验记录 <span>{row.confirmed ? "已核验" : "待核验"}</span>
            </h4>
            <ItemActions
              row={row}
              busy={action.busyIds.has(row.item_id)}
              error={action.errors[row.item_id] ?? null}
              onConfirm={() => action.confirm(row.item_id)}
              onSetStatus={(status) => action.setStatus(row.item_id, status)}
            />
            <span className="rd-save-notice" role="status">
              {action.savedIds.has(row.item_id) ? "已保存" : ""}
            </span>
          </section>
        )}
        <button
          type="button"
          className="rd-text-button rd-collapse"
          onClick={toggle}
          aria-expanded={open}
          aria-controls={contentId}
        >
          收起详情
        </button>
      </div>
    </article>
  );
}

/** 全量筛选后分页；展开身份由父级保存，原文层关闭后不丢失阅读上下文。 */
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
  const [category, setCategory] = useState("");
  const [query, setQuery] = useState("");
  const [onlyPending, setOnlyPending] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [page, setPage] = useState(0);
  const [openIds, setOpenIds] = useState(new Set<string>());
  const [retainedIds, setRetainedIds] = useState(new Set<string>());
  const headRef = useRef<HTMLDivElement>(null);
  const filterId = useId();
  const action = useItemAction(type);
  const pageSize = 50;
  if (slot.status !== "ready" || !slot.data)
    return <SlotFallback slot={slot} />;
  const all = slot.data.items ?? [];
  const rowsById = new Map((slot.itemRows ?? []).map((r) => [r.item_id, r]));
  const keyOf = (it: RequirementItem, i: number) =>
    it.id ?? `${it.category ?? "other"}:${i}`;
  const active = REQ_FILTERS.find((f) => f.k === filter)!;
  const term = query.trim().toLocaleLowerCase();
  const categories = [...new Set(all.map((it) => it.category || "other"))];
  const searchable = (it: RequirementItem) =>
    [
      it.id,
      it.title,
      it.requirement_text,
      zh(categoryMap, it.category),
      ...(it.evidence_required ?? []),
      ...(it.acceptance_criteria ?? []),
      it.notes,
    ]
      .filter(Boolean)
      .join(" ")
      .toLocaleLowerCase();
  const filtered = all
    .map((it, i) => ({ it, i, key: keyOf(it, i) }))
    .filter(
      ({ it, key }) =>
        active.pred(it) &&
        (!category || (it.category || "other") === category) &&
        (!onlyPending ||
          (it.id &&
            rowsById.has(it.id) &&
            (!rowsById.get(it.id)?.confirmed || retainedIds.has(key)))) &&
        (!term || searchable(it).includes(term)),
    );
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, pageCount - 1);
  const items = filtered.slice(
    currentPage * pageSize,
    (currentPage + 1) * pageSize,
  );
  const reviewable = all.filter((it) => it.id && rowsById.has(it.id));
  const confirmed = reviewable.filter(
    (it) => rowsById.get(it.id!)?.confirmed,
  ).length;
  const resetPage = () => {
    setPage(0);
    // 过滤变化移除已确认的暂留项；仍展开的待核验项继续保留阅读身份。
    setRetainedIds(
      new Set(
        all.flatMap((it, i) =>
          it.id &&
          rowsById.has(it.id) &&
          !rowsById.get(it.id)?.confirmed &&
          openIds.has(keyOf(it, i))
            ? [keyOf(it, i)]
            : [],
        ),
      ),
    );
  };
  const clear = () => {
    setFilter("all");
    setCategory("");
    setOnlyPending(false);
    setQuery("");
    resetPage();
  };
  const summaries = [
    filter !== "all" ? active.label : "",
    category ? zh(categoryMap, category) : "",
    onlyPending ? "仅待核验" : "",
    term ? `搜索“${query.trim()}”` : "",
  ].filter(Boolean);
  const toggle = (key: string, item: RequirementItem) => {
    const opening = !openIds.has(key);
    setOpenIds((cur) => {
      const next = new Set(cur);
      if (opening) next.add(key);
      else next.delete(key);
      return next;
    });
    setRetainedIds((cur) => {
      const next = new Set(cur);
      if (
        opening &&
        onlyPending &&
        item.id &&
        !rowsById.get(item.id)?.confirmed
      )
        next.add(key);
      else next.delete(key);
      return next;
    });
  };
  return (
    <div className="rd-requirements">
      <SummaryStrip data={slot.data} />
      <div className="rd-progress">
        <span>
          <b>{all.length}</b> 条要求
        </span>
        <span>
          {reviewable.length
            ? `已核验 ${confirmed} / ${reviewable.length}`
            : "尚无核验记录"}
        </span>
        {reviewable.length > 0 && (
          <progress
            aria-label="核验进度"
            value={confirmed}
            max={reviewable.length}
          />
        )}
      </div>
      <div ref={headRef} className="rd-toolbar" tabIndex={-1}>
        <div className="rd-search-row">
          <input
            type="search"
            aria-label="搜索要求、证明材料或验收说明"
            placeholder="搜索要求、材料或关键词…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              resetPage();
            }}
          />
          <button
            type="button"
            className="rd-button"
            aria-expanded={filtersOpen}
            aria-controls={filterId}
            onClick={() => setFiltersOpen((v) => !v)}
          >
            筛选{summaries.length ? ` · ${summaries.length}` : ""}
            <ChevronIcon width={14} height={14} aria-hidden="true" />
          </button>
        </div>
        <div id={filterId} className="rd-filter-panel" hidden={!filtersOpen}>
          <label>
            重要性
            <select
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value as ReqFilter);
                resetPage();
              }}
            >
              {REQ_FILTERS.map((f) => (
                <option value={f.k} key={f.k}>
                  {f.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            分类
            <select
              value={category}
              onChange={(e) => {
                setCategory(e.target.value);
                resetPage();
              }}
            >
              <option value="">全部分类</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {zh(categoryMap, cat)}
                </option>
              ))}
            </select>
          </label>
          <label className="rd-checkbox">
            <input
              type="checkbox"
              checked={onlyPending}
              onChange={(e) => {
                setOnlyPending(e.target.checked);
                resetPage();
              }}
            />
            仅待核验
          </label>
        </div>
        {!!summaries.length && (
          <div className="rd-filter-summary">
            <span>
              {summaries.join(" · ")} · {filtered.length} 条
            </span>
            <button type="button" className="rd-text-button" onClick={clear}>
              清空
            </button>
          </div>
        )}
      </div>
      {!items.length ? (
        <div className="rd-empty">
          <b>{all.length ? "没有匹配的要求" : "尚未提取到要求"}</b>
          <p>
            {all.length
              ? "试试其他关键词，或清空筛选条件。"
              : "解析完成后，要求与原文依据会显示在这里。"}
          </p>
          {!!summaries.length && (
            <button type="button" className="rd-button" onClick={clear}>
              清空筛选
            </button>
          )}
        </div>
      ) : (
        items.map(({ it, i, key }, n) => (
          <Fragment key={key}>
            {(n === 0 ||
              (items[n - 1]?.it.category || "other") !==
                (it.category || "other")) && (
              <h2 className="rd-group-title">{zh(categoryMap, it.category)}</h2>
            )}
            <RequirementRow
              item={it}
              index={i}
              type={type}
              row={it.id ? rowsById.get(it.id) : undefined}
              action={action}
              open={openIds.has(key)}
              onToggle={() => toggle(key, it)}
            />
          </Fragment>
        ))
      )}
      {pageCount > 1 && (
        <div className="rd-pagination" role="group" aria-label="条目分页">
          <span role="status">
            {currentPage * pageSize + 1}–
            {Math.min((currentPage + 1) * pageSize, filtered.length)} /{" "}
            {filtered.length} 条
          </span>
          {([-1, 1] as const).map((dir) => (
            <button
              type="button"
              className="rd-button"
              key={dir}
              disabled={
                dir < 0 ? currentPage === 0 : currentPage >= pageCount - 1
              }
              onClick={() => {
                setPage(currentPage + dir);
                headRef.current
                  ?.closest(".cv-drawer-body")
                  ?.scrollTo({ top: 0 });
                headRef.current?.focus({ preventScroll: true });
              }}
            >
              {dir < 0 ? "上一页" : "下一页"}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** 分组固定排序:与招标文件评分办法的常见叙述顺序一致,未知分组按出现序垫底 */
const SCORE_GROUP_ORDER: readonly string[] = [
  "price",
  "business",
  "technical",
  "service",
  "policy",
  "other",
];

/** 分值展示:整数原样,小数保留一位(「其他」由总分差值推得,可能带小数) */
/** 否决条件保留在评分项之前，展开后逐条阅读依据。 */
function VetoBand({ rules }: { rules: VetoRule[] }) {
  const [open, setOpen] = useState(false);
  if (rules.length === 0) return null;
  return (
    <section className="cv-det-veto">
      <button
        type="button"
        className="cv-det-veto-btn"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <ProhibitIcon width={15} height={15} />
        否决项 / 通过性条款
        <span className="cv-det-veto-count">{rules.length} 条</span>
        <ChevronIcon
          width={13}
          height={13}
          className={open ? "cv-det-veto-caret is-open" : "cv-det-veto-caret"}
        />
      </button>
      {open ? (
        rules.map((v, i) => (
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
        ))
      ) : (
        <div className="cv-det-veto-peek">{rules[0]?.text}</div>
      )}
    </section>
  );
}

/** 偏离档位译名:★/▲ 是招标文件的原生记号,原样呈现;general 是「列为空」的一般参数,需译。 */
const DEV_SCOPE: Record<string, string> = {
  "★": "★",
  "▲": "▲",
  general: "一般",
};

/** 偏离规则的结构化摘要:数字字段齐了才拼,缺了就返回 null 交给原文兜底 ——
 *  「负偏离 −0.3 分/项」是能直接用来算账的一句,拼不出来时硬凑半句反而误导。 */
function deviationSummary(rec: Rec | null): string | null {
  if (!rec) return null;
  // 字段承载绝对值(方向由 direction 表达);抽取侧写了负号也照样读得对
  const num = (v: unknown): number | null =>
    typeof v === "number" && Number.isFinite(v) ? Math.abs(v) : null;
  const scope = Array.isArray(rec.applies_to)
    ? rec.applies_to
        .map((v: unknown) => (typeof v === "string" ? (DEV_SCOPE[v] ?? v) : ""))
        .filter(Boolean)
        .join(" / ")
    : "";
  const head = scope ? `${scope} ` : "";
  if (rec.direction === "zero_out") {
    const n = num(rec.threshold_items);
    if (n === null) return null;
    const effect =
      typeof rec.effect_text === "string" && rec.effect_text.trim()
        ? rec.effect_text.trim()
        : "该部分得分清零";
    return `${head}负偏离满 ${fmtScore(n)} 项 · ${effect}`;
  }
  if (rec.direction !== "positive" && rec.direction !== "negative") return null;
  const per = num(rec.delta_per_item);
  const cap = num(rec.cap);
  if (per === null && cap === null) return null;
  const name = rec.direction === "positive" ? "正偏离" : "负偏离";
  const sign = rec.direction === "positive" ? "+" : "−";
  return (
    head +
    [
      per !== null ? `${name} ${sign}${fmtScore(per)} 分/项` : name,
      cap !== null ? `封顶 ${fmtScore(cap)} 分` : "",
    ]
      .filter(Boolean)
      .join(" · ")
  );
}

/** 偏离计分规则带:与否决项带同一副骨架,但走中性刻度 ——
 *  偏离是算分规则不是废标线,占用红区会把真正的否决项冲淡。 */
function DeviationBand({ rules }: { rules: DeviationRule[] }) {
  const [open, setOpen] = useState(false);
  if (rules.length === 0) return null;
  const first = rules[0];
  return (
    <section className="cv-det-veto is-dev">
      <button
        type="button"
        className="cv-det-veto-btn"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <ArrowsDownUpIcon width={15} height={15} />
        偏离计分规则
        <span className="cv-det-veto-count">{rules.length} 条</span>
        <ChevronIcon
          width={13}
          height={13}
          className={open ? "cv-det-veto-caret is-open" : "cv-det-veto-caret"}
        />
      </button>
      {open ? (
        rules.map((v, i) => (
          <div key={i} className="cv-det-veto-row">
            <span className="cv-det-veto-no" aria-hidden>
              {String(i + 1).padStart(2, "0")}
            </span>
            <div style={{ minWidth: 0 }}>
              {v.summary && <div className="cv-det-dev-sum">{v.summary}</div>}
              <span className={v.summary ? "cv-det-dev-text" : undefined}>
                {v.text}
              </span>
              <SourceRow
                refs={v.refs}
                itemKey={`dev:${v.id ?? i}`}
                claim={{
                  matrixType: "scoring",
                  itemId: null,
                  label: `偏离规则 ${v.id ?? i + 1}`,
                  title: v.summary ?? "偏离计分规则",
                  requirementText: v.text,
                }}
              />
            </div>
          </div>
        ))
      ) : (
        <div className="cv-det-veto-peek">{first?.text || first?.summary}</div>
      )}
    </section>
  );
}

/** 评分项沿用阅读条目语法，分值固定在右侧数字列。 */
function ScoringRow({ item, itemKey }: { item: ScoringItem; itemKey: string }) {
  const [open, setOpen] = useState(false);
  const contentId = useId();
  const rule = item.scoring_rule?.trim();
  return (
    <article
      className={`rd-item rd-score-item${open ? " is-open" : ""}`}
      data-reading-item={itemKey}
    >
      <div className="rd-item-eyebrow">
        <span>{item.id || "评分项"}</span>
        {item.subgroup && <span>{item.subgroup}</span>}
        {item.mandatory_gate && <span className="rd-warning">否决条件</span>}
      </div>
      <div className="rd-score-heading">
        <h3 className="rd-item-title">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls={contentId}
          >
            {item.title || "未命名评分项"}
          </button>
        </h3>
        <span className="rd-score-value">
          {typeof item.max_score === "number" ? (
            <>
              <b>{fmtScore(item.max_score)}</b> 分
            </>
          ) : (
            "未提取"
          )}
        </span>
      </div>
      {!open && <p className="rd-excerpt">{rule || "未提取评分规则"}</p>}
      <div id={contentId} hidden={!open} className="rd-item-content">
        <section className="rd-detail-section">
          <h4>评分规则</h4>
          <p>{rule || "未提取评分规则"}</p>
        </section>
        {item.related_format && (
          <section className="rd-detail-section">
            <h4>关联格式</h4>
            <p>{item.related_format}</p>
          </section>
        )}
        {item.notes && (
          <section className="rd-detail-section">
            <h4>补充说明</h4>
            <p>{item.notes}</p>
          </section>
        )}
        <section className="rd-detail-section">
          <h4>原文依据</h4>
          <SourceChips
            refs={item.source_refs ?? []}
            itemKey={itemKey}
            claim={{
              matrixType: "scoring",
              itemId: null,
              label: `评分项 ${item.id ?? itemKey}`,
              title: item.title || "未命名评分项",
              requirementText: rule || "",
              highRisk: !!item.mandatory_gate,
            }}
          />
        </section>
      </div>
      <button
        type="button"
        className="rd-text-button rd-collapse"
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "收起详情" : "查看详情"}
      </button>
    </article>
  );
}

interface VetoRule {
  text: string;
  refs: SourceRef[];
  id: string | null;
}
interface DeviationRule extends VetoRule {
  summary: string | null;
}

function ScoringDetail({ slot }: { slot: MatrixSlot<ScoringMatrix> }) {
  const [category, setCategory] = useState("");
  const [byScore, setByScore] = useState(false);
  if (slot.status !== "ready" || !slot.data)
    return <SlotFallback slot={slot} />;
  const d = slot.data;
  const ev = d.evaluation ?? {};
  const readRule = (r: unknown) => {
    const rec = asRec(r);
    return {
      text: vetoRuleText(r),
      refs: asSourceRefs(rec?.source_refs),
      id: typeof rec?.id === "string" ? rec.id : null,
    };
  };
  const vetoRules = (ev.pass_fail_rules ?? [])
    .map(readRule)
    .filter((r) => r.text);
  const deviationRules = (ev.deviation_rules ?? [])
    .map((r) => ({ ...readRule(r), summary: deviationSummary(asRec(r)) }))
    .filter((r) => r.text || r.summary);
  const all = (d.items ?? []).map((it, i) => ({
    it,
    key: `score:${it.id ?? i}`,
  }));
  const nominal: Record<string, number | null | undefined> = {
    price: ev.price_score,
    business: ev.business_score,
    technical: ev.technical_score,
  };
  const keys = [
    ...new Set([
      ...SCORE_GROUP_ORDER.filter(
        (k) =>
          all.some(({ it }) => (it.group || "other") === k) ||
          typeof nominal[k] === "number",
      ),
      ...all.map(({ it }) => it.group || "other"),
    ]),
  ];
  const parts = keys.map((key) => {
    const scored = all.filter(
      ({ it }) =>
        (it.group || "other") === key && typeof it.max_score === "number",
    );
    return {
      key,
      score: scored.length
        ? scored.reduce((sum, { it }) => sum + it.max_score!, 0)
        : (nominal[key] ?? null),
    };
  });
  const known = parts.reduce((sum, part) => sum + (part.score ?? 0), 0);
  const total = typeof ev.total_score === "number" ? ev.total_score : null;
  if (total !== null && total - known > 0.005)
    parts.push({ key: "__unassigned", score: total - known });
  const base = total ?? known;
  const visible = all.filter(
    ({ it }) => !category || (it.group || "other") === category,
  );
  if (byScore)
    visible.sort(
      (a, b) => (b.it.max_score ?? -Infinity) - (a.it.max_score ?? -Infinity),
    );
  return (
    <div className="rd-scoring">
      <SummaryStrip data={d} />
      <section className="rd-score-overview">
        <div className="rd-score-total">
          <div>
            <span className="rd-eyebrow">评分构成</span>
            <h2>{ev.method || "评标方法未提取"}</h2>
          </div>
          <span>
            {total !== null ? (
              <>
                <b>{fmtScore(total)}</b> 分
              </>
            ) : (
              "总分未提取"
            )}
          </span>
        </div>
        <div className="rd-score-parts">
          {parts.map((part) => (
            <div className="rd-score-part" key={part.key}>
              <span>
                {part.key === "__unassigned"
                  ? "未分配分值"
                  : zh(SCORE_GROUP, part.key)}
              </span>
              <div
                className={part.score === null ? undefined : "rd-score-track"}
                aria-hidden="true"
              >
                <i
                  style={{
                    width: `${base > 0 && part.score !== null ? Math.min(100, Math.max(0, (part.score / base) * 100)) : 0}%`,
                  }}
                />
              </div>
              <span>
                {part.score === null ? "未提取" : `${fmtScore(part.score)} 分`}
              </span>
            </div>
          ))}
        </div>
        {total !== null && known - total > 0.005 && (
          <p className="rd-warning">分类分值合计与总分不一致，请核对原文。</p>
        )}
      </section>
      <VetoBand rules={vetoRules} />
      <DeviationBand rules={deviationRules} />
      <div className="rd-toolbar rd-score-toolbar">
        <label>
          评分分类
          <select
            aria-label="评分分类"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">全部评分项 · {all.length}</option>
            {keys.map((k) => (
              <option value={k} key={k}>
                {zh(SCORE_GROUP, k)}
              </option>
            ))}
          </select>
        </label>
        <button
          className="rd-button"
          type="button"
          aria-pressed={byScore}
          onClick={() => setByScore((v) => !v)}
        >
          <ArrowsDownUpIcon width={14} height={14} />
          {byScore ? "恢复原文顺序" : "按分值排序"}
        </button>
      </div>
      {!visible.length ? (
        <div className="rd-empty">
          <b>未提取到评分项</b>
          <p>已提取的分类分值仍显示在上方。</p>
        </div>
      ) : (
        visible.map(({ it, key }, i) => (
          <Fragment key={key}>
            {!byScore && (i === 0 || visible[i - 1]?.it.group !== it.group) && (
              <h2 className="rd-group-title">{zh(SCORE_GROUP, it.group)}</h2>
            )}
            <ScoringRow item={it} itemKey={key} />
          </Fragment>
        ))
      )}
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
        <RequirementDetail
          type={type}
          slot={slot as MatrixSlot<BusinessMatrix>}
          categoryMap={BIZ_CATEGORY}
        />
      );
    case "technical":
      return (
        <RequirementDetail
          type={type}
          slot={slot as MatrixSlot<TechnicalMatrix>}
          categoryMap={TECH_CATEGORY}
        />
      );
    case "scoring":
      return <ScoringDetail slot={slot as MatrixSlot<ScoringMatrix>} />;
  }
}
