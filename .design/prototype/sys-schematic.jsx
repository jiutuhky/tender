// sys-schematic.jsx — C · Schematic · 蓝图
// Philosophy: 标书是精密工程,每个数字都要溯源。
// Mono-first display, grid lines, dimension annotations, blueprint aesthetic.
// Inspired by IBM Carbon, technical drawings, spec sheets, terminal UIs.

function SchematicSystem() {
  return (
    <SystemPage className="sys-schematic">
      <style>{`
        .sys-schematic {
          --bg: #eef2f5;
          --paper: #f7f9fb;
          --surface: #ffffff;
          --grid: rgba(20, 45, 80, 0.06);
          --grid-strong: rgba(20, 45, 80, 0.12);
          --ink: #0e1a2b;
          --ink-2: #2d3e55;
          --muted: #6a7a8e;
          --faint: #a3acba;
          --rule: #d2dae3;
          --rule-2: #e2e7ed;

          --cyan: #0f6ad6;
          --cyan-bright: #1d8af0;
          --cyan-soft: #d6e9fb;
          --amber: #cf8200;
          --amber-soft: #fae6c2;
          --jade: #1d8c5c;
          --jade-soft: #c8eadb;
          --crimson: #d2353a;
          --crimson-soft: #f8d8d9;

          --graphite: #131c2a;
          --graphite-2: #1e2a3e;

          --font-display: "IBM Plex Mono", "Geist Mono", ui-monospace, monospace;
          --font-body: "IBM Plex Sans", "IBM Plex Sans SC", "PingFang SC", system-ui, sans-serif;
          --font-ui: "IBM Plex Sans", "IBM Plex Sans SC", "PingFang SC", system-ui, sans-serif;
          --font-mono: "IBM Plex Mono", "Geist Mono", ui-monospace, monospace;

          background: var(--bg);
          color: var(--ink);
          font-family: var(--font-ui);
          background-image:
            linear-gradient(to right, var(--grid) 1px, transparent 1px),
            linear-gradient(to bottom, var(--grid) 1px, transparent 1px);
          background-size: 16px 16px;
        }
        .sys-schematic .mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }

        /* header */
        .sys-schematic .sys-header { position: relative; }
        .sys-schematic .sys-code {
          font-family: var(--font-mono);
          font-size: 11px;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: var(--cyan);
          font-weight: 500;
        }
        .sys-schematic .sys-name {
          font-family: var(--font-mono);
          font-size: 80px;
          line-height: 0.92;
          letter-spacing: -0.04em;
          font-weight: 600;
          color: var(--ink);
        }
        .sys-schematic .sys-cn {
          font-family: var(--font-display);
          font-size: 56px;
          font-weight: 500;
          letter-spacing: 0.02em;
          color: var(--cyan);
        }
        .sys-schematic .sys-tagline {
          font-family: var(--font-mono);
          font-size: 18px;
          font-weight: 400;
          letter-spacing: -0.005em;
          color: var(--ink-2);
        }
        .sys-schematic .sys-philosophy {
          font-family: var(--font-body);
          font-size: 14.5px;
          line-height: 1.7;
          color: var(--ink-2);
          column-count: 2;
          column-gap: 36px;
        }
        .sys-schematic .block-caption-label {
          font-family: var(--font-mono);
          font-size: 10px;
          letter-spacing: 0.18em;
          text-transform: uppercase;
          color: var(--cyan);
          font-weight: 500;
        }
        .sys-schematic .block-caption-title {
          font-family: var(--font-mono);
          font-size: 18px;
          font-weight: 500;
          color: var(--ink);
          letter-spacing: -0.01em;
        }

        /* dimension line — characteristic blueprint annotation */
        .sys-schematic .dim {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          font-family: var(--font-mono);
          font-size: 10px;
          color: var(--cyan);
          letter-spacing: 0.04em;
        }
        .sys-schematic .dim::before, .sys-schematic .dim::after {
          content: ""; width: 22px; height: 1px; background: var(--cyan); position: relative;
        }
        .sys-schematic .dim::before { box-shadow: 0 -3px 0 -2.5px var(--cyan), 0 3px 0 -2.5px var(--cyan); }
        .sys-schematic .dim::after { box-shadow: 0 -3px 0 -2.5px var(--cyan), 0 3px 0 -2.5px var(--cyan); }

        /* buttons */
        .sys-schematic .btn {
          font-family: var(--font-mono);
          font-size: 12px;
          font-weight: 500;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 8px 14px;
          border: 1px solid transparent;
          cursor: default;
          letter-spacing: -0.005em;
          border-radius: 2px;
        }
        .sys-schematic .btn svg { width: 13px; height: 13px; }
        .sys-schematic .btn-primary { background: var(--ink); color: var(--paper); }
        .sys-schematic .btn-cyan { background: var(--cyan); color: white; }
        .sys-schematic .btn-secondary { background: var(--paper); color: var(--ink); border-color: var(--ink); }
        .sys-schematic .btn-ghost { background: transparent; color: var(--ink-2); border-color: var(--rule); }

        /* input */
        .sys-schematic .input {
          font-family: var(--font-mono);
          font-size: 12.5px;
          padding: 9px 12px;
          border: 1px solid var(--rule);
          background: var(--paper);
          color: var(--ink);
          border-radius: 2px;
        }

        /* badges */
        .sys-schematic .badge {
          font-family: var(--font-mono);
          font-size: 11px;
          font-weight: 500;
          padding: 2px 8px;
          letter-spacing: 0.02em;
          display: inline-flex;
          align-items: center;
          gap: 5px;
          border-radius: 2px;
          border: 1px solid currentColor;
        }
        .sys-schematic .badge-cyan { color: var(--cyan); background: var(--cyan-soft); border-color: transparent; }
        .sys-schematic .badge-amber { color: var(--amber); background: var(--amber-soft); border-color: transparent; }
        .sys-schematic .badge-jade { color: var(--jade); background: var(--jade-soft); border-color: transparent; }
        .sys-schematic .badge-crimson { color: var(--crimson); background: var(--crimson-soft); border-color: transparent; }
        .sys-schematic .badge-outline { border-color: var(--rule); color: var(--ink-2); background: var(--paper); }

        /* card with corner crosshair marks */
        .sys-schematic .ds-card {
          background: var(--paper);
          border: 1px solid var(--rule);
          padding: 18px 22px;
          border-radius: 2px;
          position: relative;
        }
        .sys-schematic .ds-card::before, .sys-schematic .ds-card::after {
          content: "";
          position: absolute;
          width: 8px; height: 8px;
          border: 1px solid var(--cyan);
        }
        .sys-schematic .ds-card::before { top: -1px; left: -1px; border-right: 0; border-bottom: 0; }
        .sys-schematic .ds-card::after { bottom: -1px; right: -1px; border-left: 0; border-top: 0; }

        /* doc shell */
        .sys-schematic .doc-topbar {
          display: flex;
          align-items: center;
          padding: 0 18px;
          height: 44px;
          background: var(--graphite);
          color: white;
          gap: 16px;
        }
        .sys-schematic .wordmark {
          font-family: var(--font-mono);
          font-weight: 600;
          font-size: 16px;
          letter-spacing: -0.02em;
        }
        .sys-schematic .wordmark-cyan { color: var(--cyan-bright); }

        /* terminal — dark surface */
        .sys-schematic .terminal {
          background: var(--graphite);
          color: #d2e0f0;
          font-family: var(--font-mono);
          padding: 12px 14px;
          font-size: 11.5px;
          line-height: 1.65;
          border-radius: 2px;
        }
        .sys-schematic .terminal .ok { color: var(--jade-soft); }
        .sys-schematic .terminal .warn { color: #f4c469; }
        .sys-schematic .terminal .info { color: #79b8f8; }
        .sys-schematic .terminal .muted-dark { color: #6a7a8e; }
      `}</style>

      <SystemHeader
        code="C · SCHEMATIC — 蓝图"
        name="Datum"
        cn="基线"
        tagline="bid := compile(spec, evidence) — typed, traced, reproducible."
        philosophy={(
          <>
            <p style={{ margin: 0 }}>把标书当作精密工程产物来交付——每个数字、每个承诺都有溯源,每条偏离都有标注。等宽字体是显示字体,因为每一位数字都被对齐查验;蓝色是结构色,呼应工程图中的尺寸标注与剖面线。</p>
            <p style={{ margin: "10px 0 0" }}>整套语言对"数据的精度"有偏执:表格使用绷紧的栅格;输入框带刻度线;批注像 CAD 中的引出线一样指向具体位置。智能体不是一个对话框,而是一个 <span className="mono" style={{ color: "var(--cyan)" }}>$ tender --compile</span> 命令——所有动作都被记入可审计的执行流。</p>
          </>
        )}
      />

      <div style={{ height: 1, background: "var(--ink)", margin: "0 56px", boxShadow: "0 4px 0 -3px var(--ink)" }} />

      {/* Logo + Palette + grid */}
      <section style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 40, padding: "32px 56px 12px" }}>
        <div>
          <MicroLabel>01 — Identity</MicroLabel>
          <div style={{ marginTop: 16, padding: "26px 22px", background: "var(--paper)", border: "1px solid var(--rule)", position: "relative" }}>
            <div style={{ position: "absolute", top: 8, left: 8, fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--cyan)" }}>0,0</div>
            <div style={{ position: "absolute", top: 8, right: 8, fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--cyan)" }}>240,140</div>
            <div className="mono" style={{ fontSize: 58, fontWeight: 600, letterSpacing: "-0.05em", color: "var(--ink)", lineHeight: 1 }}>
              datum<span style={{ color: "var(--cyan)" }}>·</span>
            </div>
            <div className="mono" style={{ fontSize: 10, color: "var(--muted)", marginTop: 10, letterSpacing: "0.18em", textTransform: "uppercase" }}>v 2.6.0 · TENDER COMPILER</div>

            {/* dimension lines */}
            <svg style={{ position: "absolute", left: -22, top: 26, height: "calc(100% - 52px)" }} width="20" viewBox="0 0 20 100" preserveAspectRatio="none">
              <line x1="10" y1="0" x2="10" y2="100" stroke="var(--cyan)" strokeWidth="0.5" />
              <line x1="6" y1="0" x2="14" y2="0" stroke="var(--cyan)" strokeWidth="0.7" />
              <line x1="6" y1="100" x2="14" y2="100" stroke="var(--cyan)" strokeWidth="0.7" />
            </svg>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 8 }}>
            <div style={{ background: "var(--paper)", border: "1px solid var(--rule)", padding: 12, textAlign: "center", borderRadius: 2 }}>
              <div className="mono" style={{ fontSize: 28, fontWeight: 600, color: "var(--cyan)", letterSpacing: "-0.04em" }}>{`{ d }`}</div>
              <div className="mono" style={{ fontSize: 9, color: "var(--muted)", marginTop: 4, letterSpacing: "0.1em" }}>GLYPH · SVG</div>
            </div>
            <div style={{ background: "var(--graphite)", padding: 12, textAlign: "center", borderRadius: 2 }}>
              <div className="mono" style={{ fontSize: 28, fontWeight: 600, color: "var(--cyan-bright)", letterSpacing: "-0.05em" }}>datum</div>
              <div className="mono" style={{ fontSize: 9, color: "#6a7a8e", marginTop: 4, letterSpacing: "0.1em" }}>DARK · MONO</div>
            </div>
          </div>
        </div>

        <div>
          <MicroLabel>02 — Palette · oklch tokens</MicroLabel>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 0, marginTop: 16, border: "1px solid var(--ink)" }}>
            <Swatch variant="flat" color="var(--ink)" name="ink" hex="#0E1A2B" role="primary" textColor="white" height={108} />
            <Swatch variant="flat" color="var(--ink-2)" name="ink-2" hex="#2D3E55" role="secondary" textColor="white" height={108} />
            <Swatch variant="flat" color="var(--cyan)" name="cyan" hex="#0F6AD6" role="accent · trace" textColor="white" height={108} />
            <Swatch variant="flat" color="var(--amber)" name="amber" hex="#CF8200" role="warn" textColor="white" height={108} />
            <Swatch variant="flat" color="var(--jade)" name="jade" hex="#1D8C5C" role="pass" textColor="white" height={108} />
            <Swatch variant="flat" color="var(--crimson)" name="crimson" hex="#D2353A" role="fail · 扣分" textColor="white" height={108} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 0, marginTop: 12, border: "1px solid var(--rule)" }}>
            <Swatch variant="flat" color="var(--bg)" name="bg" hex="#EEF2F5" role="canvas" textColor="var(--ink)" height={64} />
            <Swatch variant="flat" color="var(--paper)" name="paper" hex="#F7F9FB" role="surface" textColor="var(--ink)" height={64} />
            <Swatch variant="flat" color="var(--cyan-soft)" name="cyan-5" hex="#D6E9FB" role="trace bg" textColor="var(--cyan)" height={64} />
            <Swatch variant="flat" color="var(--amber-soft)" name="amber-5" hex="#FAE6C2" role="warn bg" textColor="var(--amber)" height={64} />
            <Swatch variant="flat" color="var(--jade-soft)" name="jade-5" hex="#C8EADB" role="pass bg" textColor="var(--jade)" height={64} />
            <Swatch variant="flat" color="var(--crimson-soft)" name="crimson-5" hex="#F8D8D9" role="fail bg" textColor="var(--crimson)" height={64} />
          </div>
          <div style={{ marginTop: 12, fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted)", display: "flex", justifyContent: "space-between" }}>
            <span>OKLCH · WCAG AA on bg</span>
            <span style={{ color: "var(--cyan)" }}>trace.cyan = 0F6AD6 :: oklch(52% .19 245)</span>
          </div>
        </div>
      </section>

      {/* Typography */}
      <Block caption="03 — Typography" title="Mono-first display · variable Plex Sans body">
        <TypeRow
          label="DISPLAY · Mono"
          meta={<>IBM Plex Mono<br/>SemiBold · 80 · -0.04</>}
          sample={<div className="mono" style={{ fontSize: 64, fontWeight: 600, letterSpacing: "-0.05em", lineHeight: 0.95, color: "var(--ink)" }}>PUE&nbsp;=&nbsp;<span style={{ color: "var(--cyan)" }}>1.184</span></div>}
        />
        <TypeRow
          label="HEAD · Sans"
          meta={<>IBM Plex Sans · Plex Sans SC<br/>600 · 28 · -0.01</>}
          sample={(
            <div>
              <div className="mono" style={{ fontSize: 11, color: "var(--cyan)", letterSpacing: "0.16em", fontWeight: 500 }}>§ 4.2 / SUBSYSTEM</div>
              <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.01em", color: "var(--ink)", marginTop: 4 }}>液冷子系统 · Liquid Cooling</div>
            </div>
          )}
        />
        <TypeRow
          label="BODY"
          meta={<>Plex Sans · Plex Sans SC<br/>400 · 14 · 1.65</>}
          sample={<p style={{ fontSize: 14, lineHeight: 1.65, margin: 0, color: "var(--ink)", maxWidth: 620 }}>系统遵循 N+1 冗余设计,关键管路采用双路独立环网。冷却液采用专利单相氟化液,20 年内泄漏概率 <span className="mono">&lt; 0.01%</span>。</p>}
        />
        <TypeRow
          label="MONO · numeric"
          meta={<>IBM Plex Mono<br/>500 · 13 · tabular</>}
          sample={(
            <div className="mono" style={{ fontSize: 14, color: "var(--ink)", display: "grid", gridTemplateColumns: "auto auto auto auto", gap: "4px 22px" }}>
              <span>PUE</span><span style={{ color: "var(--jade)" }}>1.184</span><span>WUE</span><span style={{ color: "var(--jade)" }}>0.31</span>
              <span>RENEW</span><span style={{ color: "var(--jade)" }}>34.2%</span><span>HEAT</span><span style={{ color: "var(--amber)" }}>62%</span>
            </div>
          )}
        />
        <TypeRow
          label="LABEL · caps"
          meta={<>Plex Mono<br/>500 · 10 · +0.18 · UPPER</>}
          sample={<div className="mono" style={{ fontSize: 11, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--cyan)" }}>TRACE :: TENDER_DOC.PDF — P36 — § T-36 — REF R-07</div>}
        />
      </Block>

      {/* Components */}
      <Block caption="04 — Components" title="$ tender --compile · live trace UI">
        <div style={{ display: "grid", gridTemplateColumns: "1.1fr 0.9fr 1fr", gap: 16 }}>
          <div className="ds-card">
            <div className="mono" style={{ fontSize: 10, color: "var(--cyan)", marginBottom: 12, letterSpacing: "0.18em", textTransform: "uppercase", fontWeight: 500 }}>actions</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              <button className="btn btn-primary">$ compile</button>
              <button className="btn btn-cyan">{I.bolt} run trace</button>
              <button className="btn btn-secondary">--diff</button>
              <button className="btn btn-ghost">--abort</button>
            </div>
            <div style={{ marginTop: 14 }}>
              <input className="input" defaultValue="tender_doc.pdf --range 36..58" style={{ width: "100%", boxSizing: "border-box" }} />
            </div>
            <div className="mono" style={{ fontSize: 10, color: "var(--muted)", marginTop: 6, letterSpacing: "0.04em" }}>↩ enter · CMD+K palette</div>
          </div>
          <div className="ds-card">
            <div className="mono" style={{ fontSize: 10, color: "var(--cyan)", marginBottom: 12, letterSpacing: "0.18em", textTransform: "uppercase", fontWeight: 500 }}>signals</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              <span className="badge badge-cyan">RUNNING · 04/06</span>
              <span className="badge badge-jade">PASS · 19/19</span>
              <span className="badge badge-amber">WARN · 2 todo</span>
              <span className="badge badge-crimson">DEVIATE · 0</span>
              <span className="badge badge-outline">SAVED · 2s</span>
            </div>
            <div style={{ marginTop: 14, display: "flex", alignItems: "center", gap: 8 }}>
              <div className="dim">5,840 h / yr</div>
              <div className="mono" style={{ fontSize: 11, color: "var(--muted)" }}>natural-cool window</div>
            </div>
          </div>
          <div className="terminal">
            <div><span className="muted-dark">$</span> tender compile §4.2 --trace</div>
            <div><span className="info">[09:42]</span> load tender_doc.pdf <span className="ok">ok</span></div>
            <div><span className="info">[09:42]</span> kb.match liquid_cooling — <span className="ok">4 hits</span></div>
            <div><span className="info">[09:42]</span> select R-07 ZJ-2 · sim=87%</div>
            <div><span className="info">[09:43]</span> compose §4.2 — <span className="warn">running…</span></div>
            <div><span className="muted-dark">--&gt;</span> <span style={{ color: "#79b8f8" }}>stream → /doc/p42</span><span style={{ animation: "blink 1.1s infinite", color: "#79b8f8" }}>▍</span></div>
            <style>{`@keyframes blink { 50% { opacity: 0; } }`}</style>
          </div>
        </div>
      </Block>

      {/* UI Preview */}
      <Block caption="05 — Applied" title="workbench · live compile" style={{ paddingBottom: 36 }}>
        <div style={{ background: "var(--paper)", border: "1px solid var(--ink)", overflow: "hidden", borderRadius: 2 }}>
          <div className="doc-topbar">
            <div className="wordmark">datum<span className="wordmark-cyan">·</span></div>
            <div style={{ width: 1, height: 16, background: "rgba(255,255,255,0.2)" }} />
            <div className="mono" style={{ fontSize: 11.5, color: "#a8b5c8" }}>~/projects/east-china-dc/<span style={{ color: "var(--cyan-bright)" }}>tender.4.2.md</span></div>
            <div style={{ flex: 1 }} />
            <div className="mono" style={{ display: "flex", gap: 0, fontSize: 11.5 }}>
              <span style={{ padding: "6px 12px", color: "var(--cyan-bright)", borderBottom: "2px solid var(--cyan-bright)", marginBottom: -1 }}>workbench</span>
              <span style={{ padding: "6px 12px", color: "#a8b5c8" }}>preview</span>
              <span style={{ padding: "6px 12px", color: "#a8b5c8" }}>kb</span>
              <span style={{ padding: "6px 12px", color: "#a8b5c8" }}>diff</span>
            </div>
            <button className="btn btn-cyan" style={{ fontSize: 11, padding: "6px 12px", marginLeft: 8 }}>{I.bolt} $ ship</button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "440px 1fr", minHeight: 560 }}>
            {/* trace pane */}
            <div style={{ borderRight: "1px solid var(--rule)", background: "var(--bg)", display: "flex", flexDirection: "column" }}>
              <div style={{ padding: "10px 18px", borderBottom: "1px solid var(--rule)", display: "flex", alignItems: "center", gap: 10 }}>
                <div className="mono" style={{ fontSize: 10.5, color: "var(--cyan)", letterSpacing: "0.12em", fontWeight: 500 }}>● COMPILE / 04 / 06</div>
                <div style={{ flex: 1, height: 1, background: "var(--rule)" }} />
                <div className="mono" style={{ fontSize: 10.5, color: "var(--muted)" }}>01:14</div>
              </div>

              <div className="terminal" style={{ margin: "12px 14px 0", borderRadius: 2 }}>
                <div><span className="muted-dark">[09:42:11]</span> <span className="info">user</span> 开始 §4 撰写,招标 PUE≤1.25</div>
                <div><span className="muted-dark">[09:42:12]</span> <span className="info">agent</span> ack · 装载第 4 章</div>
                <div><span className="muted-dark">[09:42:14]</span> <span className="info">tool</span> kb.search liquid_cooling AND PUE&lt;1.25</div>
                <div style={{ paddingLeft: 18 }}>↳ <span className="ok">4 hits</span> · ZJ-2 · KD · SZ · HZ</div>
                <div><span className="muted-dark">[09:42:16]</span> <span className="info">reason</span> select ZJ-2 (recency, climate=87%)</div>
                <div><span className="muted-dark">[09:42:17]</span> <span className="info">tool</span> pdf.read tender_doc.pdf §36–§58</div>
                <div style={{ paddingLeft: 18 }}>↳ specs=19 · scoring=6 · penalty=3</div>
                <div><span className="muted-dark">[09:42:18]</span> <span className="info">agent</span> compose §4.2 → <span className="warn">running…</span></div>
              </div>

              <div style={{ padding: "16px 18px 8px" }}>
                <div className="mono" style={{ fontSize: 10, color: "var(--muted)", letterSpacing: "0.12em", textTransform: "uppercase" }}>EVIDENCE GRAPH</div>
                <div style={{ marginTop: 10, fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--ink-2)", lineHeight: 1.95 }}>
                  <div>§4.2 ── <span style={{ color: "var(--cyan)" }}>R-07</span> · ZJ-2 cert <span className="badge badge-jade" style={{ marginLeft: 4, fontSize: 10, padding: "1px 6px" }}>verified</span></div>
                  <div>    ├── <span style={{ color: "var(--cyan)" }}>T-36</span> · PUE clause</div>
                  <div>    ├── <span style={{ color: "var(--cyan)" }}>T-42.3</span> · redundancy clause</div>
                  <div>    └── <span style={{ color: "var(--cyan)" }}>W-02</span> · pump VFD whitepaper</div>
                </div>
              </div>

              <div style={{ marginTop: "auto", padding: "10px 18px", borderTop: "1px solid var(--rule)", display: "flex", alignItems: "center", gap: 10, fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--muted)" }}>
                <span style={{ width: 6, height: 6, borderRadius: 0, background: "var(--cyan)" }} />
                <span>$</span>
                <span style={{ color: "var(--ink)" }}>continue</span>
                <span style={{ marginLeft: "auto", color: "var(--faint)" }}>↵ run</span>
              </div>
            </div>

            {/* doc page with dimension marks */}
            <div style={{ background: "var(--paper)", padding: "20px 36px", position: "relative" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, color: "var(--muted)", fontFamily: "var(--font-mono)", fontSize: 10.5, letterSpacing: "0.06em" }}>
                <span style={{ color: "var(--cyan)" }}>§ 4.2</span>
                <span>/</span>
                <span>page 42 of 78</span>
                <span style={{ marginLeft: "auto", color: "var(--jade)" }}>● VALID · 0 unresolved refs</span>
              </div>

              <div style={{ marginTop: 14, padding: 18, background: "var(--surface)", border: "1px solid var(--rule)", position: "relative" }}>
                {/* dimension marks on left */}
                <div style={{ position: "absolute", left: -38, top: 8, fontFamily: "var(--font-mono)", fontSize: 9.5, color: "var(--cyan)" }}>L1</div>
                <div style={{ position: "absolute", left: -28, top: 0, bottom: 0, width: 1, background: "var(--cyan)", opacity: 0.35 }} />
                <div style={{ position: "absolute", left: -32, top: 6, width: 10, height: 1, background: "var(--cyan)" }} />
                <div style={{ position: "absolute", left: -32, bottom: 6, width: 10, height: 1, background: "var(--cyan)" }} />

                <div className="mono" style={{ fontSize: 26, fontWeight: 600, color: "var(--ink)", letterSpacing: "-0.02em", lineHeight: 1.15 }}>
                  4.2 液冷子系统 <span style={{ color: "var(--cyan)", fontSize: 16, fontWeight: 500 }}>/* liquid_cooling */</span>
                </div>

                <p style={{ fontSize: 13.5, lineHeight: 1.75, margin: "12px 0 0", color: "var(--ink)" }}>
                  采用 <span className="mono" style={{ background: "var(--cyan-soft)", color: "var(--cyan)", padding: "1px 6px", borderRadius: 2 }}>cold_plate + 25℃ HCHW</span> 方案,可在华东地区年均 <b className="mono">5,840 h</b> 实现自然冷却<sup className="mono" style={{ color: "var(--cyan)", fontSize: 9 }}>[R-07]</sup>,较传统压缩制冷节能 <b style={{ color: "var(--jade)" }}>−38%</b>。N+1 冗余,关键管路双路环网<sup className="mono" style={{ color: "var(--cyan)", fontSize: 9 }}>[T-42.3]</sup>。
                </p>

                {/* spec table */}
                <table style={{ width: "100%", marginTop: 16, borderCollapse: "collapse", fontSize: 12, fontFamily: "var(--font-mono)" }}>
                  <thead>
                    <tr style={{ background: "var(--bg)" }}>
                      <th style={{ textAlign: "left", padding: "6px 10px", fontWeight: 500, color: "var(--muted)", letterSpacing: "0.08em", fontSize: 10 }}>METRIC</th>
                      <th style={{ textAlign: "right", padding: "6px 10px", fontWeight: 500, color: "var(--muted)", letterSpacing: "0.08em", fontSize: 10 }}>SPEC</th>
                      <th style={{ textAlign: "right", padding: "6px 10px", fontWeight: 500, color: "var(--muted)", letterSpacing: "0.08em", fontSize: 10 }}>ZJ-2</th>
                      <th style={{ textAlign: "right", padding: "6px 10px", fontWeight: 500, color: "var(--muted)", letterSpacing: "0.08em", fontSize: 10 }}>COMMIT</th>
                      <th style={{ textAlign: "right", padding: "6px 10px", fontWeight: 500, color: "var(--muted)", letterSpacing: "0.08em", fontSize: 10 }}>Δ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ["pue.annual", "≤1.25", "1.184", "≤1.18", "−5.6%"],
                      ["wue.l_per_kwh", "≤0.5", "0.31", "≤0.32", "−36%"],
                      ["renewable.pct", "≥30", "34.2", "≥35", "+17%"],
                      ["heat.recover", "—", "62", "≥60", "new"],
                      ["redundancy", "N+1", "N+1", "N+1", "ok"],
                    ].map((r, i) => (
                      <tr key={i} style={{ borderTop: "1px solid var(--rule-2)" }}>
                        <td style={{ padding: "6px 10px", color: "var(--ink-2)" }}>{r[0]}</td>
                        <td style={{ padding: "6px 10px", textAlign: "right", color: "var(--muted)" }}>{r[1]}</td>
                        <td style={{ padding: "6px 10px", textAlign: "right" }}>{r[2]}</td>
                        <td style={{ padding: "6px 10px", textAlign: "right", color: "var(--ink)", fontWeight: 600 }}>{r[3]}</td>
                        <td style={{ padding: "6px 10px", textAlign: "right", color: r[4].startsWith("−") || r[4].startsWith("+") || r[4] === "new" ? "var(--jade)" : "var(--muted)", fontWeight: 500 }}>{r[4]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* trace callouts */}
                <div style={{ marginTop: 16, padding: "10px 12px", background: "var(--cyan-soft)", borderLeft: "3px solid var(--cyan)", display: "flex", gap: 12, alignItems: "flex-start", borderRadius: 2 }}>
                  <span className="mono" style={{ fontSize: 10, color: "var(--cyan)", fontWeight: 600, letterSpacing: "0.06em", flexShrink: 0 }}>// ANNOTATE</span>
                  <span style={{ fontSize: 12, color: "var(--ink)", lineHeight: 1.55 }}>所有指标已对照招标 §36–§38。下游消费节点 <span className="mono" style={{ color: "var(--cyan)" }}>§4.3 heat-recovery</span> 依赖本节 commit。</span>
                </div>
              </div>

              <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 14, fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--muted)" }}>
                <span style={{ color: "var(--cyan)" }}>✓ formatted</span>
                <span>·</span>
                <span style={{ color: "var(--cyan)" }}>✓ refs valid</span>
                <span>·</span>
                <span style={{ color: "var(--amber)" }}>⊕ §6.1 待生成</span>
                <span style={{ marginLeft: "auto" }}>1,284 chars · 0 diff</span>
              </div>
            </div>
          </div>
        </div>
      </Block>
    </SystemPage>
  );
}

window.SchematicSystem = SchematicSystem;
