"use client";

// 临时验收页：按原版 playground（replica/index.html）的能力铺开——39 态逐个看、
// 登录轮换 / 锁定、转一圈 / 跳一下 / 粒子、形体与墨色切换。不进产品导航，验收完即删。

import { useEffect, useMemo, useRef, useState } from "react";
import { GROK_GEO, ProseBotEngine, STATE_GROUPS, type BotState, type BotSnapshot } from "@/lib/bot";

const DISK = "#f3efe6";

function Disk({ seed, sizePx, onReady }: {
  seed: number;
  sizePx: number;
  onReady?: (e: ProseBotEngine) => void;
}) {
  const ref = useRef<SVGSVGElement | null>(null);
  useEffect(() => {
    const svg = ref.current;
    if (!svg) return;
    const engine = new ProseBotEngine(svg, {
      mode: "onboarding",
      sizePx,
      followPointer: seed % 2 === 0,
    });
    onReady?.(engine);
    // 首屏从 curious 起播（对齐原版 playground 的「skip the first idle beat」）
    engine.moodN = 1;
    engine.setState("curious", { resetEyes: true });
    return () => engine.destroy();
    // seed 变化 = 强制重挂载，才好反复看特技与粒子
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed]);
  return (
    <div
      style={{
        width: sizePx * 1.5,
        height: sizePx * 1.5,
        borderRadius: "50%",
        background: DISK,
        display: "grid",
        placeItems: "center",
        boxShadow: "inset 0 -8px 18px rgba(40,30,10,.08), 0 12px 28px rgba(0,0,0,.18)",
      }}
    >
      <svg ref={ref} role="img" aria-label="Prose Bot" />
    </div>
  );
}

export default function BotProbe() {
  const [seed, setSeed] = useState(0);
  const [size, setSize] = useState(64);
  const [color, setColor] = useState("black");
  const [snap, setSnap] = useState<BotSnapshot | null>(null);
  const enginesRef = useRef<ProseBotEngine[]>([]);

  const palette = useMemo(() => Object.entries(GROK_GEO.palette), []);

  const collect = (e: ProseBotEngine) => {
    enginesRef.current.push(e);
    e.onChange = setSnap;
  };

  const act = (fn: (e: ProseBotEngine) => void) => {
    for (const e of enginesRef.current) fn(e);
  };

  return (
    <div style={{ padding: 24, background: "#1a1916", minHeight: "100vh", color: "#ece7dc" }}>
      <h1 style={{ font: "600 15px/1.4 sans-serif", letterSpacing: ".08em", margin: "0 0 16px" }}>
        Prose Bot · 原版引擎验收
      </h1>

      <div style={{ display: "flex", alignItems: "flex-end", gap: 28, marginBottom: 20 }}>
        <Disk seed={seed} sizePx={size} onReady={collect} />
        <Disk seed={seed + 1} sizePx={Math.min(size, 64)} />
        <div style={{ display: "grid", gap: 8, font: "12px/1.6 ui-monospace, monospace", color: "#b7b1a4" }}>
          <div>状态 {snap?.state ?? "—"}</div>
          <div>眼睛 {snap ? `${snap.eyeFrom} → ${snap.eyeTo}` : "—"}</div>
          <div>旋转 {(snap?.spin ?? 0).toFixed(2)}°</div>
          <div>挤压 {(snap?.squash ?? 1).toFixed(3)}</div>
          <div>overlay {snap?.overlay ?? "—"}</div>
        </div>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 20 }}>
        <button onClick={() => setSeed(seed + 1)}>重挂载（重看特技）</button>
        <button onClick={() => setSize(size === 64 ? 24 : 64)}>{size}px</button>
        <button onClick={() => act((e) => e.spinOnce(1))}>转一圈</button>
        <button onClick={() => act((e) => e.bounceOnce())}>跳一下</button>
        <button onClick={() => act((e) => e.burstOnce())}>粒子</button>
        <button onClick={() => act((e) => { e.setMode("hold"); e.setState("waking", { resetEyes: true }); })}>醒来</button>
        <button onClick={() => act((e) => { e.setMode("hold"); e.setState("sleeping", { resetEyes: true }); })}>睡着</button>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 20 }}>
        {palette.map(([id, pal]) => (
          <button
            key={id}
            title={id}
            onClick={() => setColor(id)}
            style={{
              width: 28,
              height: 28,
              borderRadius: "50%",
              border: color === id ? "2px solid #e8d7a4" : "2px solid #111",
              background: pal.light,
              cursor: "pointer",
            }}
          />
        ))}
        <label style={{ font: "12px sans-serif", color: "#b7b1a4", display: "flex", alignItems: "center", gap: 6 }}>
          hue
          <input
            type="range"
            min={0}
            max={359}
            onChange={(ev) => act((e) => e.setInk(`hsl(${ev.target.value} 78% 46%)`))}
          />
        </label>
      </div>

      {STATE_GROUPS.map((g) => (
        <section key={g.label} style={{ marginBottom: 24 }}>
          <h2 style={{ font: "600 11px sans-serif", letterSpacing: ".14em", textTransform: "uppercase", color: "#6d675d", margin: "0 0 10px" }}>
            {g.label}
          </h2>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 14 }}>
            {g.states.map((s: BotState) => (
              <button
                key={s}
                onClick={() => act((e) => { e.setMode("hold"); e.setState(s); })}
                style={{
                  display: "grid",
                  justifyItems: "center",
                  gap: 4,
                  background: "#2a2823",
                  border: `1px solid ${snap?.state === s ? "#e8d7a4" : "#3a372f"}`,
                  borderRadius: 10,
                  padding: "10px 8px 6px",
                  cursor: "pointer",
                  color: "#ece7dc",
                  minWidth: 84,
                }}
              >
                <span
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: "50%",
                    background: DISK,
                    display: "grid",
                    placeItems: "center",
                  }}
                >
                  <ProbeBot state={s} color={color} />
                </span>
                <span style={{ font: "10px sans-serif", color: "#b7b1a4" }}>{s}</span>
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

/** 状态格子里的小 Bot：挂载即以该状态起播（hold 模式） */
function ProbeBot({ state, color }: { state: BotState; color: string }) {
  const ref = useRef<SVGSVGElement | null>(null);
  useEffect(() => {
    const svg = ref.current;
    if (!svg) return;
    const engine = new ProseBotEngine(svg, {
      state,
      mode: "hold",
      sizePx: 40,
      color,
      followPointer: false,
    });
    return () => engine.destroy();
  }, [state, color]);
  return <svg ref={ref} role="img" aria-label={state} />;
}
