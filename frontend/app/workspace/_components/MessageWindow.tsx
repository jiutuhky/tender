"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import { useWorkspaceStore, type StreamSize } from "@/lib/store/workspace";
import { ChevronIcon, MinusIcon, PlusIcon, ProseBotIcon } from "@/components/ui/icons";
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

// 液态玻璃参数。骨架取上游 demo（liquid-glass.maxrovensky.com）里 User Info 卡那一组
// （位移 100 / 饱和 140），两处按本产品的浅色画布调过：
//   · blurAmount 0.5（=20px）→ 0.2（≈10px）：20px 下背后只剩色块，读作毛玻璃；10px 能认出
//     卡片轮廓在弯，才读作一块透明的厚玻璃。可读性由 Frost 深色文字对浅底的对比保证。
//   · aberrationIntensity 2 → 0：色散在照片底上是"真实感"，在近白画布上只剩一圈蓝边线
//     （蓝通道位移最大、最先露出来）——用户明确不要。边缘的"玻璃感"改由 LiquidGlass 的
//     边缘光（.lg-rim）承担。
// 圆角 20px 与壳的 border-radius 一致（壳、光束、玻璃三者必须一致）。玻璃**不加底色**。
const GLASS = {
  displacementScale: 100,
  blurAmount: 0.2,
  saturation: 140,
  aberrationIntensity: 0,
  cornerRadius: 20,
  mode: "standard",
} as const;

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

  return (
    <div className="cv-msgwin-title">
      <div className="cv-msgwin-name">{docName ? `解析 ${docName}` : "标书智能解析"}</div>
      <div className="cv-msgwin-sub">
        <span className={`cv-msgwin-dot ${runDotState(phase)}`} aria-hidden="true" />
        <span role="status" aria-live="polite">
          {runStatusText(phase, todos.length, readyMatrixCount(matrices))}
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
  const live = useWorkspaceStore((s) => activityLine(s.timeline, s.phase));
  const settled = useWorkspaceStore((s) =>
    runStatusText(s.phase, s.todos.length, readyMatrixCount(s.matrices)),
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

  // prev = 已落定的上一档。转场期间它先不推进，好让退场那一棵继续在场。
  const [prev, setPrev] = useState<StreamSize>(size);
  const showMin = size === "min" || prev === "min";
  const showOpen = size === "open" || prev === "open";

  const settleScroll = useCallback(() => {
    const sc = scrollRef.current;
    if (sc && stickRef.current) sc.scrollTop = sc.scrollHeight;
  }, []);

  useLayoutEffect(() => {
    if (prev === size) return;
    const root = rootRef.current;
    if (!root) {
      setPrev(size);
      return;
    }
    // 初始状态修正（窄屏首帧收 min）不是转场，直切。
    if (skipAnimRef.current) {
      skipAnimRef.current = false;
      setPrev(size);
      return;
    }
    const min = minRef.current;
    const panel = panelRef.current;
    const sc = scrollRef.current;
    const reduce = prefersReducedMotion();
    gsap.killTweensOf([root, min, panel].filter((el) => el !== null));

    // —— 量盒 ——
    // useLayoutEffect 跑在 DOM 提交之后，此刻 data-state 已经是目标档，退场那一档的盒
    // 得临时翻回去量。三次强制重排，只在用户点开/收起时各发生一次，不在流式热路径上。
    gsap.set(root, { clearProps: "width,height" });
    root.dataset.state = "open";
    const openBox = root.getBoundingClientRect();
    // 时间线的内容宽必须量**开启档**的滚动口：面板 inset:0，收起时它已经跟着壳缩了。
    // .stream-scroll 的原生滚动条是隐藏的（scrollbar-width:none），clientWidth 即满宽。
    const contentWidth = sc ? sc.clientWidth : openBox.width;
    root.dataset.state = "min";
    const minBox = root.getBoundingClientRect();
    root.dataset.state = size; // 回到 React 已提交的值，中途重渲不会与命令式写入打架
    const from = prev === "open" ? openBox : minBox;
    const to = size === "open" ? openBox : minBox;

    // 重新打开即落到最新消息：min 的含义就是「我没在看 transcript」，
    // 回来时应当看见最新的一条，而非上次离开时的滚动位置。刻意如此，勿当 bug 修。
    if (size === "open" && sc) {
      sc.scrollTop = sc.scrollHeight;
      stickRef.current = true;
    }

    // —— 尺寸动画 ——
    // 本系统只允许 transform/opacity 动画，这里动 width/height 是既有例外
    // （论证见 globals.css「画布浮层」段）：
    // 1) 壳是 position:absolute + contain:layout，逐帧改宽高不脏化任何祖先；
    // 2) tween 开始前把 .stream-inner 的布局宽钉在**目标**像素上（--cv-msgwin-cw），
    //    整条时间线在整个过渡中只重排一次（tween 前那次），文字全程不换行；
    //    面板靠 overflow:hidden 把钉宽的内容裁开/让出，读作「窗框生长，内容原地不动」；
    // 3) scrollHeight 因此从第 0 帧就是终值，贴底数学全程稳定。
    //
    // 减弱动态不另走一条分支，而是把所有时长压成 0：终态、清理与 prev 推平的次序
    // 全部照旧走同一条时间线，只是一跳到位。少一条分支就少一处会漂移的等价实现。
    const d = (v: number) => (reduce ? 0 : v);
    root.style.setProperty("--cv-msgwin-cw", `${contentWidth}px`);
    // 过渡期把玻璃换成纯毛玻璃（CSS 里按 data-tweening 给 .lg-warp 换 backdrop-filter）。
    // 壳每帧换尺寸 = 滤镜图每帧在一张新画布上重跑一遍，实测中位帧从 16.6ms 掉到 30ms、
    // 偶发 400ms 长帧；而这 320ms 里玻璃本来就在淡入，折射看不看得见没人分辨得出来。
    root.dataset.tweening = "1";
    const settle = () => {
      root.style.removeProperty("--cv-msgwin-cw");
      delete root.dataset.tweening;
      settleScroll();
    };

    const opening = size === "open";
    // 交叉淡入的两个把手是「面板内容」与「播报条」，**玻璃本身不淡**：backdrop-filter 只能
    // 看见到最近 backdrop root 为止的画面，而 opacity<1 的祖先自己就是一个 root——淡玻璃的
    // 那 200ms 里它什么也看不见，整块变透明再"啪"地糊上。所以玻璃从第 0 帧就满不透明地
    // 跟着壳长大/缩小，读作「一块霜面从 Bot 旁边长出来」，只有字在淡。
    const enter = opening ? panel : min;
    const exit = opening ? min : panel;
    const tl = gsap.timeline({
      onComplete: () => {
        settle();
        setPrev(size);
      },
    });
    tl.fromTo(
      root,
      { width: from.width, height: from.height },
      {
        width: to.width,
        height: to.height,
        duration: d(DUR_PANEL),
        ease: TRACE_EASE_ENTER,
        clearProps: "width,height",
        onUpdate: settleScroll,
      },
      0,
    );
    if (exit) tl.to(exit, { autoAlpha: 0, duration: d(DUR_FLOAT), ease: TRACE_EASE_EXIT }, 0);
    if (enter) {
      tl.fromTo(
        enter,
        { autoAlpha: 0 },
        {
          autoAlpha: 1,
          duration: d(DUR_FLOAT),
          ease: TRACE_EASE_ENTER,
          clearProps: "opacity,visibility",
        },
        d(DUR_MICRO),
      );
    }
  }, [size, prev, settleScroll]);

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
        <ProseBotIcon aria-hidden="true" />
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
