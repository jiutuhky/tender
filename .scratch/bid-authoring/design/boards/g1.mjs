// G1 定策：骨架主视图（Main）、裁决队列抽屉（Adjudicate）；计划审批（Approval，消息窗 open 档）属 G3，放在同文件便于共用片段
import { I, bot, page, workspace, toolbar, dockedMatrixCards, msgwinMin, dock, MODE_PROPS, MODE_SCRIPT } from "../lib/parts.mjs";
import { skeleton, links } from "../lib/outline.mjs";

export function Main() {
  const badges = { c1: [{ kind: "cover", n: 1 }], c2: [{ kind: "cover", n: 1 }], c5: [{ kind: "cover", n: 1 }] };
  const world =
    links([
      { from: [256, 84 + 2 * 141 + 60], to: "c3", tone: "blue" },
      { from: [256, 84 + 3 * 141 + 60], to: "c3", tone: "blue" },
      { from: [256, 84 + 2 * 141 + 60], to: "c5" },
    ], badges) +
    dockedMatrixCards({ dim: true }) +
    skeleton({
      selected: "c3",
      badges,
      rowNotes: { "1.8": { text: "未挂接", tone: "warn" }, "2.2": { text: "缺 1 ★", tone: "warn" }, "5.3": { text: "未挂接 ★", tone: "warn" } },
    });

  const floats =
    msgwinMin({ ticker: "已生成骨架 · 覆盖闭合：<b>3</b> 条强制项未挂接" }) +
    dock({
      chips: [
        { icon: I.list(14), label: "查看未挂接项" },
        { icon: I.tree(14), label: "调整章节树" },
        { icon: I.pen(14), label: "开始备料" },
      ],
      placeholder: "对骨架下指令，例如「把 3.5 安全保密方案拆成保密与安全两节」…",
    });

  const tb = toolbar({
    label: "投标文件骨架",
    sub: `G1 定策 · 强制项 <b>41/44</b> 已挂接 · 评分项 <b>30/30</b> · 必备格式 <b>12/13</b> · <span class="is-warn">待裁决 3</span>`,
    right: `<button class="btn">${I.warning(14)}裁决<span class="n">3</span></button><button class="btn is-primary" disabled>${I.check(14)}确认骨架</button>`,
  });

  return page({
    body: workspace({ modeHole: true, tb, world, floats }),
    props: MODE_PROPS,
    script: MODE_SCRIPT,
  });
}

/* ---------- 裁决队列抽屉：覆盖闭合报告 ---------- */
export function Adjudicate() {
  const item = (no, star, title, text, src, actions, first) => `
    <div class="row${first ? " is-first" : ""}">
      <span class="row-no">${no}</span>
      <div class="row-main">
        <div class="row-t">${star ? '<span class="star">★</span>' : ""}${title}</div>
        <div class="row-d">${text}</div>
        <div class="row-f"><span class="chip">${I.file(11)}${src}</span>${actions}</div>
      </div>
    </div>`;
  const pick = (opts) => opts.map((o, i) => `<span class="act${i === 0 ? " is-primary" : ""}">${o}</span>`).join("");

  const body = `<div class="wrap" style="background:var(--surface)" data-appearance="{{mode}}">
    <div class="cv-drawer-main" style="width:100%;box-shadow:none">
      <div class="cv-drawer-head">${I.link(16)}
        <div class="cv-drawer-titlebox"><div class="cv-drawer-title">覆盖闭合 · 裁决队列</div><div class="cv-drawer-sub">每条强制项与每个评分项至少挂一节 · 未闭合不进入备料</div></div>
        <button class="cv-drawer-close">${I.x(15)}</button>
      </div>
      <div class="cv-drawer-body">
        <div class="seg"><span class="is-active">未挂接<span class="s-n">3</span></span><span>低置信挂接<span class="s-n">4</span></span><span>已裁决<span class="s-n">2</span></span></div>

        <div class="gh is-warn">${I.warning(13)}<b>强制项未挂接</b><span class="n">3 条 · 不满足即无效投标</span><span class="r">来源：商务应答矩阵 3</span></div>
        ${item("1", true, "交付（服务）时间：合同签订之日起 120 日内", "商务要求 B-01 为实质性条款，骨架中无章节响应交付时间与地点。建议挂接到 6.1 实施周期与进度，并在 2.2 商务响应表中逐条响应。", "L1262 · 商务要求", pick(["挂接到 6.1", "挂接到 2.2", "新建节", "不适用…"]), true)}
        ${item("2", true, "数据脱敏：投标文件涉密资料须脱密处理", "专用文件「特别提示」第二十条。属于编制合规要求而非技术要求，当前无章节承接；建议作为 5.3 技术支持材料的编制约束，并进入终检规则。", "L983 · 特别提示", pick(["挂接到 5.3", "转为终检规则", "不适用…"]))}
        ${item("3", true, "《供应商投标承诺书》纸质版（离线客户端编制时）", "通用文件第十八条：使用离线版投标客户端编制的，投标时必须提供纸质承诺书，否则电子投标文件被拒收。骨架 1.8 已建节但未挂接来源。", "L979 · 特别提示", pick(["挂接到 1.8", "不适用（在线版）"]))}

        <div class="gh">${I.list(13)}<b>低置信挂接</b><span class="n">4 条 · 智能体自评置信度低于 0.7</span></div>
        ${item("4", false, "技术方案 2 · 系统架构设计合理性（3 分）→ 3.2", "评分规则要求「针对性」，当前 3.2 未挂接第六章技术要求第 1 条数据归集引接软件要求；建议追加挂接。", "L1113 · 附表 4", pick(["追加挂接 T-01", "保持"]), true)}
        ${item("5", false, "培训和售后服务 2 · 免费质保期每增 12 个月得 1 分 → 7.2", "客观分。骨架把它挂到 7.2 承诺，但承诺值需要企业决策（成本项），已标记为「等你回答」。", "L1113 · 附表 4", pick(["确认挂接", "改挂 2.6"]))}
        ${item("6", false, "一般技术指标负偏离（13 分，5.2 合计 23 分）→ 5.2", "同一评分项同时挂接 5.1 与 5.2；建议 5.1 只承担 ★ 关键指标，负偏离评分由 5.2 单独响应。", "L1113 · 附表 4", pick(["按建议拆分", "保持双挂"]))}
        ${item("7", false, "项目管理与实施 3 · 项目风险（0.5 分）→ 6.3", "分值低但为独立评分项；已挂接，置信度低因规则原文被表格跨页截断。", "L1113 · 附表 4", pick(["确认挂接", "查看原文"]))}
      </div>
      <div class="cv-drawer-foot"><span class="note">裁决后覆盖闭合自动重跑；闭合即解锁「确认骨架」。</span><button class="btn">${I.refresh(14)}重跑闭合检查</button></div>
    </div>
  </div>`;
  return page({ body, props: MODE_PROPS, script: MODE_SCRIPT });
}

/* ---------- 计划审批：消息窗 open 档 ---------- */
export function Approval() {
  const body = `<div class="wrap" data-appearance="{{mode}}">
    <div class="cv-msgwin is-open glass is-thick" style="left:14px;top:14px">
      <div class="cv-msgwin-bot is-busy">${bot(36)}</div>
      <div class="cv-msgwin-head">
        <div class="cv-msgwin-title"><div class="cv-msgwin-name">撰写 信保体系建设数据资源池项目</div>
          <div class="cv-msgwin-sub"><span class="dot b" style="width:6px;height:6px"></span><span>G3 成文 · 等待计划批准</span></div></div>
        <button class="cv-msgwin-btn">${I.plus(15)}</button><button class="cv-msgwin-btn">${I.minus(15)}</button>
      </div>
      <div class="cv-msgwin-stream">
        <div class="cm-user">备料已认领完毕，开始撰写技术方案分册。</div>
        <div class="cm-agent">
          <div class="cm-thinking">${I.sparkle(15)}<span>思考过程 · 2 段推理 · 13 次工具调用</span><span class="chev">${I.chevron(12)}</span></div>
          <p>已为<b>技术方案分册</b>打包 12 份写作简报：要求原文（带来源）、评分规则与分值、可用证据锚记、篇幅预算与口径卡。</p>
          <div class="plan-card">
            <div class="plan-card-h">并行撰写计划<span>12 节 · 预计 18 分钟</span></div>
            <div class="plan-list">
              <div><span class="n">3.1</span>需求分析<span class="m">3 分 · 1,800 字 · 证据 2</span></div>
              <div><span class="n">3.2</span>系统架构设计<span class="m">3 分 · 2,400 字 · 证据 3 · 1 图</span></div>
              <div><span class="n">3.4</span>集成与实施方案<span class="m">4 分 · 2,200 字 · 证据 4</span></div>
              <div><span class="n">5.1</span>★ 关键指标逐条响应<span class="m">29 条 · 偏离表投影</span></div>
              <div><span class="n">…</span><span style="color:var(--label-3)">另 8 节</span><span class="m">口径卡 v2 · 并发 4</span></div>
            </div>
            <div class="plan-actions">
              <div class="opt is-primary">${I.play(14)}批准，自动撰写全部 12 节<small>逐节验收</small></div>
              <div class="opt">${I.eye(14)}批准，但每节写完先给我看<small>逐节确认</small></div>
              <div class="opt">${I.pen(14)}先改计划<small>在骨架上直接改</small></div>
            </div>
          </div>
          <p style="font-size:12px;color:var(--label-3)">每节独立执行、可单独停止；10 分钟未回应则按「逐节验收」开跑。</p>
        </div>
      </div>
    </div>
  </div>`;
  return page({ body, props: MODE_PROPS, script: MODE_SCRIPT });
}
