// 投标文件骨架 = 记分卡的投影。数据取自 sample-tender.md：
// 三册（资格证明文件 / 商务技术文件 / 价格文件），评审办法 100 分 = 价格 25 / 商务 19 / 技术 56，
// 评分表「关联格式」列（业绩 / 技术力量证明材料 / 技术方案 / 技术指标参数响应偏离表 / 项目管理和实施 / 培训及售后服务 / 开标一览表）
// 就是章节树的来源。
import { I } from "./parts.mjs";

// 列位：首列从 372 起（消息窗 min 档右缘在 346，列眉不再被它压住）。
// 册一与册三都很薄，堆在同一列；册二六章占三列。
export const VOLUMES = [
  { id: "v1", name: "资格证明文件", tag: "册一", x: 372 },
  { id: "v2", name: "商务技术文件", tag: "册二", x: 630 },
  { id: "v3", name: "价格文件", tag: "册三", x: 372, below: "v1" },
];

// hero: 主指标；mand: 挂接的实质性条款数（商务 ★ 12 = 册一 8 + 商务 2 + 价格 2；技术 ★ 29 同时挂 3 章与 5 章）；
// links: 信号行；评分项合计 10 + 6 + 5 + 2 + 3 + 3 + 1 = 30。
export const CHAPTERS = [
  { id: "c1", vol: "v1", col: 0, no: "1", name: "资格证明材料", hero: ["8", "项资格性审查"], mand: 8, links: ["资格 11", "审查表 8"],
    rows: [["1.1", "营业执照"], ["1.2", "近 3 年审计报告"], ["1.3", "社保缴纳证明"], ["1.4", "供应商承诺声明"], ["1.5", "法定代表人授权书"], ["1.6", "军队采购网备案"], ["1.7", "保密资质与承诺"], ["1.8", "供应商投标承诺书（纸质）"]] },
  { id: "c2", vol: "v2", col: 0, no: "2", name: "商务响应", hero: ["19", "分 · 商务评审"], mand: 2, links: ["★ 2", "评分 10"],
    rows: [["2.1", "投标函及附录"], ["2.2", "商务要求逐条响应表"], ["2.3", "同类项目业绩", "8 分"], ["2.4", "企业规模与财务状况", "8 分"], ["2.6", "服务承诺书", "3 分"]] },
  { id: "c3", vol: "v2", col: 0, no: "3", name: "技术方案", hero: ["20", "分 · 主观评审"], mand: 29, links: ["★ 29", "评分 6"],
    rows: [["3.1", "需求分析", "3 分"], ["3.2", "系统架构设计", "3 分"], ["3.3", "功能与接口设计", "3 分"], ["3.4", "集成与实施方案", "4 分"], ["3.5", "安全保密方案", "3 分"], ["3.6", "试验验证方案", "4 分"]] },
  { id: "c4", vol: "v2", col: 1, no: "4", name: "技术力量证明", hero: ["5", "分 · 客观评审"], mand: 0, links: ["评分 5"],
    rows: [["4.1", "质量 / 信息安全 / IT 服务体系认证", "3 分"], ["4.2", "GJB5000 认证", "1 分"], ["4.3", "拟派项目负责人资质", "1 分"]] },
  { id: "c5", vol: "v2", col: 1, no: "5", name: "技术指标响应偏离表", hero: ["23", "分 · 客观评审"], mand: 29, links: ["★ 29", "评分 2"],
    rows: [["5.1", "★ 关键指标逐条响应"], ["5.2", "一般指标偏离表", "23 分"], ["5.3", "技术支持材料"]] },
  { id: "c6", vol: "v2", col: 2, no: "6", name: "项目管理与实施", hero: ["1.5", "分 · 主观评审"], mand: 0, links: ["评分 3"],
    rows: [["6.1", "实施周期与进度", "0.5 分"], ["6.2", "组织管理与质量保证", "0.5 分"], ["6.3", "风险评估与控制", "0.5 分"]] },
  { id: "c7", vol: "v2", col: 2, no: "7", name: "培训与售后服务", hero: ["6.5", "分 · 服务承诺"], mand: 0, links: ["评分 3"],
    rows: [["7.1", "培训计划", "0.5 分"], ["7.2", "免费质保期承诺", "4 分"], ["7.3", "维修响应承诺", "2 分"]] },
  { id: "c8", vol: "v3", col: 0, no: "8", name: "价格文件", hero: ["25", "分 · 价格评审"], mand: 2, links: ["★ 2", "评分 1"],
    rows: [["8.1", "开标一览表"], ["8.2", "分项报价表"], ["8.3", "易损易耗件清单"]] },
];

// 度量按 tokens.mjs 的 CSS 实测：ch-face 内边距 11+9，题名行 18 + 下距 9，主指标 24，结构条 8+4+6，信号行 17 → 106；
// 健康度徽一行 6 + 14 → 20；子节行 22；行区底距 6。
const COL_W = 236, COL_GAP = 22, CARD_GAP = 16, TOP = 36, HEAD_H = 24;
const FACE_H = 106, BADGE_H = 20, ROW_H = 22, ROWS_PAD = 6;
export const cardH = (c, hasBadge) => FACE_H + (hasBadge ? BADGE_H : 0) + c.rows.length * ROW_H + ROWS_PAD;

/** 计算每张章节卡与每个册眉的 world 坐标（按册、按列纵向堆叠；册三堆在册一列下） */
export function layout(badges = {}) {
  const pos = {};
  const heads = {};
  const stacks = {};
  for (const v of VOLUMES) {
    if (v.below) continue;
    heads[v.id] = { x: v.x, y: TOP };
  }
  for (const c of CHAPTERS) {
    const vol = VOLUMES.find((v) => v.id === c.vol);
    const x = vol.x + c.col * (COL_W + COL_GAP);
    const key = `${x}`;
    if (vol.below && heads[vol.id] === undefined) {
      const y = stacks[key] ?? TOP + HEAD_H;   // 上一册的列末（已含卡间距）
      heads[vol.id] = { x: vol.x, y };
      stacks[key] = y + HEAD_H;
    }
    const y = stacks[key] ?? TOP + HEAD_H;
    const h = cardH(c, (badges[c.id] ?? []).length > 0);
    pos[c.id] = { x, y, w: COL_W, h };
    stacks[key] = y + h + CARD_GAP;
  }
  return { pos, heads };
}

/**
 * 渲染骨架。states: { [rowId]: 'todo'|'running'|'review'|'done'|'wait'|'queued' }，
 * badges: { [chapterId]: [{kind:'cover'|'cite'|'comply', n, fatal}] }，
 * rowNotes: { [rowId]: {text, tone} }，selected: chapterId
 */
export function skeleton({ states = {}, badges = {}, rowNotes = {}, selected = null, heroOverride = {}, faceState = {} } = {}) {
  const { pos, heads } = layout(badges);
  const headHtml = VOLUMES.map((v) => {
    const n = CHAPTERS.filter((c) => c.vol === v.id).reduce((a, c) => a + c.rows.length, 0);
    const h = heads[v.id];
    return `<div class="ch-col-head" style="left:${h.x}px;top:${h.y}px"><b>${v.tag} · ${v.name}</b>${n} 节</div>`;
  }).join("");

  const cards = CHAPTERS.map((c) => {
    const p = pos[c.id];
    const rowStates = c.rows.map(([id]) => states[id] ?? "todo");
    const stack = rowStates.map((s) => `<i class="${s === "done" ? "done" : s === "running" || s === "review" ? "run" : s === "wait" ? "s3" : "rest"}" style="flex:1"></i>`).join("");
    const running = rowStates.some((s) => s === "running");
    const b = badges[c.id] ?? [];
    const badgeHtml = b.length
      ? `<div class="h-badges">${b.map((x) => `<span class="h-badge ${x.fatal ? "is-fatal" : "is-warn"}">${x.kind === "cover" ? I.link(12) : x.kind === "cite" ? I.quote(12) : I.shield(12)}${x.kind === "cover" ? "覆盖" : x.kind === "cite" ? "有据" : "合规"} 缺 <b>${x.n}</b></span>`).join("")}</div>`
      : "";
    const hero = heroOverride[c.id] ?? c.hero;
    const sig = faceState[c.id]
      ? faceState[c.id]
      : `<span class="is-note">${c.links.join(" · ")} 挂接</span>`;
    const rows = c.rows.map(([id, name, score]) => {
      const s = states[id] ?? "todo";
      const note = rowNotes[id];
      const dot = s === "done" ? "g" : s === "running" ? "b" : s === "review" ? "ring" : s === "wait" ? "o" : s === "fail" ? "r" : "k";
      const side = note
        ? `<span class="ch-row-s ${note.tone ? `is-${note.tone}` : ""}">${note.text}</span>`
        : s === "running" ? `<span class="ch-row-s is-blue">正在撰写</span>`
        : s === "review" ? `<span class="ch-row-s is-blue">待验收</span>`
        : s === "wait" ? `<span class="ch-row-s is-warn">等你回答</span>`
        : s === "done" ? `<span class="ch-row-s">已验收</span>`
        : s === "queued" ? `<span class="ch-row-s">排队</span>`
        : score ? `<span class="ch-row-s">${score}</span>` : "";
      return `<div class="ch-row${s === "running" ? " is-active" : s === "wait" ? " is-wait" : ""}"><span class="dot ${dot}"></span><span class="ch-row-t">${id} ${name}</span>${side}</div>`;
    }).join("");
    return `<div class="ch-card${selected === c.id ? " is-selected" : ""}${running ? " is-running" : ""}" style="left:${p.x}px;top:${p.y}px" data-ch="${c.id}">
      ${running ? '<div class="cv-face-thread"></div>' : ""}
      <div class="ch-face">
        <div class="cv-face-head">${I.file(14)}<span class="cv-face-name">${c.no} ${c.name}</span>${c.mand ? `<span class="cv-face-state">★ ${c.mand}</span>` : ""}</div>
        <div class="cv-face-hero"><b style="font-size:22px">${hero[0]}</b><span>${hero[1]}</span></div>
        <div class="cv-face-stack" style="margin:8px 0 6px">${stack}</div>
        <div class="cv-face-sig">${sig}</div>
        ${badgeHtml}
      </div>
      <div class="ch-rows">${rows}</div>
    </div>`;
  }).join("");

  return headHtml + cards;
}

/** 依据连线：从停靠列矩阵卡右缘到章节卡左缘的贝塞尔弧（world 坐标） */
export function links(pairs, badges = {}) {
  const { pos } = layout(badges);
  const paths = pairs.map(({ from, to, tone = "" }) => {
    const [fx, fy] = from;
    const t = pos[to];
    const tx = t.x, ty = t.y + 44;
    const mx = (fx + tx) / 2;
    return `<path d="M${fx} ${fy} C ${mx} ${fy}, ${mx} ${ty}, ${tx} ${ty}" fill="none" stroke="${tone === "blue" ? "var(--blue)" : "color-mix(in srgb, var(--label-3) 40%, transparent)"}" stroke-width="1.2" stroke-dasharray="${tone === "blue" ? "0" : "3 4"}"/><circle cx="${tx}" cy="${ty}" r="2.5" fill="${tone === "blue" ? "var(--blue)" : "var(--label-3)"}"/>`;
  }).join("");
  return `<svg class="cv-links" width="1412" height="770">${paths}</svg>`;
}
