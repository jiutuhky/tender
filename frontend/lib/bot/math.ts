// 角色引擎 · 数值层 —— grok-icon-study replica src/math.js 的 1:1 移植。
//
// 弹簧、缓动、路径展平（flattenPath）、极坐标环（spanAt / spanPoly）、3D 旋转
// （rot3 / relRot / solidRadii / makeTurnAt）与指针映射（mapPointer），全部保持
// 原版的常量与数值行为；原版混淆符号以注释标在各导出处。

import type { SolidSlice } from "./geometry";

export interface Spring {
  /** 当前值 */
  x: number;
  /** 当前速度 */
  v: number;
  /** 目标值 */
  t: number;
}

export function spring(x: number): Spring {
  return { x, v: 0, t: x };
}

export function stepSpring(s: Spring, freq: number, damp: number, dt: number): void {
  s.v += (-2 * damp * freq * s.v - freq * freq * (s.x - s.t)) * dt;
  s.x += s.v * dt;
  if (!Number.isFinite(s.x) || !Number.isFinite(s.v)) {
    s.x = s.t;
    s.v = 0;
  }
}

/** 弹簧固定子步长 1/120s：rAF 的 dt 按它切分，掉帧时高频弹簧（blink 26Hz）才不发散 */
export const DT = 1 / 120;

export function springSteps(dt: number): number {
  return Math.max(1, Math.ceil(dt / DT));
}

export function clamp(n: number, a: number, b: number): number {
  return Math.min(b, Math.max(a, n));
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

export function rand(a: number, b: number): number {
  return a + Math.random() * (b - a);
}

export function sign(): number {
  return Math.random() < 0.5 ? -1 : 1;
}

/** easeInOutCubic（原 K2） */
export function K2(n: number): number {
  return n < 0.5 ? 4 * n * n * n : 1 - Math.pow(-2 * n + 2, 3) / 2;
}

/** easeOutCubic（原 Rc） */
export function Rc(n: number): number {
  return 1 - Math.pow(1 - n, 3);
}

/** easeOutBack（原 y1e） */
export function y1e(n: number): number {
  return 1 + 2.70158 * Math.pow(n - 1, 3) + 1.70158 * Math.pow(n - 1, 2);
}

export function Dke(n: number): number {
  return n * n * (3 - 2 * n);
}

/** 帧率无关的指数趋近（原 x_t / Rn） */
export function x_t(n: number, e: number): number {
  return 1 - Math.exp(Math.log(1 - n) * 60 * e);
}

export function Rn(n: number, bs = 1 / 60): number {
  return x_t(n, bs);
}

export type Poly = number[][];

export function polyPath(pts: Poly): string {
  return "M" + pts.map((p) => `${p[0]?.toFixed(2)} ${p[1]?.toFixed(2)}`).join("L") + "Z";
}

export function centroid(pts: Poly): [number, number] {
  let x = 0;
  let y = 0;
  for (const p of pts) {
    x += p[0] as number;
    y += p[1] as number;
  }
  return [x / pts.length, y / pts.length];
}

export function lerpPoly(a: Poly, b: Poly, t: number): Poly {
  return a.map((p, i) => {
    const q = b[i] as number[];
    return [
      (p[0] as number) + ((q[0] as number) - (p[0] as number)) * t,
      (p[1] as number) + ((q[1] as number) - (p[1] as number)) * t,
    ];
  });
}

export interface FaceVal {
  x: number;
  y: number;
  sx: number;
  sy: number;
  eye: number;
  leftDX?: number;
}

export function lerpFace(n: FaceVal, e: FaceVal, t: number): FaceVal {
  return {
    x: n.x + (e.x - n.x) * t,
    y: n.y + (e.y - n.y) * t,
    sx: n.sx + (e.sx - n.sx) * t,
    sy: n.sy + (e.sy - n.sy) * t,
    eye: n.eye + (e.eye - n.eye) * t,
    leftDX: (n.leftDX ?? 0) + ((e.leftDX ?? 0) - (n.leftDX ?? 0)) * t,
  };
}

/** 把 M/L/Q/C/Z 路径展平成折线（步长 4 单位） */
export function flattenPath(d: string, e = 4): Poly {
  const t = d.match(/[MLCQZmlcqz]|-?\d*\.?\d+(?:e[-+]?\d+)?/g) ?? [];
  const s: Poly = [];
  let r = 0;
  let i = "";
  let o = 0;
  let l = 0;
  let c = 0;
  let u = 0;
  const rd = () => parseFloat(t[r++] as string);
  const m = (f: (k: number) => number[], h: number) => {
    const y = Math.max(2, Math.ceil(h / e));
    for (let k = 1; k <= y; k++) s.push(f(k / y));
  };
  while (r < t.length) {
    if (/[a-z]/i.test(t[r] as string)) i = (t[r++] as string).toUpperCase();
    if (i === "Z") {
      if (Math.hypot(c - o, u - l) > 0.01) m((f) => [o + (c - o) * f, l + (u - l) * f], Math.hypot(c - o, u - l));
      o = c;
      l = u;
      continue;
    }
    if (r >= t.length) break;
    if (i === "M") {
      o = rd();
      l = rd();
      c = o;
      u = l;
      s.push([o, l]);
      i = "L";
    } else if (i === "L") {
      const f = rd();
      const h = rd();
      m((y) => [o + (f - o) * y, l + (h - l) * y], Math.hypot(f - o, h - l));
      o = f;
      l = h;
    } else if (i === "Q") {
      const f = rd();
      const h = rd();
      const y = rd();
      const k = rd();
      const v = o;
      const b = l;
      m((x) => {
        const N = 1 - x;
        return [N * N * v + 2 * N * x * f + x * x * y, N * N * b + 2 * N * x * h + x * x * k];
      }, Math.hypot(f - o, h - l) + Math.hypot(y - f, k - h));
      o = y;
      l = k;
    } else if (i === "C") {
      const f = rd();
      const h = rd();
      const y = rd();
      const k = rd();
      const v = rd();
      const b = rd();
      const x = o;
      const N = l;
      m((E) => {
        const A = 1 - E;
        return [
          A * A * A * x + 3 * A * A * E * f + 3 * A * E * E * y + E * E * E * v,
          A * A * A * N + 3 * A * A * E * h + 3 * A * E * E * k + E * E * E * b,
        ];
      }, Math.hypot(f - o, h - l) + Math.hypot(y - f, k - h) + Math.hypot(v - y, b - k));
      o = v;
      l = b;
    } else r++;
  }
  return s;
}

/**
 * 形状的「左右边界查找表」（原 buildSpan）：把折线按 Y 均分 160 档，
 * 每档记录 Re 左侧的最大 x 与右侧的最小 x，插值出任意 Y 的左右边界。
 */
function buildSpan(pts: Poly, Re: number, e = 160): (y: number) => [number, number] {
  let t = Infinity;
  let s = -Infinity;
  for (const m of pts) {
    if ((m[1] as number) < t) t = m[1] as number;
    if ((m[1] as number) > s) s = m[1] as number;
  }
  const r = s - t;
  const i = (m: number) => t + r * (m + 0.5) / e;
  const o = new Float64Array(e);
  const l = new Float64Array(e);
  for (let m = 0; m < e; m++) {
    const f = i(m);
    let h = -Infinity;
    let y = Infinity;
    for (let b = 0; b < pts.length; b++) {
      const x = pts[b] as number[];
      const N = pts[(b + 1) % pts.length] as number[];
      if ((x[1] as number) <= f === (N[1] as number) <= f) continue;
      const E = (x[0] as number) + ((N[0] as number) - (x[0] as number)) * (f - (x[1] as number)) / ((N[1] as number) - (x[1] as number));
      if (E <= Re) {
        if (E > h) h = E;
      } else if (E < y) y = E;
    }
    o[m] = Number.isFinite(h) ? h : Re;
    l[m] = Number.isFinite(y) ? y : Re;
  }
  return (h: number) => {
    const y = clamp((h - t) / r * e - 0.5, 0, e - 1);
    const k = Math.floor(y);
    const v = y - k;
    const b = Math.min(k + 1, e - 1);
    return [
      (o[k] as number) + ((o[b] as number) - (o[k] as number)) * v,
      (l[k] as number) + ((l[b] as number) - (l[k] as number)) * v,
    ];
  };
}

const spanCache = new Map<string, (y: number) => [number, number]>();

export function spanAt(path: string, Re: number): (y: number) => [number, number] {
  let fn = spanCache.get(path);
  if (!fn) {
    fn = buildSpan(flattenPath(path), Re);
    spanCache.set(path, fn);
  }
  return fn;
}

/** 折线在 Y 处的左右边界（原 spanPoly）——形变中的环没有缓存，每帧现算 */
export function spanPoly(n: Poly, e: number, Re: number): [number, number] {
  let t = -Infinity;
  let s = Infinity;
  for (let r = 0; r < n.length; r++) {
    const i = n[r] as number[];
    const o = n[(r + 1) % n.length] as number[];
    if ((i[1] as number) <= e === (o[1] as number) <= e) continue;
    const l = (i[0] as number) + ((o[0] as number) - (i[0] as number)) * (e - (i[1] as number)) / ((o[1] as number) - (i[1] as number));
    if (l <= Re) {
      if (l > t) t = l;
    } else if (l < s) s = l;
  }
  return [Number.isFinite(t) ? t : Re, Number.isFinite(s) ? s : Re];
}

export type Mat3 = number[];

/** turn/tilt/roll 三角欧拉 → 3×3 旋转矩阵（原 rot3） */
export function rot3(turn: number, tilt: number, roll: number): Mat3 {
  const d = Math.PI / 180;
  const Ui = Math.cos(turn * d);
  const Si = Math.sin(turn * d);
  const Ea = Math.cos(tilt * d);
  const Ca = Math.sin(tilt * d);
  const Wo = Math.cos(roll * d);
  const _c = Math.sin(roll * d);
  return [
    Wo * Ui - _c * Ca * Si, -_c * Ea, Wo * Si + _c * Ca * Ui,
    _c * Ui + Wo * Ca * Si, Wo * Ea, _c * Si - Wo * Ca * Ui,
    -Ea * Si, Ca, Ea * Ui,
  ];
}

/** 姿态相对 home 姿态的旋转差（原 relRot）——眼睛 3D 定位的输入 */
export function relRot(pose: { turn: number; tilt: number; roll: number }, home: { turn: number; tilt: number; roll: number }): Mat3 {
  const gn = rot3(pose.turn, pose.tilt, pose.roll);
  const Gn = rot3(home.turn, home.tilt, home.roll);
  return [
    gn[0]! * Gn[0]! + gn[1]! * Gn[1]! + gn[2]! * Gn[2]!,
    gn[0]! * Gn[3]! + gn[1]! * Gn[4]! + gn[2]! * Gn[5]!,
    gn[0]! * Gn[6]! + gn[1]! * Gn[7]! + gn[2]! * Gn[8]!,
    gn[3]! * Gn[0]! + gn[4]! * Gn[1]! + gn[5]! * Gn[2]!,
    gn[3]! * Gn[3]! + gn[4]! * Gn[4]! + gn[5]! * Gn[5]!,
    gn[3]! * Gn[6]! + gn[4]! * Gn[7]! + gn[5]! * Gn[8]!,
    gn[6]! * Gn[0]! + gn[7]! * Gn[1]! + gn[8]! * Gn[2]!,
    gn[6]! * Gn[3]! + gn[7]! * Gn[4]! + gn[8]! * Gn[5]!,
    gn[6]! * Gn[6]! + gn[7]! * Gn[7]! + gn[8]! * Gn[8]!,
  ];
}

/**
 * 回转体在偏航角 yaw 下的轮廓半径剖面（原 solidRadii）：对每个方位角，
 * 取所有圆片 (x,y,rad) 与视线求交的最大半径，再做 1-4-6-4-1 平滑。
 */
export function solidRadii(solid: readonly SolidSlice[], angle: number, n = 96): number[] {
  const c = Math.cos(angle);
  const s = Math.sin(angle);
  const r = solid.map(([x, y, z, rad]) => [x * c + z * s, y, rad] as [number, number, number]);
  const raw = Array.from({ length: n }, (_, idx) => {
    const u = (idx / n) * Math.PI * 2;
    const d = Math.cos(u);
    const m = Math.sin(u);
    let f = 0;
    for (const [h, y, k] of r) {
      const v = d * h + m * y;
      const b = v * v - (h * h + y * y) + k * k;
      if (b <= 0) continue;
      const x = v + Math.sqrt(b);
      if (x > f) f = x;
    }
    return f;
  });
  const o = raw.length;
  return raw.map((l, i) => (
    (raw[(i - 2 + o) % o] as number) + 4 * (raw[(i - 1 + o) % o] as number) + 6 * (raw[i] as number)
    + 4 * (raw[(i + 1) % o] as number) + (raw[(i + 2) % o] as number)
  ) / 16);
}

/** 由回转体剖面构造「偏航时的极坐标环」函数（原 makeTurnAt） */
export function makeTurnAt(
  solid: readonly SolidSlice[],
  ring: readonly (readonly [number, number])[],
  Re: number,
): (yaw: number) => [number, number][] {
  const rest = solidRadii(solid, 0);
  return (yaw) => {
    let v = solidRadii(solid, yaw).map((x, i) => clamp((x + 12) / ((rest[i] as number) + 12), 0.32, 1.5));
    const n = v.length;
    for (let p = 0; p < 3; p++) {
      const prev = v;
      v = prev.map((E, A) => (
        (prev[(A - 2 + n) % n] as number) + 4 * (prev[(A - 1 + n) % n] as number) + 6 * (prev[A] as number)
        + 4 * (prev[(A + 1) % n] as number) + (prev[(A + 2) % n] as number)
      ) / 16);
    }
    return ring.map(([x, y], i) => [Re + (x - Re) * (v[i] as number), Re + (y - Re) * (v[i] as number)]);
  };
}

/** 指针位置 → 标记周围椭圆上的点（原 mapPointer） */
export function mapPointer(
  rect: DOMRect,
  pt: { x: number; y: number },
  JFe = 0.6,
  iin = 22,
  ain = 14,
  oin = 2,
): { x: number; y: number } {
  const t = rect.left + rect.width / 2;
  const s = rect.top + rect.height / 2;
  const r = pt.x - t;
  const i = pt.y - s;
  const o = Math.min(1, Math.sqrt(Math.hypot(r, i) / (rect.width * oin)));
  const l = Math.atan2(i, r);
  return {
    x: t + JFe * (ain / iin) * o * Math.cos(l) * rect.width,
    y: s + JFe * o * Math.sin(l) * rect.height,
  };
}
