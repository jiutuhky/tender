// sys-statecraft.jsx — B · Statecraft · 政务
// Philosophy: 标书要看起来值这个钱。庄重、权威、可信。
// Deep navy on ivory, imperial gold accent, crimson seal, Songti display.
// Strong horizontal rules, formal hierarchy, hint of traditional bound document.

function StatecraftSystem() {
  return (
    <SystemPage className="sys-statecraft">
      <style>{`
        .sys-statecraft {
          --bg: #f5f1e7;
          --paper: #fbf8ef;
          --surface: #ffffff;
          --ink: #14213d;
          --navy: #1c2c54;
          --navy-2: #3a4970;
          --navy-3: #6b779a;
          --muted: #8c8a82;
          --faint: #b9b6ab;
          --rule: #c8c2b1;
          --rule-2: #d8d2c1;
          --gold: #b58836;
          --gold-deep: #7a5a1c;
          --gold-soft: #f3e6c4;
          --vermilion: #b8332b;
          --vermilion-soft: #efd6cf;
          --jade: #3d6e54;

          --font-display: "Noto Serif SC", "Source Han Serif SC", "Songti SC", "SimSun", "Source Serif 4", serif;
          --font-body: "PingFang SC", "Source Han Sans SC", "Noto Sans SC", -apple-system, system-ui, sans-serif;
          --font-ui: "PingFang SC", "Noto Sans SC", -apple-system, system-ui, sans-serif;
          --font-mono: "IBM Plex Mono", "Geist Mono", ui-monospace, monospace;
          --font-latin-display: "Source Serif 4", Georgia, serif;

          background: var(--bg);
          color: var(--ink);
          font-family: var(--font-ui);
        }
        .sys-statecraft .mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
        .sys-statecraft .song { font-family: var(--font-display); }

        /* header */
        .sys-statecraft .sys-code {
          font-family: var(--font-mono);
          font-size: 11px;
          letter-spacing: 0.24em;
          text-transform: uppercase;
          color: var(--vermilion);
          font-weight: 500;
        }
        .sys-statecraft .sys-name {
          font-family: var(--font-display);
          font-size: 76px;
          line-height: 1;
          letter-spacing: 0.04em;
          font-weight: 700;
          color: var(--navy);
        }
        .sys-statecraft .sys-cn {
          font-family: var(--font-display);
          font-size: 76px;
          font-weight: 900;
          letter-spacing: 0.12em;
        }
        .sys-statecraft .sys-tagline {
          font-family: var(--font-display);
          font-size: 22px;
          font-weight: 600;
          letter-spacing: 0.04em;
          color: var(--navy);
          line-height: 1.5;
        }
        .sys-statecraft .sys-philosophy {
          font-family: var(--font-body);
          font-size: 15px;
          line-height: 1.85;
          color: var(--navy-2);
          column-count: 2;
          column-gap: 36px;
          text-align: justify;
        }
        .sys-statecraft .block-caption-label {
          font-family: var(--font-mono);
          font-size: 10px;
          letter-spacing: 0.24em;
          text-transform: uppercase;
          color: var(--gold-deep);
          font-weight: 500;
        }
        .sys-statecraft .block-caption-title {
          font-family: var(--font-display);
          font-size: 22px;
          font-weight: 700;
          color: var(--navy);
          letter-spacing: 0.02em;
        }

        /* double-rule, characteristic of bound documents */
        .sys-statecraft .double-rule {
          border-top: 1px solid var(--navy);
          border-bottom: 1px solid var(--navy);
          height: 4px;
          margin: 0 56px;
        }

        /* buttons */
        .sys-statecraft .btn {
          font-family: var(--font-ui);
          font-size: 13px;
          font-weight: 500;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 9px 18px;
          border: 1px solid transparent;
          cursor: default;
          letter-spacing: 0.04em;
          border-radius: 0;
        }
        .sys-statecraft .btn svg { width: 13px; height: 13px; }
        .sys-statecraft .btn-primary { background: var(--navy); color: var(--paper); }
        .sys-statecraft .btn-secondary { background: var(--paper); color: var(--navy); border: 1px solid var(--navy); }
        .sys-statecraft .btn-gold { background: var(--gold); color: white; }
        .sys-statecraft .btn-ghost { background: transparent; color: var(--navy-2); border: 1px solid var(--rule); }

        /* input */
        .sys-statecraft .input {
          font-family: var(--font-ui);
          font-size: 13px;
          padding: 9px 12px;
          border: 1px solid var(--navy-2);
          background: var(--paper);
          color: var(--navy);
          border-radius: 0;
        }

        /* badges - more formal, rectangle */
        .sys-statecraft .badge {
          font-family: var(--font-ui);
          font-size: 11px;
          font-weight: 500;
          padding: 3px 8px;
          letter-spacing: 0.04em;
          display: inline-flex;
          align-items: center;
          gap: 5px;
          border-radius: 0;
          border: 1px solid currentColor;
        }
        .sys-statecraft .badge-vermilion { color: var(--vermilion); background: var(--vermilion-soft); border-color: transparent; }
        .sys-statecraft .badge-gold { color: var(--gold-deep); background: var(--gold-soft); border-color: transparent; }
        .sys-statecraft .badge-jade { color: var(--jade); background: #dfe9df; border-color: transparent; }
        .sys-statecraft .badge-navy { color: var(--navy); background: transparent; }

        /* card */
        .sys-statecraft .ds-card {
          background: var(--paper);
          border: 1px solid var(--rule);
          padding: 18px 22px;
          border-radius: 0;
        }

        /* seal — round red stamp */
        .sys-statecraft .seal {
          width: 88px;
          height: 88px;
          border-radius: 50%;
          border: 2.5px solid var(--vermilion);
          color: var(--vermilion);
          display: grid;
          place-items: center;
          font-family: var(--font-display);
          font-weight: 700;
          line-height: 1;
          transform: rotate(-6deg);
          flex-shrink: 0;
          position: relative;
        }
        .sys-statecraft .seal::before {
          content: "";
          position: absolute;
          inset: 4px;
          border-radius: 50%;
          border: 1px solid var(--vermilion);
        }
        .sys-statecraft .seal .seal-text {
          font-size: 16px;
          letter-spacing: 0.1em;
          writing-mode: vertical-rl;
        }

        /* doc shell */
        .sys-statecraft .doc-topbar {
          display: flex;
          align-items: center;
          padding: 0 20px;
          height: 52px;
          background: var(--navy);
          color: var(--paper);
          gap: 16px;
          border-radius: 0;
        }
        .sys-statecraft .wordmark {
          font-family: var(--font-display);
          font-weight: 700;
          font-size: 20px;
          letter-spacing: 0.14em;
        }
        .sys-statecraft .wordmark-gold { color: var(--gold); }
      `}</style>

      <SystemHeader
        code="B · STATECRAFT — 政务"
        name="Hanlin"
        cn="翰林"
        tagline="为央国企与政府采购书的庄重感而设计。"
        philosophy={(
          <>
            <p style={{ margin: 0 }}>把界面当作一份"经过用印的正式公文"来对待。深藏青(navy)是基色,与公文封面的色脉一脉相承;赭金(gold)用于章节起头与价值锚点,呼应封面烫金;朱红(vermilion)只在"已用印""已盖章"的时刻出现——是仪式感,也是不可撤销的承诺。</p>
            <p style={{ margin: "10px 0 0" }}>宋体担纲所有"被庄重对待"的位置:章节、引用、印章;非衬线只服务于功能性的工具栏与表单。所有分隔线都用 1pt 实线或双实线——这是装订文献的特征,不是装饰。</p>
          </>
        )}
      />

      <div className="double-rule" />

      {/* Logo + Palette */}
      <section style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 40, padding: "32px 56px 12px" }}>
        <div>
          <MicroLabel>01 · 标识</MicroLabel>
          <div style={{ marginTop: 22, padding: "32px 24px 28px", background: "var(--navy)", color: "var(--paper)", display: "flex", flexDirection: "column", alignItems: "center", position: "relative" }}>
            <div style={{ position: "absolute", top: 14, left: 14, right: 14, borderTop: "1px solid var(--gold)", height: 3, borderBottom: "1px solid var(--gold)" }} />
            <div className="song" style={{ fontSize: 60, fontWeight: 700, letterSpacing: "0.14em", color: "var(--gold)", lineHeight: 1, marginTop: 8 }}>翰林</div>
            <div style={{ fontSize: 11, color: "var(--paper)", marginTop: 12, fontFamily: "var(--font-mono)", letterSpacing: "0.3em", textTransform: "uppercase", opacity: 0.7 }}>HANLIN · TENDER OS</div>
          </div>
          <div style={{ display: "flex", gap: 12, marginTop: 12, alignItems: "stretch" }}>
            <div style={{ flex: 1, padding: "18px 8px", textAlign: "center", border: "1px solid var(--rule)", background: "var(--paper)" }}>
              <div className="song" style={{ fontSize: 28, fontWeight: 700, color: "var(--navy)", letterSpacing: "0.1em" }}>翰</div>
              <div style={{ fontSize: 9, color: "var(--muted)", marginTop: 4, fontFamily: "var(--font-mono)", letterSpacing: "0.1em" }}>SQUARE</div>
            </div>
            <div className="seal" style={{ width: 88, height: 88, transform: "rotate(-4deg)", margin: "0 auto" }}>
              <span className="seal-text">翰林审定</span>
            </div>
            <div style={{ flex: 1, padding: "8px", textAlign: "center", background: "var(--gold)", color: "var(--navy)", display: "grid", placeItems: "center" }}>
              <div>
                <div className="song" style={{ fontSize: 28, fontWeight: 700, letterSpacing: "0.1em" }}>翰</div>
                <div style={{ fontSize: 9, marginTop: 4, fontFamily: "var(--font-mono)", letterSpacing: "0.1em" }}>GOLD</div>
              </div>
            </div>
          </div>
        </div>

        <div>
          <MicroLabel>02 · 色系</MicroLabel>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 0, marginTop: 22, border: "1px solid var(--rule)" }}>
            <Swatch variant="flat" color="var(--navy)" name="藏青" hex="#1C2C54" role="主色" textColor="white" height={108} />
            <Swatch variant="flat" color="var(--navy-2)" name="副藏青" hex="#3A4970" role="副文字" textColor="white" height={108} />
            <Swatch variant="flat" color="var(--gold)" name="赭金" hex="#B58836" role="强调" textColor="white" height={108} />
            <Swatch variant="flat" color="var(--vermilion)" name="朱红" hex="#B8332B" role="印章 · 用印" textColor="white" height={108} />
            <Swatch variant="flat" color="var(--jade)" name="苍翠" hex="#3D6E54" role="合规" textColor="white" height={108} />
            <Swatch variant="flat" color="var(--ink)" name="墨" hex="#14213D" role="正文" textColor="white" height={108} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 0, marginTop: 12, border: "1px solid var(--rule)" }}>
            <Swatch variant="flat" color="var(--bg)" name="本色" hex="#F5F1E7" role="底色" textColor="var(--navy)" height={64} />
            <Swatch variant="flat" color="var(--paper)" name="宣纸" hex="#FBF8EF" role="页面" textColor="var(--navy)" height={64} />
            <Swatch variant="flat" color="var(--gold-soft)" name="洒金" hex="#F3E6C4" role="强调底" textColor="var(--gold-deep)" height={64} />
            <Swatch variant="flat" color="var(--vermilion-soft)" name="霁红底" hex="#EFD6CF" role="风险" textColor="var(--vermilion)" height={64} />
            <Swatch variant="flat" color="var(--rule-2)" name="弱分隔" hex="#D8D2C1" role="rule 2" textColor="var(--navy-2)" height={64} />
            <Swatch variant="flat" color="var(--rule)" name="主分隔" hex="#C8C2B1" role="rule" textColor="var(--navy-2)" height={64} />
          </div>
        </div>
      </section>

      {/* Typography */}
      <Block caption="03 · 字体体系" title="宋体担当 · 仪礼感">
        <TypeRow
          label="封面体 · Display"
          meta={<>Noto Serif SC<br/>Black · 76 · +0.12</>}
          sample={<div className="song" style={{ fontSize: 64, fontWeight: 900, letterSpacing: "0.1em", color: "var(--navy)", lineHeight: 1 }}>投 · 标 · 书</div>}
        />
        <TypeRow
          label="章节标题"
          meta={<>Noto Serif SC<br/>700 · 30 · +0.02</>}
          sample={(
            <div>
              <div className="song" style={{ fontSize: 14, fontWeight: 500, letterSpacing: "0.24em", color: "var(--gold-deep)", textTransform: "uppercase" }}>第 四 章</div>
              <div className="song" style={{ fontSize: 32, fontWeight: 700, letterSpacing: "0.04em", color: "var(--navy)", marginTop: 4 }}>绿色技术方案</div>
            </div>
          )}
        />
        <TypeRow
          label="正文 · 公文体"
          meta={<>PingFang SC<br/>400 · 15 · 1.85</>}
          sample={<p style={{ fontSize: 15, lineHeight: 1.85, margin: 0, color: "var(--ink)", maxWidth: 640, letterSpacing: "0.01em" }}>本工程采用「冷板式液冷为主、风冷为辅」的混合制冷架构,在 IT 负载侧实现端到端的高效散热,综合 PUE 控制在 <b style={{ color: "var(--gold-deep)" }}>1.18</b> 以下,优于招标要求。</p>}
        />
        <TypeRow
          label="工具 · UI"
          meta={<>PingFang SC<br/>500 · 13 · +0.04</>}
          sample={<div style={{ fontSize: 13, fontWeight: 500, letterSpacing: "0.04em" }}>导出 · 投标书正本 78 页</div>}
        />
        <TypeRow
          label="编号 · Mono"
          meta={<>IBM Plex Mono<br/>500 · 11 · +0.24</>}
          sample={<div className="mono" style={{ fontSize: 11, letterSpacing: "0.24em", textTransform: "uppercase", color: "var(--gold-deep)" }}>HL/T—2026—0142 · 审定 · 用印</div>}
        />
      </Block>

      {/* Components */}
      <Block caption="04 · 组件" title="按钮 · 状态 · 印记">
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 0.9fr", gap: 16 }}>
          <div className="ds-card">
            <div style={{ fontSize: 10, color: "var(--gold-deep)", marginBottom: 12, fontFamily: "var(--font-mono)", letterSpacing: "0.24em", textTransform: "uppercase", fontWeight: 500 }}>按钮</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              <button className="btn btn-primary">{I.check} 用印并提交</button>
              <button className="btn btn-gold">导出正本</button>
              <button className="btn btn-secondary">预览</button>
              <button className="btn btn-ghost">退回修改</button>
            </div>
            <div style={{ marginTop: 14 }}>
              <div className="mono" style={{ fontSize: 9, color: "var(--muted)", letterSpacing: "0.16em" }}>EMPHASIS LADDER</div>
              <div style={{ display: "flex", marginTop: 6, height: 6 }}>
                <div style={{ flex: 4, background: "var(--navy)" }} />
                <div style={{ flex: 2, background: "var(--gold)" }} />
                <div style={{ flex: 1, background: "var(--vermilion)" }} />
              </div>
            </div>
          </div>
          <div className="ds-card">
            <div style={{ fontSize: 10, color: "var(--gold-deep)", marginBottom: 12, fontFamily: "var(--font-mono)", letterSpacing: "0.24em", textTransform: "uppercase", fontWeight: 500 }}>状态</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              <span className="badge badge-vermilion">● 已用印</span>
              <span className="badge badge-gold">智能体撰写</span>
              <span className="badge badge-jade">{I.check} 合规通过</span>
              <span className="badge badge-navy">待会签</span>
            </div>
            <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--rule-2)" }}>
              <div className="mono" style={{ fontSize: 10, color: "var(--muted)", letterSpacing: "0.06em", marginBottom: 6 }}>批注</div>
              <div style={{ fontSize: 12, color: "var(--navy)", borderLeft: "2px solid var(--gold)", paddingLeft: 10, lineHeight: 1.6 }}>
                此节已对照招标第 38 页,<b>0 扣分风险</b>。
              </div>
            </div>
          </div>
          <div className="ds-card" style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div className="seal">
              <span className="seal-text">已审定</span>
            </div>
            <div>
              <div className="song" style={{ fontSize: 14, fontWeight: 700, color: "var(--navy)" }}>用印模块</div>
              <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 4, lineHeight: 1.6 }}>朱红圆章仅在最终交付时出现 —— 不是装饰,是承诺。</div>
            </div>
          </div>
        </div>
      </Block>

      {/* UI Preview */}
      <Block caption="05 · 应用" title="工作台 · 撰写视图" style={{ paddingBottom: 36 }}>
        <div style={{ background: "var(--paper)", border: "1px solid var(--rule)", overflow: "hidden" }}>
          <div className="doc-topbar">
            <div className="wordmark song">翰林 <span className="wordmark-gold">·</span> <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.2em", opacity: 0.7 }}>HANLIN</span></div>
            <div style={{ width: 1, height: 18, background: "var(--gold)", opacity: 0.5 }} />
            <div style={{ fontSize: 12, opacity: 0.75 }}>2026 年度项目 <span style={{ margin: "0 6px", opacity: 0.4 }}>/</span> <b style={{ opacity: 1 }}>华东数据中心绿色改造工程</b></div>
            <div style={{ flex: 1 }} />
            <div style={{ display: "flex", gap: 0, fontSize: 12, letterSpacing: "0.04em" }}>
              <span style={{ padding: "6px 12px", color: "var(--gold)", borderBottom: "2px solid var(--gold)" }}>撰写</span>
              <span style={{ padding: "6px 12px", opacity: 0.6 }}>预览</span>
              <span style={{ padding: "6px 12px", opacity: 0.6 }}>知识库</span>
              <span style={{ padding: "6px 12px", opacity: 0.6 }}>用印</span>
            </div>
            <button className="btn btn-gold" style={{ fontSize: 11.5, padding: "6px 14px", marginLeft: 8 }}>{I.check} 用印并提交</button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "420px 1fr", minHeight: 560 }}>
            {/* agent stream */}
            <div style={{ borderRight: "1px solid var(--rule)", padding: "18px 22px", background: "var(--bg)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div className="mono" style={{ fontSize: 10, color: "var(--gold-deep)", letterSpacing: "0.18em" }}>智能体执行 04 / 06</div>
                <div style={{ flex: 1, height: 1, background: "var(--rule)" }} />
                <div className="mono" style={{ fontSize: 10, color: "var(--muted)" }}>01:14</div>
              </div>
              <div className="song" style={{ fontSize: 20, fontWeight: 700, marginTop: 10, color: "var(--navy)" }}>撰写 · 4.2 液冷子系统</div>

              <div style={{ marginTop: 18, display: "flex", flexWrap: "wrap", gap: 6 }}>
                <span className="badge badge-gold">依据 · 招标 + 3 份资料</span>
                <span className="badge badge-navy">下一步 · 校对 PUE / WUE</span>
              </div>

              <div style={{ marginTop: 22, paddingTop: 14, borderTop: "1px solid var(--rule)" }}>
                <div className="mono" style={{ fontSize: 10, color: "var(--navy-3)", letterSpacing: "0.06em" }}>李慧 · 09:42</div>
                <p style={{ fontSize: 13.5, lineHeight: 1.75, margin: "6px 0 0", color: "var(--navy-2)" }}>开始撰写第 4 章,招标 PUE ≤ 1.25,我们做过 1.18 的案例。</p>
              </div>

              <div style={{ marginTop: 16, borderTop: "1px solid var(--rule)", paddingTop: 14 }}>
                <div className="mono" style={{ fontSize: 10, color: "var(--gold-deep)", letterSpacing: "0.08em" }}>翰林 · 09:42</div>
                <p style={{ fontSize: 13.5, lineHeight: 1.75, margin: "6px 0 0" }}>已锁定第 4 章。优先采用上海张江二期案例 —— 时间最近,气候相似度 87%。</p>

                <div style={{ marginTop: 12 }}>
                  {[
                    ["检索知识库", "命中 4 个项目", "2.3s"],
                    ["读取 tender_doc.pdf", "第 36–42 页 · 19 条规范", "1.1s"],
                    ["撰写 § 4.2", "字数 1,200–1,500 · 配图 2 张", "运行中"],
                  ].map(([n, r, t], i) => (
                    <div key={i} style={{ display: "grid", gridTemplateColumns: "20px 1fr auto", gap: 10, alignItems: "baseline", padding: "8px 0", borderTop: i === 0 ? 0 : "1px dashed var(--rule-2)" }}>
                      <span className="mono" style={{ fontSize: 10, color: "var(--gold)", fontWeight: 600 }}>{String(i + 1).padStart(2, "0")}</span>
                      <div>
                        <div style={{ fontSize: 12.5, color: "var(--navy)", fontWeight: 500 }}>{n}</div>
                        <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>{r}</div>
                      </div>
                      <span className="mono" style={{ fontSize: 10.5, color: t === "运行中" ? "var(--gold)" : "var(--muted)" }}>{t}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* doc page */}
            <div style={{ padding: "20px 32px 24px", background: "var(--paper)", position: "relative" }}>
              {/* page double-border */}
              <div style={{ position: "absolute", top: 16, left: 24, right: 24, borderTop: "1px solid var(--navy)", height: 3, borderBottom: "1px solid var(--navy)" }} />

              <div style={{ marginTop: 20, display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
                <div className="mono" style={{ fontSize: 10, color: "var(--gold-deep)", letterSpacing: "0.16em", textTransform: "uppercase" }}>第 四 章 · CHAPTER IV</div>
                <div className="mono" style={{ fontSize: 10, color: "var(--muted)", letterSpacing: "0.04em" }}>页 42 / 78</div>
              </div>

              <div className="song" style={{ fontSize: 32, fontWeight: 700, letterSpacing: "0.04em", color: "var(--navy)", marginTop: 4 }}>绿色技术方案</div>
              <div style={{ fontSize: 12.5, color: "var(--navy-2)", marginTop: 6, lineHeight: 1.6 }}>对应招标文件 §36–§58,围绕 PUE、WUE、可再生能源占比三项核心指标。</div>

              <div style={{ borderTop: "1px solid var(--navy)", marginTop: 14, paddingTop: 14 }}>
                <div className="song" style={{ fontSize: 18, fontWeight: 700, color: "var(--navy)" }}>4.2 液冷子系统</div>
                <p style={{ fontSize: 13.5, lineHeight: 1.95, margin: "10px 0 0", color: "var(--ink)" }}>
                  液冷子系统采用<b>冷板式液冷 + 25℃ 高温冷冻水</b>方案,可在华东地区年均 <b>5,840</b> 小时实现自然冷却<sup className="mono" style={{ color: "var(--gold-deep)", fontSize: 9 }}>[R-07]</sup>,相较传统压缩制冷节能 <b style={{ color: "var(--gold-deep)" }}>38%</b>。系统遵循 N+1 冗余设计,关键管路采用双路独立环网,任一管段故障不影响整体运行<sup className="mono" style={{ color: "var(--gold-deep)", fontSize: 9 }}>[T-42.3]</sup>。
                </p>

                {/* mini compliance table */}
                <table style={{ width: "100%", marginTop: 14, borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ borderTop: "1.5px solid var(--navy)", borderBottom: "1.5px solid var(--navy)" }}>
                      <th style={{ textAlign: "left", padding: "8px 10px", fontWeight: 600, color: "var(--navy)" }}>指标</th>
                      <th style={{ textAlign: "right", padding: "8px 10px", fontWeight: 600, color: "var(--navy)" }}>招标</th>
                      <th style={{ textAlign: "right", padding: "8px 10px", fontWeight: 600, color: "var(--navy)" }}>张江实测</th>
                      <th style={{ textAlign: "right", padding: "8px 10px", fontWeight: 600, color: "var(--navy)" }}>本工程</th>
                      <th style={{ textAlign: "right", padding: "8px 10px", fontWeight: 600, color: "var(--navy)" }}>响应</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ["年均 PUE", "≤ 1.25", "1.184", "≤ 1.18", "优于"],
                      ["WUE (L/kWh)", "≤ 0.5", "0.31", "≤ 0.32", "优于"],
                      ["可再生能源", "≥ 30%", "34.2%", "≥ 35%", "优于"],
                    ].map((r, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid var(--rule-2)" }}>
                        <td style={{ padding: "8px 10px" }}>{r[0]}</td>
                        <td className="mono" style={{ padding: "8px 10px", textAlign: "right" }}>{r[1]}</td>
                        <td className="mono" style={{ padding: "8px 10px", textAlign: "right" }}>{r[2]}</td>
                        <td className="mono" style={{ padding: "8px 10px", textAlign: "right", fontWeight: 600 }}>{r[3]}</td>
                        <td style={{ padding: "8px 10px", textAlign: "right", color: "var(--jade)", fontWeight: 500 }}>{r[4]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 12, color: "var(--gold-deep)", fontSize: 11.5 }}>
                  <span className="mono" style={{ letterSpacing: "0.06em" }}>[ T-36 ]</span>
                  <span style={{ fontStyle: "italic" }}>智能体批注 —— 已对照招标第 36 页,各项指标全部达标或优于要求。</span>
                </div>
              </div>

              {/* floating seal */}
              <div style={{ position: "absolute", bottom: 22, right: 32 }}>
                <div className="seal" style={{ width: 76, height: 76 }}>
                  <span className="seal-text" style={{ fontSize: 13 }}>待用印</span>
                </div>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", padding: "10px 18px", borderTop: "1px solid var(--navy)", background: "var(--bg)", fontSize: 11, color: "var(--navy-2)" }}>
            <span className="mono" style={{ letterSpacing: "0.08em" }}>HL/T—2026—0142</span>
            <span style={{ margin: "0 12px", opacity: 0.4 }}>·</span>
            <span>已保存 · 2 秒前</span>
            <span style={{ marginLeft: "auto", color: "var(--vermilion)", fontWeight: 500 }}>截标 05-12 17:00 · 剩余 6 天 21 时</span>
          </div>
        </div>
      </Block>
    </SystemPage>
  );
}

window.StatecraftSystem = StatecraftSystem;
