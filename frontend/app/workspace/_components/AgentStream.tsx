"use client";

import { RecoveryActions } from "./RecoveryActions";

import { memo, useCallback, useEffect, useMemo, type MutableRefObject, type RefObject } from "react";
import { useWorkspaceStore } from "@/lib/store/workspace";
import type { ChatMsg } from "@/lib/hagent/timeline";
import { ThinkingBlock, msgsToThinkingItems, type ThinkingItem } from "./ThinkingBlock";
import { ToolCallBlock, anyItemRunning } from "./ToolCallBlock";
import { Response } from "@/components/ai-elements/response";

type Turn =
  | { kind: "user"; id: string; content: string }
  | {
      kind: "assistant";
      id: string;
      items: ThinkingItem[];
      response: string;
      narration: string;
      errors: string[];
      showMeta: boolean;
    };

// 把扁平 timeline 分组为「用户回合 / 助手回合」。一个助手段 = 思考/工具块 + 紧随其后的
// 正文回复（对应设计稿的 .cm-message-turn）。关键：助手段以「正文回复」为界——一旦当前段
// 已产出正文，再出现新的 thinking/工具，就 flush 出新段，让后续思考/工具在正文**下方**另起
// 一条消息，而非全部回挤到顶部。其中「正文之后又出现思考/工具」意味着这段正文是 tool-loop
// 过程旁白（模型宣告下一步动作），flush 前降级进 narration 渲染为外层 dim 单行；真正的回合
// 末回复只在 user 边界或时间线末尾 flush，不走该分支，保持满级正文。
function groupTurns(timeline: ChatMsg[]): Turn[] {
  const turns: Turn[] = [];
  let cur: Extract<Turn, { kind: "assistant" }> | null = null;
  let roundOpened = false; // 本轮（上一条 user 之后）是否已有助手段 → 决定智能体名只在首段显示
  const flush = () => {
    if (cur && (cur.items.length || cur.response || cur.narration || cur.errors.length)) turns.push(cur);
    cur = null;
  };
  for (const m of timeline) {
    if (m.role === "user") {
      flush();
      turns.push({ kind: "user", id: m.id, content: m.content });
      roundOpened = false;
      continue;
    }
    const isThinkingItem = m.role !== "assistant_text" && m.role !== "error";
    // 当前段已经回复过正文，又来新的思考/工具 → 这段正文是过程旁白：降级后另起新段。
    if (cur && cur.response && isThinkingItem) {
      cur.narration = cur.response;
      cur.response = "";
      flush();
    }
    if (!cur) {
      cur = {
        kind: "assistant",
        id: `a-${m.id}`,
        items: [],
        response: "",
        narration: "",
        errors: [],
        showMeta: !roundOpened,
      };
      roundOpened = true;
    }
    if (m.role === "assistant_text") cur.response += m.content;
    else if (m.role === "error") cur.errors.push(m.content);
    else cur.items.push(...msgsToThinkingItems([m]));
  }
  flush();
  return turns;
}

function summaryFor(items: ThinkingItem[]): string {
  const tools = items.filter((i) => i.kind === "tool" || i.kind === "subagent").length;
  const reasoning = items.filter((i) => i.kind === "reasoning").length;
  const parts: string[] = [];
  if (reasoning) parts.push(`${reasoning} 段推理`);
  if (tools) parts.push(`${tools} 次工具调用`);
  return parts.length ? `思考过程 · ${parts.join(" · ")}` : "思考过程";
}

// 按相对 thinking 的位置把段内 items 切三段：
//   before = 第一个 thinking 之前的工具；after = 最后一个 thinking 之后的工具 —— 二者在外层与正文同级；
//   middle = 首末 thinking 之间（含夹在两段 thinking 中间的工具）—— 仅它进折叠思考块。
// 无 thinking 项时全部归 before（即所有工具都在外层，无思考块）。
function partitionItems(items: ThinkingItem[]): {
  before: ThinkingItem[];
  middle: ThinkingItem[];
  after: ThinkingItem[];
} {
  const first = items.findIndex((i) => i.kind === "reasoning");
  if (first < 0) return { before: items, middle: [], after: [] };
  let last = first;
  for (let i = items.length - 1; i > first; i -= 1) {
    if (items[i]?.kind === "reasoning") {
      last = i;
      break;
    }
  }
  return { before: items.slice(0, first), middle: items.slice(first, last + 1), after: items.slice(last + 1) };
}

// —— turn 内容签名 ——
// groupTurns 每帧都产出全新 turn 对象，直接 map 会让所有 turn（含已完成的历史回合）
// 每帧重渲染整棵子树。我们给每个 turn 算一个反映其「可变内容」的签名，配合下面 memo 的
// 自定义比较：签名相同就跳过重渲染，每帧只重渲流式末尾那个在变的 turn。
function itemSig(i: ThinkingItem): string {
  if (i.kind === "reasoning") return `r${i.id}.${i.text.length}`;
  if (i.kind === "tool")
    return `t${i.id}.${i.call.status}.${i.call.args.length}.${i.call.result?.length ?? 0}`;
  // subagent：状态文字依赖 status 与最近一条 child（最近动作），都纳入签名。
  const c = i.run.children;
  const last = c[c.length - 1];
  return `s${i.id}.${i.run.status}.${c.length}.${last ? last.role : ""}`;
}

function turnSignature(t: Turn, active = false): string {
  if (t.kind === "user") return `u:${t.id}:${t.content.length}`;
  return `a:${t.id}:${active ? 1 : 0}:${t.response.length}:${t.narration.length}:${t.errors.length}:${t.items.map(itemSig).join("|")}`;
}

const UserTurn = memo(
  function UserTurn({ turn }: { turn: Extract<Turn, { kind: "user" }>; sig: string }) {
    return (
      <div className="cm-message-turn cm-user">
        <div className="cm-user-stack">
          <div className="cm-user-meta">你</div>
          <div className="cm-user-bubble">{turn.content}</div>
        </div>
      </div>
    );
  },
  (a, b) => a.sig === b.sig,
);

const AssistantTurn = memo(
  function AssistantTurn({
    turn,
    active,
  }: {
    turn: Extract<Turn, { kind: "assistant" }>;
    active: boolean;
    sig: string;
  }) {
    const { before, middle, after } = partitionItems(turn.items);
    return (
      <div className="cm-message-turn cm-assistant">
        <div className="cm-assistant-response">
          {turn.showMeta && <div className="cm-assistant-meta">Prose</div>}
          <ToolCallBlock items={before} active={active && anyItemRunning(before)} />
          <ThinkingBlock
            items={middle}
            summary={active ? "正在思考" : summaryFor(middle)}
            active={active}
          />
          <ToolCallBlock items={after} active={active && anyItemRunning(after)} />
          {turn.narration && (
            <div className="cm-narration" title={turn.narration}>
              {turn.narration}
            </div>
          )}
          {turn.response && (
            <div className="cm-response">
              <Response>{turn.response}</Response>
            </div>
          )}
          {turn.errors.map((e, i) => (
            <div key={i} className="cm-response cm-error-message">
              <p><span className="cm-error-mark" aria-hidden="true" />{e}</p>
            </div>
          ))}
        </div>
      </div>
    );
  },
  (a, b) => a.sig === b.sig,
);

interface AgentStreamProps {
  /** 滚动容器 ref。由 MessageWindow 持有——浮窗改档时要在同一个容器上做滚动锚定。 */
  scrollRef: RefObject<HTMLDivElement | null>;
  /** 「是否贴在底部」。同样由 MessageWindow 持有，以便熬过胶囊态（那时本组件已卸载）。 */
  stickRef: MutableRefObject<boolean>;
}

/** 纯 transcript：只渲染消息本身。状态条在浮窗标题栏，输入区在底部坞，都不在这里。 */
export function AgentStream({ scrollRef, stickRef }: AgentStreamProps) {
  const phase = useWorkspaceStore((s) => s.phase);
  const timeline = useWorkspaceStore((s) => s.timeline);
  const matrices = useWorkspaceStore((s) => s.matrices);
  const errorMsg = useWorkspaceStore((s) => s.errorMsg);

  const turns = useMemo(() => groupTurns(timeline), [timeline]);

  // —— 跟随最新消息自动下滚 ——
  // 内容随流式增长时，把滚动容器贴到底部，让焦点始终在最新 message。仅当用户当前已在底部
  // 附近时才贴底，避免用户上滚回看历史时被强行拽回。
  // todos 刻意不在依赖里：它不进 transcript（渲染在右上角执行看板），订阅它只会让整条
  // 时间线跟着每次 todo.updated 白重渲一遍。
  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (el) stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }, [scrollRef, stickRef]);
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [turns, phase, matrices, scrollRef, stickRef]);

  return (
    <div className="stream-scroll" ref={scrollRef} onScroll={onScroll}>
      <div className="stream-inner">
        {turns.length === 0 && phase === "idle" && (
          <div className="cm-message-turn cm-assistant">
            <div className="cm-assistant-response">
              <div className="cm-assistant-meta">Prose</div>
              <div className="cm-response">
                <p>已就绪。请在下方输入区选择招标文件样本，或上传 <code>.md</code> 文件，我会提取项目概要、商务要求、技术要求与评分办法，供你逐项核验。</p>
              </div>
            </div>
          </div>
        )}

        {turns.length === 0 && phase === "done" && <div className="cm-message-turn cm-assistant"><div className="cm-assistant-response"><div className="cm-assistant-meta">Prose</div><div className="cm-response"><p>项目结果已载入。选择一类矩阵查看要求与原文，或在下方提出新的问题。</p><p>此处展示本次打开后的对话，历史会话尚未恢复。</p></div></div></div>}

        {turns.map((t, i) => {
          if (t.kind === "user") return <UserTurn key={t.id} turn={t} sig={turnSignature(t)} />;
          // 「正在思考」= 真·流式阶段（仅 running，不含 loading_results 等收尾态）、末段、且本段
          // 尚未产出正文（thinking→tool→thinking 阶段）。流一结束（done→loading_results）即转静态。
          const active = phase === "running" && i === turns.length - 1 && !t.response;
          return <AssistantTurn key={t.id} turn={t} active={active} sig={turnSignature(t, active)} />;
        })}

        {phase === "error" && errorMsg && (
          <div className="cm-message-turn cm-assistant">
            <div className="cm-assistant-response">
              <div className="cm-assistant-meta">Prose</div>
              <div className="cm-response cm-error-message">
                <p role="alert"><span className="cm-error-mark" aria-hidden="true" />本次操作未完成：{errorMsg}</p>
                <RecoveryActions />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
