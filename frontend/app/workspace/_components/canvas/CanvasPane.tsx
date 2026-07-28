"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { gsap } from "gsap";
import { useWorkspaceStore } from "@/lib/store/workspace";
import {
  FrameIcon,
  GridIcon,
  MinusIcon,
  PlusIcon,
  RefreshCcwIcon,
  TreeStructureIcon,
} from "@/components/ui/icons";
import { useCanvasViewport, type WorldRect } from "./useCanvasViewport";
import { SpineCard } from "./SpineCard";
import { CanvasLinks } from "./CanvasLinks";
import { ArtifactCard, type CardBadge } from "./ArtifactCard";
import { CanvasDrawer } from "./CanvasDrawer";
import { CanvasDock } from "./CanvasDock";
import { MessageWindow } from "../MessageWindow";
import {
  LINK_DEFS,
  META,
  SPINE,
  initialCards,
  isMatrixCardType,
  matrixCardBadgeForPhase,
  type CardInst,
  type CardType,
} from "./cardMeta";
import {
  MATRIX_CARD_ORDER,
  cardsForStage,
  centerStageRect,
  deriveChoreoStage,
  type ChoreoStage,
} from "./choreography";
import type { DetailType } from "./CardDetail";

// 「下一步」占位落点:停靠后让位出来的中心舞台区域(world 坐标,纯常量)。
const NEXT_HINT_RECT = centerStageRect();

// 停靠飞行与相机取景是同一次运镜的两个组成部分,时长/曲线必须一致,
// 否则相机先落定、卡片还在飞,读成两拍子。
const FLIGHT_MOTION = { duration: 0.44, ease: "power3.inOut" } as const;

interface DrawerState {
  type: DetailType;
  cardType: CardType;
  title: string;
  skipEntrance?: boolean;
}

/** 内容包围盒（world 坐标）：制品卡并集;演示模式并入 mock 主轴卡 */
function computeBounds(cards: CardInst[], withSpine: boolean): WorldRect {
  let minX = withSpine ? SPINE.x : Infinity;
  let minY = withSpine ? SPINE.y : Infinity;
  let maxX = withSpine ? SPINE.x + SPINE.w : -Infinity;
  let maxY = withSpine ? SPINE.y + SPINE.headerH + SPINE.nodes.length * SPINE.rowH : -Infinity;
  for (const c of cards) {
    const m = META[c.type];
    minX = Math.min(minX, c.x);
    minY = Math.min(minY, c.y);
    maxX = Math.max(maxX, c.x + m.w);
    maxY = Math.max(maxY, c.y + m.h);
  }
  if (minX > maxX) return { x: 0, y: 0, w: 800, h: 600 };
  return { x: minX, y: minY, w: maxX - minX, h: maxY - minY };
}

/** 按模式/编排阶段解析包围盒:演示模式并入主轴卡;已停靠阶段并入中心舞台区域(为「下一步」占位保留)。 */
function resolveBounds(cards: CardInst[], realMode: boolean, stage: ChoreoStage | null): WorldRect {
  const b = computeBounds(cards, !realMode);
  if (!realMode || stage !== "docked") return b;
  const r = centerStageRect();
  const minX = Math.min(b.x, r.x);
  const minY = Math.min(b.y, r.y);
  return {
    x: minX,
    y: minY,
    w: Math.max(b.x + b.w, r.x + r.w) - minX,
    h: Math.max(b.y + b.h, r.y + r.h) - minY,
  };
}

export function CanvasPane() {
  const phase = useWorkspaceStore((s) => s.phase);
  const matrices = useWorkspaceStore((s) => s.matrices);
  const projectId = useWorkspaceStore((s) => s.projectId);
  const projectName = useWorkspaceStore((s) => s.projectName);
  const witnessedParse = useWorkspaceStore((s) => s.witnessedParse);

  // 双模式:idle = 静态 mockup 原型;解析一旦启动(含恢复) = 真实矩阵四卡。
  const realMode = phase !== "idle";
  const running = phase === "creating" || phase === "uploading" || phase === "running";

  // 停靠单向阀:同一模式 + 同一项目内停靠过就不再回落(纯推导的 dockedBefore 输入)。
  // 换项目 / 回 idle 即开新纪元。用「渲染期比对上一状态」的官方派生模式:纪元与槽位
  // 可能在同一次 set 里一起变化,阀值必须在本次渲染就重置,不能等 effect。
  const choreoEpoch = realMode ? `real:${projectId ?? ""}` : "mock";
  const [prevEpoch, setPrevEpoch] = useState(choreoEpoch);
  const [dockedOnce, setDockedOnce] = useState(false);
  const epochChanged = prevEpoch !== choreoEpoch;
  if (epochChanged) {
    setPrevEpoch(choreoEpoch);
    setDockedOnce(false);
  }

  // 编排阶段(真实模式):中心舞台 / 已停靠 / 解析中断,由槽位状态 + 进入路径纯推导。
  const stage: ChoreoStage | null = realMode
    ? deriveChoreoStage({
        statuses: {
          basic_info: matrices.basic_info.status,
          business: matrices.business.status,
          technical: matrices.technical.status,
          scoring: matrices.scoring.status,
        },
        witnessed: witnessedParse,
        streamAborted: phase === "error",
        dockedBefore: !epochChanged && dockedOnce,
      })
    : null;
  if (stage === "docked" && !epochChanged && !dockedOnce) setDockedOnce(true);

  const [cards, setCards] = useState<CardInst[]>(() =>
    realMode ? cardsForStage(stage ?? "center") : initialCards(),
  );
  // 已铺进 cards 的布局阶段。「下一步」占位以它为准而非推导阶段:推导阶段先翻 docked、
  // 卡位在后续 effect 才重铺,间隙帧里占位会压在仍居中的四卡上闪现。
  const [layoutStage, setLayoutStage] = useState<ChoreoStage | null>(() => (realMode ? stage : null));
  const [drawer, setDrawer] = useState<DrawerState | null>(null);

  const cardsRef = useRef(cards);
  useEffect(() => {
    cardsRef.current = cards;
  }, [cards]);
  const boundsRef = useRef<WorldRect>(resolveBounds(cards, realMode, stage));

  const getCard = useCallback((id: string) => cardsRef.current.find((c) => c.id === id), []);
  const moveCard = useCallback((id: string, x: number, y: number) => {
    setCards((prev) => prev.map((c) => (c.id === id ? { ...c, x, y, isNew: false } : c)));
  }, []);
  const openCard = useCallback((id: string, source: "pointer" | "keyboard" = "pointer") => {
    const c = cardsRef.current.find((card) => card.id === id);
    if (!c) return;
    setDrawer({
      type: c.type,
      cardType: c.type,
      title: c.title || META[c.type].title,
      skipEntrance: source === "keyboard",
    });
  }, []);
  const openOutline = useCallback((source: "pointer" | "keyboard" = "pointer") => {
    setDrawer({
      type: "__outline",
      cardType: "outline",
      title: "投标大纲",
      skipEntrance: source === "keyboard",
    });
  }, []);

  const { viewportRef, worldRef, zoomLabelRef, startCardDrag, zoomIn, zoomOut, fit, resetView } =
    useCanvasViewport({ getCard, onCardMove: moveCard, onCardClick: openCard, boundsRef });

  // 整套重铺卡位并同步包围盒(供「适应」即时读取,不等 [cards] effect)。
  const applyLayout = useCallback((next: CardInst[], mode: boolean, st: ChoreoStage | null) => {
    setCards(next);
    setLayoutStage(mode ? st : null);
    boundsRef.current = resolveBounds(next, mode, st);
  }, []);

  // 包围盒随卡片变化刷新（命令式，供「适应」即时读取）。初次适应由视口 ResizeObserver 驱动。
  useEffect(() => {
    boundsRef.current = resolveBounds(cards, realMode, stage);
  }, [cards, realMode, stage]);

  // 停靠飞行(亲历会话专属):阶段切换沿记录各卡「旧卡位 → 停靠位」的位移,
  // 待新卡位提交后由 layout effect 以 gsap 回放。恢复/刷新路径装载即停靠、
  // 不经过切换沿,天然不重放动画。
  const flightRef = useRef<Map<string, { dx: number; dy: number }> | null>(null);
  const flightTlRef = useRef<gsap.core.Timeline | null>(null);

  // 终止飞行并清残余 transform:卡片 DOM 按 key(恒为矩阵类型名)跨纪元复用,
  // 单纯 kill 会把中途位移永久留在元素上,错位下一纪元的卡位。
  const killFlight = useCallback(() => {
    flightRef.current = null;
    if (!flightTlRef.current) return;
    flightTlRef.current.kill();
    flightTlRef.current = null;
    const world = worldRef.current;
    if (world) {
      gsap.set(world.querySelectorAll<HTMLElement>(".cv-card, .cv-next-hint-body"), {
        clearProps: "transform,opacity,visibility",
      });
    }
  }, [worldRef]);
  useEffect(() => () => killFlight(), [killFlight]);

  // 模式翻转 / 编排阶段切换时重铺卡位(边沿触发):
  // - 模式翻转(startParse / resumeProject / reset):整套重铺并收起抽屉;进入真实模式
  //   无条件适应视口——即使用户在 idle 原型里动过视图,新布局也是全新纪元,必须可见;
  // - 阶段切入「已停靠」:一次性接管全部卡位(含被拖动过的),此后不再干预;
  //   亲历会话播放停靠飞行(reduced-motion 直切);相机与飞行同拍取景——停靠是一次性的
  //   阶段叙事(新场景),即使用户解析期间动过视图也要无条件框住整列,溢出不可接受;
  // - 阶段切入「解析中断」:定格原位,不动卡。
  const prevChoreo = useRef<{ realMode: boolean; stage: ChoreoStage | null; epoch: string }>({
    realMode,
    stage,
    epoch: choreoEpoch,
  });
  useEffect(() => {
    const prev = prevChoreo.current;
    prevChoreo.current = { realMode, stage, epoch: choreoEpoch };
    // 纪元切换沿先终止在途飞行:复用的卡片 DOM 不能把上一纪元的位移带进新布局。
    if (prev.realMode !== realMode || prev.epoch !== choreoEpoch) killFlight();
    if (prev.realMode !== realMode) {
      applyLayout(realMode ? cardsForStage(stage ?? "center") : initialCards(), realMode, stage);
      setDrawer(null);
      if (realMode) fit();
      return;
    }
    if (!realMode || stage === null || stage === prev.stage || stage === "interrupted") return;
    // 飞行只发生在同一纪元(同项目同模式)内的阶段切换沿:跨项目切换属于新纪元,
    // 上一个项目的旧卡位不是本项目的飞行起点,直接落新布局。
    const sameEpoch = prev.epoch === choreoEpoch;
    if (sameEpoch && stage === "docked" && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const from = new Map(cardsRef.current.map((c) => [c.id, c]));
      flightRef.current = new Map(
        cardsForStage("docked").map((c) => {
          const p = from.get(c.id);
          return [c.id, { dx: (p?.x ?? c.x) - c.x, dy: (p?.y ?? c.y) - c.y }];
        }),
      );
    }
    applyLayout(cardsForStage(stage), true, stage);
    // 有飞行时相机跟飞行同节拍;直切路径(reduced-motion / 跨纪元)用默认快速取景。
    if (stage === "docked") fit(false, flightRef.current ? FLIGHT_MOTION : undefined);
  }, [realMode, stage, choreoEpoch, applyLayout, fit, killFlight]);

  // 飞行演绎:停靠卡位已提交,先把各卡 transform 反推回起点,再按停靠顺序 stagger 飞向终点;
  // 「下一步」占位随队尾落地浮现(相对时间锚定,调 stagger/时长不再静默漂移)。
  // 只动 transform/opacity,收尾清除内联样式,不留残余。
  useLayoutEffect(() => {
    const flight = flightRef.current;
    if (!flight) return;
    const world = worldRef.current;
    if (!world) return;
    killFlight();
    const tl = gsap.timeline();
    flightTlRef.current = tl;
    MATRIX_CARD_ORDER.forEach((type, i) => {
      const el = world.querySelector<HTMLElement>(`.cv-card[data-card-id="${type}"]`);
      const d = flight.get(type);
      if (!el || !d || (d.dx === 0 && d.dy === 0)) return;
      tl.fromTo(
        el,
        { x: d.dx, y: d.dy },
        { x: 0, y: 0, duration: FLIGHT_MOTION.duration, ease: FLIGHT_MOTION.ease, clearProps: "transform" },
        i * 0.06,
      );
    });
    const hint = world.querySelector<HTMLElement>(".cv-next-hint-body");
    if (hint) {
      tl.fromTo(
        hint,
        { autoAlpha: 0, y: 8 },
        { autoAlpha: 1, y: 0, duration: 0.32, ease: "power3.out", clearProps: "transform,opacity,visibility" },
        Math.max(0, tl.duration() - 0.12),
      );
    }
  }, [cards, worldRef, killFlight]);

  // 重置画布:按当前编排阶段重铺卡位(已停靠→铺回停靠列,未完毕→铺回四宫格),mock 模式铺回原型初始位。
  const reset = useCallback((instant = false) => {
    setDrawer(null);
    if (realMode) {
      applyLayout(cardsForStage(stage ?? "center"), true, stage);
      fit(instant);
    } else {
      applyLayout(initialCards(), false, null);
      resetView(instant);
    }
  }, [resetView, fit, realMode, stage, applyLayout]);

  // 真实矩阵卡的徽标由 store 槽位派生(运行中未出数据也显示「解析中」,
  // 流中断时未终态槽位翻「解析中断」);mock 卡走 META 静态值。
  const streamAborted = phase === "error";
  const badgeFor = useCallback(
    (type: CardType): CardBadge | undefined =>
      isMatrixCardType(type) ? matrixCardBadgeForPhase(matrices[type], running, streamAborted) : undefined,
    [matrices, running, streamAborted],
  );

  // 抓卡即打断该卡在途 tween(停靠飞行/进场 pop)并清残余 transform:拖拽写 left/top、
  // tween 写 transform,不打断则两者叠加,卡片脱离指针对抗到时间线结束。
  const grabCard = useCallback(
    (id: string, e: ReactPointerEvent) => {
      const el = worldRef.current?.querySelector<HTMLElement>(`.cv-card[data-card-id="${id}"]`);
      if (el) {
        gsap.killTweensOf(el);
        gsap.set(el, { clearProps: "transform" });
      }
      startCardDrag(id, e);
    },
    [startCardDrag, worldRef],
  );

  const cardEls = useMemo(
    () =>
      cards.map((c) => (
        <ArtifactCard
          key={c.id}
          card={c}
          badge={badgeFor(c.type)}
          onStartDrag={(e) => grabCard(c.id, e)}
          onOpen={(source) => openCard(c.id, source)}
        />
      )),
    [cards, grabCard, openCard, badgeFor],
  );

  return (
    <div className="canvas-pane">
      <div className="cv-toolbar">
        <span className="cv-toolbar-label">
          <GridIcon width={15} height={15} />
          大纲视图
        </span>
        <span className="cv-toolbar-sub">
          {realMode
            ? `${projectName ?? "招标文件解析"} · ${
                running ? "正在解析" : phase === "done" ? "已完成" : phase === "error" ? "解析异常" : "载入结果"
              }`
            : "招标文件解析结果 · 工作进行中"}
        </span>
        <span className="cv-toolbar-spacer" />
        <span className="cv-zoom" role="group" aria-label="缩放">
          <button type="button" aria-label="缩小" onClick={(event) => zoomOut(event.detail === 0)}>
            <MinusIcon width={15} height={15} />
          </button>
          <span className="cv-zoom-lvl" ref={zoomLabelRef}>
            72%
          </span>
          <button type="button" aria-label="放大" onClick={(event) => zoomIn(event.detail === 0)}>
            <PlusIcon width={15} height={15} />
          </button>
        </span>
        <button type="button" className="cv-tool-btn" aria-label="适应画布" title="适应画布" onClick={(event) => fit(event.detail === 0)}>
          <FrameIcon width={16} height={16} />
        </button>
        <button type="button" className="cv-tool-btn" aria-label="重置画布" title="重置画布" onClick={(event) => reset(event.detail === 0)}>
          <RefreshCcwIcon width={16} height={16} />
        </button>
      </div>

      <div className="canvas-viewport" ref={viewportRef} aria-label="制品画布">
        <div className="cv-world" ref={worldRef}>
          {/* 真实模式不渲染 mock 主轴卡与任何连线层,四张矩阵卡即全部内容 */}
          {!realMode && <SpineCard onOpenOutline={openOutline} />}
          {!realMode && <CanvasLinks cards={cards} links={LINK_DEFS} />}
          {cardEls}
          {/* 停靠后中心舞台让位给「下一步」占位:非交互纯提示,为未来真实大纲预留舞台 */}
          {realMode && layoutStage === "docked" && (
            <div
              className="cv-next-hint"
              style={{ left: NEXT_HINT_RECT.x + NEXT_HINT_RECT.w / 2, top: NEXT_HINT_RECT.y + NEXT_HINT_RECT.h / 2 }}
              aria-hidden="true"
            >
              <div className="cv-next-hint-body">
                <TreeStructureIcon width={17} height={17} />
                <span>下一步:生成投标大纲</span>
              </div>
            </div>
          )}
        </div>

        <div className="cv-viewport-hint" aria-hidden="true">拖动画布 · 滚轮缩放 · 点击卡片查看详情</div>

        {/* 对话浮层。挂在视口内部（而非 .canvas-pane 下）有两个理由：视口的
            overflow:hidden 免费给出「不许骑到工具条上」的裁剪；展开态浮窗的
            height: calc(100% - …) 也才以视口为解算盒。抽屉 z-30 的遮罩天然压住它们。 */}
        <MessageWindow />
        <CanvasDock />

        {drawer && (
          <CanvasDrawer
            type={drawer.type}
            cardType={drawer.cardType}
            title={drawer.title}
            badge={badgeFor(drawer.cardType)}
            skipEntrance={drawer.skipEntrance}
            onClose={() => setDrawer(null)}
          />
        )}
      </div>
    </div>
  );
}
