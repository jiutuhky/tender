// 角色引擎 · 特技层 —— grok-icon-study replica src/tricks.js 的 1:1 移植。
//
// hop 四段递减抛物线、spinBounce（转完接一跳）、spinDizzy（越转越快 + 处理晕眩晃动）、
// spinWild（蓄力回拉 → 甩出 → 匀速 → 拖停 → 长晕），曲线参数全部对齐原版。

import { K2, rand, sign, spring, type Spring } from "./math";

/** 蹦跳的四段 [高度, 时长]：弹力衰减是「有重量」的来源 */
export const HOP_SEGS = [
  { h: 48, d: 0.5 },
  { h: 28, d: 0.382 },
  { h: 14, d: 0.27 },
  { h: 6, d: 0.177 },
] as const;
export const HOP_DUR = HOP_SEGS.reduce((s, x) => s + x.d, 0);

/** hopAt 时刻起的垂直位移；null = 已落地（主循环据此清 hopAt） */
export function hopY(hopAt: number, now: number): number | null {
  if (hopAt < 0) return 0;
  const Et = (now - hopAt) / 1000;
  if (Et >= HOP_DUR) return null;
  let En = 0;
  for (const seg of HOP_SEGS) {
    if (Et < En + seg.d) {
      const bn = (Et - En) / seg.d;
      return -4 * seg.h * bn * (1 - bn);
    }
    En += seg.d;
  }
  return 0;
}

export type TrickKind = "spinBounce" | "spinDizzy" | "spinWild";

export interface Trick {
  kind: TrickKind;
  t0: number;
  dir: number;
  turns: number;
}

export function startTrick(kind: TrickKind, reduce: boolean): Trick | null {
  if (reduce) return null;
  const dir = sign();
  const turns = kind === "spinDizzy" ? Math.round(rand(3, 4)) : kind === "spinWild" ? 9 : 1;
  return { kind, t0: performance.now(), dir, turns };
}

export interface TrickOut {
  turn: number | null;
  /** 晕眩摆动的横向 / 纵向位移与附加旋转（原 Kr / yi / ki / Yr / Zr / wi） */
  Kr: number;
  yi: number;
  ki: number;
  Yr: number;
  Zr: number;
  wi: number;
  lidMul: number | null;
  eyeBoost: number | null;
  hop: number;
  done: boolean;
  wantHop: boolean;
}

export function evalTrick(trick: Trick | null, now: number): TrickOut {
  const empty: TrickOut = {
    turn: null, Kr: 0, yi: 0, ki: 0, Yr: 0, Zr: 0, wi: 0, lidMul: null, eyeBoost: null,
    hop: 0, done: !trick, wantHop: false,
  };
  if (!trick) return empty;
  const Et = (now - trick.t0) / 1000;
  const { kind, dir, turns } = trick;
  let turn: number | null = null;
  let Kr = 0;
  let yi = 0;
  let ki = 0;
  let Yr = 0;
  let Zr = 0;
  let wi = 0;
  let lidMul: number | null = null;
  let eyeBoost: number | null = null;
  let done = false;
  let wantHop = false;

  if (kind === "spinDizzy") {
    const on = 0.55 + turns * 0.16;
    const bn = 1.5;
    if (Et < on) {
      const Cn = Et / on;
      turn = turns * Math.PI * 2 * dir * (Cn * Cn);
    } else if (Et < on + bn) {
      const Cn = Et - on;
      const bi = Math.pow(1 - Cn / bn, 1.3);
      Kr = Math.sin(Cn * 10) * 17 * dir * bi;
      yi = Math.cos(Cn * 10) * 10 * dir * bi;
      ki = Math.sin(Cn * 20) * 3 * bi;
      lidMul = 0.46 + 0.14 * Math.sin(Cn * 21);
      eyeBoost = 1.03;
    } else done = true;
  } else if (kind === "spinWild") {
    const ud = 2.3 - 0.3;
    const Pc = 0.5;
    const Go = Math.PI * 2;
    const $i = 0.24 + 2.3 + 1.25;
    const gm = (turns * Go + Pc) / (0.3 / 2 + ud + 1.25 / 4);
    if (Et < $i + 1.7) {
      let cr: number;
      if (Et < 0.24) cr = -Pc * (1 - Math.cos((Et / 0.24) * Math.PI)) / 2;
      else if (Et < 0.24 + 0.3) {
        const Ua = Et - 0.24;
        cr = -Pc + gm * Ua * Ua / (2 * 0.3);
      } else if (Et < 0.24 + 2.3) cr = -Pc + gm * (0.3 / 2 + (Et - 0.24 - 0.3));
      else if (Et < $i) {
        const Ua = (Et - 0.24 - 2.3) / 1.25;
        cr = -Pc + gm * (0.3 / 2 + ud) + gm * 1.25 * (1 - Math.pow(1 - Ua, 4)) / 4;
      } else cr = turns * Go;
      turn = cr * dir;
      let pl = 0;
      if (Et > 0.24 + 2.3) {
        const Ua = Math.min((Et - 0.24 - 2.3) / 1.25, 1);
        pl = Ua < 0.4 ? 0 : Math.pow((Ua - 0.4) / 0.6, 2);
        if (Et >= $i) pl = Math.pow(1 - (Et - $i) / 1.7, 1.6);
      }
      const Yl = Math.max(Et - 0.24 - 2.3, 0);
      Yr = cr / (turns * Go) * 3 * 360 * dir;
      Kr = Math.sin(Yl * 9.2) * 11 * dir * pl;
      yi = (Math.cos(Yl * 9.2) - 1) * 6 * dir * pl;
      ki = Math.sin(Yl * 18.4) * 2.6 * pl;
      Zr = Math.sin(Yl * 11.5) * 13 * dir * pl;
      wi = (Math.cos(Yl * 9) - 1) * 3.5 * pl;
      lidMul = 1.14 - 0.44 * pl + 0.1 * Math.sin(Yl * 16) * pl;
      eyeBoost = 1.12 - 0.09 * pl;
    } else done = true;
  } else if (kind === "spinBounce") {
    if (Et < 0.7) turn = turns * Math.PI * 2 * dir * K2(Et / 0.7);
    else {
      wantHop = true;
      done = true;
    }
  }

  return { turn, Kr, yi, ki, Yr, Zr, wi, lidMul, eyeBoost, hop: 0, done, wantHop };
}

/** 手动转圈：目标 turns 圈，交由 spinTurn 弹簧追（原 makeSpinTurn） */
export function makeSpinTurn(turns = 1, dir = sign()): Spring {
  const s = spring(0);
  s.t = turns * Math.PI * 2 * dir;
  return s;
}

export function spinTurnSettled(s: Spring): boolean {
  return Math.abs(s.t - s.x) < 0.004 && Math.abs(s.v) < 0.015;
}
