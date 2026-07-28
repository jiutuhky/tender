// sys-quartz.jsx — D · Quartz · 晶
// Philosophy: AI 是产品的主角。把"智能体在场"可视化为温柔的光晕。
// Bright neutrals + vibrant indigo/violet + soft gradients on AI moments.
// Inspired by Linear, Vercel, Arc, modern AI-native tools.

function QuartzSystem() {
  return (
    <SystemPage className="sys-quartz">
      <style>{`
        .sys-quartz {
          --bg: #f7f7fb;
          --paper: #ffffff;
          --surface: #ffffff;
          --surface-2: #f1f2f8;
          --surface-3: #ecedf6;

          --ink: #0e0d1a;
          --ink-2: #2c2a3f;
          --muted: #6a6880;
          --faint: #a6a3ba;
          --rule: #e6e6ef;
          --rule-2: #eeeef5;

          --violet: #5a3aff;
          --violet-2: #7559ff;
          --violet-soft: #ece7ff;
          --violet-deep: #2d1d8a;
          --cyan: #0aa5b8;
          --cyan-soft: #d5f1f4;
          --pink: #ff5d8f;
          --pink-soft: #ffe1ea;
          --amber: #d68500;
          --jade: #14a06a;
          --jade-soft: #d0f0e0;

          --grad-ai: linear-gradient(135deg, #5a3aff 0%, #b56cff 50%, #ff7ab4 100%);
          --grad-ai-soft: linear-gradient(135deg, #ece7ff 0%, #f5e8ff 50%, #ffe9f1 100%);
          --grad-ai-edge: linear-gradient(135deg, #5a3aff 0%, #ff7ab4 100%);

          --font-display: "Geist", "HarmonyOS Sans SC", "PingFang SC", -apple-system, system-ui, sans-serif;
          --font-body: "Geist", "HarmonyOS Sans SC", "PingFang SC", -apple-system, system-ui, sans-serif;
          --font-ui: "Geist", "HarmonyOS Sans SC", "PingFang SC", -apple-system, system-ui, sans-serif;
          --font-mono: "Geist Mono", ui-monospace, monospace;
          --font-italic: "Instrument Serif", "Newsreader", Georgia, serif;

          background: var(--bg);
          background-image:
            radial-gradient(ellipse 800px 400px at 90% 0%, rgba(181, 108, 255, 0.10), transparent 60%),
            radial-gradient(ellipse 600px 300px at 0% 100%, rgba(10, 165, 184, 0.06), transparent 60%);
          color: var(--ink);
          font-family: var(--font-ui);
        }
        .sys-quartz .mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }
        .sys-quartz .italic-serif { font-family: var(--font-italic); font-style: italic; }

        /* header */
        .sys-quartz .sys-code {
          font-family: var(--font-mono);
          font-size: 11px;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: var(--violet);
          font-weight: 500;
        }
        .sys-quartz .sys-name {
          font-family: var(--font-display);
          font-size: 86px;
          line-height: 0.95;
          letter-spacing: -0.04em;
          font-weight: 600;
          background: var(--grad-ai-edge);
          -webkit-background-clip: text;
          background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        .sys-quartz .sys-cn {
          font-family: var(--font-italic);
          font-style: italic;
          font-size: 64px;
          font-weight: 400;
          color: var(--ink);
          letter-spacing: 0.02em;
        }
        .sys-quartz .sys-tagline {
          font-family: var(--font-display);
          font-size: 22px;
          font-weight: 500;
          letter-spacing: -0.01em;
          color: var(--ink);
          line-height: 1.4;
        }
        .sys-quartz .sys-tagline em { font-family: var(--font-italic); font-weight: 400; font-style: italic; color: var(--violet); }
        .sys-quartz .sys-philosophy {
          font-family: var(--font-body);
          font-size: 15px;
          line-height: 1.7;
          color: var(--ink-2);
          column-count: 2;
          column-gap: 36px;
        }
        .sys-quartz .block-caption-label {
          font-family: var(--font-mono);
          font-size: 10px;
          letter-spacing: 0.14em;
          text-transform: uppercase;
          color: var(--violet);
          font-weight: 500;
        }
        .sys-quartz .block-caption-title {
          font-family: var(--font-display);
          font-size: 20px;
          font-weight: 600;
          color: var(--ink);
          letter-spacing: -0.01em;
        }

        /* buttons */
        .sys-quartz .btn {
          font-family: var(--font-ui);
          font-size: 13px;
          font-weight: 500;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 9px 16px;
          border: 1px solid transparent;
          cursor: default;
          letter-spacing: -0.005em;
          border-radius: 10px;
          transition: transform .14s, box-shadow .14s;
        }
        .sys-quartz .btn svg { width: 13px; height: 13px; }
        .sys-quartz .btn-violet {
          background: var(--violet);
          color: white;
          box-shadow: 0 1px 2px rgba(90, 58, 255, 0.3), 0 8px 24px -8px rgba(90, 58, 255, 0.6), inset 0 1px 0 rgba(255,255,255,0.18);
        }
        .sys-quartz .btn-grad {
          background: var(--grad-ai-edge);
          color: white;
          box-shadow: 0 1px 2px rgba(90, 58, 255, 0.25), 0 8px 24px -8px rgba(255, 122, 180, 0.45), inset 0 1px 0 rgba(255,255,255,0.20);
        }
        .sys-quartz .btn-secondary {
          background: white;
          color: var(--ink);
          border: 1px solid var(--rule);
          box-shadow: 0 1px 2px rgba(14, 13, 26, 0.04);
        }
        .sys-quartz .btn-ghost { background: transparent; color: var(--ink-2); }

        /* input */
        .sys-quartz .input {
          font-family: var(--font-ui);
          font-size: 13.5px;
          padding: 10px 14px;
          border: 1px solid var(--rule);
          background: white;
          color: var(--ink);
          border-radius: 10px;
          transition: border-color .15s, box-shadow .15s;
          box-shadow: 0 1px 2px rgba(14, 13, 26, 0.03);
        }
        .sys-quartz .input:focus { outline: none; border-color: var(--violet); box-shadow: 0 0 0 3px var(--violet-soft); }

        /* badges - pill, soft */
        .sys-quartz .badge {
          font-family: var(--font-ui);
          font-size: 11.5px;
          font-weight: 500;
          padding: 3px 9px;
          letter-spacing: -0.005em;
          display: inline-flex;
          align-items: center;
          gap: 5px;
          border-radius: 99px;
          border: 1px solid transparent;
        }
        .sys-quartz .badge-violet { color: var(--violet-deep); background: var(--violet-soft); }
        .sys-quartz .badge-jade { color: var(--jade); background: var(--jade-soft); }
        .sys-quartz .badge-cyan { color: var(--cyan); background: var(--cyan-soft); }
        .sys-quartz .badge-pink { color: var(--pink); background: var(--pink-soft); }
        .sys-quartz .badge-neutral { color: var(--ink-2); background: var(--surface-2); border-color: var(--rule); }
        .sys-quartz .badge-grad {
          color: white;
          background: var(--grad-ai-edge);
          font-weight: 600;
          padding: 3px 11px;
        }

        /* card with soft shadow */
        .sys-quartz .ds-card {
          background: white;
          border: 1px solid var(--rule);
          padding: 18px 20px;
          border-radius: 14px;
          box-shadow: 0 1px 2px rgba(14, 13, 26, 0.03), 0 8px 24px -16px rgba(14, 13, 26, 0.08);
        }
        .sys-quartz .ds-card-ai {
          background: var(--grad-ai-soft);
          border: 1px solid transparent;
          padding: 18px 20px;
          border-radius: 14px;
          position: relative;
          overflow: hidden;
        }
        .sys-quartz .ds-card-ai::before {
          content: "";
          position: absolute;
          inset: 0;
          border-radius: inherit;
          padding: 1px;
          background: var(--grad-ai-edge);
          -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
          -webkit-mask-composite: xor;
          mask-composite: exclude;
          pointer-events: none;
        }

        /* doc shell */
        .sys-quartz .doc-topbar {
          display: flex;
          align-items: center;
          padding: 0 18px;
          height: 52px;
          background: rgba(255, 255, 255, 0.85);
          backdrop-filter: blur(12px);
          border-bottom: 1px solid var(--rule);
          gap: 14px;
        }
        .sys-quartz .wordmark {
          font-family: var(--font-display);
          font-weight: 600;
          font-size: 18px;
          letter-spacing: -0.025em;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .sys-quartz .wordmark-glyph {
          width: 24px;
          height: 24px;
          border-radius: 7px;
          background: var(--grad-ai-edge);
          display: grid;
          place-items: center;
          color: white;
          font-family: var(--font-italic);
          font-style: italic;
          font-size: 16px;
          font-weight: 400;
          box-shadow: 0 4px 12px -2px rgba(90, 58, 255, 0.5);
        }

        /* shimmer for AI states */
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        .sys-quartz .shimmer-text {
          background: linear-gradient(90deg, var(--violet) 0%, var(--pink) 25%, var(--violet) 50%, var(--pink) 75%, var(--violet) 100%);
          background-size: 200% auto;
          -webkit-background-clip: text;
          background-clip: text;
          -webkit-text-fill-color: transparent;
          animation: shimmer 3s linear infinite;
        }

        .sys-quartz .pulse-dot {
          width: 8px; height: 8px;
          border-radius: 50%;
          background: var(--violet);
          box-shadow: 0 0 0 0 rgba(90, 58, 255, 0.5);
          animation: pulseDot 1.6s infinite;
        }
        @keyframes pulseDot {
          0% { box-shadow: 0 0 0 0 rgba(90, 58, 255, 0.5); }
          70% { box-shadow: 0 0 0 8px rgba(90, 58, 255, 0); }
          100% { box-shadow: 0 0 0 0 rgba(90, 58, 255, 0); }
        }
      `}</style>

      <SystemHeader
        code="D · QUARTZ · 晶"
        name="Spire"
        cn="晶宇"
        tagline={<>A tender, drafted with you. <em>Lit from within by AI.</em></>}
        philosophy={(
          <>
            <p style={{ margin: 0 }}>这套语言把 AI 的"在场感"当成第一类公民:智能体写作的瞬间、引用的瞬间、合规校验的瞬间——都被一种温柔的紫红光晕标记出来。其他时候,界面是克制的浅色 SaaS,让用户拥有完全的视觉空间。</p>
            <p style={{ margin: "10px 0 0" }}>主色是 <span style={{ color: "var(--violet)", fontWeight: 500 }}>电气紫</span>,用在交互、链接、智能体署名;辅色是青(信任)与粉(智能瞬间)。所有渐变只出现在 AI 介入的位置 —— 不是装饰,是签名。</p>
          </>
        )}
      />

      <div style={{ height: 1, background: "var(--rule)", margin: "0 56px" }} />

      {/* Logo + Palette */}
      <section style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 40, padding: "32px 56px 12px" }}>
        <div>
          <MicroLabel>01 · Identity</MicroLabel>
          <div style={{ marginTop: 16, padding: "32px 24px", background: "white", borderRadius: 14, border: "1px solid var(--rule)", display: "flex", flexDirection: "column", alignItems: "center", boxShadow: "0 8px 32px -8px rgba(90, 58, 255, 0.12)" }}>
            <div style={{ width: 72, height: 72, borderRadius: 20, background: "var(--grad-ai-edge)", display: "grid", placeItems: "center", boxShadow: "0 12px 32px -8px rgba(90, 58, 255, 0.5)" }}>
              <div className="italic-serif" style={{ fontSize: 50, color: "white", fontWeight: 400, lineHeight: 1 }}>s</div>
            </div>
            <div className="italic-serif" style={{ fontSize: 38, color: "var(--ink)", marginTop: 16, fontWeight: 400, letterSpacing: "-0.02em" }}>Spire <span style={{ color: "var(--violet)", fontStyle: "italic" }}>晶宇</span></div>
            <div className="mono" style={{ fontSize: 10, color: "var(--muted)", marginTop: 6, letterSpacing: "0.18em", textTransform: "uppercase" }}>AI · TENDER · WORKBENCH</div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 10 }}>
            <div style={{ background: "var(--violet-soft)", padding: 14, textAlign: "center", borderRadius: 10 }}>
              <div className="italic-serif" style={{ fontSize: 28, color: "var(--violet)", fontWeight: 400, lineHeight: 1 }}>s</div>
              <div className="mono" style={{ fontSize: 9, color: "var(--violet-deep)", marginTop: 4, letterSpacing: "0.1em" }}>SOFT</div>
            </div>
            <div style={{ background: "var(--grad-ai-edge)", padding: 14, textAlign: "center", borderRadius: 10 }}>
              <div className="italic-serif" style={{ fontSize: 28, color: "white", fontWeight: 400, lineHeight: 1 }}>s</div>
              <div className="mono" style={{ fontSize: 9, color: "white", marginTop: 4, letterSpacing: "0.1em", opacity: 0.8 }}>GRAD</div>
            </div>
            <div style={{ background: "var(--ink)", padding: 14, textAlign: "center", borderRadius: 10 }}>
              <div className="italic-serif" style={{ fontSize: 28, color: "white", fontWeight: 400, lineHeight: 1 }}>s</div>
              <div className="mono" style={{ fontSize: 9, color: "var(--faint)", marginTop: 4, letterSpacing: "0.1em" }}>INK</div>
            </div>
          </div>
        </div>

        <div>
          <MicroLabel>02 · Palette</MicroLabel>
          <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr 1fr 1fr 1fr 1fr", gap: 0, marginTop: 16, borderRadius: 14, overflow: "hidden", border: "1px solid var(--rule)" }}>
            <div style={{ background: "var(--grad-ai)", color: "white", padding: "16px 14px", display: "flex", flexDirection: "column", justifyContent: "space-between", minHeight: 116 }}>
              <div style={{ fontSize: 11, opacity: 0.85, letterSpacing: "0.04em", textTransform: "uppercase" }}>AI · 智能体瞬间</div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>Gradient</div>
                <div className="mono" style={{ fontSize: 10.5, opacity: 0.8, marginTop: 2 }}>5A3AFF → FF7AB4</div>
              </div>
            </div>
            <Swatch variant="flat" color="var(--violet)" name="Violet" hex="#5A3AFF" role="primary" textColor="white" height={116} />
            <Swatch variant="flat" color="var(--cyan)" name="Cyan" hex="#0AA5B8" role="trust" textColor="white" height={116} />
            <Swatch variant="flat" color="var(--pink)" name="Pink" hex="#FF5D8F" role="spark" textColor="white" height={116} />
            <Swatch variant="flat" color="var(--jade)" name="Jade" hex="#14A06A" role="pass" textColor="white" height={116} />
            <Swatch variant="flat" color="var(--ink)" name="Ink" hex="#0E0D1A" role="text" textColor="white" height={116} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 0, marginTop: 12, borderRadius: 14, overflow: "hidden", border: "1px solid var(--rule)" }}>
            <Swatch variant="flat" color="var(--bg)" name="bg" hex="#F7F7FB" role="canvas" textColor="var(--ink)" height={64} />
            <Swatch variant="flat" color="var(--surface-2)" name="surface 2" hex="#F1F2F8" role="card 2" textColor="var(--ink)" height={64} />
            <Swatch variant="flat" color="var(--violet-soft)" name="violet 5" hex="#ECE7FF" role="AI bg" textColor="var(--violet-deep)" height={64} />
            <Swatch variant="flat" color="var(--cyan-soft)" name="cyan 5" hex="#D5F1F4" role="trust bg" textColor="var(--cyan)" height={64} />
            <Swatch variant="flat" color="var(--pink-soft)" name="pink 5" hex="#FFE1EA" role="spark bg" textColor="var(--pink)" height={64} />
            <Swatch variant="flat" color="var(--rule)" name="rule" hex="#E6E6EF" role="border" textColor="var(--ink-2)" height={64} />
          </div>
        </div>
      </section>

      {/* Typography */}
      <Block caption="03 · Typography" title="Geist sans-everywhere, Instrument Serif for grace notes">
        <TypeRow
          label="DISPLAY"
          meta={<>Geist · 600<br/>86 · -0.04 · grad fill</>}
          sample={(
            <div style={{ display: "flex", alignItems: "baseline", gap: 18 }}>
              <span style={{ fontFamily: "var(--font-display)", fontWeight: 600, fontSize: 64, letterSpacing: "-0.04em", lineHeight: 0.95, background: "var(--grad-ai-edge)", WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent" }}>Lit.</span>
              <span className="italic-serif" style={{ fontSize: 50, color: "var(--ink-2)", lineHeight: 1 }}>by AI</span>
            </div>
          )}
        />
        <TypeRow
          label="HEAD"
          meta={<>Geist · 600<br/>28 · -0.02</>}
          sample={(
            <div>
              <div className="mono" style={{ fontSize: 11, color: "var(--violet)", letterSpacing: "0.12em", textTransform: "uppercase", fontWeight: 500 }}>§ 4.2</div>
              <div style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em", color: "var(--ink)", marginTop: 4 }}>液冷子系统 · 自然冷却 5,840 h / 年</div>
            </div>
          )}
        />
        <TypeRow
          label="BODY"
          meta={<>Geist + PingFang<br/>400 · 14.5 · 1.7</>}
          sample={<p style={{ fontSize: 14.5, lineHeight: 1.7, margin: 0, color: "var(--ink)", maxWidth: 620 }}>系统遵循 N+1 冗余设计,关键管路采用双路独立环网。冷却液采用专利单相氟化液,20 年内泄漏概率 <span style={{ color: "var(--violet)", fontWeight: 500 }}>&lt; 0.01%</span>。</p>}
        />
        <TypeRow
          label="ITALIC · 高光"
          meta={<>Instrument Serif<br/>Italic · 28 · grace note</>}
          sample={<div className="italic-serif" style={{ fontSize: 26, color: "var(--ink-2)", letterSpacing: "0.005em" }}>…and the agent <span style={{ color: "var(--violet)" }}>thought about it</span> for 2.3 seconds.</div>}
        />
        <TypeRow
          label="MONO · 元数据"
          meta={<>Geist Mono<br/>500 · 11 · tabular</>}
          sample={<div className="mono" style={{ fontSize: 11, letterSpacing: "0.04em", color: "var(--muted)" }}>P-2025-0712 <span style={{ color: "var(--violet)" }}>·</span> CITED 14× <span style={{ color: "var(--violet)" }}>·</span> 2.3 S <span style={{ color: "var(--violet)" }}>·</span> 6 D 21 H LEFT</div>}
        />
      </Block>

      {/* Components */}
      <Block caption="04 · Components" title="Soft surfaces, gradient signatures for AI">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          <div className="ds-card">
            <div className="mono" style={{ fontSize: 10, color: "var(--violet)", marginBottom: 12, letterSpacing: "0.14em", textTransform: "uppercase", fontWeight: 500 }}>buttons</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              <button className="btn btn-grad">{I.sparkle} 让智能体改写</button>
              <button className="btn btn-violet">{I.arrow} 导出</button>
              <button className="btn btn-secondary">分享</button>
              <button className="btn btn-ghost">取消</button>
            </div>
            <div style={{ marginTop: 12 }}>
              <input className="input" defaultValue="向智能体描述这一节的重点…" style={{ width: "100%", boxSizing: "border-box" }} />
            </div>
          </div>
          <div className="ds-card">
            <div className="mono" style={{ fontSize: 10, color: "var(--violet)", marginBottom: 12, letterSpacing: "0.14em", textTransform: "uppercase", fontWeight: 500 }}>badges</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              <span className="badge badge-grad">{I.sparkle} AI 撰写中</span>
              <span className="badge badge-violet">智能体批注</span>
              <span className="badge badge-jade">{I.check} 合规</span>
              <span className="badge badge-cyan">交叉引用</span>
              <span className="badge badge-pink">高频被引</span>
              <span className="badge badge-neutral">草稿</span>
            </div>
            <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--rule)" }}>
              <div className="mono" style={{ fontSize: 10, color: "var(--muted)", marginBottom: 6, letterSpacing: "0.06em" }}>STATUS DOT</div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span className="pulse-dot" />
                <span style={{ fontSize: 12.5 }}>智能体正在撰写 § 4.2</span>
              </div>
            </div>
          </div>
          <div className="ds-card-ai">
            <div className="mono" style={{ fontSize: 10, color: "var(--violet)", marginBottom: 8, letterSpacing: "0.14em", textTransform: "uppercase", fontWeight: 600 }}>{I.sparkle} AI MOMENT · 智能体卡</div>
            <div style={{ fontSize: 13.5, color: "var(--ink)", lineHeight: 1.6, fontWeight: 500 }}>建议:把张江二期 PUE 1.184 提到段首,并把 87% 相似度具象化为对比表。</div>
            <div style={{ display: "flex", gap: 6, marginTop: 12 }}>
              <button className="btn btn-grad" style={{ fontSize: 11.5, padding: "6px 12px" }}>采纳</button>
              <button className="btn btn-secondary" style={{ fontSize: 11.5, padding: "6px 12px" }}>看 diff</button>
              <button className="btn btn-ghost" style={{ fontSize: 11.5, padding: "6px 8px" }}>忽略</button>
            </div>
          </div>
        </div>
      </Block>

      {/* UI Preview */}
      <Block caption="05 · Applied" title="工作台 · live AI 协作" style={{ paddingBottom: 36 }}>
        <div style={{ background: "white", border: "1px solid var(--rule)", overflow: "hidden", borderRadius: 16, boxShadow: "0 24px 60px -24px rgba(14, 13, 26, 0.18)" }}>
          <div className="doc-topbar">
            <div className="wordmark">
              <div className="wordmark-glyph">s</div>
              <span className="italic-serif" style={{ fontSize: 22 }}>Spire</span>
            </div>
            <div style={{ width: 1, height: 16, background: "var(--rule)" }} />
            <div style={{ fontSize: 12.5, color: "var(--muted)" }}>2026 年度项目 <span style={{ margin: "0 4px", opacity: 0.5 }}>›</span> <span style={{ color: "var(--ink)", fontWeight: 500 }}>华东数据中心绿色改造工程</span></div>
            <div style={{ flex: 1 }} />
            <div style={{ display: "flex", gap: 4, fontSize: 12.5, color: "var(--muted)" }}>
              <span style={{ padding: "5px 10px", color: "var(--ink)", background: "var(--surface-2)", borderRadius: 7, fontWeight: 500 }}>撰写</span>
              <span style={{ padding: "5px 10px" }}>预览</span>
              <span style={{ padding: "5px 10px" }}>知识库</span>
            </div>
            <button className="btn btn-grad" style={{ fontSize: 12, padding: "7px 14px", marginLeft: 8 }}>{I.sparkle} 导出 · PDF / A</button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "440px 1fr", minHeight: 580 }}>
            {/* agent stream */}
            <div style={{ borderRight: "1px solid var(--rule)", background: "var(--surface-2)", padding: "20px 22px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span className="pulse-dot" />
                <span className="mono" style={{ fontSize: 10.5, color: "var(--violet)", letterSpacing: "0.12em", fontWeight: 500, textTransform: "uppercase" }}>AGENT · STEP 04 / 06</span>
                <span style={{ marginLeft: "auto", color: "var(--muted)", fontSize: 11, fontFamily: "var(--font-mono)" }}>01:14</span>
              </div>
              <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.01em", marginTop: 10, color: "var(--ink)" }}>撰写 4.2 液冷子系统 <span className="italic-serif" style={{ color: "var(--violet)", fontStyle: "italic", fontWeight: 400, fontSize: 20 }}>—— still drafting…</span></div>

              <div style={{ marginTop: 14, display: "flex", flexWrap: "wrap", gap: 6 }}>
                <span className="badge badge-grad">{I.sparkle} 写入文档</span>
                <span className="badge badge-violet">依据 招标+3份资料</span>
                <span className="badge badge-cyan">下一步 校对 PUE/WUE</span>
              </div>

              {/* agent turn with reasoning glow */}
              <div style={{ marginTop: 22 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ width: 22, height: 22, borderRadius: 7, background: "var(--grad-ai-edge)", display: "grid", placeItems: "center", color: "white" }}><span className="italic-serif" style={{ fontSize: 14, lineHeight: 1 }}>s</span></div>
                  <span className="mono" style={{ fontSize: 11 }}><span className="shimmer-text" style={{ fontWeight: 600 }}>Spire</span> <span style={{ color: "var(--muted)" }}>· 09:42</span></span>
                </div>
                <p style={{ fontSize: 13.5, lineHeight: 1.65, margin: "8px 0 0 30px", color: "var(--ink)" }}>已锁定 § 4。优先采用<b>上海张江二期</b>(气候相似 87%,时间最近)。</p>

                {/* reasoning */}
                <div style={{ margin: "10px 0 0 30px", padding: "10px 12px", background: "var(--grad-ai-soft)", borderRadius: 10, position: "relative" }}>
                  <div className="mono" style={{ fontSize: 9.5, color: "var(--violet)", letterSpacing: "0.14em", textTransform: "uppercase", fontWeight: 600 }}>thinking · 2.3s</div>
                  <div className="italic-serif" style={{ fontSize: 13.5, color: "var(--violet-deep)", lineHeight: 1.55, marginTop: 4, fontStyle: "italic" }}>张江二期时间最近,与华东电网有过运维协同,气候相似度最高,首选这条线。</div>
                </div>

                {/* tool calls */}
                <div style={{ margin: "10px 0 0 30px" }}>
                  {[
                    [<>{I.search} 检索知识库</>, "命中 4 个项目", "2.3s", false],
                    [<>{I.doc} 读取 tender_doc.pdf</>, "§36–§42 · 19 条规范", "1.1s", false],
                    [<>{I.sparkle} 撰写 § 4.2</>, "实时输出至右侧文档", "running…", true],
                  ].map(([n, r, t, run], i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 12px", marginTop: 6, background: run ? "var(--violet-soft)" : "white", borderRadius: 10, border: run ? "1px solid transparent" : "1px solid var(--rule-2)", position: "relative" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, color: run ? "var(--violet)" : "var(--ink-2)" }}>
                        <span style={{ width: 13, height: 13, display: "grid", placeItems: "center" }}>{n}</span>
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 12, color: "var(--ink)" }}>{n}</div>
                        <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 1, fontFamily: "var(--font-mono)" }}>{r}</div>
                      </div>
                      <span className="mono" style={{ fontSize: 10.5, color: run ? "var(--violet)" : "var(--muted)", fontWeight: run ? 600 : 400 }}>{t}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* doc page */}
            <div style={{ background: "white", padding: "22px 36px 24px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="badge badge-grad">{I.sparkle} 智能体撰写中</span>
                  <span className="badge badge-jade">{I.check} 招标 19/19 已响应</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted)" }}>
                  <span>p. 42 / 78</span>
                  <span style={{ width: 4, height: 4, borderRadius: 2, background: "var(--jade)" }} />
                  <span>已保存 · 2 秒前</span>
                </div>
              </div>

              <div style={{ marginTop: 20 }}>
                <div className="mono" style={{ fontSize: 11, color: "var(--violet)", letterSpacing: "0.14em", textTransform: "uppercase", fontWeight: 500 }}>§ 4 · CHAPTER FOUR</div>
                <h1 style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.025em", margin: "6px 0 0", lineHeight: 1.2 }}>绿色技术方案 <span className="italic-serif" style={{ color: "var(--violet)", fontStyle: "italic", fontWeight: 400, fontSize: 24 }}>Green Engineering</span></h1>
                <p style={{ marginTop: 8, color: "var(--muted)", fontSize: 13.5, maxWidth: 580, lineHeight: 1.55 }}>对应招标 §36–§58。围绕 PUE / WUE / 可再生能源占比,结合华东项目落地经验。</p>
              </div>

              <div style={{ borderTop: "1px solid var(--rule)", marginTop: 22, paddingTop: 22 }}>
                <h2 style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.01em", margin: 0, color: "var(--ink)" }}>4.2 液冷子系统</h2>
                <p style={{ fontSize: 14.5, lineHeight: 1.75, margin: "10px 0 0", color: "var(--ink)" }}>
                  液冷子系统采用<b>冷板式液冷 + 25℃ 高温冷冻水</b>方案,可在华东地区年均 <b>5,840</b> 小时实现自然冷却<span className="mono" style={{ background: "var(--violet-soft)", color: "var(--violet)", padding: "0px 5px", borderRadius: 4, fontSize: 9.5, marginLeft: 2 }}>R-07</span>,相较传统压缩制冷节能约 <b style={{ color: "var(--violet)" }}>38%</b>。N+1 冗余,关键管路双路独立环网<span className="mono" style={{ background: "var(--violet-soft)", color: "var(--violet)", padding: "0px 5px", borderRadius: 4, fontSize: 9.5, marginLeft: 2 }}>T-42.3</span>。
                </p>

                {/* AI insight inline */}
                <div className="ds-card-ai" style={{ marginTop: 16, padding: "12px 16px", display: "flex", gap: 12, alignItems: "flex-start" }}>
                  <div style={{ width: 24, height: 24, borderRadius: 7, background: "var(--grad-ai-edge)", display: "grid", placeItems: "center", color: "white", flexShrink: 0, marginTop: 1 }}>
                    {I.sparkle}
                  </div>
                  <div>
                    <div className="mono" style={{ fontSize: 10, color: "var(--violet)", letterSpacing: "0.12em", textTransform: "uppercase", fontWeight: 600 }}>Spire 建议 · 2.3s</div>
                    <div style={{ fontSize: 13, color: "var(--ink)", marginTop: 4, lineHeight: 1.55 }}>把 <b>张江二期 PUE 1.184</b> 提到段首,并把 87% 相似度具象成关键指标对照。</div>
                  </div>
                  <div style={{ display: "flex", gap: 6, marginLeft: "auto" }}>
                    <button className="btn btn-grad" style={{ fontSize: 11, padding: "5px 11px" }}>采纳</button>
                    <button className="btn btn-secondary" style={{ fontSize: 11, padding: "5px 11px" }}>diff</button>
                  </div>
                </div>

                <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
                  {[
                    ["PUE", "≤1.18", "招标 1.25"],
                    ["WUE", "≤0.32", "招标 0.5"],
                    ["再生能源", "≥35%", "招标 30%"],
                    ["余热回收", "≥60%", "增项"],
                  ].map((r, i) => (
                    <div key={i} style={{ padding: "10px 12px", background: "var(--surface-2)", borderRadius: 10 }}>
                      <div className="mono" style={{ fontSize: 9.5, color: "var(--muted)", letterSpacing: "0.08em", textTransform: "uppercase" }}>{r[0]}</div>
                      <div style={{ fontSize: 19, fontWeight: 600, letterSpacing: "-0.02em", marginTop: 2, color: "var(--ink)" }}>{r[1]}</div>
                      <div style={{ fontSize: 10.5, color: "var(--jade)", marginTop: 1, fontFamily: "var(--font-mono)" }}>{r[2]} · 优于<span className="shimmer-text" style={{ marginLeft: 4 }}>{i === 0 ? "▍" : ""}</span></div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", padding: "12px 18px", borderTop: "1px solid var(--rule)", background: "var(--surface-2)", fontSize: 11.5, color: "var(--muted)" }}>
            <span className="mono">{I.clock}<span style={{ marginLeft: 4 }}>2.3 s · 3 tools used</span></span>
            <span style={{ margin: "0 12px", opacity: 0.4 }}>·</span>
            <span>本会话已节省约 <b style={{ color: "var(--violet)" }}>4 小时</b></span>
            <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6, color: "var(--pink)", fontWeight: 500 }}>截标 05-12 17:00 · 剩余 6 天 21 时</span>
          </div>
        </div>
      </Block>
    </SystemPage>
  );
}

window.QuartzSystem = QuartzSystem;
