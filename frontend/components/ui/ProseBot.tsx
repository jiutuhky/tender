"use client";

import { useEffect, useRef, type CSSProperties, type SVGProps } from "react";
import { ProseBotEngine, type BotState, type BotCue } from "@/lib/bot";
import {
  BOT_VIEWBOX,
  REST_BODY_PATH,
  REST_EYES_PATH,
} from "@/lib/bot/geometry";
import { botIdentityTone } from "@/lib/bot/identity";
import "./prose-bot.css";

export interface ProseBotProps extends Omit<
  SVGProps<SVGSVGElement>,
  "ref" | "onChange"
> {
  state?: BotState;
  size?: number;
  identity?: string;
  intensity?: "normal" | "quiet";
  motion?: "full" | "reduced" | "static";
  paused?: boolean;
  ribbons?: boolean;
  followPointer?: boolean;
  idleMoods?: boolean;
  blinkOnHover?: boolean;
  spawn?: boolean;
  completionKey?: string;
  celebrateOnComplete?: boolean;
  once?: BotCue;
  onceKey?: string | number;
}

export function ProseBot({
  state = "idle",
  size = 40,
  identity,
  intensity = "normal",
  motion = "full",
  paused = false,
  ribbons = true,
  followPointer = false,
  idleMoods = false,
  blinkOnHover = false,
  spawn = false,
  completionKey = "",
  celebrateOnComplete = true,
  once,
  onceKey,
  style,
  className,
  onPointerEnter,
  onPointerMove,
  onPointerLeave,
  ...props
}: ProseBotProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const engineRef = useRef<ProseBotEngine | null>(null);
  const tone = identity ? botIdentityTone(identity) : undefined;
  const initial = useRef({
    state,
    size,
    intensity,
    motion,
    paused,
    ribbons,
    idleMoods,
    seed: tone ?? 0,
    entrance: spawn,
    completionKey,
    celebrateOnComplete,
  });

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const engine = new ProseBotEngine(svg, initial.current);
    engineRef.current = engine;
    return () => {
      engine.destroy();
      engineRef.current = null;
    };
  }, []);
  useEffect(() => {
    engineRef.current?.configure({
      size,
      intensity,
      motion,
      paused,
      ribbons,
      idleMoods,
      seed: tone ?? 0,
      completionKey,
      celebrateOnComplete,
    });
  }, [
    size,
    intensity,
    motion,
    paused,
    ribbons,
    idleMoods,
    tone,
    completionKey,
    celebrateOnComplete,
  ]);
  useEffect(() => {
    engineRef.current?.setState(state);
  }, [state]);
  useEffect(() => {
    if (once && onceKey !== undefined)
      engineRef.current?.playOnce(once, onceKey);
  }, [once, onceKey]);

  return (
    <svg
      {...props}
      ref={svgRef}
      width={size}
      height={size}
      viewBox={BOT_VIEWBOX}
      className={`pb${className ? ` ${className}` : ""}`}
      data-bot-identity={tone}
      style={
        {
          ...(tone === undefined
            ? {}
            : { "--bot-ink": `var(--bot-tone-${tone})` }),
          ...style,
        } as CSSProperties
      }
      onPointerEnter={(event) => {
        onPointerEnter?.(event);
        if (blinkOnHover && event.pointerType === "mouse")
          engineRef.current?.blinkOnce();
      }}
      onPointerMove={(event) => {
        onPointerMove?.(event);
        if (!followPointer || event.pointerType !== "mouse") return;
        const r = event.currentTarget.getBoundingClientRect();
        if (r.width && r.height)
          engineRef.current?.setPointer(
            ((event.clientX - r.left) / r.width - 0.5) * 6,
            ((event.clientY - r.top) / r.height - 0.5) * 4,
          );
      }}
      onPointerLeave={(event) => {
        onPointerLeave?.(event);
        engineRef.current?.setPointer(0, 0);
      }}
    >
      <g data-bot-rest="">
        <path d={REST_BODY_PATH} fill="var(--bot-ink)" />
        <path d={REST_EYES_PATH} fill="var(--bot-eye)" />
      </g>
    </svg>
  );
}
