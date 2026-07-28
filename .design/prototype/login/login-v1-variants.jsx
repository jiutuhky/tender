// V1A · Manuscript  |  V1B · Voices  |  V1C · Cover
// Three takes on the LEFT pane of the editorial login.
// References:
//   · Linear / Cursor    — product-moment manuscript framing  (V1A)
//   · Pitch / Superhuman — floating customer voices             (V1B)
//   · Arc / Things 3     — typographic poster / magazine cover  (V1C)
// All three keep the dark editorial stage, the clay accent, and the
// serif-headline / mono-eyebrow rhythm of the rest of Prose.


// ─────────────────────────────────────────────────────────────
// V1A · Manuscript
//   A real tender page floats in dark space, mid-edit.
//   Cursor blinking in the prose. Three AI margin notes fade in
//   one after another. A progress bar pulses at the page foot.
// ─────────────────────────────────────────────────────────────

const v1aStyles = `
.v1a-body {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 14px 0;
}
.v1a-glow {
  position: absolute;
  width: 580px; height: 580px;
  border-radius: 50%;
  background: radial-gradient(closest-side, rgba(217,119,87,0.12), transparent 65%);
  pointer-events: none;
  animation: v1a-glow 11s ease-in-out infinite;
}
@keyframes v1a-glow {
  0%,100% { opacity: 0.7; transform: scale(0.97); }
  50%     { opacity: 1;   transform: scale(1.06); }
}

.v1a-doc {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 28px;
  animation: v1a-rise 900ms cubic-bezier(.2,.7,.2,1) both;
}
@keyframes v1a-rise {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}

.v1a-page {
  width: 380px;
  background: #FAF9F5;
  color: #1a1816;
  border-radius: 3px;
  padding: 32px 36px 26px;
  position: relative;
  box-shadow:
    0 50px 100px -30px rgba(0,0,0,0.55),
    0 18px 40px -22px rgba(0,0,0,0.35),
    0 0 0 1px rgba(255,255,255,0.05);
  transform: rotate(-0.6deg);
}
.v1a-page-head {
  display: flex; justify-content: space-between; align-items: baseline;
  font-family: var(--font-mono);
  font-size: 9.5px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: oklch(54% 0.012 60);
  border-bottom: 1px solid oklch(90% 0.008 70);
  padding-bottom: 10px;
  margin-bottom: 20px;
}
.v1a-section-label {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--clay);
  margin-bottom: 8px;
}
.v1a-heading {
  font-family: var(--font-serif);
  font-style: normal;
  font-weight: 600;
  font-size: 18px;
  letter-spacing: -0.012em;
  color: oklch(20% 0.015 60);
  margin: 0 0 16px;
  line-height: 1.3;
}
.v1a-prose {
  font-family: var(--font-serif);
  font-weight: 400;
  font-size: 12.5px;
  line-height: 1.78;
  color: oklch(28% 0.015 60);
  margin: 0 0 12px;
  text-wrap: pretty;
}
.v1a-prose .mark {
  background: linear-gradient(transparent 60%, rgba(217,119,87,0.22) 60%);
  padding: 0 1px;
}
.v1a-cursor {
  display: inline-block;
  width: 2px;
  height: 14px;
  background: var(--clay);
  vertical-align: -2px;
  margin-left: 1px;
  animation: lgblink 1.1s steps(2) infinite;
}

.v1a-progress {
  position: absolute;
  bottom: 0; left: 0; right: 40%;
  height: 2px;
  background: var(--clay);
  border-bottom-left-radius: 3px;
  overflow: hidden;
}
.v1a-progress::after {
  content: "";
  position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.55), transparent);
  animation: v1a-shimmer 2.4s linear infinite;
}
@keyframes v1a-shimmer {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(160%); }
}

.v1a-margins {
  width: 170px;
  display: flex;
  flex-direction: column;
  gap: 28px;
  padding-top: 64px;
}
.v1a-margin {
  opacity: 0;
  animation: v1a-fade 700ms ease-out forwards;
}
.v1a-margin:nth-child(1) { animation-delay: 700ms; }
.v1a-margin:nth-child(2) { animation-delay: 1100ms; }
.v1a-margin:nth-child(3) { animation-delay: 1500ms; }
@keyframes v1a-fade {
  from { opacity: 0; transform: translateX(-6px); }
  to   { opacity: 1; transform: translateX(0); }
}
.v1a-margin-head {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--font-mono);
  font-size: 9.5px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--clay);
  margin-bottom: 6px;
}
.v1a-margin-head::before {
  content: "";
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--clay);
  box-shadow: 0 0 0 3px rgba(217,119,87,0.18);
}
.v1a-margin-body {
  color: var(--dark-fg-3);
  font-family: var(--font-sans);
  font-size: 11.5px;
  line-height: 1.55;
}
.v1a-margin-body strong { color: var(--dark-fg-2); font-weight: 500; }
`;

function V1ALeft() {
  return (
    <>
      <style>{v1aStyles}</style>
      <div className="v1-stage">
        <div className="v1-head">
          <span className="lg-brand">
            <span className="lg-brand-mark inverse">P</span>
            <span className="lg-wordmark inverse">
              Prose
              <span className="lg-pipe"></span>
              <span className="lg-wordmark-sub">智能标书</span>
            </span>
          </span>
          <span style={{fontFamily:'var(--font-mono)',fontSize:10.5,letterSpacing:'0.18em',textTransform:'uppercase',color:'var(--dark-fg-3)'}}>
            session · live
          </span>
        </div>

        <div className="v1a-body">
          <div className="v1a-glow"></div>
          <div className="v1a-doc">
            <div className="v1a-page">
              <div className="v1a-page-head">
                <span>华东数据中心 · 绿色改造</span>
                <span>p. 14 / 86</span>
              </div>

              <div className="v1a-section-label">§4.2 · 散热架构</div>
              <h3 className="v1a-heading">液冷子系统 — 混合架构设计</h3>

              <p className="v1a-prose">
                本项目机房整体冷却采用<span className="mark">板式冷板与间接蒸发自然冷却</span>的混合架构。在华东典型气候条件下,自然冷却时段可覆盖全年 68%,显著降低全年 PUE。
              </p>
              <p className="v1a-prose">
                冷板系统针对单机柜热密度大于 30kW 的高密区部署,通过近端 CDU 提供二次侧水温控制——<span className="v1a-cursor"></span>
              </p>

              <div className="v1a-progress"></div>
            </div>

            <div className="v1a-margins">
              <div className="v1a-margin">
                <div className="v1a-margin-head">Prose 建议</div>
                <div className="v1a-margin-body">引用 <strong>张江二期</strong> 实测数据 · PUE 1.18</div>
              </div>
              <div className="v1a-margin">
                <div className="v1a-margin-head">数据已核</div>
                <div className="v1a-margin-body">来源 <strong>气象局 2024 年报</strong></div>
              </div>
              <div className="v1a-margin">
                <div className="v1a-margin-head">待补充</div>
                <div className="v1a-margin-body">建议加入冗余度 <strong>N+1</strong> 说明</div>
              </div>
            </div>
          </div>
        </div>

        <div className="v1-stage-foot">
          <span className="v1-foot-mark">{I.sparkLogo(14)} 自动保存 · 14:32</span>
          <span>v2.4 · 2026 春</span>
        </div>
      </div>
    </>
  );
}


// ─────────────────────────────────────────────────────────────
// V1B · Voices
//   Three testimonial cards in a staggered stack, drifting slowly
//   on independent phases. The middle card is "active" — slightly
//   brighter, with a clay accent, and at full opacity. The other
//   two recede into the dark.
// ─────────────────────────────────────────────────────────────

const v1bStyles = `
.v1b-body {
  flex: 1;
  position: relative;
  display: grid;
  place-items: center;
  padding: 8px 0;
}
.v1b-eye {
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  display: inline-flex; align-items: center; gap: 12px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--dark-fg-3);
  white-space: nowrap;
}
.v1b-eye .num { color: var(--clay); }
.v1b-eye .rule { width: 28px; height: 1px; background: rgba(255,255,255,0.16); }

.v1b-stack {
  position: relative;
  width: 380px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.v1b-card { /* wrapper: holds rotation + horizontal offset */ }
.v1b-card-1 { transform: translateX(-22px) rotate(-1.4deg); }
.v1b-card-2 { transform: translateX(24px)  rotate(0.5deg);  z-index: 2; }
.v1b-card-3 { transform: translateX(-10px) rotate(-0.4deg); }

.v1b-inner {
  background: rgba(255,255,255,0.025);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 9px;
  padding: 22px 24px 20px;
  box-shadow:
    0 22px 40px -22px rgba(0,0,0,0.55),
    inset 0 1px 0 rgba(255,255,255,0.04);
  animation: v1b-float 7.5s ease-in-out infinite;
}
.v1b-card-1 .v1b-inner { animation-delay: -0.3s; }
.v1b-card-2 .v1b-inner {
  animation-delay: -3s;
  background: linear-gradient(180deg, rgba(217,119,87,0.075), rgba(217,119,87,0.025));
  border-color: rgba(217,119,87,0.30);
  box-shadow:
    0 30px 60px -22px rgba(0,0,0,0.6),
    0 0 0 1px rgba(217,119,87,0.10),
    inset 0 1px 0 rgba(255,255,255,0.06);
}
.v1b-card-3 .v1b-inner { animation-delay: -5.5s; }
@keyframes v1b-float {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-7px); }
}

.v1b-quote {
  font-family: var(--font-serif);
  font-weight: 500;
  font-size: 14.5px;
  line-height: 1.6;
  color: var(--dark-fg);
  margin: 0 0 16px;
  letter-spacing: -0.005em;
  text-wrap: pretty;
}
.v1b-card-1 .v1b-quote,
.v1b-card-3 .v1b-quote { color: var(--dark-fg-2); }

.v1b-quote::before {
  content: "“";
  font-family: var(--font-serif);
  color: var(--clay);
  margin-right: 2px;
  font-weight: 600;
}

.v1b-attr {
  display: flex; align-items: center; gap: 10px;
}
.v1b-avatar {
  width: 30px; height: 30px;
  border-radius: 50%;
  background: rgba(217,119,87,0.16);
  color: var(--clay);
  display: grid; place-items: center;
  font-family: var(--font-serif);
  font-weight: 600;
  font-size: 13px;
  flex-shrink: 0;
  border: 1px solid rgba(217,119,87,0.22);
}
.v1b-card-2 .v1b-avatar {
  background: var(--clay);
  color: #FAF9F5;
  border-color: rgba(255,255,255,0.10);
}
.v1b-name {
  font-family: var(--font-sans);
  font-size: 12.5px;
  font-weight: 500;
  color: var(--dark-fg);
  letter-spacing: -0.005em;
  line-height: 1.2;
}
.v1b-meta {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--dark-fg-3);
  margin-top: 2px;
}
`;

const TESTIMONIALS = [
  { quote: '从前一份关键标书要熬三个通宵。现在我只校三遍。',
    name: '王云涛', role: '项目总监 · 鼎和能源', initial: '王' },
  { quote: 'Prose 写出来的语气,比我们标书部门还像我们自己。',
    name: '林晓溪', role: '投标经理 · 景明集团', initial: '林' },
  { quote: '中标率从 22% 到 51%。我们把所有模板都重写了。',
    name: '陈牧之', role: '副总裁 · 清岳交通', initial: '陈' },
];

function V1BLeft() {
  return (
    <>
      <style>{v1bStyles}</style>
      <div className="v1-stage">
        <div className="v1-head">
          <span className="lg-brand">
            <span className="lg-brand-mark inverse">P</span>
            <span className="lg-wordmark inverse">
              Prose
              <span className="lg-pipe"></span>
              <span className="lg-wordmark-sub">智能标书</span>
            </span>
          </span>
          <span style={{fontFamily:'var(--font-mono)',fontSize:10.5,letterSpacing:'0.18em',textTransform:'uppercase',color:'var(--dark-fg-3)'}}>
            voices · enterprise
          </span>
        </div>

        <div className="v1b-body">
          <span className="v1b-eye">
            <span className="rule"></span>
            <span><span className="num">37</span> 家头部客户的真实回响</span>
            <span className="rule"></span>
          </span>

          <div className="v1b-stack">
            {TESTIMONIALS.map((t, i) => (
              <div key={i} className={`v1b-card v1b-card-${i + 1}`}>
                <div className="v1b-inner">
                  <p className="v1b-quote">{t.quote}</p>
                  <div className="v1b-attr">
                    <div className="v1b-avatar">{t.initial}</div>
                    <div>
                      <div className="v1b-name">{t.name}</div>
                      <div className="v1b-meta">{t.role}</div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="v1-stage-foot">
          <span className="v1-foot-mark">{I.sparkLogo(14)} Prose for Enterprise</span>
          <span>SOC 2 · ISO 27001</span>
        </div>
      </div>
    </>
  );
}


// ─────────────────────────────────────────────────────────────
// V1C · Cover
//   A magazine-cover composition. Issue meta up top, a giant
//   serif headline filling the middle, a clay rule, a calm
//   sub-line, and an index strip at the bottom. Reveal-on-mount
//   staggered by line.
// ─────────────────────────────────────────────────────────────

const v1cStyles = `
.v1c-body {
  flex: 1;
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0;
}
.v1c-grain {
  position: absolute; inset: 0;
  pointer-events: none;
  opacity: 0.5;
  background:
    radial-gradient(120% 80% at 100% 0%, rgba(217,119,87,0.10), transparent 55%);
}

.v1c-issue {
  display: flex; align-items: center; gap: 14px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--dark-fg-3);
  margin-bottom: 44px;
  opacity: 0;
  animation: v1c-up 800ms ease-out 150ms forwards;
}
.v1c-issue .rule {
  width: 36px;
  height: 1px;
  background: var(--clay);
}
.v1c-issue .num { color: var(--clay); }

.v1c-display {
  font-family: var(--font-serif);
  font-weight: 600;
  font-size: 64px;
  line-height: 1.08;
  letter-spacing: -0.022em;
  color: var(--dark-fg);
  margin: 0 0 30px;
  text-wrap: balance;
  position: relative;
}
.v1c-display .ln {
  display: block;
  opacity: 0;
  transform: translateY(14px);
  animation: v1c-up 900ms cubic-bezier(.2,.7,.2,1) forwards;
}
.v1c-display .ln1 { animation-delay: 450ms; }
.v1c-display .ln2 {
  animation-delay: 700ms;
  padding-left: 1.4em;
}
.v1c-display em {
  font-style: normal;
  color: var(--clay);
  position: relative;
  white-space: nowrap;
}
.v1c-display em::after {
  content: "";
  position: absolute;
  left: 0; right: 0; bottom: 0.06em;
  height: 6px;
  background: rgba(217,119,87,0.18);
  z-index: -1;
  transform-origin: left center;
  transform: scaleX(0);
  animation: v1c-underline 800ms cubic-bezier(.6,0,.3,1) 1100ms forwards;
}
@keyframes v1c-underline {
  to { transform: scaleX(1); }
}
@keyframes v1c-up {
  to { opacity: 1; transform: translateY(0); }
}

.v1c-divider {
  width: 64px;
  height: 1px;
  background: rgba(255,255,255,0.20);
  margin: 4px 0 22px;
  opacity: 0;
  animation: v1c-up 700ms ease-out 1050ms forwards;
}

.v1c-sub {
  font-family: var(--font-serif);
  font-weight: 400;
  font-size: 17px;
  line-height: 1.55;
  color: var(--dark-fg-2);
  max-width: 480px;
  margin: 0 0 56px;
  opacity: 0;
  animation: v1c-up 700ms ease-out 1200ms forwards;
  text-wrap: pretty;
}
.v1c-sub strong {
  color: var(--dark-fg);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.v1c-contents {
  display: flex; align-items: baseline; gap: 26px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--dark-fg-3);
  opacity: 0;
  animation: v1c-up 700ms ease-out 1450ms forwards;
}
.v1c-contents .num {
  color: var(--clay);
  margin-right: 7px;
  font-variant-numeric: tabular-nums;
}
.v1c-contents .item {
  display: inline-flex; gap: 0;
}
.v1c-contents .sep {
  color: rgba(255,255,255,0.13);
}
`;

function V1CLeft() {
  return (
    <>
      <style>{v1cStyles}</style>
      <div className="v1-stage">
        <div className="v1-head">
          <span className="lg-brand">
            <span className="lg-brand-mark inverse">P</span>
            <span className="lg-wordmark inverse">
              Prose
              <span className="lg-pipe"></span>
              <span className="lg-wordmark-sub">智能标书</span>
            </span>
          </span>
          <span style={{fontFamily:'var(--font-mono)',fontSize:10.5,letterSpacing:'0.18em',textTransform:'uppercase',color:'var(--dark-fg-3)'}}>
            issue 04 · spring 2026
          </span>
        </div>

        <div className="v1c-body">
          <div className="v1c-issue">
            <span className="rule"></span>
            <span><span className="num">№ 04</span>  ·  Briefing Notes  ·  春 2026</span>
          </div>

          <h1 className="v1c-display">
            <span className="ln ln1">再没有一份标书,</span>
            <span className="ln ln2">值得熬到 <em>天亮。</em></span>
          </h1>

          <div className="v1c-divider"></div>

          <p className="v1c-sub">
            把繁文与排版交给 Prose · 把判断与决策留给您。本周已为 <strong>312</strong> 位投标经理写完关键章节。
          </p>

          <div className="v1c-contents">
            <span className="item"><span className="num">01</span>撰写</span>
            <span className="sep">／</span>
            <span className="item"><span className="num">02</span>审阅</span>
            <span className="sep">／</span>
            <span className="item"><span className="num">03</span>数据库</span>
            <span className="sep">／</span>
            <span className="item"><span className="num">04</span>历史标书</span>
          </div>
        </div>

        <div className="v1-stage-foot">
          <span className="v1-foot-mark">{I.sparkLogo(14)} Prose Quarterly</span>
          <span>est. 2024 · Shanghai</span>
        </div>
      </div>
    </>
  );
}


// ─────────────────────────────────────────────────────────────
// Combined variants
// ─────────────────────────────────────────────────────────────

function V1A() {
  return (
    <>
      <style>{V1Styles}</style>
      <div className="v1-root">
        <V1ALeft />
        <V1RightPane />
      </div>
    </>
  );
}
function V1B() {
  return (
    <>
      <style>{V1Styles}</style>
      <div className="v1-root">
        <V1BLeft />
        <V1RightPane />
      </div>
    </>
  );
}
function V1C() {
  return (
    <>
      <style>{V1Styles}</style>
      <div className="v1-root">
        <V1CLeft />
        <V1RightPane />
      </div>
    </>
  );
}

Object.assign(window, { V1A, V1B, V1C });
