// G2 备料：缺料清单（画布 + 右侧抽屉）
import { I, page, workspace, toolbar, dockedMatrixCards, msgwinMin, dock, MODE_PROPS, MODE_SCRIPT } from "../lib/parts.mjs";
import { skeleton } from "../lib/outline.mjs";

export function Evidence() {
  const world =
    dockedMatrixCards({ dim: true }) +
    skeleton({
      // 缺料 6 项按章分布：册一 2（审计报告、保密承诺）· 商务 1（业绩合同）· 技术力量 3（ISO27001、GJB5000、负责人社保）
      badges: { c1: [{ kind: "cite", n: 2 }], c2: [{ kind: "cite", n: 1 }], c4: [{ kind: "cite", n: 3 }] },
      rowNotes: {
        "2.3": { text: "缺 3 份", tone: "warn" }, "2.4": { text: "命中 3/3" },
        "4.1": { text: "1 份过期", tone: "warn" }, "4.2": { text: "无记录", tone: "warn" }, "4.3": { text: "缺社保凭证", tone: "warn" },
        "1.2": { text: "缺 2025", tone: "warn" }, "1.7": { text: "缺 1", tone: "warn" },
        "3.2": { text: "证据 3" }, "3.4": { text: "证据 4" },
      },
    });

  const floats =
    msgwinMin({ ticker: "证据库命中 <b>14</b> · 缺料 <b>6</b> · 2 项影响实质性" }) +
    dock({
      chips: [{ icon: I.upload(14), label: "上传企业资料" }, { icon: I.users(14), label: "指派同事" }, { icon: I.pen(14), label: "开始撰写" }],
      placeholder: "例如「把去年聊城项目的合同和进账凭证归档为业绩证据」…",
    });

  const tb = toolbar({
    label: "投标文件骨架",
    sub: `G2 备料 · 证据库命中 <b>14</b> · <span class="is-warn">缺料 6</span> · 已认领 2 · 影响实质性 <span class="is-fatal">2</span>`,
    right: `<button class="btn">${I.stack(14)}缺料清单<span class="n">6</span></button><button class="btn is-primary" disabled>${I.pen(14)}开始撰写</button>`,
  });

  const need = (no, title, sub, status, tone, chips, actions, first) => `
    <div class="row${first ? " is-first" : ""}">
      <span class="row-no">${no}</span>
      <div class="row-main">
        <div class="row-t">${title}<span class="mark ${tone}" style="margin-left:auto">${status}</span></div>
        <div class="row-d">${sub}</div>
        <div class="row-f">${chips}${actions}</div>
      </div>
    </div>`;
  const chip = (t, blue) => `<span class="chip${blue ? " is-blue" : ""}">${blue ? I.check(11) : I.file(11)}${t}</span>`;
  const acts = (...a) => a.map((x, i) => `<span class="act${i === 0 ? " is-primary" : ""}">${x}</span>`).join("");

  const drawer = `<div class="cv-drawer"><div class="cv-drawer-scrim"></div>
    <div class="cv-drawer-main">
      <div class="cv-drawer-head">${I.stack(16)}
        <div class="cv-drawer-titlebox"><div class="cv-drawer-title">缺料清单</div><div class="cv-drawer-sub">按章节推导「写这节需要什么」，与机构证据库比对 · 强制项与高分值项证据不得为空</div></div>
        <button class="cv-drawer-close">${I.x(15)}</button>
      </div>
      <div class="cv-drawer-body">
        <div class="seg"><span class="is-active">缺料<span class="s-n">6</span></span><span>已命中<span class="s-n">14</span></span><span>已认领<span class="s-n">2</span></span><span>不适用<span class="s-n">1</span></span></div>

        <div class="gh is-fatal">${I.prohibit(13)}<b>影响实质性响应</b><span class="n">2 项 · 缺失即无效投标</span></div>
        ${need("1", "近 3 年审计报告（含四表一注）", "资格性审查第 8 项。证据库命中 2023 / 2024 年度，缺 <b>2025 年度</b>（投标截止 9 月 4 日在 6 月 1 日后，近 3 年按含上年度计）。", "缺 1 / 3", "is-risk", chip("2023 审计报告", true) + chip("2024 审计报告", true), acts("上传", "指派财务", "标记不适用"), true)}
        ${need("2", "拟派项目负责人：信息系统项目管理师证书 + 近 3 个月社保", "附表 4 技术力量 5（1 分）且资格审查要求正式员工。证据库有 3 名持证人员，但近 3 个月社保凭证均未归档。", "缺社保凭证", "is-risk", chip("王工 · 高级项目管理师", true) + chip("李工 · 系统集成项目管理师", true), acts("指派人事", "上传"))}

        <div class="gh is-warn">${I.warning(13)}<b>影响得分</b><span class="n">3 项 · 合计 6 分</span></div>
        ${need("3", "同类项目合同（近 3 年，≥ 270 万元，最多 5 份）+ 30% 进账凭证", "附表 3 业绩 1（4 分）：每提供一份 270 万元以上合同得 20%。证据库命中 2 份合格合同，再补 3 份可得满分。", "命中 2 / 5", "is-warn", chip("2024 · 聊城数据中台 · 318 万", true) + chip("2023 · 某部队信息系统 · 296 万", true), acts("上传合同", "指派销售", "接受 2 份"), true)}
        ${need("4", "ISO27001 信息安全管理体系认证证书", "附表 4 技术力量 2（1 分）。证据库中的证书有效期至 2026-03-31，<b>已过期</b>；再认证证书若已取得请上传。", "已过期", "is-warn", chip("ISO27001 · 2023–2026", false), acts("上传新证", "标记不适用"))}
        ${need("5", "GJB5000 软件能力成熟度认证", "附表 4 技术力量 4（1 分）：五级得满分、四级 60%、三级 30%。证据库无记录。", "无记录", "is-warn", "", acts("上传", "标记不适用"))}

        <div class="gh">${I.list(13)}<b>影响可信度</b><span class="n">1 项</span></div>
        ${need("6", "保密资质与保密承诺书模板", "第六章商务要求第 4 条（★）要求签署保密承诺；模板可由智能体按合同样本第三章生成，签章页需人工。", "可生成", "is-ok", "", acts("生成模板", "上传已有"), true)}
      </div>
      <div class="cv-drawer-foot"><span class="note">认领后进入证据请求队列；上传即入机构证据库，下一次投标自动命中。</span><button class="btn is-primary">${I.check(14)}认领完毕，开始撰写</button></div>
    </div></div>`;

  return page({
    body: workspace({ modeHole: true, tb, world, floats, overlay: drawer }),
    props: MODE_PROPS,
    script: MODE_SCRIPT,
  });
}
