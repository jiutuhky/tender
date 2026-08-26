// 共享片段：图标、Bot 形象、顶栏、工具栏、停靠列矩阵卡、消息窗、子代理看板、输入坞、页面包装。
import { TOKENS_CSS } from "./tokens.mjs";

/* ---------- 图标（Phosphor regular 风格，1.5px 描边，24 网格） ---------- */
const svg = (body, size = 14, extra = "") =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" ${extra}>${body}</svg>`;

export const I = {
  tree: (s) => svg(`<rect x="3" y="4" width="7" height="5" rx="1.2"/><rect x="14" y="3" width="7" height="5" rx="1.2"/><rect x="14" y="16" width="7" height="5" rx="1.2"/><path d="M10 6.5h2v11.5h2M12 6.5h2"/>`, s),
  table: (s) => svg(`<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 15h18M9 4v16"/>`, s),
  idcard: (s) => svg(`<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8.5" cy="11" r="2"/><path d="M5.5 16c.6-1.6 1.8-2.4 3-2.4s2.4.8 3 2.4M14 10h4M14 14h4"/>`, s),
  cases: (s) => svg(`<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7M3 12h18"/>`, s),
  list: (s) => svg(`<path d="M9 6h12M9 12h12M9 18h12"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>`, s),
  chart: (s) => svg(`<path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/>`, s),
  sparkle: (s) => svg(`<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/>`, s),
  check: (s) => svg(`<path d="M5 12.5l4.5 4.5L19 7.5"/>`, s),
  x: (s) => svg(`<path d="M6 6l12 12M18 6L6 18"/>`, s),
  warning: (s) => svg(`<path d="M12 4l9 16H3zM12 10v4M12 17.2v.3"/>`, s),
  prohibit: (s) => svg(`<circle cx="12" cy="12" r="8.5"/><path d="M6 6l12 12"/>`, s),
  file: (s) => svg(`<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>`, s),
  files: (s) => svg(`<path d="M8 6h7l4 4v10H8z"/><path d="M15 6v4h4M5 9v12h10"/>`, s),
  plus: (s) => svg(`<path d="M12 5v14M5 12h14"/>`, s),
  minus: (s) => svg(`<path d="M5 12h14"/>`, s),
  chevron: (s) => svg(`<path d="M6 9l6 6 6-6"/>`, s),
  chevR: (s) => svg(`<path d="M9 6l6 6-6 6"/>`, s),
  arrowR: (s) => svg(`<path d="M4 12h16M13 5l7 7-7 7"/>`, s),
  search: (s) => svg(`<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>`, s),
  paperclip: (s) => svg(`<path d="M20 11.5l-8.5 8.5a5 5 0 0 1-7-7l9-9a3.3 3.3 0 0 1 4.7 4.7l-9 9a1.6 1.6 0 0 1-2.3-2.3L15 7.5"/>`, s),
  plane: (s) => svg(`<path d="M21 3L10 14M21 3l-7 18-4-7-7-4z"/>`, s),
  sidebar: (s) => svg(`<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>`, s),
  frame: (s) => svg(`<path d="M6 3v18M18 3v18M3 6h18M3 18h18"/>`, s),
  grid: (s) => svg(`<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>`, s),
  refresh: (s) => svg(`<path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5"/>`, s),
  clock: (s) => svg(`<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>`, s),
  users: (s) => svg(`<circle cx="9" cy="8" r="3.2"/><path d="M3.5 19c.8-3 3-4.5 5.5-4.5s4.7 1.5 5.5 4.5M16 5.5a3 3 0 0 1 0 6M20.5 19c-.5-2.4-1.8-3.8-3.5-4.3"/>`, s),
  pen: (s) => svg(`<path d="M4 20l4-1 11-11-3-3L5 16zM14 7l3 3"/>`, s),
  wrench: (s) => svg(`<path d="M14.5 6.5a4 4 0 0 0 5 5L9 22l-3-3zM14.5 6.5L17 4l3 3-2.5 2.5"/>`, s),
  gear: (s) => svg(`<circle cx="12" cy="12" r="3"/><path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M5.6 18.4l1.8-1.8M16.6 7.4l1.8-1.8"/>`, s),
  folder: (s) => svg(`<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5H9l2 2h8.5A1.5 1.5 0 0 1 21 8.5V18a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18z"/>`, s),
  download: (s) => svg(`<path d="M12 4v11M7 10l5 5 5-5M4 19h16"/>`, s),
  upload: (s) => svg(`<path d="M12 15V4M7 9l5-5 5 5M4 19h16"/>`, s),
  stack: (s) => svg(`<path d="M12 4l9 4.5-9 4.5-9-4.5zM3 13l9 4.5 9-4.5"/>`, s),
  link: (s) => svg(`<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>`, s),
  shield: (s) => svg(`<path d="M12 3l8 3v6c0 4.5-3.3 7.8-8 9-4.7-1.2-8-4.5-8-9V6z"/><path d="M9 12l2 2 4-4"/>`, s),
  calc: (s) => svg(`<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 12h2M12 12h2M16 12h0M8 16h2M12 16h2M16 16h0"/>`, s),
  building: (s) => svg(`<path d="M4 21V5l8-2v18M12 21V9l8 2v10M20 21H4M8 8h1M8 12h1M8 16h1M15 13h1M15 17h1"/>`, s),
  cert: (s) => svg(`<circle cx="12" cy="9" r="5"/><path d="M9 13.5L8 21l4-2 4 2-1-7.5"/>`, s),
  stop: (s) => svg(`<rect x="6" y="6" width="12" height="12" rx="2"/>`, s),
  play: (s) => svg(`<path d="M7 5l12 7-12 7z"/>`, s),
  history: (s) => svg(`<path d="M4 12a8 8 0 1 0 2.3-5.7M4 4v5h5M12 8v4l3 2"/>`, s),
  eye: (s) => svg(`<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>`, s),
  bookmark: (s) => svg(`<path d="M6 3h12v18l-6-4-6 4z"/>`, s),
  dots: (s) => svg(`<circle cx="6" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="18" cy="12" r="1.2"/>`, s),
  quote: (s) => svg(`<path d="M7 10a3 3 0 0 0-3 3v4h5v-5H6a1 1 0 0 1 1-2zM17 10a3 3 0 0 0-3 3v4h5v-5h-3a1 1 0 0 1 1-2z"/>`, s),
  sun: (s) => svg(`<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>`, s),
  bell: (s) => svg(`<path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20a2 2 0 0 0 4 0"/>`, s),
  print: (s) => svg(`<path d="M7 8V3h10v5M7 17H4v-6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v6h-3M7 14h10v7H7z"/>`, s),
  seal: (s) => svg(`<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/>`, s),
  ruler: (s) => svg(`<path d="M3 17l14-14 4 4L7 21zM8 12l2 2M11 9l2 2M14 6l2 2"/>`, s),
  git: (s) => svg(`<circle cx="6" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="9" r="2.5"/><path d="M6 8.5v7M18 11.5c0 3-3 4-6 4H8.5"/>`, s),
  db: (s) => svg(`<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>`, s),
  cpu: (s) => svg(`<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="10" y="10" width="4" height="4"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>`, s),
  doc: (s) => svg(`<path d="M6 3h9l4 4v14H6z"/><path d="M15 3v4h4M9 12h7M9 16h7M9 8h3"/>`, s),
  lock: (s) => svg(`<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>`, s),
  comment: (s) => svg(`<path d="M4 5h16v11H9l-5 4z"/>`, s),
};

/* ---------- Prose Bot 形象（frontend/components/ui/icons ProseBotIcon 原样） ---------- */
export function bot(size = 36, hue) {
  const id = hue === undefined ? "b0" : `b${Math.round(hue)}`;
  const face = hue === undefined
    ? `<stop offset="0" stop-color="#5fb0ff"/><stop offset=".55" stop-color="#1670ec"/><stop offset="1" stop-color="#0a3fa8"/>`
    : `<stop offset="0" stop-color="hsl(${hue} 100% 69%)"/><stop offset=".55" stop-color="hsl(${hue + 5} 85% 51%)"/><stop offset="1" stop-color="hsl(${hue + 10} 89% 35%)"/>`;
  return `<svg width="${size}" height="${size}" viewBox="0 0 36 36"><defs><linearGradient id="face-${id}" x1="0" y1="0" x2="1" y2="1">${face}</linearGradient><linearGradient id="gloss-${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs><rect width="36" height="36" rx="8.06" fill="url(#face-${id})"/><rect width="36" height="17" rx="8.06" fill="url(#gloss-${id})"/><rect x=".6" y=".6" width="34.8" height="34.8" rx="7.7" fill="none" stroke="#fff" stroke-opacity=".38"/><g fill="#fff"><rect x="10.4" y="14.8" width="5.2" height="6.4" rx="2.6"/><rect x="20.4" y="14.8" width="5.2" height="6.4" rx="2.6"/></g></svg>`;
}

/* ---------- 品牌标（assets/frost-icon.svg） ---------- */
export const brandMark = `<svg viewBox="0 0 120 120"><defs><linearGradient id="frost-bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5fb0ff"/><stop offset=".55" stop-color="#1670ec"/><stop offset="1" stop-color="#0a3fa8"/></linearGradient></defs><rect width="120" height="120" rx="27" fill="url(#frost-bg)"/><rect x="30" y="46" width="60" height="44" rx="8" fill="#fff" opacity=".28"/><rect x="26" y="36" width="68" height="48" rx="8" fill="#fff" opacity=".5"/><rect x="22" y="25" width="76" height="52" rx="9" fill="#fff"/><rect x="34" y="38" width="40" height="5" rx="2.5" fill="#1670ec"/><rect x="34" y="50" width="52" height="4" rx="2" fill="#9cc4f5"/><rect x="34" y="60" width="46" height="4" rx="2" fill="#9cc4f5"/></svg>`;

/* ---------- 顶栏 ---------- */
export function topbar({ crumbs = ["项目", "信保体系建设数据资源池项目"], active = "工作台" } = {}) {
  const tabs = ["首页", "工作台", "文档预览", "知识库"]
    .map((t) => `<a class="${t === active ? "active" : ""}">${t}</a>`)
    .join("");
  const bc = crumbs
    .map((c, i) => `${i ? '<span class="breadcrumb-sep">/</span>' : ""}<span class="${i === crumbs.length - 1 ? "crumb-current" : ""}">${c}</span>`)
    .join("");
  return `<header class="topbar glass is-soft is-thick is-flush">
    <div class="brand"><div class="brand-mark">${brandMark}</div>Prose</div>
    <div class="topbar-divider"></div>
    <div class="breadcrumb">${bc}</div>
    <nav class="nav-tabs">${tabs}</nav>
    <div class="topbar-actions"><button class="icon-btn">${I.sun(16)}</button><div class="avatar">LH</div></div>
  </header>`;
}

/* ---------- 画布工具栏 ---------- */
export function toolbar({ label = "投标文件骨架", sub = "", right = "" } = {}) {
  return `<div class="cv-toolbar">
    <div class="cv-toolbar-label">${I.tree(14)}${label}</div>
    <div class="cv-toolbar-sub">${sub}</div>
    <div class="cv-toolbar-spacer"></div>
    ${right}
    <div class="cv-zoom"><button>${I.minus(13)}</button><span class="cv-zoom-lvl">90%</span><button>${I.plus(13)}</button></div>
    <button class="cv-tool-btn" title="适配视口">${I.frame(15)}</button>
    <button class="cv-tool-btn" title="网格">${I.grid(15)}</button>
  </div>`;
}

/* ---------- 停靠列：四张矩阵卡（依据层） ---------- */
export function dockedMatrixCards({ x = 24, y = 84, gap = 14, dim = false } = {}) {
  const h = 127;
  const card = (i, inner) =>
    `<div class="cv-card is-face${dim ? " is-dim" : ""}" style="left:${x}px;top:${y + i * (h + gap)}px">${inner}</div>`;
  return [
    card(0, `<div class="cv-face-head">${I.idcard(14)}<span class="cv-face-name">项目概要</span></div>
      <div class="cv-face-hero is-warn"><b>9</b><span>天 · 距投标截止</span></div>
      <div class="cv-face-stack"><i class="s2" style="flex:31"></i><i class="rest" style="flex:9"></i></div>
      <div class="cv-face-sig"><span class="is-note">9 月 4 日 09:30 截止 · 预算 270 万元</span></div>`),
    card(1, `<div class="cv-face-head">${I.cases(14)}<span class="cv-face-name">商务应答矩阵</span></div>
      <div class="cv-face-hero"><b>38</b><span>条商务要求</span></div>
      <div class="cv-face-stack"><i class="s1" style="flex:11"></i><i class="s2" style="flex:9"></i><i class="s3" style="flex:8"></i><i class="s4" style="flex:6"></i><i class="rest" style="flex:4"></i></div>
      <div class="cv-face-sig"><span class="is-mand">实质性 <b>12</b> 项</span><span class="is-note">资格 11 · 投标文件 9</span></div>`),
    card(2, `<div class="cv-face-head">${I.list(14)}<span class="cv-face-name">技术应答矩阵</span></div>
      <div class="cv-face-hero"><b>63</b><span>条技术要求</span></div>
      <div class="cv-face-stack"><i class="s1" style="flex:24"></i><i class="s2" style="flex:15"></i><i class="s3" style="flex:11"></i><i class="s4" style="flex:8"></i><i class="rest" style="flex:5"></i></div>
      <div class="cv-face-sig"><span class="is-mand">实质性 <b>29</b> 项</span><span class="is-fatal">高风险 <b>4</b></span></div>`),
    card(3, `<div class="cv-face-head">${I.chart(14)}<span class="cv-face-name">评分办法</span></div>
      <div class="cv-face-hero"><b>100</b><span>分 · 30 项</span></div>
      <div class="cv-face-stack"><i class="s1" style="flex:56"></i><i class="s2" style="flex:25"></i><i class="s3" style="flex:19"></i></div>
      <div class="cv-face-sig"><span class="is-fatal">否决项 <b>9</b> 条</span><span class="is-note">技术 56 · 价格 25</span></div>`),
  ].join("");
}

/* ---------- Bot 消息窗（min 档） ---------- */
export function msgwinMin({ ticker = "", busy = false } = {}) {
  return `<div class="cv-msgwin glass is-thick">
    <div class="cv-msgwin-bot${busy ? " is-busy" : ""}">${bot(36)}</div>
    <div class="cv-msgwin-ticker">${ticker}</div>
    <span class="cv-msgwin-caret">${I.chevron(12)}</span>
  </div>`;
}

/* ---------- 子代理看板 ---------- */
export function agentBoard({ rows = [], head = "" } = {}) {
  const running = rows.filter((r) => r.state === "running").length;
  const list = rows
    .map(
      (r) => `<div class="cv-agentboard-row${r.state === "done" ? " is-done" : ""}">
      <span class="cv-agentboard-avatar">${bot(24, r.hue)}</span>
      <div class="cv-agentboard-main">
        <div class="cv-agentboard-line1"><span class="cv-agentboard-desc">${r.desc}</span>
          <span class="cv-agentboard-state"><span class="dot ${r.state === "running" ? "b" : r.state === "wait" ? "o" : "g"}"></span>${r.state === "running" ? "运行中" : r.state === "wait" ? "等你回答" : "已完成"}</span></div>
        <div class="cv-agentboard-sum">${r.sum}</div>
      </div></div>`,
    )
    .join("");
  return `<section class="cv-agentboard glass is-thick">
    <header class="cv-agentboard-head">${head || `子代理 · ${running > 0 ? `${running} 运行中` : `${rows.length} 已完成`}`}</header>
    <div class="cv-agentboard-list">${list}</div>
  </section>`;
}

/* ---------- 输入坞：快捷指令 或 活动条 + Composer ---------- */
export function dock({ chips = [], actbar = "", placeholder = "对这份投标文件下指令，或直接提问…" } = {}) {
  const bar = actbar
    ? `<button class="cv-actbar glass is-thin"><span class="dot b"></span><span class="cv-actbar-text">${actbar}</span>${I.chevron(11).replace("<svg", '<svg class="chev"')}</button>`
    : chips.map((c) => `<button class="cv-dock-chip glass is-soft is-thin">${c.icon}${c.label}</button>`).join("");
  return `<div class="cv-dock">
    <div class="cv-dockbar">${bar}</div>
    <div class="composer"><div class="composer-ph">${placeholder}</div>
      <div class="composer-actions"><span class="act">${I.paperclip(13)} 附件</span><span class="act">${I.folder(13)} 企业资料</span><span class="composer-send">${I.plane(12)} 发送</span></div>
    </div>
  </div>`;
}

/* ---------- 页面包装：完整 .dc.html ---------- */
export function page({ body, extraCss = "", script = null, props = null }) {
  const propsAttr = props ? ` data-props='${JSON.stringify(props).replace(/'/g, "&#39;")}'` : "";
  const scriptTag = script ? `\n<script data-dc-script${propsAttr}>\n${script}\n</script>` : "";
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <style>${TOKENS_CSS}${extraCss}
  </style>
</helmet>
${body}
</x-dc>${scriptTag}
</body>
</html>
`;
}

/** 工作台外壳：顶栏 + 画布窗口（工具栏 + 视口 + 浮层） */
export function workspace({ mode = "light", modeHole = false, crumbs, tb = "", world = "", floats = "", overlay = "" }) {
  const appearance = modeHole ? '{{mode}}' : mode;
  return `<div class="wrap" data-appearance="${appearance}">
  ${topbar({ crumbs })}
  <div class="main"><div class="center">
    ${tb}
    <div class="canvas-viewport">
      <div class="cv-viewport-hint glass is-soft is-thin">拖拽平移 · 滚轮缩放</div>
      <div class="cv-world">${world}</div>
      ${floats}
    </div>
    ${overlay}
  </div></div>
</div>`;
}

/** 外观切换 tweak（只此一枚：行为开关，不做文案 tweak） */
export const MODE_PROPS = { mode: { editor: "enum", options: ["light", "dark"], default: "light", section: "外观" } };
export const MODE_SCRIPT = `class Component extends DCLogic {
  renderVals() { return { mode: this.props.mode ?? 'light' }; }
}`;
