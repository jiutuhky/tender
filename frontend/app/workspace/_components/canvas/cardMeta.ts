import type { ComponentType, SVGProps } from "react";
import {
  ListDashesIcon,
  LayersIcon,
  TableIcon,
  RowsIcon,
  TreeStructureIcon,
  FileIcon,
  ChartBarIcon,
  FilesIcon,
  IdCardIcon,
  CasesIcon,
} from "@/components/ui/icons";
import type { MatrixSlot, MatrixSlotStatus } from "@/lib/store/workspace";
import type { MatrixType } from "@/lib/hagent/matrix";

// 工作台画布（大纲视图）的制品模型。
// 事实来源：.design/prototype/frost/标书工作台画布.html 的 Workbench.META / spine / initCards。
// 两种模式:idle 时为静态 mockup 原型(主轴卡 + 连线);解析启动后切换为四张真实应答矩阵卡
// (basic_info/business/technical/scoring,数据订阅自 workspace store)。
// 真实模式不渲染主轴卡与连线,卡位由编排阶段决定,见 choreography.ts。

export type CardType =
  | "req"
  | "knowledge"
  | "matrix"
  | "deviation"
  | "outline"
  | "chapter"
  | "chart"
  | "assemble"
  | MatrixType;

/** 四种真实矩阵卡的类型守卫(与 skill 输出的 matrix_type 同名) */
export function isMatrixCardType(t: CardType): t is MatrixType {
  return t === "basic_info" || t === "business" || t === "technical" || t === "scoring";
}

/** 状态色：对应卡角状态徽标与连点配色 */
export type StatusColor = "green" | "blue" | "gray" | "orange";

type IconCmp = ComponentType<SVGProps<SVGSVGElement>>;

export interface CardMeta {
  title: string;
  icon: IconCmp;
  stage: string;
  status: string;
  sc: StatusColor;
  w: number;
  h: number;
}

export const META: Record<CardType, CardMeta> = {
  req: { title: "技术需求清单", icon: ListDashesIcon, stage: "解析", status: "已生成", sc: "green", w: 218, h: 170 },
  knowledge: { title: "知识库素材", icon: LayersIcon, stage: "素材", status: "引用 6 处", sc: "blue", w: 222, h: 184 },
  matrix: { title: "应答矩阵", icon: TableIcon, stage: "应答", status: "进行中", sc: "blue", w: 250, h: 200 },
  deviation: { title: "技术偏差表", icon: RowsIcon, stage: "应答", status: "草稿", sc: "gray", w: 228, h: 158 },
  outline: { title: "投标大纲", icon: TreeStructureIcon, stage: "大纲", status: "已生成", sc: "green", w: 226, h: 206 },
  chapter: { title: "技术方案 · 总体设计", icon: FileIcon, stage: "章节", status: "草稿", sc: "gray", w: 260, h: 208 },
  chart: { title: "实施进度计划", icon: ChartBarIcon, stage: "章节", status: "已生成", sc: "green", w: 238, h: 166 },
  assemble: { title: "投标文件 · 成稿", icon: FilesIcon, stage: "成稿", status: "编制中", sc: "blue", w: 226, h: 182 },
  // —— 真实矩阵卡(数据订阅自 store,META 中的 status/sc 仅为兜底,实际状态由 matrixCardBadge 驱动) ——
  // h 为就绪态卡面实测高度(卡身实际由内容自适应,h 只喂编排布局的间距计算)。
  // 四卡同高是卡面四行语法(题名/主指标/结构条/信号行)的直接结果,停靠列里逐行对齐。
  basic_info: { title: "项目概要", icon: IdCardIcon, stage: "解析", status: "等待解析", sc: "gray", w: 232, h: 127 },
  business: { title: "商务应答矩阵", icon: CasesIcon, stage: "应答", status: "等待解析", sc: "gray", w: 232, h: 127 },
  technical: { title: "技术应答矩阵", icon: ListDashesIcon, stage: "应答", status: "等待解析", sc: "gray", w: 232, h: 127 },
  scoring: { title: "评分办法", icon: ChartBarIcon, stage: "评审", status: "等待解析", sc: "gray", w: 232, h: 127 },
};

/* ---- 主轴：投标文件大纲（背景骨架卡） ---- */

export interface SpineNode {
  t: string;
  s: StatusColor;
  /** 缩进层级（0 为章、1 为节） */
  ind: number;
}

export const SPINE = {
  x: 556,
  y: 58,
  w: 206,
  headerH: 44,
  rowH: 30,
  nodes: [
    { t: "一  投标函与附录", s: "green", ind: 0 },
    { t: "二  商务及报价响应", s: "green", ind: 0 },
    { t: "三  技术方案", s: "blue", ind: 0 },
    { t: "3.1  总体技术架构", s: "gray", ind: 1 },
    { t: "3.2  技术需求逐条响应", s: "green", ind: 1 },
    { t: "3.3  技术偏差表", s: "gray", ind: 1 },
    { t: "四  项目实施与服务", s: "gray", ind: 0 },
    { t: "五  资质证明材料", s: "green", ind: 0 },
    { t: "六  拟投入人员", s: "gray", ind: 0 },
  ] satisfies SpineNode[],
};

/** 第 i 个主轴节点的纵向锚点（world 坐标），供连线终点定位 */
export function spineNodeY(i: number): number {
  return SPINE.y + SPINE.headerH + i * SPINE.rowH + SPINE.rowH / 2;
}

/* ---- 画布上的制品卡实例 ---- */

export interface CardInst {
  id: string;
  type: CardType;
  x: number;
  y: number;
  /** 覆盖标题（新增卡用），缺省时取 META[type].title */
  title?: string;
  /** 进场动画标记（新增卡 pop 一次） */
  isNew?: boolean;
}

/** 初始铺点：解析阶段产物围绕主轴左右两翼 + 底部成稿 */
export function initialCards(): CardInst[] {
  const mk = (type: CardType, x: number, y: number): CardInst => ({ id: type, type, x, y });
  return [
    mk("req", 118, 52),
    mk("matrix", 104, 288),
    mk("deviation", 128, 556),
    mk("chapter", 912, 68),
    mk("knowledge", 912, 298),
    mk("chart", 912, 512),
    mk("assemble", 556, 520),
  ];
}

/** 连线定义：制品卡 → 主轴第 n 个节点 */
export const LINK_DEFS: Array<{ a: string; n: number }> = [
  { a: "req", n: 4 },
  { a: "matrix", n: 4 },
  { a: "deviation", n: 5 },
  { a: "chapter", n: 3 },
  { a: "knowledge", n: 7 },
  { a: "chart", n: 6 },
];

/* ---- 真实模式:四张矩阵卡 ---- */

/** 终态:ready 或 error(error 计入终态)。编排推导与徽标/卡面共用的领域谓词。 */
export const isTerminalSlotStatus = (s: MatrixSlotStatus): boolean => s === "ready" || s === "error";

/** 解析中断:流整体异常终止且本槽位未终态 → 徽标与卡面如实定格,不再假装进行中。 */
export const isSlotInterrupted = (s: MatrixSlotStatus, streamAborted: boolean): boolean =>
  streamAborted && !isTerminalSlotStatus(s);

/** 卡面基调。决定题名行报不报状态、卡壳立不立色条:
 *  progress/idle 报一行状态文字;done 什么都不报(卡面有数字本身就是「已生成」,
 *  全局进度画布工具栏已报过一次);failed/stalled 不报文字,改由卡壳左缘色条 +
 *  卡面一句直陈承担。这是「状态标签只在偏离常态时发声」的落点。 */
export type FaceTone = "progress" | "idle" | "done" | "failed" | "stalled";

export interface MatrixCardBadge {
  label: string;
  sc: StatusColor;
  inProgress: boolean;
  tone: FaceTone;
}

/** 矩阵槽位状态 → 卡面基调与状态文案(蓝只授予进行中;成功绿、失败橙、待命灰) */
export function matrixCardBadge(status: MatrixSlotStatus): MatrixCardBadge {
  switch (status) {
    case "loading":
      return { label: "正在解析", sc: "blue", inProgress: true, tone: "progress" };
    case "ready":
      return { label: "已生成", sc: "green", inProgress: false, tone: "done" };
    case "error":
      return { label: "解析失败", sc: "orange", inProgress: false, tone: "failed" };
    default:
      return { label: "等待解析", sc: "gray", inProgress: false, tone: "idle" };
  }
}

/** 运行中(尚无槽位数据)时四卡统一显示「正在解析」;流中断时未终态槽位如实翻「解析中断」 */
export function matrixCardBadgeForPhase(
  slot: MatrixSlot<unknown>,
  running: boolean,
  aborted = false,
): MatrixCardBadge {
  if (isSlotInterrupted(slot.status, aborted))
    return { label: "解析中断", sc: "gray", inProgress: false, tone: "stalled" };
  if (slot.status === "empty" && running)
    return { label: "正在解析", sc: "blue", inProgress: true, tone: "progress" };
  return matrixCardBadge(slot.status);
}

/* ---- 配色助手 ---- */

/** 状态色 → [底色, 前景色]，用于状态徽标。
 *  底色恒为中性：语义色只落文字与图标，不做彩色填充块（规范 + CONTEXT.md 提示语汇通则）。
 *  唯一例外是蓝——它表达「可交互 / 进行中」，蓝衬底属规范发放的 --blue-soft。 */
export function scPair(sc: StatusColor): [string, string] {
  switch (sc) {
    case "green":
      return ["var(--surface-2)", "var(--green-text)"];
    case "blue":
      return ["var(--blue-soft)", "var(--blue)"];
    case "orange":
      return ["var(--surface-2)", "var(--orange-text)"];
    default:
      return ["var(--surface-2)", "var(--label-2)"];
  }
}

/** 状态色 → 连点 / 圆点实色 */
export function dotColor(sc: StatusColor): string {
  return sc === "gray" ? "var(--label-3)" : `var(--${sc})`;
}
