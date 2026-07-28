// V1 · Editorial Split — three takes on the LEFT pane.
// Right pane shared, NO italics in any of its text.
//
// V1A · Workflow microcosm  — a small product card showing the agent at work
// V1B · Trust wall          — customer logos + tight KPIs
// V1C · Brand insignia      — huge spark + breathing room

// ─────────────────────────────────────────────────────────────
// Shared layout + RIGHT pane
// ─────────────────────────────────────────────────────────────

const v1Styles = `
.v1-root {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(440px, 0.95fr);
  width: 100%; height: 100%;
  background: var(--bg);
  color: var(--fg);
  overflow: hidden;
}

/* ---------- common LEFT stage chrome ---------- */
.v1-stage {
  position: relative;
  background: var(--dark-bg);
  color: var(--dark-fg);
  padding: 44px 52px;
  display: flex; flex-direction: column;
  overflow: hidden;
}
.v1-stage::before {
  content: "";
  position: absolute; inset: 0;
  background:
    radial-gradient(120% 80% at 100% 0%, rgba(217,119,87,0.10), transparent 55%),
    radial-gradient(80% 60% at 0% 100%, rgba(217,119,87,0.06), transparent 60%);
  pointer-events: none;
}
.v1-stage > * { position: relative; }

.v1-head {
  display: flex; align-items: center; justify-content: space-between;
}
.v1-head .v1-eyebrow {
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--dark-fg-3);
}
.v1-head .v1-eyebrow span { color: var(--clay); }

.v1-stage-foot {
  display: flex; align-items: center; justify-content: space-between;
  color: var(--dark-fg-3);
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.v1-stage-foot .v1-foot-mark {
  display: inline-flex; align-items: center; gap: 8px;
  color: var(--clay);
}

/* ---------- RIGHT pane (shared, NO italics) ---------- */
.v1-pane {
  position: relative;
  padding: 44px 48px;
  display: flex; flex-direction: column;
}
.v1-pane-head {
  display: flex; align-items: center; justify-content: space-between;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 11.5px;
}
.v1-pane-head a { color: var(--clay); text-decoration: none; }
.v1-pane-head a:hover { color: var(--clay-deep); }

.v1-pane-body {
  flex: 1;
  display: flex; flex-direction: column; justify-content: center;
  max-width: 380px;
  margin: 0 auto;
  width: 100%;
}
.v1-eyebrow-sm {
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--clay);
  margin-bottom: 14px;
}
.v1-title {
  font-family: var(--font-serif);
  font-style: normal;
  font-weight: 600;
  font-size: 30px;
  line-height: 1.18;
  letter-spacing: -0.015em;
  color: var(--fg);
  margin: 0 0 8px;
}
.v1-sub {
  font-style: normal;
  color: var(--fg-2);
  font-size: 13.5px;
  line-height: 1.55;
  margin: 0 0 28px;
}
.v1-pane-foot {
  text-align: center;
  color: var(--muted);
  font-size: 12.5px;
  font-style: normal;
}
.v1-pane-foot a {
  color: var(--clay);
  font-weight: 500;
  text-decoration: none;
  margin-left: 4px;
}
.v1-legal {
  margin-top: 32px;
  text-align: center;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--faint);
  letter-spacing: 0.04em;
  font-style: normal;
}
`;

function V1RightPane() {
  return (
    <div className="v1-pane">
      <div className="v1-pane-head">
        <span>EN / 简</span>
        <span>还没有账号?<a href="#" style={{marginLeft: 6}}>申请试用 →</a></span>
      </div>

      <div className="v1-pane-body">
        <div className="v1-eyebrow-sm">登录 · Sign in</div>
        <h1 className="v1-title">回到您的工作台</h1>
        <p className="v1-sub">使用企业邮箱继续。新设备登录将触发二次验证。</p>

        <form className="lg-form" onSubmit={(e) => e.preventDefault()}>
          <div className="lg-field">
            <label className="lg-label">企业邮箱</label>
            <div className="lg-input-wrap">
              <input className="lg-input" type="email" placeholder="name@company.com" defaultValue="lihui@huadong-arch.com" />
            </div>
          </div>
          <div className="lg-field">
            <div className="lg-row">
              <label className="lg-label">密码</label>
              <a className="lg-label-link" href="#">忘记?</a>
            </div>
            <div className="lg-input-wrap">
              <input className="lg-input" type="password" placeholder="••••••••" defaultValue="••••••••••" />
              <span className="lg-input-icon" title="显示">{I.eye}</span>
            </div>
          </div>

          <button type="submit" className="lg-submit">
            继续 {I.arrow}
          </button>

          <div className="lg-divider">或</div>

          <div className="lg-sso-row">
            <button type="button" className="lg-sso">{I.wechatWork} 企业微信</button>
            <button type="button" className="lg-sso">{I.dingtalk} 钉钉</button>
            <button type="button" className="lg-sso">{I.sso} SSO</button>
          </div>
        </form>

        <div className="v1-legal">
          继续即表示您同意 服务条款 与 隐私政策 · ICP 备 2024-001
        </div>
      </div>
    </div>
  );
}

window.V1Styles = v1Styles;
window.V1RightPane = V1RightPane;
