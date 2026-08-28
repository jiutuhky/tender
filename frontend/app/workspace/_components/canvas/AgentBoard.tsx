"use client";

import { memo, type CSSProperties, useEffect, useRef } from "react";
import { useWorkspaceStore } from "@/lib/store/workspace";
import { ProseBotIcon } from "@/components/ui/icons";
import { DUR_FLOAT } from "./traceMotion";
import { LiquidGlass } from "../LiquidGlass";
import { collectSubagentRuns, isRunning } from "../runStatus";

/** callId → 色相：字符串 hash × 黄金角(137.5°)铺满色轮。伪随机但稳定——同一
 *  子代理重渲不变色（rAF 批帧下不闪），不同子代理均匀散开不扎堆。 */
function hashHue(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i += 1) h = (h * 31 + seed.charCodeAt(i)) | 0;
  return ((h < 0 ? ~h + 1 : h) * 137.508) % 360;
}

// 画布右上角的子代理状态看板：主智能体每派发一个子代理，这里长出一行——Bot 头像
// （与左上消息窗同一形象，按 callId 派生一枚身份色，见 hashHue）+ 任务描述 +
// 最近动作摘要。
//
// 结构约束（同 .cv-msgwin 的备案）：玻璃面禁不起在壳/玻璃上做 opacity 动画——
// opacity 会把子树隔离成 backdrop root，玻璃只看见自己、塌成透明板。所以进出场
// 拆成两半：壳走 transform 缩放，面板内容走 opacity 淡入淡出。
//
// 生命周期刻意做成零状态纯派生：rows 非空即挂载，data-state 随 live 翻转
// "live" / "done"。本轮结束后看板**不退场**（用户定）：终态行保留在面板里，头像静止、
// 标题翻成「N 已完成」，供用户回看本轮派发了什么；DOM 要到下一轮 user 消息令 rows
// 清空才卸载，卸载时用户的注意力已在新一轮上。
//
// 性能：collectSubagentRuns 是 O(末段扫描) 纯函数，随 timeline 的 rAF 批帧跑；
// 行组件收原始值 props 走默认浅比较，流式期只有内容真变了的那几行会重渲。

// 液态玻璃参数：沿用 MessageWindow 的配方，圆角与壳的 16px 一致。
const GLASS = {
  displacementScale: 100,
  blurAmount: 0.2,
  saturation: 140,
  aberrationIntensity: 0,
  cornerRadius: 20,   // lens 面板档（规范：凝玻璃面板 20），与 globals.css .cv-agentboard 同步
  mode: "standard",
} as const;


export function AgentBoard() {
  const timeline = useWorkspaceStore((s) => s.timeline);
  const phase = useWorkspaceStore((s) => s.phase);
  const rows = collectSubagentRuns(timeline);
  const live = isRunning(phase);
  const rootRef = useRef<HTMLElement | null>(null);

  // 规范 rule 4「Transitions run soft」：壳做 scale 补间时位移滤镜会逐帧在新尺寸上
  // 重跑，这段期间按 data-tweening 换成纯毛玻璃，落位后再弯回来。
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    root.dataset.tweening = "1";
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const timer = window.setTimeout(
      () => {
        delete root.dataset.tweening;
      },
      reduce ? 0 : DUR_FLOAT * 1000,
    );
    return () => window.clearTimeout(timer);
  }, [live]);

  if (rows.length === 0) return null;

  const runningCount = rows.filter((r) => r.status === "running").length;

  return (
    <section
      ref={rootRef}
      className="cv-agentboard"
      data-state={live ? "live" : "done"}
      aria-label="子代理执行看板"
    >
      {/* 玻璃是纯背景层（不装 children）：壳的高度由正常流的面板内容撑起——
          若把面板塞进 LiquidGlass（absolute inset:0）里，壳就只剩绝对定位子元素，
          高度塌成 0（消息窗不踩这个坑是因为它两档尺寸都写死）。 */}
      <div className="cv-agentboard-glass">
        <LiquidGlass className="cv-agentboard-lg" {...GLASS} />
      </div>
      <div className="cv-agentboard-panel">
        <header className="cv-agentboard-head" role="status" aria-live="polite">
          子代理 · {runningCount > 0 ? `${runningCount} 运行中` : `${rows.length} 已完成`}
        </header>
        <div className="cv-agentboard-list">
          {rows.map((row, i) => (
            <AgentRow
              key={row.callId}
              callId={row.callId}
              description={row.description}
              summary={row.summary}
              running={row.status === "running"}
              depth={row.depth}
              index={i}
              live={live}
            />
          ))}
        </div>
      </div>
    </section>
  );
}

type RowDotState = "running" | "done" | "stopped";

interface AgentRowProps {
  callId: string;
  description: string;
  summary: string;
  running: boolean;
  depth: number;
  index: number;
  /** 本轮是否仍在运行。流出错/中断时 running 行降级为「已停止」，不撒谎也不永久流光。 */
  live: boolean;
}

const AgentRow = memo(function AgentRow({
  callId,
  description,
  summary,
  running,
  depth,
  index,
  live,
}: AgentRowProps) {
  const dotState: RowDotState = running ? (live ? "running" : "stopped") : "done";
  const isRunningRow = dotState === "running";
  return (
    <div
      className={`cv-agentboard-row${isRunningRow ? " is-running" : ""}${dotState === "done" ? " is-done" : ""}`}
      // 缩进走 --depth 进 CSS calc：内联 paddingLeft 会把行自身的左内边距整个盖掉，
      // depth=0 时头像就顶出行边（曾出过这个 bug）。
      style={{ "--i": index, "--depth": Math.min(depth, 2) } as CSSProperties}
    >
      <span className="cv-agentboard-avatar" aria-hidden="true">
        <ProseBotIcon hue={hashHue(callId)} width={24} height={24} />
      </span>
      <span className="cv-agentboard-main">
        <span className="cv-agentboard-line1">
          <span className="cv-agentboard-desc">{description}</span>
          <span className="cv-agentboard-state">
            <span
              className={`run-dot${dotState === "running" ? " running" : dotState === "done" ? " done" : ""}`}
              aria-hidden="true"
            />
            {isRunningRow ? "运行中" : dotState === "done" ? "已完成" : "已停止"}
          </span>
        </span>
        {isRunningRow && (
          // keyed by summary：文本一变即重挂载，走上滑淡入（事件驱动的「滚动」，不跑马灯）。
          <span className="cv-agentboard-sumline" key={summary}>
            <span className="cv-agentboard-sum cv-shimmer">{summary}</span>
          </span>
        )}
      </span>
    </div>
  );
});
