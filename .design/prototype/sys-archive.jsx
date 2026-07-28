// sys-archive.jsx — A · Archive Editorial · 档案
// Philosophy: 标书是当代公文,需要文献感与编辑学的考究。
// Inspired by editorial typography (FT, Stripe Press, NYT Magazine).
// Restrained, document-first. Warm cream paper, ink black, ochre accent.

function ArchiveSystem() {
  return (
    <SystemPage className="sys-archive">
      <style>{`
        .sys-archive {
          /* tokens */
          --bg: #f7f5ef;
          --paper: #ffffff;
          --surface: #ffffff;
          --surface-2: #f1eee5;
          --ink: #1a1612;
          --ink-2: #534a3f;
          --muted: #8a7d6c;
          --faint: #beb09a;
          --rule: #d9cebd;
          --rule-2: #e6dcc9;
          --ochre: #b06b35;
          --ochre-soft: #f0e1c8;
          --jade: #5a8366;
          --oxide: #a8523e;

          --font-display: "Source Serif 4", "Source Han Serif SC", "Songti SC", Georgia, serif;
          --font-body: "Source Serif 4", "Source Han Serif SC", "Songti SC", Georgia, serif;
          --font-ui: "Inter", "PingFang SC", -apple-system, system-ui, sans-serif;
          --font-mono: "Geist Mono", "JetBrains Mono", ui-monospace, monospace;

          background: var(--bg);
          color: var(--ink);
          font-family: var(--font-ui);
        }
        .sys-archive .mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
        .sys-archive .serif { font-family: var(--font-display); }
        .sys-archive .ui { font-family: var(--font-ui); }

        /* header */
        .sys-archive .sys-code {
          font-family: var(--font-mono);
          font-size: 11px;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: var(--ochre);
        }
        .sys-archive .sys-name {
          font-family: var(--font-display);
          font-size: 78px;
          line-height: 1;
          letter-spacing: -0.025em;
          font-weight: 500;
          font-style: italic;
        }
        .sys-archive .sys-cn {
          font-family: var(--font-display);
          font-size: 38px;
          font-style: normal;
          font-weight: 400;
          letter-spacing: 0.04em;
        }
        .sys-archive .sys-tagline {
          font-family: var(--font-display);
          font-size: 22px;
          font-style: italic;
          color: var(--ink-2);
          line-height: 1.4;
          max-width: 720px;
        }
        .sys-archive .sys-philosophy {
          font-family: var(--font-body);
          font-size: 15.5px;
          line-height: 1.7;
          color: var(--ink-2);
          column-count: 2;
          column-gap: 36px;
          text-align: justify;
          hyphens: auto;
        }
        .sys-archive .block-caption-label {
          font-family: var(--font-mono);
          font-size: 10px;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: var(--ochre);
          font-weight: 500;
        }
        .sys-archive .block-caption-title {
          font-family: var(--font-display);
          font-size: 20px;
          font-style: italic;
          font-weight: 500;
          letter-spacing: -0.01em;
        }

        /* buttons */
        .sys-archive .btn {
          font-family: var(--font-ui);
          font-size: 13px;
          font-weight: 500;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 9px 16px;
          border-radius: 4px;
          border: 1px solid transparent;
          cursor: default;
          letter-spacing: -0.005em;
        }
        .sys-archive .btn svg { width: 13px; height: 13px; }
        .sys-archive .btn-primary { background: var(--ink); color: var(--paper); }
        .sys-archive .btn-secondary { background: var(--paper); color: var(--ink); border-color: var(--rule); }
        .sys-archive .btn-ghost { background: transparent; color: var(--ink-2); }
        .sys-archive .btn-link {
          color: var(--ochre);
          padding: 0;
          border-bottom: 1px solid currentColor;
          border-radius: 0;
          background: transparent;
        }

        /* input */
        .sys-archive .input {
          font-family: var(--font-ui);
          font-size: 13px;
          padding: 9px 12px;
          border: 1px solid var(--rule);
          border-bottom-width: 2px;
          background: var(--paper);
          color: var(--ink);
          border-radius: 4px 4px 0 0;
        }

        /* badges */
        .sys-archive .badge {
          font-family: var(--font-ui);
          font-size: 11px;
          font-weight: 500;
          padding: 3px 9px;
          border-radius: 2px;
          letter-spacing: 0.01em;
          display: inline-flex;
          align-items: center;
          gap: 5px;
        }
        .sys-archive .badge-ochre { background: var(--ochre-soft); color: var(--ochre); }
        .sys-archive .badge-jade { background: #e1ebdf; color: var(--jade); }
        .sys-archive .badge-neutral { background: var(--rule-2); color: var(--ink-2); }
        .sys-archive .badge-outline { border: 1px solid var(--rule); color: var(--ink-2); background: transparent; }

        /* component card */
        .sys-archive .ds-card {
          background: var(--paper);
          border: 1px solid var(--rule);
          border-radius: 4px;
          padding: 18px 22px;
        }

        /* doc preview shell */
        .sys-archive .doc-shell {
          background: var(--paper);
          border: 1px solid var(--rule);
        }
        .sys-archive .doc-topbar {
          display: flex;
          align-items: center;
          padding: 0 18px;
          height: 44px;
          border-bottom: 1px solid var(--rule);
          gap: 14px;
          background: var(--bg);
        }
        .sys-archive .wordmark {
          font-family: var(--font-display);
          font-style: italic;
          font-weight: 500;
          font-size: 18px;
          letter-spacing: -0.01em;
        }
        .sys-archive .wordmark::first-letter { color: var(--ochre); }
        .sys-archive .breadcrumb {
          font-family: var(--font-ui);
          font-size: 12px;
          color: var(--muted);
          letter-spacing: 0.01em;
        }
        .sys-archive .breadcrumb b { color: var(--ink); font-weight: 500; }
      `}</style>

      <SystemHeader
        code="A · Archive Editorial"
        name="Archive"
        cn="档案"
        tagline="A bid is a contemporary public document. Treat it like one."
        philosophy={(
          <>
            <p style={{ margin: 0 }}>把标书当作文献,把界面当作排印。整套系统脱胎于编辑出版传统:Source Serif 担当显示字体,大量留白以呼应"印张"的呼吸,引用与脚注被视觉化地区别于正文,而非塞进信息密度的洪流。</p>
            <p style={{ margin: "10px 0 0" }}>赭石(ochre)是唯一的非黑非灰强调色,留给招标条款引用、智能体批注、关键指标。其他一切——状态、表头、规则线——都用墨色的不同浓度去表达。读起来像是一份被精心装帧过的政商文献。</p>
          </>
        )}
      />

      <SystemRule style={{ margin: "0 56px" }} />

      {/* Logo + Palette + Type — three columns */}
      <section style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 40, padding: "32px 56px 12px" }}>
        {/* Logo column */}
        <div>
          <MicroLabel>01 · Wordmark</MicroLabel>
          <div style={{ marginTop: 22, padding: "28px 24px", border: "1px solid var(--rule)", borderRadius: 4, background: "var(--paper)" }}>
            <div className="wordmark" style={{ fontSize: 56 }}>Prose</div>
            <div style={{ marginTop: 8, fontSize: 11, color: "var(--muted)", fontFamily: "var(--font-mono)", letterSpacing: "0.06em", textTransform: "uppercase" }}>智能标书工作台</div>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <div style={{ flex: 1, padding: "16px 12px", textAlign: "center", border: "1px solid var(--rule)", borderRadius: 4, background: "var(--paper)" }}>
              <div className="serif" style={{ fontStyle: "italic", fontSize: 32, color: "var(--ochre)" }}>P</div>
              <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 2 }}>正向 · 浅底</div>
            </div>
            <div style={{ flex: 1, padding: "16px 12px", textAlign: "center", borderRadius: 4, background: "var(--ink)" }}>
              <div className="serif" style={{ fontStyle: "italic", fontSize: 32, color: "var(--paper)" }}>P</div>
              <div style={{ fontSize: 10, color: "var(--faint)", marginTop: 2 }}>反向 · 深底</div>
            </div>
          </div>
        </div>

        {/* Palette */}
        <div>
          <MicroLabel>02 · Palette</MicroLabel>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 12, marginTop: 22 }}>
            <Swatch color="var(--ink)" name="Ink" hex="#1A1612" role="正文 / 标题" />
            <Swatch color="var(--ink-2)" name="Ink 2" hex="#534A3F" role="次要文字" />
            <Swatch color="var(--muted)" name="Muted" hex="#8A7D6C" role="附注 / 元数据" />
            <Swatch color="var(--ochre)" name="Ochre" hex="#B06B35" role="引用 · 强调" />
            <Swatch color="var(--jade)" name="Jade" hex="#5A8366" role="合规 / 通过" />
            <Swatch color="var(--oxide)" name="Oxide" hex="#A8523E" role="风险 / 偏离" />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 12, marginTop: 12 }}>
            <Swatch color="var(--bg)" name="Paper" hex="#F7F5EF" role="底色" height={56} />
            <Swatch color="var(--paper)" name="Sheet" hex="#FFFFFF" role="页面" height={56} />
            <Swatch color="var(--ochre-soft)" name="Ochre 5" hex="#F0E1C8" role="高亮" height={56} />
            <Swatch color="var(--rule-2)" name="Rule 2" hex="#E6DCC9" role="弱分隔" height={56} />
            <Swatch color="var(--rule)" name="Rule" hex="#D9CEBD" role="主分隔" height={56} />
            <Swatch color="var(--faint)" name="Faint" hex="#BEB09A" role="占位 / 禁用" height={56} />
          </div>
        </div>
      </section>

      {/* Typography */}
      <Block caption="03 · Typography" title="Bilingual editorial stack" style={{ paddingTop: 28 }}>
        <TypeRow
          label="Display Serif"
          meta={<>Source Serif 4<br/>Italic · 78 / -2.5%</>}
          sample={<span className="serif" style={{ fontStyle: "italic", fontSize: 60, lineHeight: 1, letterSpacing: "-0.025em", fontWeight: 500 }}>The Tender, Composed.</span>}
        />
        <TypeRow
          label="Section · 标题"
          meta={<>Source Serif / Source Han Serif<br/>500 · 32 / -1%</>}
          sample={(
            <div>
              <div className="serif" style={{ fontSize: 32, fontWeight: 500, letterSpacing: "-0.01em", lineHeight: 1.2 }}>第四章 · 绿色技术方案</div>
              <div className="serif" style={{ fontStyle: "italic", fontSize: 17, color: "var(--ink-2)", marginTop: 6 }}>Chapter IV — Green Engineering Proposal</div>
            </div>
          )}
        />
        <TypeRow
          label="Body · 正文"
          meta={<>Source Serif / Source Han Serif<br/>400 · 15.5 / 1.75</>}
          sample={<p className="serif" style={{ fontSize: 15.5, lineHeight: 1.75, margin: 0, color: "var(--ink)", maxWidth: 620 }}>本工程采用「冷板式液冷为主、风冷为辅」的混合制冷架构,在 IT 负载侧实现端到端的高效散热,在基础设施侧通过余热回收与光储一体化将综合 PUE 控制在 <span style={{ color: "var(--ochre)" }}>1.18</span> 以下。</p>}
        />
        <TypeRow
          label="UI · 界面"
          meta={<>Inter / PingFang SC<br/>500 · 13 / 1.5</>}
          sample={<div className="ui" style={{ fontSize: 13, fontWeight: 500 }}>导出完整标书 · 78 页 · PDF / A</div>}
        />
        <TypeRow
          label="Mono · 元数据"
          meta={<>Geist Mono<br/>500 · 11 · UPPERCASE</>}
          sample={<div className="mono" style={{ fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--ochre)" }}>P-2025-0712 · CITED 14× · UPDATED 2025-08-04</div>}
        />
      </Block>

      {/* Components */}
      <Block caption="04 · Components" title="Buttons · Badges · Inputs · Citations">
        <div style={{ display: "grid", gridTemplateColumns: "1.1fr 1fr 0.9fr", gap: 16 }}>
          <div className="ds-card">
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 12, fontFamily: "var(--font-mono)", letterSpacing: "0.06em", textTransform: "uppercase" }}>Buttons</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              <button className="btn btn-primary">导出完整标书 {I.arrow}</button>
              <button className="btn btn-secondary">{I.plus} 新建条目</button>
              <button className="btn btn-ghost">取消</button>
              <a className="btn btn-link">查看招标第 38 页</a>
            </div>
          </div>
          <div className="ds-card">
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 12, fontFamily: "var(--font-mono)", letterSpacing: "0.06em", textTransform: "uppercase" }}>Badges & Status</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              <span className="badge badge-ochre">智能体撰写中</span>
              <span className="badge badge-jade">{I.check} 已合规</span>
              <span className="badge badge-neutral">待审 · 6.1</span>
              <span className="badge badge-outline">扣分项 0</span>
            </div>
            <div style={{ marginTop: 14, fontSize: 12, color: "var(--ink-2)", lineHeight: 1.6 }}>
              <span style={{ background: "var(--ochre-soft)", color: "var(--ochre)", padding: "1px 6px", borderRadius: 2, fontFamily: "var(--font-mono)", fontSize: 10, marginRight: 4 }}>T-36</span>
              脚注式引用,正文外溢的元数据。
            </div>
          </div>
          <div className="ds-card">
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 12, fontFamily: "var(--font-mono)", letterSpacing: "0.06em", textTransform: "uppercase" }}>Form Field</div>
            <label style={{ fontSize: 11, color: "var(--ink-2)", fontFamily: "var(--font-mono)", letterSpacing: "0.06em", textTransform: "uppercase" }}>项目名称</label>
            <input className="input" defaultValue="华东数据中心绿色改造工程" style={{ marginTop: 6, width: "100%", boxSizing: "border-box" }} />
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 6, fontStyle: "italic", fontFamily: "var(--font-display)" }}>底线一条墨,继承自编辑稿。</div>
          </div>
        </div>
      </Block>

      {/* UI Preview */}
      <Block caption="05 · Applied" title="工作台 · 撰写视图" style={{ paddingBottom: 36 }}>
        <div className="doc-shell" style={{ borderRadius: 4, overflow: "hidden" }}>
          {/* topbar */}
          <div className="doc-topbar">
            <div className="wordmark">Prose</div>
            <div style={{ width: 1, height: 16, background: "var(--rule)" }} />
            <div className="breadcrumb">2026 年度项目 / <b>华东数据中心绿色改造工程</b></div>
            <div style={{ flex: 1 }} />
            <div style={{ display: "flex", gap: 6, fontFamily: "var(--font-ui)", fontSize: 12, color: "var(--muted)" }}>
              <span style={{ color: "var(--ink)", fontWeight: 500 }}>撰写</span>
              <span>预览</span>
              <span>知识库</span>
            </div>
            <div style={{ marginLeft: 14 }}>
              <button className="btn btn-primary" style={{ fontSize: 11.5, padding: "6px 12px" }}>导出 · PDF / A</button>
            </div>
          </div>

          {/* split */}
          <div style={{ display: "grid", gridTemplateColumns: "420px 1fr", minHeight: 530 }}>
            {/* agent stream */}
            <div style={{ borderRight: "1px solid var(--rule)", padding: "22px 22px" }}>
              <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--ochre)" }}>EXECUTION · 04 / 06</div>
              <div className="serif" style={{ fontSize: 22, fontStyle: "italic", fontWeight: 500, marginTop: 6, lineHeight: 1.25 }}>撰写 4.2 液冷子系统</div>

              <div style={{ marginTop: 20, borderTop: "1px solid var(--rule)", paddingTop: 14 }}>
                <div className="mono" style={{ fontSize: 10, color: "var(--muted)", letterSpacing: "0.06em" }}>09:42 · 李慧</div>
                <p className="serif" style={{ fontSize: 13.5, lineHeight: 1.65, margin: "6px 0 0", color: "var(--ink-2)", fontStyle: "italic" }}>开始撰写第 4 章,招标要求 PUE ≤ 1.25,我们做过 1.18 的案例。</p>
              </div>

              <div style={{ marginTop: 18, borderTop: "1px solid var(--rule)", paddingTop: 14 }}>
                <div className="mono" style={{ fontSize: 10, color: "var(--ochre)", letterSpacing: "0.06em" }}>09:42 · PROSE 智能体</div>
                <p className="serif" style={{ fontSize: 13.5, lineHeight: 1.65, margin: "6px 0 0" }}>已锁定第 4 章。优先采用上海张江二期案例 —— 时间最近,气候相似度 87%。</p>

                <div style={{ marginTop: 10, paddingLeft: 12, borderLeft: "1px solid var(--ochre)" }}>
                  <div style={{ fontSize: 12, color: "var(--ochre)", fontStyle: "italic", fontFamily: "var(--font-display)", lineHeight: 1.6 }}>
                    思考 · 张江案例时间最近,与华东电网有过运维协同,首选。
                  </div>
                </div>

                <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "baseline" }}>
                  <span className="mono" style={{ fontSize: 10, color: "var(--ochre)", letterSpacing: "0.08em" }}>FN.01</span>
                  <span style={{ fontSize: 12, color: "var(--ink-2)" }}>检索知识库 · 命中 <b style={{ color: "var(--ink)" }}>4 个项目</b></span>
                  <span className="mono" style={{ fontSize: 10, color: "var(--muted)", marginLeft: "auto" }}>2.3s</span>
                </div>
                <div style={{ marginTop: 6, display: "flex", gap: 8, alignItems: "baseline" }}>
                  <span className="mono" style={{ fontSize: 10, color: "var(--ochre)", letterSpacing: "0.08em" }}>FN.02</span>
                  <span style={{ fontSize: 12, color: "var(--ink-2)" }}>读取 <i>tender_doc.pdf</i> · 第 36–42 页</span>
                  <span className="mono" style={{ fontSize: 10, color: "var(--muted)", marginLeft: "auto" }}>1.1s</span>
                </div>
                <div style={{ marginTop: 6, display: "flex", gap: 8, alignItems: "baseline" }}>
                  <span className="mono" style={{ fontSize: 10, color: "var(--ochre)", letterSpacing: "0.08em" }}>FN.03</span>
                  <span style={{ fontSize: 12, color: "var(--ink)" }}>撰写 § 4.2 液冷子系统</span>
                  <span className="mono" style={{ fontSize: 10, color: "var(--ochre)", marginLeft: "auto" }}>· · ·</span>
                </div>
              </div>
            </div>

            {/* doc page */}
            <div style={{ padding: "32px 44px 28px", background: "var(--paper)" }}>
              <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--muted)", display: "flex", justifyContent: "space-between" }}>
                <span>华东数据中心绿色改造工程</span><span>页 42 / 78</span>
              </div>
              <div style={{ borderBottom: "1px solid var(--rule)", marginTop: 8, marginBottom: 22 }} />

              <div className="serif" style={{ fontStyle: "italic", fontSize: 11.5, color: "var(--ochre)", fontFamily: "var(--font-mono)", letterSpacing: "0.1em", textTransform: "uppercase" }}>Chapter IV</div>
              <div className="serif" style={{ fontSize: 30, fontWeight: 500, letterSpacing: "-0.01em", lineHeight: 1.25, marginTop: 6 }}>绿色技术方案</div>
              <div className="serif" style={{ fontStyle: "italic", fontSize: 14, color: "var(--ink-2)", marginTop: 6, lineHeight: 1.5 }}>Green engineering proposal for the East-China data centre, addressing tender clauses §36–§58.</div>

              <div style={{ borderTop: "1px solid var(--rule)", marginTop: 16, paddingTop: 16 }}>
                <div className="serif" style={{ fontSize: 18, fontWeight: 500, lineHeight: 1.3 }}>4.2 液冷子系统</div>
                <p className="serif" style={{ fontSize: 13.5, lineHeight: 1.85, margin: "10px 0 0" }}>
                  液冷子系统采用<b>冷板式液冷 + 25℃ 高温冷冻水</b>方案,可在华东地区年均 <b>5,840</b> 小时实现自然冷却<sup style={{ color: "var(--ochre)", fontFamily: "var(--font-mono)", fontSize: 9, fontStyle: "normal" }}>R-07</sup>,相较传统压缩制冷节能约 <span style={{ color: "var(--ochre)", fontWeight: 500 }}>38%</span>。系统遵循 N+1 冗余设计,关键管路采用双路独立环网,任一管段故障不影响整体运行<sup style={{ color: "var(--ochre)", fontFamily: "var(--font-mono)", fontSize: 9, fontStyle: "normal" }}>T-42.3</sup>。
                </p>
                <p className="serif" style={{ fontSize: 13.5, lineHeight: 1.85, margin: "10px 0 0" }}>
                  方案整体已在投标方 2025 年 8 月完成的「上海张江绿色数据中心二期」项目中得到验证,与本工程在气候、负载、网架上具备 <span style={{ background: "var(--ochre-soft)", padding: "0 4px" }}>87% 以上相似度</span>。
                </p>

                <div className="mono" style={{ fontSize: 10, color: "var(--muted)", marginTop: 16, letterSpacing: "0.04em" }}>
                  <span style={{ color: "var(--ochre)" }}>FN.01</span> 知识库 · liquid_cooling AND PUE&lt;1.25 · 命中 4 项 &nbsp;·&nbsp; <span style={{ color: "var(--ochre)" }}>FN.02</span> tender_doc.pdf · 第 36–42 页
                </div>
              </div>
            </div>
          </div>

          {/* footer */}
          <div style={{ display: "flex", alignItems: "center", padding: "10px 18px", borderTop: "1px solid var(--rule)", fontSize: 11, color: "var(--muted)", fontFamily: "var(--font-mono)", letterSpacing: "0.04em" }}>
            <span>SAVED · 2 SEC AGO</span>
            <span style={{ margin: "0 14px", opacity: 0.4 }}>·</span>
            <span>23 CITATIONS · 78 P · 14.2 MB</span>
            <span style={{ marginLeft: "auto", color: "var(--ochre)" }}>截标 05-12 17:00 · 剩余 6 天 21 时</span>
          </div>
        </div>
      </Block>
    </SystemPage>
  );
}

window.ArchiveSystem = ArchiveSystem;
