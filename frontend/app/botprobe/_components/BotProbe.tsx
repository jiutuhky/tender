"use client";

import { useState } from "react";
import { ProseBot } from "@/components/ui/icons";
import {
  ALL_STATES,
  BOT_DEFINITIONS,
  STATE_GROUPS,
  getBotRuntimeStats,
  type BotState,
  type BotCue,
} from "@/lib/bot";
import { collectSubagentRuns } from "@/app/workspace/_components/runStatus";
import { AgentBoardView } from "@/app/workspace/_components/canvas/AgentBoard";
import { botReviewFixture, DEMO_TODOS } from "./fixtures";
import "./styles.css";

export function BotProbe() {
  const [state, setState] = useState<BotState>("idle");
  const [event, setEvent] = useState<{ state: BotCue; key: number } | null>(
    null,
  );
  const [reduced, setReduced] = useState(false);
  const [paused, setPaused] = useState(false);
  const [ribbons, setRibbons] = useState(true);
  const [complete, setComplete] = useState(false);
  const [stopped, setStopped] = useState(false);
  const [mounted, setMounted] = useState(true);
  const [runtime, setRuntime] = useState<ReturnType<
    typeof getBotRuntimeStats
  > | null>(null);
  const fixture = botReviewFixture(complete);
  const rows = collectSubagentRuns(fixture.timeline, !stopped, fixture.signals);
  const motion = reduced ? "reduced" : "full";
  function choose(next: BotState) {
    if (BOT_DEFINITIONS[next].group === "state") setState(next);
    else setEvent({ state: next as BotCue, key: Date.now() });
  }
  return (
    <main className="botprobe">
      <header>
        <h1>Bot 产品验收</h1>
        <p>使用真实角色组件与任务看板，演示数据不写入工作区。</p>
      </header>
      <div className="botprobe-controls">
        <button
          onClick={() =>
            document.documentElement.setAttribute(
              "data-appearance",
              document.documentElement.getAttribute("data-appearance") ===
                "dark"
                ? "light"
                : "dark",
            )
          }
        >
          切换主题
        </button>
        <button aria-pressed={reduced} onClick={() => setReduced(!reduced)}>
          减少动效
        </button>
        <button aria-pressed={paused} onClick={() => setPaused(!paused)}>
          暂停预览
        </button>
        <button aria-pressed={ribbons} onClick={() => setRibbons(!ribbons)}>
          彩色拖尾
        </button>
        <button onClick={() => setMounted(!mounted)}>
          {mounted ? "卸载预览" : "重新挂载"}
        </button>
        <button onClick={() => setRuntime(getBotRuntimeStats())}>
          刷新运行统计
        </button>
      </div>
      <p className="botprobe-runtime" role="status">
        {runtime
          ? `实例 ${runtime.instances} · 活动 ${runtime.active} · 帧时钟 ${runtime.frameScheduled ? "运行" : "停止"}`
          : "可检查卸载与减少动效后的帧调度。"}
      </p>
      {mounted && (
        <>
          <section className="botprobe-hero">
            <ProseBot
              state={state}
              size={128}
              motion={motion}
              paused={paused}
              ribbons={ribbons}
              followPointer
              idleMoods
              once={event?.state}
              onceKey={event?.key}
              aria-label={`主智能体：${BOT_DEFINITIONS[state].name}`}
              role="img"
            />
            <div>
              <h2>{BOT_DEFINITIONS[state].name}</h2>
              <p>{BOT_DEFINITIONS[state].desc}</p>
              <p>{BOT_DEFINITIONS[state].rhythm}</p>
            </div>
            <div className="botprobe-sizes">
              {[20, 32, 48, 64].map((size) => (
                <div key={size}>
                  <ProseBot
                    state={state}
                    size={size}
                    motion={motion}
                    paused={paused}
                    ribbons={ribbons}
                    aria-hidden="true"
                  />
                  <span>{size}px</span>
                </div>
              ))}
            </div>
          </section>
          {STATE_GROUPS.map((group) => (
            <section key={group.label} className="botprobe-group">
              <h2>{group.label}</h2>
              <div className="botprobe-grid">
                {group.states.map((id) => (
                  <button
                    key={id}
                    onClick={() => choose(id)}
                    aria-pressed={state === id}
                  >
                    <ProseBot
                      state={id}
                      size={48}
                      motion="static"
                      ribbons={false}
                      aria-hidden="true"
                    />
                    <span>{BOT_DEFINITIONS[id].name}</span>
                  </button>
                ))}
              </div>
            </section>
          ))}
          <section className="botprobe-board-demo">
            <h2>画布任务看板 · {ALL_STATES.length} 项动作共用同一引擎</h2>
            <div className="botprobe-controls">
              <button
                onClick={() => {
                  setComplete(!complete);
                  setStopped(false);
                }}
              >
                {complete ? "重新运行子任务" : "完成全部子任务"}
              </button>
              <button
                aria-pressed={stopped}
                onClick={() => setStopped(!stopped)}
              >
                切换主流连接中断
              </button>
            </div>
            <div className="botprobe-canvas">
              <p>画布右上角 · 多个智能体独立工作</p>
              <AgentBoardView rows={rows} todos={DEMO_TODOS} live={!stopped} />
            </div>
            <div className="cv-overview">
              <AgentBoardView rows={rows} todos={DEMO_TODOS} live={!stopped} />
            </div>
          </section>
        </>
      )}
    </main>
  );
}
