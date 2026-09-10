"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import { useWorkspaceStore, type StreamSize } from "@/lib/store/workspace";
import { ChevronIcon, MinusIcon, PlusIcon } from "@/components/ui/icons";
import { ProseBot } from "@/components/ui/icons";
import { deriveMainBotState, currentTurnKey } from "@/lib/bot/derive";
import {
  DUR_FLOAT,
  DUR_MICRO,
  DUR_PANEL,
  TRACE_EASE_ENTER,
  TRACE_EASE_EXIT,
  prefersReducedMotion,
} from "./canvas/traceMotion";
import { activityLine, isRunning, readyMatrixCount, runDotState, runStatusText } from "./runStatus";
import { AgentStream } from "./AgentStream";
import { StreamScrollbar } from "./StreamScrollbar";

import { LiquidGlass } from "./LiquidGlass";

// 大面积浮层使用单层毛玻璃，圆角与窗口外壳保持一致。
const GLASS = { cornerRadius: 28 } as const;

/**
 * Bot 形象单拆一层：它按时间线末段派生状态（在思考？在检索？在落笔？），流式期每帧
 * 都可能变。selector 返回的是**字符串**，状态没真的换档时 Object.is 相等，zustand 直接
 * 跳过重渲——所以绝大多数帧这一层是静止的，动的是引擎内部的 rAF。
 */
function WindowBot() {
  const state = useWorkspaceStore((s) => deriveMainBotState(s.phase, s.timeline, s.botSignals));
  const turn = useWorkspaceStore((s) => currentTurnKey(s.timeline));
  return (
    <ProseBot
      state={state}
      followPointer
      idleMoods
      blinkOnHover
      size={48}
      completionKey={turn}
      aria-hidden="true"
    />
  );
}

// 标题栏内容单拆一层：todos / matrices 在流式期每帧都变，让它们只重渲这一小块，
// 外层 MessageWindow 就不会在改档的 tween 中途被重渲、把 data-state 冲掉。
//
// 版式照原型的两行标题块，但第一行放的是**在办的文件**而非 "Prose Bot"——
// 身份已由左侧常驻的 Bot 形象交代，再写一遍品牌名是把一行字浪费在重复上。
function WindowStatus() {
  const phase = useWorkspaceStore((s) => s.phase);
  const docName = useWorkspaceStore((s) => s.currentDocName);
  const todos = useWorkspaceStore((s) => s.todos);
  const matrices = useWorkspaceStore((s) => s.matrices);
  const signals = useWorkspaceStore((s) => s.botSignals);

  return (
    <div className="cv-msgwin-title">
      <div className="cv-msgwin-name">{docName ? `解析 ${docName}` : "标书智能解析"}</div>
      <div className="cv-msgwin-sub">
        <span className={`cv-msgwin-dot ${runDotState(phase, signals)}`} aria-hidden="true" />
        <span role="status" aria-live="polite">
          {runStatusText(phase, todos.length, readyMatrixCount(matrices), signals)}
        </span>
      </div>
    </div>
  );
}

// 同样单拆，理由同上：它订阅 projectId / phase，与标题栏、与窗壳互不牵连。
function NewSessionButton() {
  const projectId = useWorkspaceStore((s) => s.projectId);
  const phase = useWorkspaceStore((s) => s.phase);
  const newSession = useWorkspaceStore((s) => s.newSession);

  if (!projectId) return null;
  return (
    <button
      className="cv-msgwin-btn"
      type="button"
      disabled={isRunning(phase)}
      aria-label="新建会话"
      title="在当前项目内新建会话，共享同一工作区"
      onClick={() => void newSession()}
    >
      <PlusIcon width={15} height={15} />
    </button>
  );
}

/**
 * min 档的一行滚动播报。
 *
 * 推进由**新活动行到达**驱动，不是定时器——原型里的 3.6s 轮播只是没有真实数据流时的
 * 替身。文案取 activityLine（运行中「正在…」），待命/完成态换成与标题栏同源的完成句。
 *
 * 出场那条留在 DOM 里直到下一次推进：一次推进要有两个物体同时在场，纯淡入只会看到
 * 「一个消失、一个出现」而读不出「上一条被顶上去了」。
 */
function MinTicker() {
  const phase = useWorkspaceStore((s) => s.phase);
  const live = useWorkspaceStore((s) => activityLine(s.timeline, s.phase, s.botSignals));
  const settled = useWorkspaceStore((s) =>
    runStatusText(s.phase, s.todos.length, readyMatrixCount(s.matrices), s.botSignals),
  );
  const text = isRunning(phase) ? live : settled;

  // 渲染期就地校正（React 官方的「props 变了要调整 state」写法）：本次渲染直接得出
  // 新旧两条，不必等一趟 effect 再补一次渲染——播报要跟 SSE 同帧到位。
  const [roll, setRoll] = useState<{ cur: string; out: string | null }>({ cur: text, out: null });
  if (roll.cur !== text) setRoll({ cur: text, out: roll.cur });
  const out = roll.out;

  // key 取文案本身：文案一变，进场那条换 key 重挂载、动画重播；上一条被复用为出场那条，
  // animation-name 一换即重新起跑。两者同时在场，才读得出「上一条被顶上去了」。
  return (
    <span className="cv-msgwin-ticker" role="status" aria-live="polite">
      {out !== null && out !== text && (
        <span key={out} className="cv-msgwin-tick is-out" aria-hidden="true">
          {out}
        </span>
      )}
      <span key={text} className="cv-msgwin-tick is-in">
        {text}
      </span>
    </span>
  );
}

/**
 * 画布左上角的 Prose Bot 消息窗，两档：min（Bot + 一行播报，无底）/ open（玻璃面板）。
 *
 * Bot 是转场的锚点——两档里它的绝对坐标完全一致，窗口从它右下方生长出来，
 * 所以点击不产生位移感，读作「窗口围着 Bot 展开」而非「换了一个控件」。
 *
 * 播报条与面板是**两棵不同的 DOM**，交叉淡入。这不是审美取舍：min 档必须卸载整条
 * transcript，否则几百个 memo'd turn 在解析全程每个 rAF 帧都要参与 reconcile——
 * 而「我不看对话了」正是用户点收起的意思。
 */
export function MessageWindow() {
  const size = useWorkspaceStore((s) => s.streamSize);
  const setStreamSize = useWorkspaceStore((s) => s.setStreamSize);
  const phase = useWorkspaceStore((s) => s.phase);
  const running = isRunning(phase);

  const rootRef = useRef<HTMLDivElement>(null);
  const minRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const botRef = useRef<HTMLButtonElement>(null);
  const stickRef = useRef(true);
  // 下一次档位变化是「初始状态修正」而非用户转场时置位：直切，不播动画。
  const skipAnimRef = useRef(false);

  // 改档时保留两份内容，动画落定后卸载退场内容；反向操作也复用当前节点。
  const [presence, setPresence] = useState({ target: size, min: size === "min", open: size === "open" });
  if (presence.target !== size) setPresence({ target: size, min: true, open: true });
  const showMin = presence.min;
  const showOpen = presence.open;
  const previousTargetRef = useRef<StreamSize>(size);

  const settleScroll = useCallback(() => {
    const sc = scrollRef.current;
    if (sc && stickRef.current) sc.scrollTop = sc.scrollHeight;
  }, []);

  useLayoutEffect(() => {
    const previousTarget = previousTargetRef.current;
    previousTargetRef.current = size;
    if (previousTarget === size) return;
    const root = rootRef.current;
    const finishPresence = () => setPresence({ target: size, min: size === "min", open: size === "open" });
    if (!root) {
      finishPresence();
      return;
    }
    if (skipAnimRef.current) {
      skipAnimRef.current = false;
      finishPresence();
      return;
    }
    const min = minRef.current;
    const panel = panelRef.current;
    const sc = scrollRef.current;
    if (prefersReducedMotion()) {
      for (const element of [root, min, panel]) {
        if (!element) continue;
        for (const property of ["width", "height", "opacity", "visibility"]) element.style.removeProperty(property);
      }
      root.style.removeProperty("--cv-msgwin-cw");
      delete root.dataset.tweening;
      settleScroll();
      finishPresence();
      return;
    }
    const reversing = root.dataset.tweening === "1";

    // 先读取屏幕上的实际尺寸，再量目标盒；中途反向时保留正在显示的宽高与透明度。
    root.dataset.state = previousTarget;
    const from = root.getBoundingClientRect();
    gsap.set(root, { clearProps: "width,height" });
    root.dataset.state = "open";
    const openBox = root.getBoundingClientRect();
    const contentWidth = sc ? sc.clientWidth : openBox.width;
    root.dataset.state = "min";
    const minBox = root.getBoundingClientRect();
    root.dataset.state = size;
    const to = size === "open" ? openBox : minBox;

    if (size === "open" && sc) {
      sc.scrollTop = sc.scrollHeight;
      stickRef.current = true;
    }

    // 外壳以 contain:layout 限定布局影响，正文钉在展开宽度，逐帧仅裁切而不重新换行。
    root.style.setProperty("--cv-msgwin-cw", `${contentWidth}px`);
    root.dataset.tweening = "1";
    const enter = size === "open" ? panel : min;
    const exit = size === "open" ? min : panel;
    if (enter && !reversing) gsap.set(enter, { autoAlpha: 0 });

    // 只淡入淡出正文，玻璃持续采样背景；反向时取消旧时间线，立刻接续当前形态。
    const tl = gsap.timeline({
      onComplete: () => {
        root.style.removeProperty("--cv-msgwin-cw");
        delete root.dataset.tweening;
        settleScroll();
        finishPresence();
      },
    });
    tl.fromTo(root, { width: from.width, height: from.height }, {
      width: to.width,
      height: to.height,
      duration: DUR_PANEL,
      ease: TRACE_EASE_ENTER,
      clearProps: "width,height",
      onUpdate: settleScroll,
    }, 0);
    if (exit) tl.to(exit, { autoAlpha: 0, duration: DUR_FLOAT, ease: TRACE_EASE_EXIT }, 0);
    if (enter) tl.to(enter, {
      autoAlpha: 1,
      duration: DUR_FLOAT,
      ease: TRACE_EASE_ENTER,
      clearProps: "opacity,visibility",
    }, reversing ? 0 : DUR_MICRO);

    // 保留当前内联形态供下一次操作接续；卸载时也取消时间线的延迟回调。
    return () => { tl.kill(); };
  }, [size, settleScroll]);

  // 收起时把焦点从即将卸载的面板交给 Bot，别让它掉回 <body>（对齐 CanvasDrawer 的焦点交接）。
  const collapse = useCallback(() => {
    const panel = panelRef.current;
    if (panel && panel.contains(document.activeElement)) {
      requestAnimationFrame(() => botRef.current?.focus());
    }
    setStreamSize("min");
  }, [setStreamSize]);

  // 解析失败不能只藏在一行播报里：出错即自动打开。
  useEffect(() => {
    if (phase === "error" && size === "min") setStreamSize("open");
  }, [phase, size, setStreamSize]);

  // 窄屏首帧收成 min，别让画布被整个盖住。只做一次——resize 时再改会跟用户打架。
  // 打上 skipAnim：这是初始状态修正，不是用户发起的转场，一进页面不该播退场动画。
  useEffect(() => {
    if (!window.matchMedia("(max-width: 640px)").matches) return;
    if (useWorkspaceStore.getState().streamSize === "min") return;
    skipAnimRef.current = true;
    setStreamSize("min");
  }, [setStreamSize]);

  useEffect(() => {
    const targets = [rootRef.current, minRef.current, panelRef.current];
    return () => {
      const live = targets.filter((el) => el !== null);
      if (live.length) gsap.killTweensOf(live);
    };
  }, []);

  const open = size === "open";
  return (
    <div
      id="cv-msgwin"
      ref={rootRef}
      className="cv-msgwin"
      data-state={size}
      data-busy={running ? "1" : "0"}
    >
      {/* Bot 是唯一的开合控件（用户定），播报文字与 caret 只是提示，不可点。 */}
      <button
        ref={botRef}
        type="button"
        className="cv-msgwin-bot"
        aria-expanded={open}
        aria-controls="cv-msgwin-panel"
        aria-label={open ? "收起执行流" : "展开执行流"}
        title={open ? "收起 Prose Bot 执行流" : "展开 Prose Bot 执行流"}
        onClick={() => (open ? collapse() : setStreamSize("open"))}
      >
        <WindowBot />
      </button>

      {showMin && (
        <div ref={minRef} className="cv-msgwin-min">
          <MinTicker />
          <ChevronIcon className="cv-msgwin-caret" width={11} height={11} aria-hidden="true" />
        </div>
      )}

      {/* 玻璃面（LiquidGlass）铺满壳；面板内容作为它的 children 长在玻璃里。
          外层 .cv-msgwin-glass 只是定位盒——**不要**给它加 opacity/visibility 动画（理由见上）。 */}
      {showOpen && (
        <div className="cv-msgwin-glass">
          <LiquidGlass className="cv-msgwin-lg" {...GLASS}>
            <div
              ref={panelRef}
              id="cv-msgwin-panel"
              className="cv-msgwin-panel"
              role="region"
              aria-label="智能体执行流"
            >
              <header className="cv-msgwin-head">
                <WindowStatus />
                <span className="cv-msgwin-tools">
                  <NewSessionButton />
                  <button
                    className="cv-msgwin-btn"
                    type="button"
                    aria-label="收起为播报条"
                    title="收起为播报条"
                    onClick={collapse}
                  >
                    <MinusIcon width={15} height={15} />
                  </button>
                </span>
              </header>

              <AgentStream scrollRef={scrollRef} stickRef={stickRef} />
              <StreamScrollbar />
            </div>
          </LiquidGlass>
        </div>
      )}

      {/* 边框光束在最上层，且在玻璃壳之外：壳的 overflow:hidden 会剪掉外扩的辉光。
          只在 open 档亮——min 没有边可扫，运行中由 Bot 的光晕与扫描眼交代。 */}
      {running && showOpen && (
        <div className="cv-msgwin-beam" aria-hidden="true">
          <i className="cv-msgwin-beam-inner" />
          <i className="cv-msgwin-beam-stroke" />
          <i className="cv-msgwin-beam-bloom" />
        </div>
      )}
    </div>
  );
}
