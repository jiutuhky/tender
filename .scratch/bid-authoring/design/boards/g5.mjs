// G5 成册：装订导出（确定性排版管线 · 终稿签发）
import { I, page, workspace, toolbar, dockedMatrixCards, msgwinMin, dock, MODE_PROPS, MODE_SCRIPT } from "../lib/parts.mjs";
import { skeleton } from "../lib/outline.mjs";

export function Export() {
  const allDone = Object.fromEntries(["1.1","1.2","1.3","1.4","1.5","1.6","1.7","1.8","2.1","2.2","2.3","2.4","2.5","2.6","3.1","3.2","3.3","3.4","3.5","3.6","4.1","4.2","4.3","5.1","5.2","5.3","6.1","6.2","6.3","7.1","7.2","7.3","8.1","8.2","8.3","8.4"].map((k) => [k, "done"]));
  const world = dockedMatrixCards({ dim: true }) + skeleton({ states: allDone });
  const floats =
    msgwinMin({ ticker: "终检零 error · 三册已排版，等待签发" }) +
    dock({ chips: [{ icon: I.eye(14), label: "预览成稿" }, { icon: I.history(14), label: "版本对比" }], placeholder: "例如「副本改成 5 份，封面加项目编号」…" });
  const tb = toolbar({
    label: "投标文件骨架",
    sub: `G5 成册 · 三册 · 正本 1 副本 3 · 企业模板 v3 · 排版规则 <b>18/18</b> 通过`,
    right: `<button class="btn">${I.eye(14)}预览</button><button class="btn is-primary">${I.download(14)}签发终稿</button>`,
  });

  const vol = (tag, name, pages, size, items) => `
    <div class="row" style="align-items:center">
      <span class="row-no" style="padding-top:0">${I.doc(16)}</span>
      <div class="row-main"><div class="row-t">${tag} · ${name}<span style="margin-left:auto;font-weight:500;color:var(--label-3);font-size:11.5px">${pages} 页 · ${size}</span></div>
      <div class="row-d" style="-webkit-line-clamp:1">${items}</div></div>
    </div>`;
  const chk = (t, on = true) => `<div class="check"><i class="${on ? "on" : ""}">${on ? I.check(11) : ""}</i>${t}</div>`;

  const modal = `<div class="cv-drawer" style="justify-content:center;align-items:center"><div class="cv-drawer-scrim"></div>
    <div class="sheet-modal" style="position:relative;left:auto;top:auto;transform:none">
      <div class="cv-drawer-head">${I.print(16)}
        <div class="cv-drawer-titlebox"><div class="cv-drawer-title">装订导出</div><div class="cv-drawer-sub">md → pandoc（企业模板）→ python-docx 后处理 → 分册打包 · 模型不参与排版</div></div>
        <button class="cv-drawer-close">${I.x(15)}</button>
      </div>
      <div style="display:grid;grid-template-columns:1fr 292px;min-height:0">
        <div style="padding:14px 20px 18px;box-shadow:inset -.5px 0 0 var(--separator)">
          <div class="gh" style="padding-top:4px">${I.files(13)}<b>分册</b><span class="n">按第三章「投标文件内容及格式」</span><span class="r">合计 214 页</span></div>
          ${vol("册一", "资格证明文件", 38, "6.1 MB", "8 节 · 证照扫描件 14 份 · 签署位 3 处")}
          ${vol("册二", "商务技术文件", 152, "18.4 MB", "6 章 23 节 · 图 11 · 表 27 · 偏离表投影 1 · 证据附件 21")}
          ${vol("册三", "价格文件", 24, "1.2 MB", "开标一览表 · 分项报价表（37 行）· 易损易耗件清单")}
          <div class="gh">${I.ruler(13)}<b>排版规则</b><span class="n">18 项全部通过</span></div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px 18px;padding:4px 0">
            ${chk("目录域代码重建")}${chk("页眉页脚 · 项目名称与编号")}${chk("页码按册分节起始")}${chk("封面 · 正 / 副本标识")}${chk("签章占位 · 3 处")}${chk("骑缝章提示页")}${chk("跨页表头重复")}${chk("图表编号连续")}${chk("字体 · 宋体 / 黑体 / Times")}${chk("锚记转脚注 · 211 处")}
          </div>
          <div style="margin-top:14px;padding:10px 12px;border-radius:var(--r-window);background:var(--surface-2);font-size:12px;line-height:1.7;color:var(--label-2);display:flex;gap:9px">${I.lock(14)}<span><b style="color:var(--label)">边界说明</b>：本平台交付规范 docx / pdf。CA 电子签章与加密由军队采购网投标客户端完成，请在导入客户端后签章、加密并取得投标回执。</span></div>
        </div>
        <div style="padding:14px 18px 18px;display:flex;flex-direction:column;gap:14px">
          <div class="field"><label>企业模板</label><div class="select">${I.doc(13)}投标文件模板 v3（2026-06）${I.chevron(12)}</div></div>
          <div class="field"><label>正本 / 副本</label><div style="display:flex;gap:10px"><div class="stepper"><i>${I.minus(12)}</i><span>正 1</span><i>${I.plus(12)}</i></div><div class="stepper"><i>${I.minus(12)}</i><span>副 3</span><i>${I.plus(12)}</i></div></div></div>
          <div class="field"><label>输出</label>${chk("docx（可导入投标客户端）")}${chk("pdf（含书签）")}${chk("分项报价 xlsx（含公式）", true)}${chk("过程包：终检报告 + 审计链", true)}</div>
          <div class="field"><label>签发</label><div style="font-size:12px;line-height:1.7;color:var(--label-2)">签发即固定为版本 <span style="font-family:var(--mono);font-size:11px">final-r7</span> 并保存工作区检查点；此后修改走「新版本」。</div></div>
          <div style="margin-top:auto;display:flex;flex-direction:column;gap:8px">
            <button class="btn is-primary" style="height:36px">${I.download(14)}签发终稿并导出</button>
            <button class="btn">${I.eye(14)}先预览册二</button>
          </div>
        </div>
      </div>
    </div></div>`;

  return page({ body: workspace({ modeHole: true, tb, world, floats, overlay: modal }), props: MODE_PROPS, script: MODE_SCRIPT });
}
