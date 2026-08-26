// 总览：五道闸门流程图（Flow）、架构与契约（Architecture）
import { I, page } from "../lib/parts.mjs";

const CSS = `
    .ov { position: absolute; inset: 0; background: var(--canvas); padding: 40px 48px; overflow: hidden; }
    .ov h1 { font-size: 22px; font-weight: 600; letter-spacing: -.018em; margin: 0 0 4px; }
    .ov .lead { font-size: 13px; color: var(--label-2); margin: 0 0 26px; max-width: 900px; line-height: 1.7; }
    .gates { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 14px; }
    .gate { background: var(--surface); border-radius: var(--r-card); box-shadow: var(--elev-1); padding: 14px 15px 15px; display: flex; flex-direction: column; gap: 10px; min-height: 0; }
    .gate.is-done { opacity: .78; }
    .gate-h { display: flex; align-items: baseline; gap: 8px; }
    .gate-h .g { font-size: 11px; font-weight: 700; color: var(--label-3); letter-spacing: .06em; }
    .gate-h b { font-size: 15px; font-weight: 700; letter-spacing: -.01em; }
    .gate-h .st { margin-left: auto; font-size: 10.5px; font-weight: 600; color: var(--green-text); }
    .gate-h .st.todo { color: var(--label-3); }
    .gate-k { font-size: 10.5px; font-weight: 600; color: var(--label-3); letter-spacing: .04em; margin-top: 2px; }
    .gate-v { font-size: 12px; line-height: 1.65; color: var(--label-2); }
    .gate-v b { color: var(--label); font-weight: 600; }
    .gate-gate { display: flex; align-items: flex-start; gap: 6px; font-size: 12px; line-height: 1.6; color: var(--label); font-weight: 600; padding-top: 8px; border-top: 1px solid var(--separator); }
    .gate-gate svg { flex: 0 0 auto; color: var(--red-text); margin-top: 3px; }
    .gate-stage { display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: var(--label-3); }
    .gate-stage svg { color: var(--label-3); }
    .rhythm { margin-top: 26px; background: var(--surface); border-radius: var(--r-card); box-shadow: var(--elev-1); padding: 16px 20px 18px; }
    .rhythm-h { display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; }
    .rhythm-h b { font-size: 13px; font-weight: 700; }
    .rhythm-h span { font-size: 12px; color: var(--label-3); }
    .rules { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px 22px; margin-top: 14px; }
    .rule { display: flex; gap: 9px; font-size: 12px; line-height: 1.65; color: var(--label-2); }
    .rule svg { flex: 0 0 auto; color: var(--label-3); margin-top: 3px; }
    .rule b { color: var(--label); font-weight: 600; display: block; }
    .rule i { font-style: normal; color: var(--label-3); font-size: 11px; }

    .arch { position: absolute; inset: 0; background: var(--canvas); overflow: hidden; }
    .box { position: absolute; background: var(--surface); border-radius: var(--r-card); box-shadow: var(--elev-1); padding: 12px 14px; font-size: 12px; line-height: 1.6; color: var(--label-2); }
    .box h4 { margin: 0 0 6px; font-size: 12.5px; font-weight: 700; color: var(--label); display: flex; align-items: center; gap: 6px; }
    .box h4 svg { color: var(--label-3); }
    .box h4 .tag { margin-left: auto; font-size: 10px; font-weight: 600; color: var(--label-3); letter-spacing: .04em; }
    .box .new { color: var(--blue); font-weight: 600; }
    .box ul { margin: 0; padding-left: 0; list-style: none; display: flex; flex-direction: column; gap: 3px; }
    .box li { position: relative; padding-left: 11px; }
    .box li::before { content: ""; position: absolute; left: 0; top: 7px; width: 4px; height: 4px; border-radius: 999px; background: var(--label-3); }
    .box li i { font-style: normal; color: var(--label-3); }
    .box li.ok::before { background: var(--green); }
    .box li.new::before { background: var(--blue); }
    .zone { position: absolute; border-radius: var(--r-panel); border: 1.5px dashed color-mix(in srgb, var(--label-3) 28%, transparent); }
    .zone-l { position: absolute; font-size: 10.5px; font-weight: 700; color: var(--label-3); letter-spacing: .06em; }
    .code { font-family: var(--mono); font-size: 11px; line-height: 1.7; color: var(--label); white-space: pre; }
    .code .c { color: var(--label-3); }
    .code .k { color: var(--blue); }
    .arrows { position: absolute; inset: 0; pointer-events: none; }
    .arrows path { fill: none; stroke: color-mix(in srgb, var(--label-3) 55%, transparent); stroke-width: 1.4; }
    .arrows path.b { stroke: var(--blue); }
    .arrows text { font-size: 10.5px; font-weight: 600; fill: var(--label-3); font-family: var(--font); }
`;

export function Flow() {
  const gate = (g, name, st, agent, human, hard, stage, done) => `
    <div class="gate${done ? " is-done" : ""}">
      <div class="gate-h"><span class="g">${g}</span><b>${name}</b><span class="st${done ? "" : " todo"}">${st}</span></div>
      <div><div class="gate-k">智能体放开跑</div><div class="gate-v">${agent}</div></div>
      <div><div class="gate-k">人只确权一次</div><div class="gate-v">${human}</div></div>
      <div class="gate-gate">${I.prohibit(13)}<span>${hard}</span></div>
      <div class="gate-stage">${stage}</div>
    </div>`;

  const body = `<div class="wrap" data-appearance="light"><div class="ov">
    <h1>从「读懂招标文件」到「交出投标文件」· 五道闸门</h1>
    <p class="lead">闸门之间智能体尽量放开跑，闸门上人只做一次高杠杆确权。「写得好不好」被降解成三个可判定的问题——<b>覆盖</b>（每条要求 / 每个评分项有没有章节答它）、<b>有据</b>（每个事实断言有没有一份资产）、<b>合规</b>（格式与废标项）——三者都是有 / 无，不是好 / 坏；Prose 永远不预测得分。</p>
    <div class="gates">
      ${gate("G0", "读懂", "已完成", "四路抽取 worker 并行，把招标文件抽成 <b>四张应答矩阵</b>（概要 / 商务 / 技术 / 评分），行级溯源到原文。", "逐条确认、标注应答状态（合规 / 正偏离 / 负偏离）。", "校验 all_pass + publish", `${I.grid(13)}中心舞台 2×2 → 停靠列`, true)}
      ${gate("G1", "定策", "本原型起点", "把评分办法与投标文件格式条款<b>投影成章节树</b>：分册 → 章 → 节，逐节挂接要求与评分项，给篇幅预算与证据提示。", "<b>章节树与挂接关系</b>——全流程最高杠杆的一分钟；允许推翻重排，闭合在人改完后重跑。", "覆盖闭合：每条 ★ 与每个评分项至少挂一节；未闭合不进 G2", `${I.tree(13)}骨架成为中心舞台，矩阵降为依据`, false)}
      ${gate("G2", "备料", "", "逐节推导「写这节需要什么材料」，比对<b>机构证据库</b>，产出缺料清单；证据按案例 › 数据 › 证言分级。", "认领缺口：上传 / 指派同事 / 标记不适用并说明。", "有据可查：强制项与高分值项证据不得为空", `${I.stack(13)}缺料清单抽屉 · 卡面「有据」徽`, false)}
      ${gate("G3", "成文", "", "叶子节点 fan-out，<b>每节一个 Run 并行</b>；写作简报打包要求原文、评分规则、证据锚记、篇幅与口径卡；正文进 deliverables/。", "计划一次批准（自动 / 逐节 / 先改）；逐节验收：接受 / 打回附意见 / 手改；选中段落就地下指令。", "断言有据：事实性断言必须带锚记", `${I.pen(13)}多卡同时进行 · 写作台盖满画布`, false)}
      ${gate("G4", "合规", "", "<b>确定性检查器</b>：覆盖复检、废标项逐条核、格式规则、报价一致性（纯算术）、交叉一致性、偏离表投影。不用模型打分。", "逐条销项；warning 可豁免但留痕并进终检报告。", "零 error", `${I.shield(13)}终检清单抽屉 · 卡面「合规」徽`, false)}
      ${gate("G5", "成册", "", "确定性排版管线：md → pandoc（企业模板）→ python-docx 后处理（目录域 / 页眉页脚 / 分节页码 / 封面 / 签章占位）→ 分册打包。", "终稿签发：打 revision 标签，工作区 checkpoint。", "排版规则全部通过", `${I.print(13)}装订导出面板 · 签章加密不在边界内`, false)}
    </div>
    <div class="rhythm">
      <div class="rhythm-h"><b>检查点节奏</b><span>审批留给有代价、有歧义、有真实影响的决策；其余只播报不打断</span></div>
      <svg width="100%" height="54" viewBox="0 0 1300 54" preserveAspectRatio="none" style="display:block">
        <line x1="20" y1="27" x2="1280" y2="27" stroke="color-mix(in srgb, var(--label-3) 40%, transparent)" stroke-width="1.5"/>
        ${[0, 1, 2, 3, 4, 5].map((i) => `<g transform="translate(${20 + i * 252},27)"><circle r="7" fill="var(--surface)" stroke="var(--label)" stroke-width="1.6"/><text y="-14" text-anchor="middle" font-size="11" font-weight="700" fill="var(--label)" font-family="inherit">G${i} 确权</text></g>`).join("")}
        ${[0, 1, 2, 3, 4].map((i) => `<text x="${146 + i * 252}" y="46" text-anchor="middle" font-size="10.5" fill="var(--label-3)" font-family="inherit">${["四路抽取 · 只播报", "生成骨架 · 只播报", "比对证据库 · 只播报", "并行撰写 · 「等你回答」不阻塞其他节", "确定性检查 · 只播报"][i]}</text>`).join("")}
      </svg>
      <div class="rules">
        <div class="rule">${I.play(14)}<div><b>计划是可编辑对象，不是一段话</b>G3 开跑前一次批准整条轨迹（自动 / 逐节 / 先改），批准即命名本轮 Run。<i>Claude Code plan mode · Gemini Deep Research「Edit plan」</i></div></div>
        <div class="rule">${I.stop(14)}<div><b>随时可中断，粒度是节</b>每节一个 Run，可单独停；验收粒度 = 生成粒度 = 章节，不存在全文重写。<i>Manus 单页修复 · Cowork Dispatch 子任务</i></div></div>
        <div class="rule">${I.comment(14)}<div><b>批注不停机</b>打回意见与选中段落的指令以批注进入 Run，智能体不停机吸收；「等你回答」只挂起本节。<i>Antigravity 行内评论 · Cowork edit-in-place</i></div></div>
        <div class="rule">${I.history(14)}<div><b>一切可撤销、可回放</b>发布即版本：矩阵 revision、章节 v1…vN、工作区 git checkpoint；抽屉「执行流」页签回看本节 Run。<i>Notion 版本历史 · Manus Replay</i></div></div>
      </div>
    </div>
  </div></div>`;
  return page({ body, extraCss: CSS });
}

export function Architecture() {
  const body = `<div class="wrap" data-appearance="light"><div class="arch">
    <div style="position:absolute;left:48px;top:32px"><div style="font-size:22px;font-weight:600;letter-spacing:-.018em">架构：四域 + 三链接 · 结构入库，正文入文件</div><div style="font-size:13px;color:var(--label-2);margin-top:4px">在 ADR 0008 的管理面上扩表，不重造；章节的元数据 / 链接 / 状态进对象库，正文本体留 workspace markdown，版本交给 project git（ADR 0007）。</div></div>

    <div class="zone" style="left:48px;top:112px;width:300px;height:610px"></div><div class="zone-l" style="left:64px;top:122px">界面层 · Next.js</div>
    <div class="zone" style="left:388px;top:112px;width:560px;height:610px"></div><div class="zone-l" style="left:404px;top:122px">管理面 · hagent 结构化资产服务（唯一写入口）</div>
    <div class="zone" style="left:988px;top:112px;width:404px;height:610px"></div><div class="zone-l" style="left:1004px;top:122px">执行层 · 主智能体 + Run 租约 VM</div>

    <div class="box" style="left:64px;top:146px;width:268px"><h4>${I.grid(13)}工作台画布<span class="tag">中心舞台 / 停靠列</span></h4><ul><li class="ok">四矩阵卡（依据层）</li><li class="new">骨架：分册纵列 + 章节卡</li><li class="new">健康度徽：覆盖 · 有据 · 合规</li><li class="new">子代理看板 · 活动条（业务语言）</li></ul></div>
    <div class="box" style="left:64px;top:296px;width:268px"><h4>${I.sidebar(13)}抽屉<span class="tag">548px</span></h4><ul><li class="ok">矩阵详情 · 溯源预览</li><li class="new">裁决队列 · 缺料清单 · 终检清单</li><li class="new">章节 Run 执行流 · 版本</li></ul></div>
    <div class="box" style="left:64px;top:424px;width:268px"><h4>${I.pen(13)}写作台<span class="tag">与溯源层同构</span></h4><ul><li>左：正文纸面（锚记可点）</li><li>右：写作简报四页签</li><li>选中段落 → 就地指令 / 批注</li></ul></div>
    <div class="box" style="left:64px;top:552px;width:268px"><h4>${I.print(13)}导出面板</h4><ul><li>分册 · 正副本 · 模板 · 规则通过项</li><li>边界：签章加密归投标客户端</li></ul></div>

    <div class="box" style="left:404px;top:146px;width:256px"><h4>${I.db(13)}对象库<span class="tag">SQLite 扩表</span></h4><ul><li class="ok">Matrix ×4（project）</li><li class="new">OutlineNode（project）· G1</li><li class="new">Section 元数据 / 状态 · G3</li><li class="new">EvidenceAsset（<b>org</b>）+ blob · G2</li><li class="new">EvidenceRequest（project 缺口）</li><li class="new">ComplianceRun · ExportPackage</li></ul></div>
    <div class="box" style="left:676px;top:146px;width:256px"><h4>${I.link(13)}三条链接 → 三个门禁</h4><ul><li class="ok">trace：Requirement → Document<i>（line_span）</i></li><li class="new">coverage：OutlineNode → Requirement / Scoring <i>→ 覆盖闭合，SQL 可算</i></li><li class="new">cite：Section → EvidenceAsset <i>→ 断言有据，锚记确定性解析</i></li><li>规则引擎：废标 / 格式 / 报价算术 <i>→ 合规</i></li></ul></div>
    <div class="box" style="left:404px;top:372px;width:528px"><h4>${I.wrench(13)}双 adapter<span class="tag">REST 给前端 · MCP 给智能体</span></h4>
      <div class="code"><span class="c"># prose_* 工具面扩展（命名沿用，全局仅一份）</span>
大纲  <span class="k">prose_generate_outline</span> · update_outline_node · move_outline_node
      link_coverage · validate_outline · publish_outline
章节  <span class="k">prose_get_section_brief</span> · set_section_state · report_section   <span class="c">← 不提供写正文的工具</span>
证据  prose_search_evidence · get_evidence · request_evidence · attach_evidence
检查  prose_run_compliance_check        导出  prose_export_package</div></div>
    <div class="box" style="left:404px;top:548px;width:528px"><h4>${I.doc(13)}prose_get_section_brief · 并行 fan-out 的关键契约</h4>
      <div class="code">{ section_id, title, budget: { words: 2400, figures: 1, tables: 1 },
  requirements: [{ id, text, mandatory, source_refs }],   <span class="c">← 要求原文可回跳</span>
  scoring: [{ id, rule, score, subjective }],             <span class="c">← 写作者答的是记分卡</span>
  evidence: [{ anchor: "E:C-2024-0318", grade, summary }],<span class="c">← 只能引用这些锚记</span>
  style_card: { company, project_alias, tech_route, forbidden: ["报价"] },
  siblings: [{ id, title, state }] }                      <span class="c">← 交叉一致性用</span></div></div>

    <div class="box" style="left:1004px;top:146px;width:372px"><h4>${I.cpu(13)}主智能体 · Skills<span class="tag">deepagents</span></h4><ul><li class="ok">bid-response-matrix（G0）</li><li class="new">bid-outline（G1）· bid-evidence（G2）· bid-authoring（G3）</li><li class="new">bid-compliance（G4，调确定性检查器）· bid-export（G5）</li></ul></div>
    <div class="box" style="left:1004px;top:290px;width:372px"><h4>${I.users(13)}章节 worker · Run = node_generation<span class="tag">ADR 0007 M3</span></h4><ul><li>每节一个 Run，路径锁 deliverables/ch-3.2.md</li><li>并发上限 4（沙箱容量压测后定）· 失败重试 · 部分失败可见</li><li>Run 结束即 checkpoint（host git commit）</li><li>「等你回答」= Run 挂起，不占并发</li></ul></div>
    <div class="box" style="left:1004px;top:454px;width:372px"><h4>${I.folder(13)}Project workspace（租约 VM 内）</h4><div class="code">sources/      招标文件 md + sidecar（只读）
structured/   导出投影（只读、可再生）
deliverables/ ch-3.2.md …  <span class="c">← 正文本体，锚记 [^E:C-2024-0318]</span>
evidence/     本项目上传的企业资料</div></div>
    <div class="box" style="left:1004px;top:600px;width:372px"><h4>${I.print(13)}导出管线（确定性，沙箱内执行）</h4><div class="code">md → pandoc --reference-doc=模板.docx
   → python-docx（目录域 / 页眉页脚 / 分节 / 封面 / 签章占位）
   → 分册打包 → ExportPackage  <span class="c">← 最大技术风险：M1 先 spike</span></div></div>

    <svg class="arrows" width="1440" height="760">
      <path d="M332 200 H404" marker-end="url(#a)"/><text x="345" y="192">REST</text>
      <path d="M932 200 H1004" class="b"/><text x="950" y="192" fill="var(--blue)">MCP</text>
      <path d="M932 430 C 968 430, 968 350, 1004 350" marker-end="url(#a)"/><text x="946" y="398">brief</text>
      <path d="M660 254 H676"/>
      <defs><marker id="a" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0 0L6 3L0 6z" fill="color-mix(in srgb, var(--label-3) 55%, transparent)"/></marker></defs>
    </svg>
  </div></div>`;
  return page({ body, extraCss: CSS });
}
