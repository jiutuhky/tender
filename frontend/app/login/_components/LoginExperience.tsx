"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";
import { BrandMark } from "@/components/ui/icons";
import { LoginForm } from "./LoginForm";
import { WorkspacePreview } from "./WorkspacePreview";

/** 登录体验壳层（Frost）：持有转场 phase，用 gsap（useGSAP）驱动「窗口 zoom」。
 *  叙事：玻璃登录卡片浮在桌面壁纸上；登录后卡片淡出，工作区窗口从中心
 *  平滑放大铺满（macOS 打开 App 的 zoom 效果）→ 转场末尾 router.push('/home')。
 *
 *  reduced-motion 用一次性 window.matchMedia 判断（转场是一次性动作，无需响应式重判）。
 *  注意：不能在 useGSAP（已基于 gsap.context）内再调 gsap.matchMedia —— 那会嵌套
 *  context，卸载 revert 时递归栈溢出。动画直接写在 useGSAP 回调里，由其自动清理。 */
export function LoginExperience() {
  const router = useRouter();
  const rootRef = useRef<HTMLDivElement>(null);
  const [phase, setPhase] = useState<"idle" | "transition">("idle");

  // 预取目标页，降低跳转白屏
  useEffect(() => {
    router.prefetch("/home");
  }, [router]);

  // 入场：预览窗口藏起（缩小态）；玻璃卡片浮入
  useGSAP(
    () => {
      const q = gsap.utils.selector(rootRef);
      gsap.set(q(".lg-file"), {
        autoAlpha: 0,
        scale: 0.9,
        borderRadius: 14,
        transformOrigin: "center center",
      });

      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduce) return; // 窗口已藏、卡片默认可见，跳过入场动画

      gsap
        .timeline()
        .from(q(".lg-card"), { autoAlpha: 0, y: 18, scale: 0.985, duration: 0.6, ease: "power3.out" })
        .from(q(".lg-locale"), { autoAlpha: 0, y: -8, duration: 0.4, ease: "power2.out" }, "-=0.35");
    },
    { scope: rootRef }
  );

  // 转场：phase 切到 transition 时播放窗口 zoom timeline，末尾跳转
  useGSAP(
    (_ctx, contextSafe) => {
      if (phase !== "transition") return;

      const q = gsap.utils.selector(rootRef);
      const card = q(".lg-card");
      const locale = q(".lg-locale");
      const file = q(".lg-file");

      const finish = contextSafe!(() => router.push("/home"));
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      // 减弱动态：跳过 zoom，卡片淡出 + 窗口直接铺满后跳转
      if (reduce) {
        gsap
          .timeline({ onComplete: finish })
          .to([card, locale], { autoAlpha: 0, duration: 0.22 })
          .to(file, { autoAlpha: 1, scale: 1, borderRadius: 0, duration: 0.32 }, "-=0.05");
        return;
      }

      // ① 卡片轻微缩小上浮淡出 ② 窗口从中心浮现 ③ expo 放大铺满
      gsap
        .timeline({ onComplete: finish })
        .to(card, { scale: 0.96, y: -10, autoAlpha: 0, duration: 0.42, ease: "power2.in" }, 0)
        .to(locale, { autoAlpha: 0, duration: 0.3 }, 0)
        .to(file, { autoAlpha: 1, duration: 0.45, ease: "power1.out" }, 0.25)
        .to(file, { scale: 1, borderRadius: 0, duration: 0.95, ease: "expo.out" }, 0.3);
    },
    { scope: rootRef, dependencies: [phase] }
  );

  return (
    <div className="lg-root" ref={rootRef}>
      <WorkspacePreview />
      <div className="lg-locale">EN / 简</div>
      <div className="lg-card">
        <header className="lg-card-head">
          <span className="lg-brand">
            <BrandMark />
            Prose
          </span>
          <span className="lg-head-aux">
            <span>还没有账号?</span>
            <a href="#">申请试用 →</a>
          </span>
        </header>
        <LoginForm onLogin={() => setPhase("transition")} disabled={phase !== "idle"} />
      </div>
    </div>
  );
}
