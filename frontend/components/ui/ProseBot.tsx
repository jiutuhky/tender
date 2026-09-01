"use client";

// Prose Bot —— lib/bot 角色引擎（grok-icon-study 1:1 移植，block 方块形体）的 React 壳。
//
// 引擎自己构建 SVG 内部 DOM（原版 GrokCharacter 的模式）：壳只负责建一个空 svg、
// 把平台 props 翻成引擎调用，并在 SSR 首帧渲染静态方块占位——水合前它是品牌方块，
// 引擎挂载后接管为角色。
//
// 颜色两条路（引擎的 inkFlat / eyeColor 通道）：
//   · 主 Agent —— --pb-ink-2（暗色外观自动翻白），眼洞 --pb-eye；
//   · 子代理   —— 按 callId 派生的身份 hue 平色，眼洞固定白。
// 特效层吃引擎的 --fg，即同一份墨色；并排的子代理由此可分。

import { useEffect, useRef, type SVGProps } from "react";
import { GROK_GEO, ProseBotEngine, isBotState, type BotState } from "@/lib/bot";

/** 静态占位：水合前的品牌方块（引擎挂载后整棵替换） */
const REST_PATH = GROK_GEO.shapes.block?.path ?? "";

/** 待命期随机穿插的小情绪与节奏（平台行为，沿用旧 ProseBot 的参数） */
const IDLE_MOODS: BotState[] = ["curious", "happy", "bored", "playful", "proud", "shy"];
const IDLE_MOOD_AFTER: [number, number] = [14000, 26000];
const IDLE_MOOD_DURATION: [number, number] = [2600, 4600];

function rand(a: number, b: number): number {
  return a + Math.random() * (b - a);
}

export interface ProseBotProps extends Omit<SVGProps<SVGSVGElement>, "ref"> {
  /** 当前状态，默认待命 */
  state?: BotState;
  /** 身份色相；缺省 = 主 Agent（中性墨） */
  hue?: number;
  size?: number;
  /** 视线与头部跟随指针。只给主 Bot 开——看板上十几个头像一起盯着鼠标是灵异片 */
  followPointer?: boolean;
  /** 待命久了随机穿插一点小情绪 */
  idleMoods?: boolean;
  /** 挂载时先播一次派生动画（子代理头像出现时用） */
  spawn?: boolean;
  /** 指针移入时眨一次眼（旧版 hover 交互，只给可点的主 Bot 开） */
  blinkOnHover?: boolean;
  /** 插播一次性表达，onceKey 变化时触发 */
  once?: BotState;
  onceKey?: string | number;
  onceMs?: number;
}

export function ProseBot({
  state = "idle",
  hue,
  size,
  followPointer = false,
  idleMoods = false,
  spawn = false,
  blinkOnHover = false,
  once,
  onceKey,
  onceMs = 2000,
  ...props
}: ProseBotProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const engineRef = useRef<ProseBotEngine | null>(null);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;

    const tinted = hue !== undefined;
    const h = tinted ? ((Math.round(hue % 360) + 360) % 360) : 0;
    const engine = new ProseBotEngine(svg, {
      shape: "block",
      state: isBotState(state) ? state : "idle",
      mode: "hold",
      followPointer,
      sizePx: size ?? null,
      inkFlat: tinted ? `hsl(${h} 78% 46%)` : "var(--pb-ink-2, #1d1d1f)",
      eyeColor: tinted ? "#ffffff" : "var(--pb-eye, #ffffff)",
      badgeColor: tinted ? `hsl(${h} 78% 46%)` : "var(--gb-badge, #1d9bf0)",
    });
    engineRef.current = engine;
    if (spawn) engine.playOnce("spawning", 900);

    return () => {
      engine.destroy();
      engineRef.current = null;
    };
    // 只在挂载时建引擎；后续 props 变化走下面几个 effect 推给引擎。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    engineRef.current?.setState(state);
  }, [state]);

  useEffect(() => {
    engineRef.current?.setFollowPointer(followPointer);
  }, [followPointer]);

  useEffect(() => {
    if (once && onceKey !== undefined) engineRef.current?.playOnce(once, onceMs);
    // once / onceMs 只是本次插播的参数，靠 onceKey 变化触发，不进依赖
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onceKey]);

  // 待命期的小情绪：由组件排程（引擎保持原版 onboarding/hold 两档不动）
  useEffect(() => {
    const engine = engineRef.current;
    if (!engine || !idleMoods) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const schedule = () => {
      timer = setTimeout(() => {
        if (engine.state === "idle") {
          const mood = IDLE_MOODS[Math.floor(Math.random() * IDLE_MOODS.length)];
          if (mood) engine.playOnce(mood, rand(...IDLE_MOOD_DURATION));
        }
        schedule();
      }, rand(...IDLE_MOOD_AFTER));
    };
    schedule();
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [idleMoods]);

  const handleEnter = () => engineRef.current?.blinkOnce();

  const tinted = hue !== undefined;
  const h = tinted ? ((Math.round(hue % 360) + 360) % 360) : 0;
  const ink = tinted ? `hsl(${h} 78% 46%)` : "var(--pb-ink-2, #1d1d1f)";

  return (
    <svg
      {...props}
      ref={svgRef}
      viewBox="-15 -15 259 259"
      width={size ?? props.width}
      height={size ?? props.height}
      className={`pb${props.className ? ` ${props.className}` : ""}`}
      // 特效层与转圈时的缎带画在本体框外，必须放行溢出：
      // svg:root 的 UA 默认是 overflow:hidden，不覆盖就只剩本体那一格
      style={{ overflow: "visible", ...props.style }}
      onPointerEnter={blinkOnHover ? handleEnter : props.onPointerEnter}
    >
      {/* 水合前的静态占位；引擎 _build() 会 innerHTML="" 掉这棵子树 */}
      <path d={REST_PATH} fill={ink} />
    </svg>
  );
}
