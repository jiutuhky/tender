// G4 合规：终检清单（确定性检查器 · 逐条销项 · 零 error 解锁导出）
import { I, page, workspace, toolbar, dockedMatrixCards, msgwinMin, dock, MODE_PROPS } from "../lib/parts.mjs";
import { skeleton } from "../lib/outline.mjs";

const CHECKS = [
  { g: "veto", id: "v1", title: "投标文件其他部分不得出现报价信息", desc: "3.4 集成与实施方案 第 6 段检测到「报价 268 万元」字样（规则 R-07，对应特别提示第十条）。", where: "3.4 · 第 6 段", level: "error" },
  { g: "veto", id: "v2", title: "带 ★ 条款全部实质性响应", desc: "41 条 ★ 条款（商务 12 · 技术 29）均有章节响应且应答状态为「完全响应」；正偏离 6 项均已附证明材料。", where: "5.1 / 2.2", level: "ok" },
  { g: "veto", id: "v3", title: "投标有效期 ≥ 90 日", desc: "投标函载明 90 日，与前附表第 7 项一致。", where: "2.1", level: "ok" },
  { g: "fmt", id: "f1", title: "法定代表人签字页缺失", desc: "投标函、授权书、承诺声明三处要求签字，当前 docx 投影中授权书无签字占位（规则 F-03）。", where: "1.5 · 签署位", level: "error" },
  { g: "fmt", id: "f2", title: "正文字号与行距", desc: "3.6 试验验证方案中的用例表字号 9pt，低于企业模板要求的 10.5pt（规则 F-11）。", where: "3.6 · 表 3-4", level: "warn" },
  { g: "fmt", id: "f3", title: "编号唯一与目录一致", desc: "8 章 34 节编号唯一；目录域将在导出时重建。", where: "全册", level: "ok" },
  { g: "price", id: "p1", title: "分项合计 ≠ 投标总价", desc: "分项报价表合计 2,679,600.00 元，开标一览表总价 2,680,000.00 元，差 400.00 元（规则 P-02，纯算术）。", where: "8.1 / 8.2", level: "error" },
  { g: "price", id: "p2", title: "大小写金额一致", desc: "贰佰陆拾捌万元整 = 2,680,000.00 元。", where: "8.1", level: "ok" },
  { g: "price", id: "p3", title: "报价不超预算 270 万元", desc: "总价 268 万元，低于预算；单价 × 数量 = 合价 逐行通过（37 行）。", where: "8.2", level: "ok" },
  { g: "cover", id: "c1", title: "覆盖闭合复检", desc: "成文后重跑：强制项 44/44、评分项 30/30、必备格式 13/13 均有章节承接。", where: "全册", level: "ok" },
  { g: "cover", id: "c2", title: "断言有据", desc: "事实性断言 211 处，无锚记 0 处；豁免留痕 2 处（已由 LH 批准）。", where: "全册", level: "ok" },
  { g: "cover", id: "c3", title: "交叉一致性", desc: "同一资产在不同章节的表述：质保期在 2.6 写「36 个月」、7.2 写「3 年」，口径不一致但等价（规则 X-04）。", where: "2.6 / 7.2", level: "warn" },
];

export function Compliance() {
  const world =
    dockedMatrixCards({ dim: true }) +
    skeleton({
      states: Object.fromEntries(["1.1","1.2","1.3","1.4","1.5","1.6","1.7","1.8","2.1","2.2","2.3","2.4","2.5","2.6","3.1","3.2","3.3","3.4","3.5","3.6","4.1","4.2","4.3","5.1","5.2","5.3","6.1","6.2","6.3","7.1","7.2","7.3","8.1","8.2","8.3","8.4"].map((k) => [k, "done"])),
      badges: { c1: [{ kind: "comply", n: 1, fatal: true }], c3: [{ kind: "comply", n: 1, fatal: true }], c8: [{ kind: "comply", n: 1, fatal: true }] },
      rowNotes: { "1.5": { text: "缺签字页", tone: "fatal" }, "3.4": { text: "含报价", tone: "fatal" }, "8.2": { text: "合计不符", tone: "fatal" }, "3.6": { text: "字号", tone: "warn" }, "7.2": { text: "口径", tone: "warn" } },
      faceState: { c3: `<span class="is-ok">已验收 <b>6</b></span><span class="is-note">2,400 字 × 6</span>` },
    });

  const floats =
    msgwinMin({ ticker: "终检 14 项：<b>error 3</b> · warning 2 · 零 error 解锁导出" }) +
    dock({ chips: [{ icon: I.shield(14), label: "重跑终检" }, { icon: I.table(14), label: "生成偏离表" }, { icon: I.download(14), label: "导出成册" }], placeholder: "例如「把 3.4 里的报价字样改成『详见价格文件』」…" });

  const tb = toolbar({
    label: "投标文件骨架",
    sub: `G4 合规 · 检查 <b>14</b> 项 · <span class="is-fatal">error {{errN}}</span> · <span class="is-warn">warning {{warnN}}</span> · 偏离表已生成`,
    right: `<button class="btn">${I.shield(14)}终检清单<span class="n">{{openN}}</span></button><button class="btn is-primary" disabled="{{locked}}">${I.download(14)}导出成册</button>`,
  });

  const group = (key, icon, title, sub) => `
    <div class="gh">${icon}<b>${title}</b><span class="n">${sub}</span></div>
    <sc-for list="{{${key}}}" as="it" hint-placeholder-count="3">
      <div class="row {{it.cls}}">
        <span class="row-no"><span class="dot {{it.dot}}"></span></span>
        <div class="row-main">
          <div class="row-t">{{it.title}}<span class="chip" style="margin-left:auto">{{it.where}}</span></div>
          <div class="row-d" style="-webkit-line-clamp:3">{{it.desc}}</div>
          <sc-if value="{{it.open}}" hint-placeholder-val="{{true}}"><div class="row-f"><span class="act is-primary" onClick="{{it.fix}}">{{it.fixLabel}}</span><span class="act">打开原文</span><span class="act is-ghost">豁免并留痕</span></div></sc-if>
          <sc-if value="{{it.fixed}}" hint-placeholder-val="{{false}}"><div class="row-f"><span class="mark is-ok">已销项 · 复检通过</span><span class="act is-ghost" onClick="{{it.fix}}">撤销</span></div></sc-if>
        </div>
      </div>
    </sc-for>`;

  const drawer = `<div class="cv-drawer"><div class="cv-drawer-scrim"></div>
    <div class="cv-drawer-main">
      <div class="cv-drawer-head">${I.shield(16)}
        <div class="cv-drawer-titlebox"><div class="cv-drawer-title">终检清单</div><div class="cv-drawer-sub">全部由确定性检查器完成，不用模型打分 · 零 error 才能导出</div></div>
        <button class="cv-drawer-close">${I.x(15)}</button>
      </div>
      <div class="cv-drawer-body">
        <div class="seg"><span class="is-active">待销项<span class="s-n">{{openN}}</span></span><span>已通过<span class="s-n">{{okN}}</span></span><span>已豁免<span class="s-n">2</span></span></div>
        ${group("veto", I.prohibit(13), "废标项逐条核", "9 条否决项 · 来自评分办法与特别提示")}
        ${group("price", I.calc(13), "报价一致性", "纯算术 · 机器包办")}
        ${group("fmt", I.ruler(13), "格式规则", "企业模板 v3 · 招标文件格式要求")}
        ${group("cover", I.link(13), "覆盖 · 有据 · 一致性复检", "成文后链接是否仍闭合")}
      </div>
      <div class="cv-drawer-foot"><span class="note">{{footNote}}</span><button class="btn is-primary" disabled="{{locked}}">${I.download(14)}进入导出</button></div>
    </div></div>`;

  const body = workspace({ modeHole: true, tb, world, floats, overlay: drawer });
  const script = `class Component extends DCLogic {
  constructor(p) { super(p); this.state = { fixed: {} }; }
  renderVals() {
    const fixed = this.state.fixed;
    const all = ${JSON.stringify(CHECKS)}.map((c) => {
      const isFixed = !!fixed[c.id];
      const open = c.level !== 'ok' && !isFixed;
      return { ...c, open, fixed: isFixed, cls: open ? '' : 'is-ok',
        dot: open ? (c.level === 'error' ? 'r' : 'o') : 'g',
        fixLabel: c.level === 'error' ? '已修复，复检' : '已调整，复检',
        fix: () => this.setState({ fixed: { ...fixed, [c.id]: !isFixed } }) };
    });
    const by = (g) => all.filter((c) => c.g === g);
    const errN = all.filter((c) => c.level === 'error' && !c.fixed).length;
    const warnN = all.filter((c) => c.level === 'warn' && !c.fixed).length;
    const openN = errN + warnN;
    const okN = all.length - openN;
    return { mode: this.props.mode ?? 'light', veto: by('veto'), price: by('price'), fmt: by('fmt'), cover: by('cover'),
      errN, warnN, openN, okN, locked: errN > 0,
      footNote: errN > 0 ? ('还有 ' + errN + ' 个 error 未销项；warning 不阻塞导出但会写入终检报告。') : 'error 已清零，可进入导出；本次终检报告随终稿一并归档。' };
  }
}`;
  return page({ body, props: MODE_PROPS, script });
}
