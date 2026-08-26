// G3 成文：并行生成主视图（Writing）+ 写作台（Desk，与溯源预览层同构）
import { I, page, workspace, toolbar, dockedMatrixCards, msgwinMin, agentBoard, dock, MODE_PROPS, MODE_SCRIPT } from "../lib/parts.mjs";
import { skeleton } from "../lib/outline.mjs";

export function Writing() {
  const world =
    dockedMatrixCards({ dim: true }) +
    // 本批 12 节 = 3.1–3.6、5.1–5.3、6.1–6.3：进行中 4 · 待验收 2 · 已验收 3 · 排队 2 · 等你回答 1
    skeleton({
      selected: "c3",
      states: {
        "3.1": "done", "3.2": "running", "3.3": "review", "3.4": "running", "3.5": "wait", "3.6": "running",
        "5.1": "review", "5.2": "running", "5.3": "queued",
        "6.1": "done", "6.2": "done", "6.3": "queued",
      },
      badges: { c3: [{ kind: "cite", n: 2 }] },
      faceState: { c3: `<span class="is-run">进行中 <b>3</b></span><span class="is-note">待验收 1 · 等你回答 1</span>` },
    });

  const floats =
    msgwinMin({ busy: true, ticker: "12 节 · <b>4</b> 进行中 · 2 待验收 · <b>1</b> 等你回答" }) +
    agentBoard({
      rows: [
        { hue: 212, desc: "3.2 系统架构设计", state: "running", sum: "正在引用 E:C-2024-0318 · 已写 1,640 / 2,400 字" },
        { hue: 350, desc: "3.4 集成与实施方案", state: "running", sum: "正在读取 6.1 进度计划以对齐里程碑" },
        { hue: 128, desc: "3.6 试验验证方案", state: "running", sum: "正在生成测试用例表（14 行）" },
        { hue: 46, desc: "5.2 一般指标偏离表", state: "running", sum: "投影矩阵应答状态 · 正偏离 6 / 负偏离 0" },
        { hue: 275, desc: "3.5 安全保密方案", state: "wait", sum: "需要确认：是否承诺三级等保测评？" },
        { hue: 20, desc: "3.3 功能与接口设计", state: "done", sum: "已提交验收 · 2,610 字 · 断言 9 处全部有锚记" },
      ],
    }) +
    dock({
      actbar: "正在撰写 <b>3.2 系统架构设计</b> · 4 路并行 · 断言有据 37/39",
      placeholder: "例如「3.5 按三级等保承诺写，测评费用计入报价」…",
    });

  const tb = toolbar({
    label: "投标文件骨架",
    sub: `G3 成文 · 12 节并行 · 进行中 <b>4</b> · 待验收 <b>2</b> · 已验收 <b>3</b> · 排队 2 · <span class="is-warn">等你回答 1</span>`,
    right: `<button class="btn">${I.table(14)}验收矩阵</button><button class="btn">${I.stop(14)}暂停全部</button>`,
  });

  return page({
    body: workspace({ modeHole: true, tb, world, floats }),
    props: MODE_PROPS,
    script: MODE_SCRIPT,
  });
}

/* ---------- 写作台：左正文纸面 / 右写作简报；就地协商 ---------- */
export function Desk() {
  const tabs = [
    { key: "req", label: "要求原文", n: 4 },
    { key: "score", label: "评分规则", n: 2 },
    { key: "ev", label: "可用证据", n: 3 },
    { key: "chk", label: "锚记检查", n: 2 },
  ];
  const tabHtml = `<div class="seg" style="width:100%"><sc-for list="{{tabs}}" as="t" hint-placeholder-count="4"><button class="{{t.cls}}" onClick="{{t.pick}}">{{t.label}}<span class="s-n">{{t.n}}</span></button></sc-for></div>`;

  const req = `
    <div class="gh">${I.list(13)}<b>本节响应的要求</b><span class="n">技术矩阵 T-01 / T-02 / T-04 · 商务 B-07</span></div>
    <div class="row is-first"><span class="row-no">T-01</span><div class="row-main"><div class="row-t"><span class="star">★</span>数据归集引接软件要求</div><div class="row-d">支持对采购单位现有的安全风险评估系统、业务信息系统、计划规划系统等进行数据接入适配；支持结构化、半结构化与非结构化数据源；接入延迟不高于 5 分钟。</div><div class="row-f"><span class="chip is-blue">${I.file(11)}L1268–1275 · 技术要求</span><span class="mark is-ok">已响应</span></div></div></div>
    <div class="row"><span class="row-no">T-02</span><div class="row-main"><div class="row-t"><span class="star">★</span>数据融合应用软件要求</div><div class="row-d">支持跨源异构数据的智能关联分析与知识挖掘；人员信息、专用平台、物资储备三类主题统一建模。</div><div class="row-f"><span class="chip">${I.file(11)}L1290–1301</span><span class="mark is-ok">已响应</span></div></div></div>
    <div class="row"><span class="row-no">T-04</span><div class="row-main"><div class="row-t">综合告警分析</div><div class="row-d">对人员、专用平台的各类异常进行告警，支持告警等级划分；对专项练习完成度、参训率等异常告警。</div><div class="row-f"><span class="chip">${I.file(11)}L1304–1309</span><span class="mark is-warn">部分响应 · 告警等级未写</span></div></div></div>
    <div class="row"><span class="row-no">B-07</span><div class="row-main"><div class="row-t">交付地点：山东省聊城市东昌府区</div><div class="row-d">架构部署拓扑须体现部署地点与网络边界。</div><div class="row-f"><span class="chip">${I.file(11)}L1262 · 商务要求</span><span class="mark is-ok">已响应</span></div></div></div>`;

  const score = `
    <div class="gh">${I.chart(13)}<b>评分规则 · 评委据此打分</b><span class="n">附表 4 · 技术方案 2、3</span><span class="r">合计 6 分 · 主观</span></div>
    <div class="row is-first"><span class="row-no">2</span><div class="row-main"><div class="row-t">系统架构设计的合理性、针对性<span style="margin-left:auto;font-weight:600">3.00</span></div><div class="row-d">最优的得标准分值，其余依次按标准分值的 5% 递减，最低分为 0 分。注：技术方案应对采购文件技术要求全面响应。</div><div class="row-f"><span class="chip">${I.file(11)}L1113 · 附表 4</span><span class="chip">${I.users(11)}评委找什么：分层架构图 · 与第六章逐条对应</span></div></div></div>
    <div class="row"><span class="row-no">3</span><div class="row-main"><div class="row-t">系统功能描述全面、准确，接口设计合理<span style="margin-left:auto;font-weight:600">3.00</span></div><div class="row-d">同上递减规则。本节只需给出接口总体设计，功能逐项描述在 3.3 承接。</div><div class="row-f"><span class="chip">${I.file(11)}L1113 · 附表 4</span><span class="chip">${I.link(11)}3.3 功能与接口设计</span></div></div></div>
    <div class="gh">${I.gear(13)}<b>篇幅与口径</b></div>
    <dl class="kv" style="padding:6px 0"><dt>篇幅预算</dt><dd>2,400 字 · 1 张架构图 · 1 张部署表</dd><dt>公司称谓</dt><dd>「我公司」；全称仅首次出现</dd><dt>项目简称</dt><dd>数据资源池项目</dd><dt>技术路线</dt><dd>湖仓一体 · 微服务 · 国产化适配（统一口径 v2）</dd><dt>禁写</dt><dd>任何报价信息（终检规则 R-07）</dd></dl>`;

  const ev = `
    <div class="gh">${I.stack(13)}<b>可用证据</b><span class="n">按证据分级：案例 › 数据 › 证言</span></div>
    <div class="row is-first"><span class="row-no">E:C</span><div class="row-main"><div class="row-t">聊城数据中台项目（2024）· 案例</div><div class="row-d">同类项目，12 类数据源接入，日均归集 1.8 亿条；验收报告与合同已归档。</div><div class="row-f"><span class="chip is-blue">${I.check(11)}E:C-2024-0318 · 本节已引 2 处</span><span class="chip">${I.link(11)}被 2.3 / 3.4 引用</span></div></div></div>
    <div class="row"><span class="row-no">E:D</span><div class="row-main"><div class="row-t">数据接入性能测试报告 · 数据</div><div class="row-d">第三方检测：平均接入延迟 47 秒（要求 ≤ 5 分钟）。</div><div class="row-f"><span class="chip is-blue">${I.check(11)}E:D-2025-0092 · 已引 1 处</span></div></div></div>
    <div class="row"><span class="row-no">E:Q</span><div class="row-main"><div class="row-t">ISO27001 证书 · 资质</div><div class="row-d">有效期至 2026-03-31，<b>已过期</b>，G2 缺料清单待认领。</div><div class="row-f"><span class="chip">${I.warning(11)}不可引用 · 等待新证</span></div></div></div>
    <div style="margin-top:14px;font-size:11.5px;color:var(--label-3)">证据范围：本项目上传资料 · 机构证据库 <span class="chip" style="margin-left:4px">公网 · 关</span></div>`;

  const chk = `
    <div class="gh is-warn">${I.quote(13)}<b>断言无锚记</b><span class="n">2 处 · 事实性断言必须指向证据</span></div>
    <div class="row is-first"><span class="row-no">1</span><div class="row-main"><div class="row-t">「累计服务军队单位 17 家」</div><div class="row-d">第 2 段。业绩类断言，证据库无「客户数量」记录。可改为引用具体合同，或删除数量。</div><div class="row-f"><span class="act is-primary">改为引用 E:C</span><span class="act">删除数量</span><span class="act is-ghost">忽略并留痕</span></div></div></div>
    <div class="row"><span class="row-no">2</span><div class="row-main"><div class="row-t">「7×24 小时运维响应，30 分钟到场」</div><div class="row-d">第 5 段。承诺类语句，须与 7.3 维修响应承诺口径一致（当前 7.3 尚未成文）。</div><div class="row-f"><span class="act is-primary">与 7.3 对齐</span><span class="act">改为 2 小时</span></div></div></div>
    <div class="gh">${I.check(13)}<b>已通过</b><span class="n">断言 9 / 11 · 口径 6 / 6 · 禁写词 0</span></div>`;

  const body = `<div class="wrap" data-appearance="{{mode}}">
    <div class="stage">
      <div class="stage-head">
        <button class="cv-drawer-close" style="width:28px;height:28px">${I.chevR(14).replace('<svg', '<svg style="transform:rotate(180deg)"')}</button>
        <div class="cv-drawer-titlebox"><div class="cv-drawer-title">3.2 系统架构设计 <span style="font-weight:500;color:var(--label-3);font-size:12px;margin-left:6px">v3 · 正在撰写 · 1,640 / 2,400 字</span></div><div class="cv-drawer-sub">技术方案 · 3 分 · 响应 T-01 / T-02 / T-04 · 证据 3 · 断言有据 9 / 11</div></div>
        <div class="seg"><span class="is-active">正文</span><span>执行记录</span><span>版本<span class="s-n">3</span></span></div>
        <button class="btn">${I.history(14)}打回重写</button>
        <button class="btn is-primary">${I.check(14)}验收本节</button>
      </div>
      <div class="stage-body">
        <div class="paper-stage">
          <div class="sheet">
            <h2>3.2 系统架构设计</h2>
            <p style="font-size:12px;color:var(--label-3);margin-bottom:18px">响应第六章技术要求第 1、2、4 条 · 对应评分项「系统架构设计的合理性、针对性」</p>
            <h3>3.2.1 总体架构</h3>
            <p>针对数据资源池项目「多源异构接入、跨源关联分析、统一权限管控」三项核心诉求，我公司采用<b>湖仓一体 + 微服务</b>的分层架构：自下而上分为数据接入层、数据湖仓层、融合分析层、应用服务层与统一门户层，各层之间通过标准化服务接口解耦，满足第六章第 1 条对结构化、半结构化与非结构化数据源统一接入的要求<span class="anchor">${I.quote(10)}T-01</span>。</p>
            <p>该架构已在聊城数据中台项目中完整落地，接入 12 类业务系统，日均归集 1.8 亿条记录<span class="anchor">${I.quote(10)}E:C-2024-0318</span>；第三方检测的平均接入延迟为 47 秒，优于本项目「不高于 5 分钟」的指标<span class="anchor">${I.quote(10)}E:D-2025-0092</span>。我公司累计服务军队单位 17 家<span class="anchor is-missing">${I.warning(10)}无锚记</span>，具备同类项目实施经验。</p>
            <h3>3.2.2 数据接入层</h3>
            <p><span class="sel">接入适配模块面向采购单位现有的安全风险评估系统、业务信息系统、计划规划系统提供数据库直连、文件交换、消息订阅与接口调用四类适配器，并支持按单位、按数据类型配置接入策略与调度周期。</span>对于不具备开放接口的遗留系统，提供基于日志解析的增量抽取能力，保证接入过程对源系统零侵入。</p>
            <table><tr><th>层级</th><th>核心组件</th><th>响应要求</th><th>部署位置</th></tr>
              <tr><td>数据接入层</td><td>多源适配器 · 调度中心 · 质量探针</td><td>T-01 ①②③</td><td>东昌府区机房 · 接入区</td></tr>
              <tr><td>数据湖仓层</td><td>对象存储 · 分布式数仓 · 元数据目录</td><td>T-01 ④ · T-02 ①</td><td>核心区</td></tr>
              <tr><td>融合分析层</td><td>关联分析引擎 · 规则告警 · 知识图谱</td><td>T-02 ②③ · T-04</td><td>核心区</td></tr></table>
            <h3>3.2.3 融合分析层</h3>
            <p>围绕人员信息、专用平台、物资储备三类主题构建统一主题模型，支持跨源异构数据的关联分析与隐式关系挖掘<span class="anchor">${I.quote(10)}T-02</span>。综合告警引擎对人员与专用平台的异常进行分级告警，并对专项练习完成度、参训率、练习评分等异常自动生成待办 …</p>
          </div>
        </div>
        <div class="brief">
          <div style="padding:14px 18px 0">${tabHtml}</div>
          <div class="brief-body">
            <sc-if value="{{isReq}}" hint-placeholder-val="{{true}}">${req}</sc-if>
            <sc-if value="{{isScore}}" hint-placeholder-val="{{false}}">${score}</sc-if>
            <sc-if value="{{isEv}}" hint-placeholder-val="{{false}}">${ev}</sc-if>
            <sc-if value="{{isChk}}" hint-placeholder-val="{{false}}">${chk}</sc-if>
          </div>
        </div>
      </div>
      <div class="pop glass" style="left:420px;top:516px">
        <div class="pop-row">${I.sparkle(14)}让智能体改这段</div>
        <div class="pop-row">${I.quote(14)}为这段补证据锚记</div>
        <div class="pop-row">${I.comment(14)}留批注，不打断撰写</div>
        <div class="pop-input">${I.pen(13)}这段换成强调接入零侵入与延迟指标…<span style="margin-left:auto;color:var(--label-3);display:inline-flex">${I.chevR(12)}</span></div>
      </div>
    </div>
  </div>`;

  const script = `class Component extends DCLogic {
  constructor(p) { super(p); this.state = { tab: 'req' }; }
  renderVals() {
    const cur = this.state.tab;
    const tabs = ${JSON.stringify(tabs)}.map((t) => ({ ...t, cls: t.key === cur ? 'is-active' : '', pick: () => this.setState({ tab: t.key }) }));
    return { mode: this.props.mode ?? 'light', tabs, isReq: cur === 'req', isScore: cur === 'score', isEv: cur === 'ev', isChk: cur === 'chk' };
  }
}`;
  return page({ body, props: MODE_PROPS, script });
}
