import type { MatrixType } from "@/lib/hagent/matrix";
import type { MatrixSlotStatus } from "@/lib/store/workspace";
import { META, isTerminalSlotStatus, type CardInst } from "./cardMeta";

// 编排阶段纯推导模块(本特性唯一新缝):输入四个矩阵槽位状态 + 进入路径(亲历解析 / 恢复刷新),
// 输出画布编排阶段;卡位坐标挂在同一条缝下游。无 DOM 依赖,是本特性唯一的单元可测点。
// 「停靠中」是亲历会话里 中心舞台 → 已停靠 的过渡动画态,由画布容器在阶段切换沿上演绎,不在此推导。

/** 编排阶段:中心舞台(解析进行中) / 已停靠(生成完毕) / 解析中断(流中断且有槽位未终态) */
export type ChoreoStage = "center" | "docked" | "interrupted";

/** 四宫格与停靠列共用的固定卡序:概要 → 商务 → 技术 → 评分,与阅读招标文件的自然顺序一致 */
export const MATRIX_CARD_ORDER: readonly MatrixType[] = ["basic_info", "business", "technical", "scoring"];

/** 终态:ready 或 error(error 计入终态,不阻塞编排)。谓词定义在 cardMeta,与徽标/卡面共用。 */
const isTerminal = (s: MatrixSlotStatus) => isTerminalSlotStatus(s);

export interface ChoreoInput {
  statuses: Record<MatrixType, MatrixSlotStatus>;
  /** 本浏览器会话是否亲历解析(startParse 路径为 true;恢复/刷新路径为 false) */
  witnessed: boolean;
  /** 解析流是否异常终止(store phase === "error") */
  streamAborted: boolean;
  /** 本项目在本会话内是否已停靠过。停靠是单向阀:之后槽位刷新(如对话轮把 error 槽
   *  翻回 loading)不得把阶段跌回中心舞台——「停靠后系统不再干预卡位」。 */
  dockedBefore: boolean;
}

export function deriveChoreoStage(input: ChoreoInput): ChoreoStage {
  if (input.dockedBefore) return "docked";
  // 生成完毕 = 四槽位全部终态,即触发停靠;与对话相位、流是否收尾解耦,
  // 天然覆盖恢复场景(装载即终态)与部分失败场景(error 照常停靠)。
  if (MATRIX_CARD_ORDER.every((t) => isTerminal(input.statuses[t]))) return "docked";
  // 恢复/刷新路径不经过居中阶段:装载中即按停靠位呈现。
  if (!input.witnessed) return "docked";
  // 亲历会话里流异常中断且有槽位未终态 → 定格中心舞台的中断态。
  if (input.streamAborted) return "interrupted";
  return "center";
}

/* ---- 各阶段卡位(world 坐标) ---- */

// 卡宽维持 232(PRD 锁定);取自 META 单一事实来源,四张矩阵卡同宽。
const CARD_W = Math.max(...MATRIX_CARD_ORDER.map((t) => META[t].w));
const GRID = { x: 340, y: 120, gap: 48 };
const DOCK = { x: 40, y: 40, gap: 24 };

/** 中心舞台:2×2 四宫格居中,行高取本行最高卡 */
export function centerStageCards(): CardInst[] {
  const cards: CardInst[] = [];
  let y = GRID.y;
  for (let row = 0; row < 2; row++) {
    let rowH = 0;
    MATRIX_CARD_ORDER.slice(row * 2, row * 2 + 2).forEach((type, col) => {
      cards.push({ id: type, type, x: GRID.x + col * (CARD_W + GRID.gap), y });
      rowH = Math.max(rowH, META[type].h);
    });
    y += rowH + GRID.gap;
  }
  return cards;
}

/** 停靠列:画布最左侧,自上而下同序垂直排列 */
export function dockedCards(): CardInst[] {
  let y = DOCK.y;
  return MATRIX_CARD_ORDER.map((type) => {
    const card: CardInst = { id: type, type, x: DOCK.x, y };
    y += META[type].h + DOCK.gap;
    return card;
  });
}

/** 阶段 → 整套卡位。解析中断定格中心舞台,不另设布局。 */
export function cardsForStage(stage: ChoreoStage): CardInst[] {
  return stage === "docked" ? dockedCards() : centerStageCards();
}

/** 中心舞台占用的画布区域(world 包围盒)。停靠后此区域让位给「下一步」占位,
 *  计入内容包围盒,使「适应画布」呈现 停靠列贴左 + 中心留空 的阶段叙事。 */
export function centerStageRect(): { x: number; y: number; w: number; h: number } {
  let maxX = GRID.x;
  let maxY = GRID.y;
  for (const c of centerStageCards()) {
    maxX = Math.max(maxX, c.x + CARD_W);
    maxY = Math.max(maxY, c.y + META[c.type].h);
  }
  return { x: GRID.x, y: GRID.y, w: maxX - GRID.x, h: maxY - GRID.y };
}
