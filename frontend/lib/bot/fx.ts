// 角色引擎 · 特效层 —— grok-icon-study replica src/fx.js 的 1:1 移植。
//
// 两半：OverlayLayer（dots/orbit/radar/progress/gather/wave/send/receive/dock/
// whirl/pencil/bang/standby 十四种覆盖绘制 + pencil 的墨迹）与 createParticles
// （迸发粒子 + 高速旋转时甩出的轨道缎带，HSL 色相漂移，前后景深度分层）。
// 结构与数值全部对齐原版；原版混淆符号以注释标注。

import { clamp, K2, flattenPath, makeTurnAt, rand, Rc, y1e } from "./math";
import type { SolidSlice } from "./geometry";
import { GROK_GEO } from "./geometry";

const NS = "http://www.w3.org/2000/svg";
const Re0 = 114.2705;
const STAR_COLOR = "#f4c34e";
const PALETTE = ["#f9705c", "#5b95f0", "#3fbe86", "#f5b13f", "#9a72ee", "#35c3bd"];
const STAR = (() => {
  const n: string[] = [];
  for (let e = 0; e < 10; e++) {
    const t = -Math.PI / 2 + (e * Math.PI) / 5;
    const s = e % 2 === 0 ? 1 : 0.42;
    n.push(`${(Math.cos(t) * s).toFixed(3)} ${(Math.sin(t) * s).toFixed(3)}`);
  }
  return "M" + n.join("L") + "Z";
})();

/** 状态 → 特效种类 */
export const MAP: Record<string, string> = {
  thinking: "dots",
  orbit: "orbit",
  radar: "radar",
  progress: "progress",
  spawning: "gather",
  dictating: "wave",
  sending: "send",
  receiving: "receive",
  uploading: "dock",
  bouncing: "ball",
  loading: "whirl",
  "powering-down": "standby",
  writing: "pencil",
  alerting: "bang",
};
/** 这两种特效「播一阵歇一阵」，一直转会被读成卡死 */
export const CYCLE: ReadonlySet<string> = new Set(["progress", "spawning"]);
export const CYCLE_ON: Record<string, number> = { progress: 2500, spawning: 2000 };
export const CYCLE_OFF = 1500;
export const SCALE: Record<string, number> = {
  dots: 1.5, orbit: 1.14, radar: 1.14, progress: 1.32, gather: 1.15,
  wave: 1.42, send: 1.12, receive: 1.12, dock: 1.3, ball: 1.22,
  whirl: 1.45, pencil: 1.18, bang: 1.28, standby: 1.75,
};
const RADIUS: Record<string, number> = {
  dots: 22, orbit: 19, radar: 19, progress: 19, gather: 19, wave: 16,
  send: 20, receive: 20, dock: 20, ball: 18, whirl: 15, pencil: 17,
  bang: 13, standby: 13,
};
/** overlay 与本体的混色起点：overlay.x 超过它，本体路径开始向圆过渡 */
export const P_BLEND = 0.62;
const DOT_R = 22;
const DOT_GAP = 62;
const POP0 = 0.84;
const POP1 = 0.22;
const SEND_MS = 1500;
const RECV_MS = 1700;
const PENCIL_MS = 2500;

function el<K extends keyof SVGElementTagNameMap>(tag: K, attrs?: Record<string, string>): SVGElementTagNameMap[K] {
  const n = document.createElementNS(NS, tag);
  if (attrs) for (const k in attrs) n.setAttribute(k, attrs[k] as string);
  return n;
}

/** 闭合 Catmull-Rom 样条（前一轮环切线作控制点） */
export function closedSpline(pts: readonly [number, number][]): string {
  const e = pts.length;
  let t = `M${pts[0]![0].toFixed(2)} ${pts[0]![1].toFixed(2)}`;
  for (let s = 0; s < e; s++) {
    const r = pts[(s - 1 + e) % e] as [number, number];
    const i = pts[s] as [number, number];
    const o = pts[(s + 1) % e] as [number, number];
    const l = pts[(s + 2) % e] as [number, number];
    t += `C${(i[0] + (o[0] - r[0]) / 6).toFixed(2)} ${(i[1] + (o[1] - r[1]) / 6).toFixed(2)} ${(o[0] - (l[0] - i[0]) / 6).toFixed(2)} ${(o[1] - (l[1] - i[1]) / 6).toFixed(2)} ${o[0].toFixed(2)} ${o[1].toFixed(2)}`;
  }
  return t + "Z";
}

export function circleRing(R: number, n = 96): [number, number][] {
  return Array.from({ length: n }, (_, e) => {
    const t = (e / n) * Math.PI * 2;
    return [R + Math.cos(t) * R, R + Math.sin(t) * R];
  });
}

/** 折线 → 以 (R,R) 为心的极坐标环（48×2 网格均匀方位角） */
export function polarRing(pts: readonly [number, number][], R: number, n = 96): [number, number][] {
  return Array.from({ length: n }, (_, t) => {
    const s = (t / n) * Math.PI * 2;
    const r = Math.cos(s);
    const i = Math.sin(s);
    let o = 0;
    for (let l = 0; l < pts.length; l++) {
      const c = pts[l] as [number, number];
      const u = pts[(l + 1) % pts.length] as [number, number];
      const d = c[0] - R;
      const m = c[1] - R;
      const f = u[0] - R;
      const h = u[1] - R;
      const y = (f - d) * i - (h - m) * r;
      if (Math.abs(y) < 1e-9) continue;
      const k = (d * i - m * r) / -y;
      if (k < 0 || k > 1) continue;
      const v = (d + (f - d) * k) * r + (m + (h - m) * k) * i;
      if (v > o) o = v;
    }
    return [R + r * o, R + i * o];
  });
}

export function rotateRing(n: readonly [number, number][], e: number, R: number): [number, number][] {
  const t = n.length;
  const s = (e / t) * Math.PI * 2;
  const r = Math.cos(s);
  const i = Math.sin(s);
  return Array.from({ length: t }, (_, l) => {
    const [c, u] = n[(((l - e) % t) + t) % t] as [number, number];
    const d = c - R;
    const m = u - R;
    return [R + d * r - m * i, R + d * i + m * r];
  });
}

export function lerpRing(a: readonly [number, number][], b: readonly [number, number][], t: number): [number, number][] {
  return a.map((p, i) => [p[0] + ((b[i] as [number, number])[0] - p[0]) * t, p[1] + ((b[i] as [number, number])[1] - p[1]) * t]);
}

function spanHalf(ring: readonly [number, number][], y: number, R: number): [number, number] {
  let left = -Infinity;
  let right = Infinity;
  for (let i = 0; i < ring.length; i++) {
    const a = ring[i] as [number, number];
    const b = ring[(i + 1) % ring.length] as [number, number];
    if (a[1] <= y === b[1] <= y) continue;
    const x = a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]);
    if (x <= R) {
      if (x > left) left = x;
    } else if (x < right) right = x;
  }
  return [Number.isFinite(left) ? left : R, Number.isFinite(right) ? right : R];
}

/** 竖直胶囊（pencil 的笔杆） */
export function capsule(n: number, e: number, R: number): string {
  const t = n / 2;
  const s = R - e / 2 + t;
  const r = R + e / 2 - t;
  return `M${R - t} ${s}A${t} ${t} 0 0 1 ${R + t} ${s}L${R + t} ${r}A${t} ${t} 0 0 1 ${R - t} ${r}Z`;
}

/** 上圆下尖的锥形（bang 的感叹号） */
export function taper(n: number, e: number, t: number, R: number): string {
  const s = n / 2;
  const r = e / 2;
  const i = R - t / 2;
  const o = R + t / 2;
  return `M${R - s} ${i + s}A${s} ${s} 0 0 1 ${R + s} ${i + s}L${R + r} ${o - r}A${r} ${r} 0 0 1 ${R - r} ${o - r}Z`;
}

const ringCache = new Map<string, [number, number][]>();

export function shapeRing(path: string, R: number): [number, number][] {
  let r = ringCache.get(path);
  if (!r) {
    r = polarRing(flattenPath(path) as [number, number][], R);
    ringCache.set(path, r);
  }
  return r;
}

/** pencil 的笔画循环：向右写 → 抬笔飘回，正弦抖动是「手写」的来源 */
function pencilPose(now: number, stateAt: number): { x: number; y: number; wig: number; rot: number; lift: boolean } {
  const Pt = now - stateAt;
  const mt = (((Pt / PENCIL_MS) % 1) + 1) % 1;
  if (mt < 0.68) {
    const Mt = mt / 0.68;
    const Lt = Mt * Mt * (3 - 2 * Mt);
    const yn = clamp(Mt / 0.08, 0, 1) * clamp((1 - Mt) / 0.08, 0, 1);
    return { x: -54 + 118 * Lt, y: 26, wig: Math.sin(Mt * 24) * 3.2 * yn, rot: 17 + Math.sin(Pt * 6e-4) * 1, lift: false };
  }
  const Dt = K2((mt - 0.68) / 0.32);
  return { x: 64 - 118 * Dt, y: 26 - 20 * Math.sin(Dt * Math.PI), wig: 0, rot: 17 - 2 * Math.sin(Dt * Math.PI) + Math.sin(Pt * 6e-4) * 1, lift: true };
}

function smoothLine(pts: readonly [number, number][]): string {
  const Pt = pts.length;
  let mt = `M${pts[0]![0].toFixed(1)} ${pts[0]![1].toFixed(1)}`;
  if (Pt === 2) return mt + `L${pts[1]![0].toFixed(1)} ${pts[1]![1].toFixed(1)}`;
  for (let Dt = 0; Dt < Pt - 1; Dt++) {
    const Mt = pts[Math.max(Dt - 1, 0)] as [number, number];
    const Lt = pts[Dt] as [number, number];
    const yn = pts[Dt + 1] as [number, number];
    const an = pts[Math.min(Dt + 2, Pt - 1)] as [number, number];
    mt += `C${(Lt[0] + (yn[0] - Mt[0]) / 6).toFixed(1)} ${(Lt[1] + (yn[1] - Mt[1]) / 6).toFixed(1)} ${(yn[0] - (an[0] - Lt[0]) / 6).toFixed(1)} ${(yn[1] - (an[1] - Lt[1]) / 6).toFixed(1)} ${yn[0].toFixed(1)} ${yn[1].toFixed(1)}`;
  }
  return mt;
}

/** 音量条的包络：三个不可整除频率叠加，听感是「人声」不是节拍器 */
function wave(ze: number): number {
  return 0.42 + 0.29 * Math.sin(ze * 0.0021) * Math.sin(ze * 0.0034) + 0.29 * Math.sin(ze * 0.0013 + 1.7);
}

// —— 缎带粒子 ——

interface BurstP {
  x: number; y: number; vx: number; vy: number;
  life: number; max: number; r: number;
  rot: number; vr: number; color: string;
  round: boolean; star: boolean;
  orbit: null;
  el: SVGElement | null;
}

interface BeltPlane { tilt: number; roll: number }

interface OrbitP {
  lam: number; lamVel: number; tilt: number; roll: number;
  rad: number; radVel: number; follow: number; carry: number; arc: number;
}

interface BeltP {
  x: number; y: number; vx: number; vy: number;
  ret: number; life: number; max: number;
  r: number; rot: number; vr: number; color: string;
  hue: number; hueSpan: number; hueVel: number;
  orbit: OrbitP;
  hist: { x: number; y: number; l: number; z: number }[];
  el: null;
  trailEl: SVGPathElement | null;
  trailFrontEl: SVGPathElement | null;
  gradEl: SVGLinearGradientElement | null;
  stops: SVGStopElement[] | null;
}

type Particle = BurstP | BeltP;

export interface ParticlesHandle {
  burst(count?: number, power?: number, grace?: number): void;
  clear(): void;
  update(now: number, dt: number, g: { spinAngle: number; sizeScale: number; wideStyle: boolean; sustainBelts: boolean }): void;
  hasLife(): boolean;
}

export function createParticles({ back, front, idPrefix, getRadius }: {
  back: SVGGElement | null;
  front: SVGGElement | null;
  idPrefix: string;
  getRadius: () => number;
}): ParticlesHandle {
  const reduce = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  const scale = () => getRadius() / Re0;
  let spin = 0;
  let sizeScale = 1;
  let wide = false;
  let sustain = false;
  let last = -1;
  let parts: Particle[] = [];

  const burst = (W = 20, H = 1, G = 0): void => {
    if (reduce || !back || parts.length > 120) return;
    const R = GROK_GEO.Re;
    for (let Y = 0; Y < W; Y++) {
      const U = (Y / W) * Math.PI * 2 + rand(-0.35, 0.35);
      const ee = rand(96, 116) * scale();
      const te = rand(170, 360) * H;
      const ne = -Math.sin(U);
      const j = Math.cos(U);
      const Z = G * te * 0.2;
      const X = Math.random() < 0.18;
      parts.push({
        x: R + Math.cos(U) * ee, y: R + Math.sin(U) * ee,
        vx: Math.cos(U) * te + ne * Z, vy: Math.sin(U) * te + j * Z - rand(20, 75),
        life: 0, max: rand(0.45, 0.85), r: X ? rand(4, 7) : rand(3.5, 8),
        rot: rand(0, 360), vr: rand(-260, 260), color: X ? STAR_COLOR : PALETTE[(Math.random() * PALETTE.length) | 0] as string,
        round: !X && Math.random() < 0.3, star: X, orbit: null, el: null,
      });
    }
  };

  let planes: BeltPlane[] = [];
  let hue0 = 0;
  let beltN = 4;
  let spawnQ: { at: number; i: number }[] = [];
  let prevSpin = 0;
  let spinVel = 0;
  let seeding = false;
  let cooling = false;
  let trailId = 0;
  const THRESH = 0.9;
  const HARD = 5;

  const makePlanes = (W = 1): void => {
    const H = rand(-0.85, 0.85);
    planes = [];
    for (let G = 0; G < W; G++) planes.push({ tilt: rand(0.16, 0.5), roll: H + (G * Math.PI) / W + rand(-0.12, 0.12) });
    beltN = W > 1 ? W * 3 : Math.round(rand(3, 5));
    hue0 = rand(0, 360);
  };

  const spawnBelt = (lam: number, dir: number, i: number): void => {
    if (parts.length > 110) return;
    if (!planes.length) makePlanes();
    const Y = planes[i % planes.length] as BeltPlane;
    const R = GROK_GEO.Re;
    parts.push({
      x: R, y: R, vx: 0, vy: 0, ret: 0, life: 0, max: 9,
      r: (beltN <= 3 ? rand(8, 10.5) : beltN === 4 ? rand(6.6, 8.6) : rand(5.6, 7.4)),
      rot: rand(0, 360), vr: rand(-240, 240), color: PALETTE[(Math.random() * PALETTE.length) | 0] as string,
      hue: hue0 + (i * 360) / Math.max(beltN, 1) + rand(-14, 14),
      hueSpan: rand(45, 95) * (Math.random() < 0.5 ? 1 : -1),
      hueVel: rand(18, 42) * (Math.random() < 0.5 ? 1 : -1),
      orbit: {
        lam, lamVel: dir * rand(0.5, 1.1), tilt: Y.tilt + rand(-0.04, 0.04), roll: Y.roll + rand(-0.05, 0.05),
        rad: scale() * 116 + ((i / planes.length) | 0) * (38 / Math.max(Math.ceil(beltN / planes.length) - 1, 1)) + rand(-1.5, 1.5),
        radVel: rand(0, 2.5), follow: rand(0.74, 0.94), carry: 0, arc: rand(2.2, 3.4),
      },
      hist: [], el: null, trailEl: null, trailFrontEl: null, gradEl: null, stops: null,
    });
  };

  const project = (W: OrbitP, H: number): { x: number; y: number } => {
    const G = W.rad * Math.sin(H);
    const Y = -W.rad * Math.cos(H) * Math.sin(W.tilt);
    const U = Math.cos(W.roll);
    const ee = Math.sin(W.roll);
    const R = GROK_GEO.Re;
    return { x: R + G * U - Y * ee, y: R + G * ee + Y * U };
  };
  const depth = (W: OrbitP, H: number): number => Math.cos(H) * Math.cos(W.tilt);
  const q = (W: number): number => Math.round(W * 10) / 10;

  /** 把历史点织成「前/后」两半缎带：变宽度、圆弧封端，按 z 分侧 */
  const ribbon = (W: { x: number; y: number; z: number }[], H: number): { front: string; back: string } => {
    const G = W.length;
    let Y = 0;
    for (let le = 1; le < G; le++) Y += Math.hypot((W[le] as { x: number }).x - (W[le - 1] as { x: number }).x, (W[le] as { y: number }).y - (W[le - 1] as { y: number }).y);
    const U = Math.min(H, Y * 0.34);
    const ee: number[] = [];
    const te: number[] = [];
    for (let le = 0; le < G; le++) {
      const Q = W[le > 0 ? le - 1 : 0] as { x: number; y: number };
      const ae = W[le < G - 1 ? le + 1 : G - 1] as { x: number; y: number };
      let ce = ae.x - Q.x;
      let xe = ae.y - Q.y;
      const Se = Math.hypot(ce, xe) || 1;
      ce /= Se;
      xe /= Se;
      const fe = (U * (0.5 + 0.5 * (le / (G - 1)))) / 2;
      ee.push(-xe * fe);
      te.push(ce * fe);
    }
    const arc = (le: number): string => `A${q(Math.max(Math.hypot(ee[le] as number, te[le] as number), 0.2))} ${q(Math.max(Math.hypot(ee[le] as number, te[le] as number), 0.2))} 0 0 0 `;
    const band = (le: number, Q: number): string => {
      let ae = "";
      for (let ce = le; ce <= Q; ce++) ae += `${ce === le ? "M" : "L"}${q((W[ce] as { x: number }).x + (ee[ce] as number))} ${q((W[ce] as { y: number }).y + (te[ce] as number))}`;
      ae += Q === G - 1 ? arc(Q) : "L";
      for (let ce = Q; ce >= le; ce--) ae += `${ce === Q ? "" : "L"}${q((W[ce] as { x: number }).x - (ee[ce] as number))} ${q((W[ce] as { y: number }).y - (te[ce] as number))}`;
      if (le === 0) ae += `${arc(0)}${q((W[0] as { x: number }).x + (ee[0] as number))} ${q((W[0] as { y: number }).y + (te[0] as number))}`;
      return ae + "Z";
    };
    if (Y < 2) return { front: "", back: "" };
    let Z = "";
    let X = "";
    let se = 0;
    while (se < G) {
      const le = (W[se] as { z: number }).z >= 0;
      let Q = se;
      while (Q + 1 < G && (W[Q + 1] as { z: number }).z >= 0 === le) Q++;
      const ae = Math.max(se - 1, 0);
      const ce = Math.min(Q + 1, G - 1);
      if (ce > ae) {
        const xe = band(ae, ce);
        if (le) Z += xe;
        else X += xe;
      }
      se = Q + 1;
    }
    return { front: Z, back: X };
  };

  const tickVel = (dt: number): void => {
    let H = spin - prevSpin;
    if (!isFinite(H) || Math.abs(H) > 1.2) H = 0;
    prevSpin = spin;
    const was = Math.abs(spinVel) >= THRESH;
    spinVel = dt > 0 ? H / dt : 0;
    const nowFast = Math.abs(spinVel) >= THRESH;
    if (!was && nowFast) {
      makePlanes(wide ? 3 : 1);
      seeding = false;
      cooling = false;
    }
    if (was && !nowFast) {
      spawnQ.length = 0;
      cooling = false;
    }
  };

  const seedBelts = (now: number): void => {
    if (reduce || !back) return;
    const H = Math.abs(spinVel);
    const live = parts.some((U) => U.orbit != null && (U as BeltP).ret < 1);
    if (sustain && seeding && spawnQ.length === 0 && H >= THRESH && !live) {
      seeding = false;
      cooling = true;
    }
    if (!seeding && (H >= HARD || (sustain && cooling && H >= THRESH))) {
      seeding = true;
      cooling = false;
      spawnQ = [];
      for (let U = 0; U < beltN; U++) spawnQ.push({ at: now + U * rand(55, 105), i: U });
    }
    while (spawnQ.length && now >= (spawnQ[0] as { at: number }).at) {
      const U = spawnQ.shift() as { at: number; i: number };
      spawnBelt(spin - rand(0, 0.18), Math.sign(spinVel) || 1, U.i);
    }
  };

  const step = (dt: number, realDt: number): void => {
    if (!back || !parts.length) return;
    const spinning = Math.abs(spinVel) >= THRESH;
    const keep: Particle[] = [];
    for (const j of parts) {
      j.life += j.life > 0 ? realDt : dt;
      const Z = clamp(j.life / j.max, 0, 1);
      if (j.orbit) {
        const bp = j as BeltP;
        const ce = !spinning || Z > 0.55;
        bp.ret = clamp(bp.ret + (ce ? realDt / 0.5 : -realDt / 0.35), 0, 1);
        if (bp.ret >= 1) {
          bp.trailEl?.remove();
          bp.trailFrontEl?.remove();
          bp.gradEl?.remove();
          continue;
        }
      } else if (j.life >= j.max) {
        j.el?.remove();
        continue;
      }
      const X = j.orbit ? Math.min(1, j.life / 0.26) : Z < 0.1 ? Z / 0.1 : Math.pow(1 - (Z - 0.1) / 0.9, 1.7);
      if (j.orbit) {
        const ce = (j as BeltP).orbit;
        if (spinning) {
          ce.carry = spinVel * ce.follow;
          ce.lam += spinVel * dt * ce.follow + ce.lamVel * dt;
          ce.rad += ce.radVel * dt;
        } else {
          ce.lam += (ce.carry + ce.lamVel) * dt;
          ce.carry *= Math.exp(-2.6 * dt);
          ce.lamVel *= Math.exp(-2.6 * dt);
          ce.rad += ce.radVel * dt;
        }
        const xe = project(ce, ce.lam);
        j.x = xe.x;
        j.y = xe.y;
        const Se = depth(ce, ce.lam);
        const fe = 0.72 + 0.28 * clamp(Se, 0, 1);
        const ke = Math.min(j.life / 0.34, 1);
        const be = ke * ke * (3 - 2 * ke);
        const Ne = Math.max(j.r * fe * 1.7 * sizeScale * be * (1 - 0.72 * (j as BeltP).ret * (j as BeltP).ret), 0.5);
        if (!(j as BeltP).trailEl) {
          const bp = j as BeltP;
          const de = el("path", { "data-trail": "", stroke: "none" });
          const Te = el("linearGradient", { id: `${idPrefix}t${trailId++}`, gradientUnits: "userSpaceOnUse" });
          bp.stops = [];
          for (let Ie = 0; Ie < 5; Ie++) {
            const qe = el("stop", { offset: (Ie / 4).toFixed(3) });
            Te.appendChild(qe);
            (bp.stops as SVGStopElement[]).push(qe);
          }
          back.appendChild(Te);
          bp.gradEl = Te;
          de.setAttribute("fill", `url(#${Te.id})`);
          back.appendChild(de);
          bp.trailEl = de;
          const Ce = el("path", { "data-trail": "", stroke: "none", fill: de.getAttribute("fill") ?? "none" });
          front?.appendChild(Ce);
          bp.trailFrontEl = Ce;
        }
        const Ae = (j as BeltP).hist;
        const oe = Ae.length ? (Ae[Ae.length - 1] as { l: number }).l : ce.lam;
        const ve = ce.lam - oe;
        const ge = Math.min(Math.ceil(Math.abs(ve) / 0.09), 24);
        for (let de = 1; de <= ge; de++) {
          const Te = oe + (ve * de) / ge;
          const Je = project(ce, Te);
          Ae.push({ x: Je.x, y: Je.y, l: Te, z: depth(ce, Te) });
        }
        if (!Ae.length) Ae.push({ x: j.x, y: j.y, l: ce.lam, z: Se });
        const ye = ce.arc * (1 - (j as BeltP).ret * (j as BeltP).ret * (3 - 2 * (j as BeltP).ret));
        while (Ae.length > 2 && Math.abs(ce.lam - (Ae[0] as { l: number }).l) > ye) Ae.shift();
        const ue = Math.abs(ce.lam - (Ae[0] as { l: number }).l) - ye;
        if (Ae.length >= 2 && ue > 0) {
          const de = (Ae[0] as { l: number }).l + Math.sign(ce.lam - (Ae[0] as { l: number }).l) * ue;
          const Te = project(ce, de);
          Ae[0] = { x: Te.x, y: Te.y, l: de, z: depth(ce, de) };
        }
        if (Ae.length > 48) Ae.splice(0, Ae.length - 48);
        if (Ae.length >= 2) {
          const { front: de, back: Te } = ribbon(Ae, Ne);
          const Je = X.toFixed(3);
          (j as BeltP).trailEl?.setAttribute("d", Te);
          (j as BeltP).trailEl?.setAttribute("opacity", Je);
          (j as BeltP).trailFrontEl?.setAttribute("d", de);
          (j as BeltP).trailFrontEl?.setAttribute("opacity", Je);
          if ((j as BeltP).stops) {
            const qe = (j as BeltP).hue + (j as BeltP).hueVel * j.life;
            for (let we = 0; we < (j as BeltP).stops!.length; we++) {
              const Pe = we / ((j as BeltP).stops!.length - 1);
              const je = qe + Pe * (j as BeltP).hueSpan;
              (j as BeltP).stops![we]!.setAttribute("stop-color", `hsl(${(((je % 360) + 360) % 360).toFixed(0)} 56% ${(56 + 11 * Pe).toFixed(0)}%)`);
            }
          }
          const Ce = Ae[0] as { x: number; y: number };
          const Ie = Ae[Ae.length - 1] as { x: number; y: number };
          (j as BeltP).gradEl?.setAttribute("x1", Ce.x.toFixed(1));
          (j as BeltP).gradEl?.setAttribute("y1", Ce.y.toFixed(1));
          (j as BeltP).gradEl?.setAttribute("x2", Ie.x.toFixed(1));
          (j as BeltP).gradEl?.setAttribute("y2", Ie.y.toFixed(1));
        } else {
          (j as BeltP).trailEl?.setAttribute("opacity", "0");
          (j as BeltP).trailFrontEl?.setAttribute("opacity", "0");
        }
        keep.push(j);
        continue;
      }
      j.x += j.vx * dt;
      j.y += j.vy * dt;
      const se = Math.pow(0.94, dt * 60);
      j.vx *= se;
      j.vy = j.vy * se + 40 * dt;
      const le = j.life / j.max;
      const Q = le < 0.1 ? le / 0.1 : Math.pow(1 - (le - 0.1) / 0.9, 1.7);
      const ae = Math.max(j.r * (1 - le * 0.4), 0.5);
      if (!j.el) {
        const ce = el(j.star ? "path" : j.round ? "circle" : "rect");
        if (j.star) ce.setAttribute("d", STAR);
        ce.setAttribute("fill", j.color);
        back.appendChild(ce);
        j.el = ce;
      }
      j.el.setAttribute("opacity", Q.toFixed(3));
      if (j.star) {
        j.rot += j.vr * dt;
        j.el.setAttribute("transform", `translate(${j.x.toFixed(1)} ${j.y.toFixed(1)}) rotate(${j.rot.toFixed(1)}) scale(${ae.toFixed(2)})`);
      } else if (j.round) {
        j.el.setAttribute("cx", j.x.toFixed(1));
        j.el.setAttribute("cy", j.y.toFixed(1));
        j.el.setAttribute("r", ae.toFixed(2));
      } else {
        const ce = Math.hypot(j.vx, j.vy);
        const xe = Math.max(ae * 2, Math.min(ce * 0.05, 30));
        const Se = ae * 1.5;
        const fe = (Math.atan2(j.vy, j.vx) * 180) / Math.PI;
        j.el.setAttribute("width", xe.toFixed(1));
        j.el.setAttribute("height", Se.toFixed(1));
        j.el.setAttribute("rx", (Se / 2).toFixed(2));
        j.el.setAttribute("x", (j.x - xe / 2).toFixed(1));
        j.el.setAttribute("y", (j.y - Se / 2).toFixed(1));
        j.el.setAttribute("transform", `rotate(${fe.toFixed(1)} ${j.x.toFixed(1)} ${j.y.toFixed(1)})`);
      }
      keep.push(j);
    }
    parts = keep;
  };

  return {
    burst,
    clear() {
      for (const W of parts) {
        W.el?.remove();
        (W as BeltP).trailEl?.remove();
        (W as BeltP).trailFrontEl?.remove();
        (W as BeltP).gradEl?.remove();
      }
      parts = [];
      spawnQ = [];
      seeding = false;
      cooling = false;
    },
    update(now: number, dt: number, G: { spinAngle: number; sizeScale: number; wideStyle: boolean; sustainBelts: boolean }) {
      const Y = last < 0 ? dt : Math.max((now - last) / 1000, 0);
      last = now;
      sizeScale = G.sizeScale;
      spin = G.spinAngle;
      wide = G.wideStyle;
      sustain = G.sustainBelts === true;
      tickVel(dt);
      seedBelts(now);
      step(dt, Y);
    },
    hasLife: () => parts.length > 0 || spawnQ.length > 0,
  };
}

// —— 覆盖绘制层 ——

export class OverlayLayer {
  uid = `fx-${Math.random().toString(36).slice(2, 8)}`;
  back: SVGGElement;
  front: SVGGElement;
  dots: SVGPathElement[];
  rings: SVGCircleElement[];
  parts: SVGCircleElement[];
  glyphs: SVGPathElement[];
  ink: [number, number][] = [];
  recvDir = -0.7;
  recvTick = -1;
  overlayAt = 0;
  circlePath = "";
  pencilPath = "";
  bangPath = "";
  _reduce = false;

  constructor() {
    this.back = el("g", { "aria-hidden": "true" });
    this.front = el("g", { "aria-hidden": "true" });
    this.dots = [0, 1].map(() => el("path", { style: "fill:var(--fg);display:none" }));
    this.rings = [0, 1, 2, 3, 4, 5, 6].map(() =>
      el("circle", { cx: "0", cy: "0", r: "0", fill: "none", style: "display:none;stroke:var(--fg)" }));
    this.parts = [0, 1, 2, 3, 4, 5, 6].map(() =>
      el("circle", { cx: "0", cy: "0", r: "0", style: "fill:var(--fg);display:none" }));
    this.glyphs = [0, 1, 2].map(() => el("path", { style: "display:none" }));
  }

  attach(svg: SVGElement, bodyGroup: SVGElement): void {
    svg.appendChild(this.back);
    this.dots.forEach((n) => svg.appendChild(n));
    this.rings.forEach((n) => svg.appendChild(n));
    this.parts.forEach((n) => svg.appendChild(n));
    this.glyphs.forEach((n) => svg.appendChild(n));
    svg.appendChild(bodyGroup);
    svg.appendChild(this.front);
  }

  hideAll(): void {
    for (const n of this.dots) n.style.display = "none";
    for (const n of this.rings) n.style.display = "none";
    for (const n of this.parts) n.style.display = "none";
    for (const n of this.glyphs) n.style.display = "none";
  }

  amount(name: string, cur: string | null, prev: string | null, yl: number, mix: number): number {
    if (name === cur) return yl * mix;
    if (name === prev) return yl * (1 - mix);
    return 0;
  }

  /** 思考点的起落脉冲：slot 决定相位差，高斯包是「一个一个冒」的来源 */
  dotsPulse(now: number, slot: number, yl: number, reduce = false): { lift: number; pop: number; tone: number } {
    const Dt = ((((now - this.overlayAt) / 1400 + 0.119) % 1) + 1) % 1;
    let Mt = Math.abs(Dt - slot / 3);
    Mt = Math.min(Mt, 1 - Mt);
    const Lt = reduce ? 1 : Math.exp(-(Mt * Mt) / (2 * 0.15 * 0.15));
    const yn = reduce ? 0 : 1;
    return { lift: Lt * 9 * yl * yn, pop: 1 + yn * (POP0 + POP1 * Lt - 1), tone: 1 - yn * 0.5 * (1 - Lt) };
  }

  paint(now: number, stateAt: number, cur: string | null, prev: string | null, yl: number, mix: number, R: number, reduce = false): void {
    this.hideAll();
    this._reduce = reduce;
    const extra = this.extras(now, stateAt, cur, prev, yl, mix);
    const kl = (name: string) => this.amount(name, cur, prev, yl, mix);
    const run = (name: string, fn: (a: number) => void) => {
      const a = kl(name);
      if (a > 0.004) fn(a);
    };
    run("dots", (a) => this.paintDots(a, now, R));
    run("orbit", (a) => this.paintOrbit(a, now, R));
    run("radar", (a) => this.paintRadar(a, now, R, extra.A2));
    run("progress", (a) => this.paintProgress(a, now, R));
    run("gather", (a) => this.paintGather(a, now, R));
    run("wave", (a) => this.paintWave(a, now, R));
    run("send", (a) => this.paintSend(a, now, stateAt, R));
    run("receive", (a) => this.paintRecv(a, now, stateAt, R));
    run("dock", (a) => this.paintDock(a, now, stateAt, R));
    run("pencil", (a) => this.paintPencil(a, now, stateAt, R));
    run("bang", (a) => this.paintBang(a, now, stateAt, R));
    run("standby", (a) => this.paintStandby(a, now, R));
  }

  paintDots(ze: number, now: number, R: number): void {
    const mt = [R - DOT_GAP, R + DOT_GAP];
    for (let Dt = 0; Dt < 2; Dt++) {
      const Mt = this.dots[Dt] as SVGPathElement;
      const Lt = clamp((ze - Dt * 0.12) / (1 - Dt * 0.12), 0, 1);
      if (Lt <= 0.004) {
        Mt.style.display = "none";
        continue;
      }
      const yn = Rc(Lt);
      const an = y1e(Lt);
      const Et = this.dotsPulse(now, Dt === 0 ? 0 : 2, ze, this._reduce);
      const En = (DOT_R * yn * Et.pop) / R * 1.02;
      Mt.style.display = "";
      Mt.setAttribute("d", this.circlePath);
      Mt.setAttribute("transform", `translate(${(R + ((mt[Dt] as number) - R) * an).toFixed(1)} ${(R - Et.lift).toFixed(1)}) scale(${En.toFixed(4)}) translate(${-R} ${-R})`);
      Mt.setAttribute("opacity", (yn * Et.tone).toFixed(3));
    }
  }

  paintOrbit(ze: number, now: number, R: number): void {
    const mt = Rc(ze);
    const Mt = 52 * y1e(ze);
    const Lt = 12;
    const yn = now * 0.0017;
    for (let an = 0; an < 5; an++) {
      const Et = this.parts[an] as SVGCircleElement;
      const En = yn + (an * Math.PI * 2) / 5;
      const Zt = Math.cos(En);
      const dn = 0.5 + 0.5 * clamp(Zt, 0, 1);
      Et.style.display = "";
      Et.setAttribute("cx", (R + Mt * Math.sin(En)).toFixed(1));
      Et.setAttribute("cy", (R - Mt * 0.42 * Math.cos(En)).toFixed(1));
      Et.setAttribute("r", Math.max(Lt * dn * mt, 0.3).toFixed(2));
      Et.setAttribute("opacity", (clamp((Zt + 0.4) / 0.6, 0.18, 1) * mt).toFixed(3));
    }
  }

  paintRadar(ze: number, now: number, R: number, bodyR: number): void {
    const Dt = Rc(ze);
    for (let yn = 0; yn < 3; yn++) {
      const an = this.rings[yn] as SVGCircleElement;
      const Et = (now / 1300 + yn / 3) % 1;
      an.style.display = "";
      an.removeAttribute("stroke-dasharray");
      an.removeAttribute("transform");
      an.setAttribute("cx", `${R}`);
      an.setAttribute("cy", `${R}`);
      an.setAttribute("r", (bodyR + (104 - bodyR) * Et).toFixed(1));
      an.setAttribute("stroke-width", (3.4 * (1 - Et * 0.55)).toFixed(2));
      an.setAttribute("opacity", (Dt * (1 - Et) * 0.9).toFixed(3));
    }
  }

  paintProgress(ze: number, now: number, R: number): void {
    const mt = Rc(ze);
    const Dt = y1e(ze);
    const Mt = 62;
    const Lt = clamp((now - this.overlayAt) / (CYCLE_ON.progress ?? 2500), 0, 1);
    const yn = clamp(Lt / 0.85, 0, 1);
    const an = this.rings[3] as SVGCircleElement;
    an.style.display = "";
    an.setAttribute("cx", `${R}`);
    an.setAttribute("cy", `${R}`);
    an.setAttribute("r", (Mt * Dt).toFixed(1));
    an.setAttribute("stroke-width", "5");
    an.removeAttribute("stroke-dasharray");
    an.removeAttribute("transform");
    an.setAttribute("opacity", (mt * 0.16).toFixed(3));
    const Et = this.rings[4] as SVGCircleElement;
    const En = Mt * Dt;
    const Zt = 2 * Math.PI * En;
    Et.style.display = "";
    Et.setAttribute("cx", `${R}`);
    Et.setAttribute("cy", `${R}`);
    Et.setAttribute("r", En.toFixed(1));
    Et.setAttribute("stroke-width", "5");
    Et.setAttribute("stroke-dasharray", `${Zt.toFixed(1)}`);
    Et.setAttribute("stroke-dashoffset", (Zt * (1 - yn)).toFixed(1));
    Et.setAttribute("transform", `rotate(-90 ${R} ${R})`);
    Et.setAttribute("opacity", mt.toFixed(3));
  }

  paintGather(ze: number, now: number, R: number): void {
    const mt = Rc(ze);
    const Dt = CYCLE_ON.spawning ?? 2000;
    for (let Mt = 0; Mt < 5; Mt++) {
      const Lt = this.parts[Mt] as SVGCircleElement;
      const yn = clamp(((now - this.overlayAt) / Dt - Mt * 0.09) / 0.62, 0, 1);
      if (yn >= 1) {
        Lt.style.display = "none";
        continue;
      }
      const an = 1 - Math.pow(1 - yn, 3);
      const Et = Mt * 2.4 + yn * 2.2;
      const En = 96 * (1 - an);
      Lt.style.display = "";
      Lt.setAttribute("cx", (R + En * Math.cos(Et)).toFixed(1));
      Lt.setAttribute("cy", (R + En * Math.sin(Et) * 0.8).toFixed(1));
      Lt.setAttribute("r", (9 * (0.5 + 0.5 * an) * mt).toFixed(2));
      Lt.setAttribute("opacity", (mt * clamp(yn * 5, 0, 1) * (1 - an * 0.25)).toFixed(3));
    }
  }

  paintWave(ze: number, now: number, R: number): void {
    const mt = [-2, -1, 1, 2];
    const Dt = 44;
    for (let Mt = 0; Mt < 4; Mt++) {
      const Lt = Mt < 2 ? this.dots[Mt] as SVGPathElement : this.parts[3 + Mt] as SVGCircleElement;
      const yn = mt[Mt] as number;
      const an = clamp((ze - Math.abs(yn) * 0.1) / (1 - Math.abs(yn) * 0.1), 0, 1);
      if (an <= 0.004) {
        Lt.style.display = "none";
        continue;
      }
      const Et = y1e(an);
      const En = wave(now) * (0.55 + 0.45 * Math.sin(now * 0.012 - Math.abs(yn) * 1.05));
      const Zt = (7 + 9 * clamp(En, 0.08, 1)) * Rc(an);
      const dn = 6 * clamp(En, 0, 1) * an;
      Lt.style.display = "";
      if (Mt < 2) {
        const on = (Zt / R) * 1.02;
        Lt.setAttribute("d", this.circlePath);
        Lt.setAttribute("transform", `translate(${(R + yn * Dt * Et).toFixed(1)} ${(R - dn).toFixed(1)}) scale(${on.toFixed(4)}) translate(${-R} ${-R})`);
        Lt.setAttribute("opacity", an.toFixed(3));
      } else {
        Lt.setAttribute("cx", (R + yn * Dt * Et).toFixed(1));
        Lt.setAttribute("cy", (R - dn).toFixed(1));
        Lt.setAttribute("r", Zt.toFixed(2));
        Lt.setAttribute("opacity", an.toFixed(3));
      }
    }
  }

  paintSend(ze: number, now: number, stateAt: number, R: number): void {
    const mt = Rc(ze);
    const Dt = ((((now - stateAt) / SEND_MS) % 1) + 1) % 1;
    const Mt = clamp((Dt - 0.18) / 0.55, 0, 1);
    const Lt = Mt * Mt * (0.4 + 0.6 * Mt);
    const yn = 0.74;
    const an = -0.62;
    const Et = 108 * Lt;
    const En = this.parts[5] as SVGCircleElement;
    const on = Mt > 0 && Mt < 1;
    En.style.display = on ? "" : "none";
    if (on) {
      En.setAttribute("cx", (R + yn * Et).toFixed(1));
      En.setAttribute("cy", (R + an * Et).toFixed(1));
      En.setAttribute("r", (10 * (1 - Lt * 0.55) * mt).toFixed(2));
      En.setAttribute("opacity", (mt * (1 - Lt * Lt)).toFixed(3));
    }
    const Zt = this.parts[6] as SVGCircleElement;
    const on2 = clamp((Dt - 0.26) / 0.55, 0, 1);
    const bn = on2 * on2 * (0.4 + 0.6 * on2);
    const Cn = Mt > 0 && on2 > 0 && on2 < 1;
    Zt.style.display = Cn ? "" : "none";
    if (Cn) {
      const bi = 108 * bn;
      Zt.setAttribute("cx", (R + yn * bi).toFixed(1));
      Zt.setAttribute("cy", (R + an * bi).toFixed(1));
      Zt.setAttribute("r", (5 * (1 - bn * 0.6) * mt).toFixed(2));
      Zt.setAttribute("opacity", (mt * 0.3 * (1 - bn)).toFixed(3));
    }
    const dn = this.rings[5] as SVGCircleElement;
    const on3 = clamp((Dt - 0.18) / 0.3, 0, 1);
    const bn3 = on3 > 0 && on3 < 1;
    dn.style.display = bn3 ? "" : "none";
    if (bn3) {
      dn.removeAttribute("stroke-dasharray");
      dn.removeAttribute("transform");
      dn.setAttribute("cx", `${R}`);
      dn.setAttribute("cy", `${R}`);
      dn.setAttribute("r", (20 + 34 * Rc(on3)).toFixed(1));
      dn.setAttribute("stroke-width", (2.8 * (1 - on3)).toFixed(2));
      dn.setAttribute("opacity", (mt * (1 - on3) * 0.8).toFixed(3));
    }
  }

  paintRecv(ze: number, now: number, stateAt: number, R: number): void {
    const mt = Rc(ze);
    const Dt = now - stateAt;
    const Mt = Math.floor(Dt / RECV_MS);
    if (Mt !== this.recvTick) {
      this.recvTick = Mt;
      this.recvDir = rand(-Math.PI * 1.25, Math.PI * 0.25);
    }
    const Lt = (((Dt / RECV_MS) % 1) + 1) % 1;
    const yn = clamp(Lt / 0.6, 0, 1);
    const an = 1 - Math.pow(1 - yn, 3);
    const Et = Math.cos(this.recvDir);
    const En = Math.sin(this.recvDir);
    const Zt = 108 * (1 - an);
    const dn = this.parts[5] as SVGCircleElement;
    const bn = yn < 1;
    dn.style.display = bn ? "" : "none";
    if (bn) {
      const Cn = 18 * Math.sin(yn * Math.PI) * (1 - an * 0.7);
      dn.setAttribute("cx", (R + Et * Zt + -En * Cn).toFixed(1));
      dn.setAttribute("cy", (R + En * Zt + Et * Cn).toFixed(1));
      dn.setAttribute("r", (3.5 + 6.5 * an).toFixed(2));
      dn.setAttribute("opacity", (mt * clamp(yn * 3.5, 0, 1) * (0.3 + 0.7 * an)).toFixed(3));
    }
    const on = this.rings[6] as SVGCircleElement;
    const bn2 = clamp((Lt - 0.58) / 0.32, 0, 1);
    const Cn = bn2 > 0 && bn2 < 1;
    on.style.display = Cn ? "" : "none";
    if (Cn) {
      on.removeAttribute("stroke-dasharray");
      on.removeAttribute("transform");
      on.setAttribute("cx", `${R}`);
      on.setAttribute("cy", `${R}`);
      on.setAttribute("r", (20 + 26 * Rc(bn2)).toFixed(1));
      on.setAttribute("stroke-width", (2.8 * (1 - bn2)).toFixed(2));
      on.setAttribute("opacity", (mt * (1 - bn2) * 0.8).toFixed(3));
    }
  }

  paintDock(ze: number, now: number, stateAt: number, R: number): void {
    const mt = Rc(ze);
    const Dt = (now - stateAt) / 1000;
    const Mt = 42;
    const Lt = 1.1;
    for (let yn = 0; yn < 2; yn++) {
      const an = this.parts[5 + yn] as SVGCircleElement;
      const Et = clamp((Dt - (0.2 + yn * 1.3)) / 0.9, 0, 1);
      if (Et <= 0) {
        an.style.display = "none";
        continue;
      }
      const En = 1 - Math.pow(1 - Et, 3);
      const Zt = now * 0.001 * Lt + yn * Math.PI;
      const dn = R + Mt * Math.sin(Zt);
      const on = R + Mt * 0.5 * Math.cos(Zt) + Math.sin(now * 0.003 + yn) * 2;
      const bn = R - 120 + yn * 30;
      const Cn = R + 95;
      an.style.display = "";
      an.setAttribute("cx", (bn + (dn - bn) * En).toFixed(1));
      an.setAttribute("cy", (Cn + (on - Cn) * En).toFixed(1));
      an.setAttribute("r", ((7 + 3 * En) * mt).toFixed(2));
      an.setAttribute("opacity", (mt * clamp(Et * 4, 0, 1)).toFixed(3));
    }
  }

  paintPencil(ze: number, now: number, stateAt: number, R: number): void {
    const mt = pencilPose(now, stateAt);
    const Dt = this.glyphs[0] as SVGPathElement;
    const Lt = ((mt.rot - 90) * Math.PI) / 180;
    const yn = 68;
    const an = Math.cos(Lt) * yn;
    const Et = Math.sin(Lt) * yn;
    Dt.style.display = "";
    Dt.setAttribute("d", this.pencilPath);
    Dt.style.fill = "var(--fg)";
    Dt.setAttribute("transform", `translate(${(R + (mt.x + an) * ze).toFixed(1)} ${(R + (mt.y + mt.wig * 0.15 + Et) * ze).toFixed(1)}) rotate(${(mt.rot * ze).toFixed(1)}) scale(${Rc(ze).toFixed(3)}) translate(${-R} ${-R})`);
    Dt.setAttribute("opacity", clamp(ze * 1.6 - 0.3, 0, 1).toFixed(3));
    if (ze > 0.6 && !mt.lift) {
      const x = R + mt.x;
      const y = R + mt.y + mt.wig + 19;
      const last = this.ink[this.ink.length - 1];
      if (!last || Math.hypot(x - last[0], y - last[1]) > 2.4) {
        this.ink.push([x, y]);
        if (this.ink.length > 64) this.ink.shift();
      } else {
        last[0] = x;
        last[1] = y;
      }
    } else if (this.ink.length) this.ink.splice(0, 2);
    const line = this.glyphs[1] as SVGPathElement;
    if (this.ink.length < 2) line.style.display = "none";
    else {
      line.style.display = "";
      line.style.fill = "none";
      line.style.stroke = "var(--fg)";
      line.setAttribute("stroke-width", "6");
      line.setAttribute("stroke-linecap", "round");
      line.setAttribute("stroke-linejoin", "round");
      line.setAttribute("d", smoothLine(this.ink));
      line.setAttribute("opacity", clamp(ze * 1.2, 0, 1).toFixed(3));
    }
  }

  paintBang(ze: number, now: number, stateAt: number, R: number): void {
    const mt = this.glyphs[2] as SVGPathElement;
    const Dt = (now - stateAt) / 1000;
    const Mt = Rc(clamp(ze * 1.1, 0, 1));
    const Lt = Math.exp(-((Dt % 2.2) * 5.5));
    const yn = Math.sin(Dt * 42) * 2.2 * Lt;
    mt.style.display = "";
    mt.setAttribute("d", this.bangPath);
    mt.style.fill = "var(--fg)";
    mt.setAttribute("transform", `translate(0 ${(-26 - (1 - Mt) * 70).toFixed(1)}) rotate(${yn.toFixed(2)} ${R} ${(R - 74).toFixed(1)}) translate(${R} ${R}) scale(${clamp(ze * 1.2, 0, 1).toFixed(3)}) translate(${-R} ${-R})`);
    mt.setAttribute("opacity", clamp(ze * 1.5 - 0.2, 0, 1).toFixed(3));
  }

  paintStandby(ze: number, now: number, R: number): void {
    const mt = Rc(ze);
    const Dt = this.parts[4] as SVGCircleElement;
    const Lt = 0.5 + 0.5 * Math.sin(now * 0.0016);
    Dt.style.display = "";
    Dt.setAttribute("cx", `${R}`);
    Dt.setAttribute("cy", `${R}`);
    Dt.setAttribute("r", (26 + 7 * Lt).toFixed(1));
    Dt.setAttribute("opacity", (mt * (0.06 + 0.1 * Lt)).toFixed(3));
    const Mt = this.rings[2] as SVGCircleElement;
    const show = ze < 0.995;
    Mt.style.display = show ? "" : "none";
    if (show) {
      Mt.removeAttribute("stroke-dasharray");
      Mt.removeAttribute("transform");
      Mt.setAttribute("cx", `${R}`);
      Mt.setAttribute("cy", `${R}`);
      Mt.setAttribute("r", (104 - 88 * mt).toFixed(1));
      Mt.setAttribute("stroke-width", "2.4");
      Mt.setAttribute("opacity", ((1 - mt) * 0.5).toFixed(3));
    }
  }

  /** 本体层的反作用量：思考点把本体 pop、send/receive/bang 轻微缩放、pencil 带着身体平移 */
  extras(now: number, stateAt: number, cur: string | null, prev: string | null, yl: number, mix: number): {
    Lee: number; rX: { lift: number; pop: number; tone: number }; yre: number; aX: number; wl: number;
    wre: number; fade: number; zoom: number; A2: number;
  } {
    const kl = (name: string) => this.amount(name, cur, prev, yl, mix);
    const Lee = kl("dots");
    const rX = this.dotsPulse(now, 1, yl, this._reduce);
    let iX = 1;
    if (cur === "dots" || prev === "dots") iX = 1 + (rX.pop - 1) * (Lee / Math.max(yl, 0.001));
    const Fme = kl("receive");
    if (Fme > 0.004) {
      const _t = ((((now - stateAt) / RECV_MS) % 1) + 1) % 1;
      const gn = clamp((_t - 0.58) / 0.34, 0, 1);
      iX *= 1 + 0.11 * Math.sin(gn * Math.PI) * Fme;
    }
    const zme = kl("send");
    if (zme > 0.004) {
      const _t = ((((now - stateAt) / SEND_MS) % 1) + 1) % 1;
      const gn = _t < 0.18 ? -0.06 * Math.sin((_t / 0.18) * Math.PI) : 0;
      const Gn = _t >= 0.18 && _t < 0.42 ? 0.05 * Math.sin(((_t - 0.18) / 0.24) * Math.PI) : 0;
      iX *= 1 + (gn + Gn) * zme;
    }
    const qee = kl("bang");
    if (qee > 0.004) iX *= 1 + 0.04 * Math.exp(-(((now - stateAt) / 1000) % 2.2) * 5.5) * qee;
    let yre = 0;
    let aX = 0;
    let wl = 0;
    const c1 = kl("pencil");
    if (c1 > 0.004) {
      const _t = pencilPose(now, stateAt);
      yre += _t.x * c1;
      aX += (_t.y + _t.wig * 0.5) * c1;
      wl += _t.rot * c1;
    }
    if (qee > 0.004) aX += 58 * qee;
    const jee = kl("whirl");
    if (jee > 0.004) {
      const _t = now / 1000;
      yre += (Math.sin(_t * 0.9) * 2 + Math.sin(_t * 1.7) * 0.8) * jee;
      aX += (Math.sin(_t * 1.3) * 2.4 + Math.sin(_t * 0.6) * 1.2) * jee;
    }
    const kre = kl("ball");
    if (kre > 0.004) {
      const _t = (now - stateAt) / 1000;
      const gn = 0.62;
      const Gn = 52;
      const Ti = (8 * Gn) / (gn * gn);
      const Ui = 40;
      const Si = Math.sqrt((2 * Ui) / Ti);
      let Ea: number;
      if (_t < Si) Ea = Ui - 0.5 * Ti * _t * _t;
      else {
        const Ca = ((((_t - Si) / gn) % 1) + 1) % 1;
        Ea = 4 * Gn * Ca * (1 - Ca);
      }
      aX += (40 - Ea) * kre;
    }
    const mixR = (tbl: Record<string, number>): number => {
      if (!cur) return 19;
      return ((tbl[cur] ?? 19) * mix) + (prev ? (tbl[prev] ?? tbl[cur] ?? 19) : (tbl[cur] ?? 19)) * (1 - mix);
    };
    const A2 = mixR(RADIUS);
    const wre = (A2 / (GROK_GEO.Re || Re0)) * iX;
    const standby = kl("standby");
    const fade = standby > 0 ? (0.28 + 0.2 * Math.sin(now * 0.0016)) * standby : 0;
    const zoomCur = cur ? Math.max(SCALE[cur] ?? 1, 1) : 1;
    const zoomPrev = prev ? Math.max(SCALE[prev] ?? 1, 1) : zoomCur;
    const zoom = 1 + (zoomCur * mix + zoomPrev * (1 - mix) - 1) * yl;
    return { Lee, rX, yre, aX, wl, wre, fade, zoom, A2 };
  }

  resetInk(): void {
    this.ink = [];
  }
}

// —— 形状辅助 ——

const turnAtCache = new Map<string, ((yaw: number) => [number, number][]) | null>();

export function turnAtOf(name: string, path: string, R: number): ((yaw: number) => [number, number][]) | null {
  if (turnAtCache.has(name)) return turnAtCache.get(name) ?? null;
  const solid = GROK_GEO.solids[name] as readonly SolidSlice[] | undefined;
  if (!solid) {
    turnAtCache.set(name, null);
    return null;
  }
  const fn = makeTurnAt(solid, shapeRing(path, R), R);
  turnAtCache.set(name, fn);
  return fn;
}

const beltCache = new Map<string, number>();

/** 形状最宽处的半宽（粒子迸发的出发半径） */
export function beltRadius(path: string, R: number): number {
  const m = beltCache.get(path);
  if (m != null) return m;
  const ring = shapeRing(path, R);
  let top = Infinity;
  let bot = -Infinity;
  for (const p of ring) {
    if (p[1] < top) top = p[1];
    if (p[1] > bot) bot = p[1];
  }
  let m2 = 0;
  for (let y = top; y <= bot; y += 2) {
    const [L, Right] = spanHalf(ring, y, R);
    const half = (Right - L) / 2;
    if (half > m2) m2 = half;
  }
  beltCache.set(path, m2);
  return m2;
}

export function shapeMetrics(shape: { path: string; face: { x: number; y: number; sx: number; sy: number; eye: number; leftDX?: number }; tiltScale?: number; beltRadius?: number }, R: number): {
  face: { x: number; y: number; sx: number; sy: number; eye: number; leftDX?: number };
  ring: [number, number][];
  tilt: number;
  belt: number;
} {
  return {
    face: shape.face,
    ring: shapeRing(shape.path, R),
    tilt: shape.tiltScale || 1,
    belt: shape.beltRadius || beltRadius(shape.path, R),
  };
}

export function circlePathOf(R: number): string {
  return closedSpline(circleRing(R));
}

/** overlay 激活时本体的目标环：pencil 时变成 teardrop（笔尖朝向的形），其余变圆 */
export function overlayRing(kind: string | null, R: number, teardropPath: string | undefined): [number, number][] {
  if (kind === "pencil" && teardropPath) {
    const ring = polarRing(flattenPath(teardropPath) as [number, number][], R);
    return rotateRing(ring, ring.length / 2, R);
  }
  return circleRing(R);
}
