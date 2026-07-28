"use client";

import { useState } from "react";
import {
  ArrowRightIcon,
  EyeIcon,
  EyeOffIcon,
  WechatWorkIcon,
  DingtalkIcon,
  SsoIcon,
} from "@/components/ui/icons";

/** 玻璃卡片内的登录表单（Frost macOS 控件风格）。
 *  假登录：点击「继续」后进入加载态，并通过 onLogin 通知父层启动「窗口 zoom」转场，
 *  由 LoginExperience 在转场末尾 router.push 到 /home（本组件不再自行跳转）。 */
export function LoginForm({
  onLogin,
  disabled = false,
}: {
  onLogin: () => void;
  disabled?: boolean;
}) {
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  function fakeLogin() {
    if (submitting || disabled) return;
    setSubmitting(true);
    onLogin();
  }

  const busy = submitting || disabled;

  return (
    <div className="lg-card-body">
      <h1 className="lg-title">回到您的工作台</h1>
      <p className="lg-sub">使用企业邮箱继续。新设备登录将触发二次验证。</p>

      <form
        className="lg-form"
        onSubmit={(e) => {
          e.preventDefault();
          fakeLogin();
        }}
      >
        <div className="lg-field">
          <label className="lg-label">企业邮箱</label>
          <div className="lg-input-wrap">
            <input
              className="lg-input"
              type="email"
              placeholder="name@company.com"
              defaultValue="lihui@huadong-arch.com"
            />
          </div>
        </div>
        <div className="lg-field">
          <div className="lg-row">
            <label className="lg-label">密码</label>
            <a className="lg-label-link" href="#">
              忘记?
            </a>
          </div>
          <div className="lg-input-wrap">
            <input
              className="lg-input"
              type={showPassword ? "text" : "password"}
              placeholder="••••••••"
              defaultValue="prose-demo-2026"
            />
            <button
              type="button"
              className="lg-input-icon"
              title={showPassword ? "隐藏" : "显示"}
              aria-label={showPassword ? "隐藏密码" : "显示密码"}
              onClick={() => setShowPassword((v) => !v)}
            >
              {showPassword ? <EyeOffIcon /> : <EyeIcon />}
            </button>
          </div>
        </div>

        <button type="submit" className="lg-submit" disabled={busy}>
          {submitting ? (
            <>
              登录中 <span className="lg-spinner" />
            </>
          ) : (
            <>
              继续 <ArrowRightIcon />
            </>
          )}
        </button>

        <div className="lg-divider">或</div>

        <div className="lg-sso-row">
          <button type="button" className="lg-sso" onClick={fakeLogin} disabled={busy}>
            <WechatWorkIcon /> 企业微信
          </button>
          <button type="button" className="lg-sso" onClick={fakeLogin} disabled={busy}>
            <DingtalkIcon /> 钉钉
          </button>
          <button type="button" className="lg-sso" onClick={fakeLogin} disabled={busy}>
            <SsoIcon /> SSO
          </button>
        </div>
      </form>

      <div className="lg-legal">
        继续即表示您同意 服务条款 与 隐私政策 · ICP 备 2024-001
      </div>
    </div>
  );
}
