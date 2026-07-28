"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import { useWorkspaceStore, type StreamSize } from "@/lib/store/workspace";
import {
  ChevronIcon,
  CornersInIcon,
  CornersOutIcon,
  MinusIcon,
  PlusIcon,
} from "@/components/ui/icons";
import {
  DUR_FLOAT,
  DUR_PANEL,
  TRACE_EASE_ENTER,
  TRACE_EASE_EXIT,
  prefersReducedMotion,
} from "./canvas/traceMotion";
import { activityLine, isRunning, readyMatrixCount, runDotState, runStatusText } from "./runStatus";
import { AgentStream } from "./AgentStream";
import { StreamScrollbar } from "./StreamScrollbar";

type OpenSize = Exclude<StreamSize, "capsule">;

const GLASS = {
  backdropFilter: "blur(30px) saturate(180%)",
  WebkitBackdropFilter: "blur(30px) saturate(180%)",
} as const;

// 标题栏内容单拆一层：todos / matrices 在流式期每帧都变，让它们只重渲这一小块，
// 外层 MessageWindow 就不会在改尺寸的 tween 中途被重渲、把 data-size 冲掉。
function WindowStatus() {
  const phase = useWorkspaceStore((s) => s.phase);
  const docName = useWorkspaceStore((s) => s.currentDocName);
  const todos = useWorkspaceStore((s) => s.todos);
  const matrices = useWorkspaceStore((s) => s.matrices);
  const projectId = useWorkspaceStore((s) => s.projectId);
  const newSession = useWorkspaceStore((s) => s.newSession);

  return (
    <>
      <span className={`run-dot ${runDotState(phase)}`} aria-hidden="true" />
      <span className="run-brief-name">{docName ? `解析 ${docName}` : "标书智能解析"}</span>
      <span className="run-brief-status" role="status" aria-live="polite">
        {runStatusText(phase, todos.length, readyMatrixCount(matrices))}
      </span>
      {projectId && (
        <button
          className="run-brief-new"
          type="button"
          disabled={isRunning(phase)}
          title="在当前项目内新建会话，共享同一工作区"
          onClick={() => void newSession()}
        >
          <PlusIcon width={13} height={13} />
          <span>新建会话</span>
        </button>
      )}
    </>
  );
}

// 胶囊上的一行状态。同样单拆，理由同上。
// 运行中额外挂两层动效：边框流光（.cv-sheen）与文字流光（.cv-shimmer）。
function CapsuleStatus() {
  const phase = useWorkspaceStore((s) => s.phase);
  const line = useWorkspaceStore((s) => activityLine(s.timeline, s.phase));
  const running = isRunning(phase);
  return (
    <>
      {running && <span className="cv-sheen" aria-hidden="true" />}
      <span className={`run-dot ${runDotState(phase)}`} aria-hidden="true" />
      <span
        className={`cv-capsule-text${running ? " cv-shimmer" : ""}`}
        role="status"
        aria-live="polite"
      >
        {running ? line : `标书智能体 · ${line}`}
      </span>
    </>
  );
}

/**
 * 画布左上角的消息浮窗，三档：capsule / normal / expanded。
 *
 * 胶囊与窗壳是**两棵不同的 DOM**，交叉淡入。这不是审美取舍：胶囊态必须卸载整条
 * transcript，否则几百个 memo'd turn 在解析全程每个 rAF 帧都要参与 reconcile——
 * 而「我不看对话了」正是用户点收起的意思。
 */
export function MessageWindow() {
  const size = useWorkspaceStore((s) => s.streamSize);
  const lastOpenSize = useWorkspaceStore((s) => s.lastOpenSize);
  const setStreamSize = useWorkspaceStore((s) => s.setStreamSize);
  const phase = useWorkspaceStore((s) => s.phase);

  const shellRef = useRef<HTMLDivElement>(null);
  const capsuleRef = useRef<HTMLButtonElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);
  // 下一次档位变化是「初始状态修正」而非用户转场时置位：直切，不播动画。
  const skipAnimRef = useRef(false);

  // prev = 已落定的上一档。转场期间它先不推进，好让退场那一档继续在场——
  // 交叉淡入需要两个物体同时可见，纯淡入只会看到「一个消失、一个出现」。
  const [prev, setPrev] = useState<StreamSize>(size);
  const showCapsule = size === "capsule" || prev === "capsule";
  const showShell = size !== "capsule" || prev !== "capsule";
  // 窗壳的呈现档：收起过程中 size 已是 capsule，壳要保留退场前的尺寸。
  const shellSize: OpenSize = size === "capsule" ? (prev === "capsule" ? lastOpenSize : prev) : size;

  // 改档后把滚动位置重新钉住：贴底的继续贴底，上滚过的保住「距底距离」——
  // clientHeight 变大时浏览器会 clamp scrollTop，直接存 scrollTop 会静默漂移。
  const settleScroll = useCallback((gap: number) => {
    const sc = scrollRef.current;
    if (!sc) return;
    sc.scrollTop = stickRef.current
      ? sc.scrollHeight
      : Math.max(0, sc.scrollHeight - sc.clientHeight - gap);
  }, []);

  useLayoutEffect(() => {
    if (prev === size) return;
    // 初始状态修正（窄屏首帧收胶囊）不是转场，直切。
    if (skipAnimRef.current) {
      skipAnimRef.current = false;
      setPrev(size);
      return;
    }
    const shell = shellRef.current;
    const capsule = capsuleRef.current;
    const reduce = prefersReducedMotion();
    const targets = [shell, capsule].filter((el) => el !== null);
    if (targets.length) gsap.killTweensOf(targets);

    // —— 开启档之间：一棵树改尺寸 ——
    // 三态里唯一动 width/height 的过渡。合法性论证（勿反复评审）：
    // 1) 元素是 position:absolute + contain:layout paint，逐帧改宽高不脏化任何祖先；
    // 2) tween 开始前把 .stream-inner 的布局宽钉在**目标**像素上（--cv-msgwin-cw），
    //    整条时间线在整个过渡中只重排一次（tween 前那一次），文字全程不换行；
    //    外壳靠 overflow:hidden 把钉宽的内容裁开/让出，读作「窗框生长，内容原地不动」；
    // 3) scrollHeight 因此从第 0 帧就是终值，贴底/锚定数学全程稳定。
    // 结构上这正是 traceMotion.ts 已备案那条例外的镜像：抽屉加宽时靠主列恒定 548px
    // 让列表零重排，这里反过来——内容持恒定像素宽，外壳围着它长/缩。
    if (prev !== "capsule" && size !== "capsule") {
      if (!shell) {
        setPrev(size);
        return;
      }
      const from = shell.getBoundingClientRect();
      gsap.set(shell, { clearProps: "width,height,transform,opacity,visibility" });
      shell.dataset.size = size; // CSS 给出目标盒
      const to = shell.getBoundingClientRect(); // 一次强制重排，取真实终值
      shell.style.setProperty("--cv-msgwin-cw", `${to.width}px`);
      const sc = scrollRef.current;
      const gap = sc ? sc.scrollHeight - sc.scrollTop - sc.clientHeight : 0;
      setPrev(size); // 立即推平：React 的 data-size 绑定随即与命令式写入一致，中途重渲不会冲掉
      const unpin = () => {
        shell.style.removeProperty("--cv-msgwin-cw");
        settleScroll(gap);
      };
      if (reduce) {
        unpin();
        return;
      }
      gsap.fromTo(
        shell,
        { width: from.width, height: from.height },
        {
          width: to.width,
          height: to.height,
          duration: DUR_PANEL,
          ease: TRACE_EASE_ENTER,
          clearProps: "width,height",
          onUpdate: () => settleScroll(gap),
          onComplete: unpin,
        },
      );
      return;
    }

    // —— 胶囊 → 展开 ——
    if (size !== "capsule") {
      // 重新打开即落到最新消息：胶囊的含义就是「我没在看 transcript」，
      // 回来时应当看见最新的一条，而非上次离开时的滚动位置。刻意如此，勿当 bug 修。
      const sc = scrollRef.current;
      if (sc) sc.scrollTop = sc.scrollHeight;
      stickRef.current = true;
      if (reduce || !shell) {
        setPrev(size);
        return;
      }
      gsap.fromTo(
        shell,
        { autoAlpha: 0, y: -4, scale: 0.98 },
        {
          autoAlpha: 1,
          y: 0,
          scale: 1,
          duration: DUR_PANEL,
          ease: TRACE_EASE_ENTER,
          transformOrigin: "0 0",
          clearProps: "transform,opacity,visibility",
        },
      );
      if (capsule) {
        gsap.to(capsule, {
          autoAlpha: 0,
          scale: 1.02,
          duration: DUR_FLOAT,
          ease: TRACE_EASE_EXIT,
          onComplete: () => setPrev(size),
        });
      } else {
        setPrev(size);
      }
      return;
    }

    // —— 展开 → 胶囊 ——
    if (reduce || !shell) {
      setPrev("capsule");
      return;
    }
    if (capsule) {
      gsap.fromTo(
        capsule,
        { autoAlpha: 0, y: -4 },
        {
          autoAlpha: 1,
          y: 0,
          duration: DUR_FLOAT,
          ease: TRACE_EASE_ENTER,
          clearProps: "transform,opacity,visibility",
        },
      );
    }
    gsap.to(shell, {
      autoAlpha: 0,
      y: -4,
      scale: 0.98,
      duration: DUR_FLOAT,
      ease: TRACE_EASE_EXIT,
      transformOrigin: "0 0",
      onComplete: () => setPrev("capsule"),
    });
  }, [size, prev, settleScroll]);

  // 收起时把焦点从即将卸载的窗壳交给胶囊，别让它掉回 <body>（对齐 CanvasDrawer 的焦点交接）。
  const collapse = useCallback(() => {
    const shell = shellRef.current;
    if (shell && shell.contains(document.activeElement)) {
      requestAnimationFrame(() => capsuleRef.current?.focus());
    }
    setStreamSize("capsule");
  }, [setStreamSize]);

  // 解析失败不能只藏在一个胶囊里：出错即自动打开。
  useEffect(() => {
    if (phase === "error" && size === "capsule") setStreamSize(lastOpenSize);
  }, [phase, size, lastOpenSize, setStreamSize]);

  // 窄屏首帧收成胶囊，别让画布被整个盖住。只做一次——resize 时再改会跟用户打架。
  // 打上 skipAnim：这是初始状态修正，不是用户发起的转场，一进页面不该播退场动画。
  useEffect(() => {
    if (!window.matchMedia("(max-width: 640px)").matches) return;
    skipAnimRef.current = true;
    setStreamSize("capsule");
  }, [setStreamSize]);

  useEffect(() => {
    const shell = shellRef.current;
    const capsule = capsuleRef.current;
    return () => {
      const targets = [shell, capsule].filter((el) => el !== null);
      if (targets.length) gsap.killTweensOf(targets);
    };
  }, []);

  return (
    <>
      {showCapsule && (
        <button
          ref={capsuleRef}
          type="button"
          className={`cv-capsule${isRunning(phase) ? " is-running" : ""}`}
          style={GLASS}
          title="展开执行流"
          aria-expanded={false}
          onClick={() => setStreamSize(lastOpenSize)}
        >
          <CapsuleStatus />
          <ChevronIcon className="cv-capsule-chevron" width={11} height={11} aria-hidden="true" />
        </button>
      )}

      {showShell && (
        <div
          id="cv-msgwin"
          ref={shellRef}
          className="cv-msgwin"
          data-size={shellSize}
          role="region"
          aria-label="智能体执行流"
        >
          <div className="cv-msgwin-head">
            <WindowStatus />
            <span className="cv-msgwin-tools">
              <button
                className="cv-msgwin-btn"
                type="button"
                aria-label={shellSize === "expanded" ? "还原窗口" : "放大窗口"}
                title={shellSize === "expanded" ? "还原窗口" : "放大窗口"}
                onClick={() => setStreamSize(shellSize === "expanded" ? "normal" : "expanded")}
              >
                {shellSize === "expanded" ? (
                  <CornersInIcon width={15} height={15} />
                ) : (
                  <CornersOutIcon width={15} height={15} />
                )}
              </button>
              <button
                className="cv-msgwin-btn"
                type="button"
                aria-label="收起为状态条"
                title="收起为状态条"
                onClick={collapse}
              >
                <MinusIcon width={15} height={15} />
              </button>
            </span>
          </div>

          <AgentStream scrollRef={scrollRef} stickRef={stickRef} />
          <StreamScrollbar />
        </div>
      )}
    </>
  );
}
