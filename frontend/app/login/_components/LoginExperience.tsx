"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";
import { ArrowRightIcon, BrandMark } from "@/components/ui/icons";
import {
  DUR_MICRO,
  DUR_FLOAT,
  DUR_PANEL,
  TRACE_EASE_ENTER,
  TRACE_EASE_EXIT,
  prefersReducedMotion,
} from "@/app/workspace/_components/canvas/traceMotion";
import { LoginForm } from "./LoginForm";
import { WorkspacePreview } from "./WorkspacePreview";

/** 登录体验壳层（Frost）：持有转场 phase，用 gsap（useGSAP）驱动「窗口 zoom」。
 *  叙事：玻璃登录卡片浮在桌面壁纸上；登录后卡片淡出，工作区窗口从中心
 *  平滑放大铺满（macOS 打开 App 的 zoom 效果）→ 转场末尾 router.push('/home')。
 *
 *  动效常量统一复用 traceMotion（全站唯一动效常量模块）：时长走 120/200/320ms
 *  三档，缓动用品牌标准曲线及其镜像退场。窗口圆角不做补间——在放大启动、
 *  窗口透明度仍为 0 的瞬间瞬切归零，视觉上无痕。
 *  reduced-motion 用一次性 prefersReducedMotion() 判断（转场是一次性动作，
 *  无需响应式重判），退化为即时切换。
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

      if (prefersReducedMotion()) return; // 窗口已藏、卡片默认可见，跳过入场动画

      gsap
        .timeline()
        .from(q(".lg-card"), {
          autoAlpha: 0,
          y: 8,
          scale: 0.985,
          duration: DUR_PANEL,
          ease: TRACE_EASE_ENTER,
        })
        .from(
          q(".lg-locale"),
          { autoAlpha: 0, y: -8, duration: DUR_FLOAT, ease: TRACE_EASE_ENTER },
          `-=${DUR_FLOAT}`
        );
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

      // 减弱动态：即时切换——卡片隐去、窗口直接铺满后跳转
      if (prefersReducedMotion()) {
        gsap.set([card, locale], { autoAlpha: 0 });
        gsap.set(file, { autoAlpha: 1, scale: 1, borderRadius: 0 });
        finish();
        return;
      }

      // ① 卡片轻微缩小上浮淡出（镜像退场曲线） ② 窗口从中心浮现（圆角在
      // 透明度为 0 的瞬间瞬切归零） ③ 标准曲线放大铺满
      gsap
        .timeline({ onComplete: finish })
        .to(card, { scale: 0.96, y: -8, autoAlpha: 0, duration: DUR_FLOAT, ease: TRACE_EASE_EXIT }, 0)
        .to(locale, { autoAlpha: 0, duration: DUR_MICRO, ease: TRACE_EASE_EXIT }, 0)
        .set(file, { borderRadius: 0 }, DUR_MICRO)
        .to(file, { autoAlpha: 1, duration: DUR_FLOAT, ease: TRACE_EASE_ENTER }, DUR_MICRO)
        .to(file, { scale: 1, duration: DUR_PANEL, ease: TRACE_EASE_ENTER }, DUR_MICRO);
    },
    { scope: rootRef, dependencies: [phase] }
  );

  return (
    <div className="lg-root" ref={rootRef}>
      <WorkspacePreview />
      <div className="lg-locale frost-glass frost-glass--lens frost-glass--interactive" data-thick="thin">
        EN / 简
      </div>
      <div className="lg-card frost-glass frost-glass--soft" data-thick="thick">
        <header className="lg-card-head">
          <span className="lg-brand">
            <BrandMark />
            Prose
          </span>
          <span className="lg-head-aux">
            <span>还没有账号？</span>
            <a href="#">
              申请试用
              <ArrowRightIcon />
            </a>
          </span>
        </header>
        <LoginForm onLogin={() => setPhase("transition")} disabled={phase !== "idle"} />
      </div>
    </div>
  );
}
