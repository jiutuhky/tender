// 已确认的二维动作母版：保持正面，转向由面部横移与侧面补位表现。
import { BOT_DEFINITIONS, type BotState } from "./states";
export type Point = [number, number];
export type BotPose = typeof REST_POSE;
export const clamp = (x: number, a = 0, b = 1): number =>
  Math.max(a, Math.min(b, x));
export const smooth = (x: number): number => {
  x = clamp(x);
  return x * x * (3 - 2 * x);
};
const hump = (x: number, a: number, b: number): number =>
  x < a || x > b ? 0 : Math.sin((Math.PI * (x - a)) / (b - a));
export const REST_POSE = {
  x: 0,
  y: 0,
  r: 0,
  sx: 1,
  sy: 1,
  lean: 0,
  top: 0,
  bottom: 0,
  shoulder: 0,
  yaw: 0,
  gx: 0,
  gy: 0,
  lh: 18,
  rh: 18,
  lw: 8,
  rw: 8,
  la: 0,
  ra: 0,
  ls: 0,
  rs: 0,
};
const samples: Partial<Record<BotState, number>> = {
  idle: 0.18,
  listening: 0.28,
  connecting: 0.3,
  receiving: 0.47,
  sending: 0.37,
  thinking: 0.22,
  planning: 0.14,
  searching: 0.22,
  reading: 0.45,
  working: 0.28,
  generating: 0.23,
  verifying: 0.27,
  coordinating: 0.23,
  waiting: 0.18,
  retrying: 0.3,
};
export function poseFor(id: BotState, time: number, still = false): BotPose {
  const s = BOT_DEFINITIONS[id],
    p = { ...REST_POSE };
  let c = s.period ? (time % s.period) / s.period : 0;
  if (still) c = samples[id] ?? 0.4;
  const tau = 2 * Math.PI,
    w = Math.sin(c * tau),
    soft = Math.tanh(w * 2),
    entry = still ? 1 : smooth(time / 0.48);
  switch (id) {
    case "idle":
      p.r = 0.8 * Math.sin(c * tau);
      p.y = 0.3 * Math.sin(c * tau);
      p.gx = still ? 0 : 1.5 * hump(c, 0.7, 0.92);
      break;
    case "listening":
      Object.assign(p, {
        r: -6,
        lean: -4,
        sx: 0.97,
        sy: 1.05,
        gx: -3,
        gy: -1,
        lh: 22,
        rh: 21,
      });
      p.r -= hump(c, 0.1, 0.4);
      break;
    case "connecting": {
      const q = hump(c, 0.05, 0.65);
      Object.assign(p, {
        sx: 1 - 0.17 * q,
        sy: 1 + 0.09 * q,
        top: 3 * q,
        bottom: -q,
        lh: 18 - 5 * q,
        rh: 18 - 5 * q,
        gx: 0,
        gy: -1,
      });
      break;
    }
    case "receiving": {
      const q = hump(c, 0.23, 0.65),
        up = hump(c, 0.04, 0.23);
      Object.assign(p, {
        y: 4 * q - 2 * up,
        sx: 1 + 0.13 * q,
        sy: 1 - 0.17 * q,
        top: -2 * q,
        gx: 0,
        gy: -4 * (1 - q),
        lh: 20 - 6 * q,
        rh: 20 - 6 * q,
      });
      break;
    }
    case "sending": {
      const coil = hump(c, 0, 0.25),
        push = hump(c, 0.25, 0.72);
      Object.assign(p, {
        y: 3 * coil - 7 * push,
        sx: 1 + 0.1 * coil - 0.13 * push,
        sy: 1 - 0.1 * coil + 0.17 * push,
        top: 2 * push,
        gy: -4 * push,
        lh: 17,
        rh: 17,
      });
      break;
    }
    case "thinking":
      Object.assign(p, {
        r: -9 + 4 * w,
        y: -2 - hump(c, 0.1, 0.55) * 1.3,
        yaw: 26 * soft,
        lean: 2 * w,
        sx: 0.97,
        sy: 1.03,
        gx: -3 + 2 * w,
        gy: -3,
        lh: 10,
        rh: 19,
        ls: 1.2,
        rs: 1,
      });
      break;
    case "planning": {
      const step = c < 0.28 ? -1 : c < 0.6 ? 0 : 1;
      Object.assign(p, {
        x: step * 3,
        r: step * 8,
        y: -hump(c % 0.32, 0.03, 0.27),
        lean: step * 2,
        gx: step * 4,
        gy: -2,
        lh: 14,
        rh: 18,
      });
      break;
    }
    case "searching":
      Object.assign(p, {
        x: 7 * soft,
        r: 9 * soft,
        yaw: 36 * soft,
        sx: 0.95,
        sy: 1.025,
        gx: 4.5 * soft,
        gy: -0.5,
        lh: 23,
        rh: 23,
      });
      break;
    case "reading": {
      const x = c < 0.7 ? -1 + (2 * c) / 0.7 : 1 - 2 * smooth((c - 0.7) / 0.3);
      Object.assign(p, {
        r: 2 * x,
        lean: 1.7 * x,
        y: c < 0.7 ? c * 2 : 1.4 * (1 - smooth((c - 0.7) / 0.3)),
        gx: 4 * x,
        gy: 2,
        lh: 13,
        rh: 13,
        sy: 0.98,
      });
      break;
    }
    case "working": {
      const q = hump(c, 0.06, 0.7);
      Object.assign(p, {
        x: 3 * q,
        y: 3 * q,
        r: -6 * q,
        lean: 5 * q,
        sx: 1 + 0.1 * q,
        sy: 1 - 0.12 * q,
        top: -2 * q,
        gx: 3,
        gy: 3,
        lh: 10,
        rh: 10,
        ls: 1,
        rs: -1,
      });
      break;
    }
    case "generating":
      Object.assign(p, {
        r: 5 * w,
        lean: 4 * soft,
        shoulder: 2 * w,
        sx: 1 + 0.06 * Math.abs(w),
        sy: 1 - 0.04 * Math.abs(w),
        gx: 3 * soft,
        gy: 1,
        lh: 14 - 3 * w,
        rh: 14 + 3 * w,
      });
      break;
    case "verifying": {
      const q = hump(c, 0.08, 0.43),
        v = hump(c, 0.47, 0.8);
      Object.assign(p, {
        sx: 1 - 0.16 * q,
        sy: 1 + 0.09 * q + 0.05 * v,
        y: -v,
        top: 2 * q,
        bottom: 2 * q,
        lh: 6 + 6 * v,
        rh: 6 + 6 * v,
        lw: 11,
        rw: 11,
        gy: 1,
      });
      break;
    }
    case "coordinating":
      Object.assign(p, {
        lean: 7 * soft,
        shoulder: 3 * w,
        r: 2 * w,
        yaw: 22 * soft,
        gx: 4 * soft,
        gy: -0.5,
        lh: 16,
        rh: 16,
        top: 1.5,
        bottom: -1,
      });
      break;
    case "waiting":
      Object.assign(p, {
        r: 8,
        lean: 3,
        x: 2,
        y: 2,
        sx: 1.03,
        sy: 0.97,
        gx: 2 + hump(c, 0.72, 0.93),
        lh: 10,
        rh: 10,
      });
      break;
    case "awaiting-input":
      Object.assign(p, {
        r: 0,
        y: -3,
        top: -2,
        bottom: 2,
        sx: 0.94,
        sy: 1.1,
        lh: 24,
        rh: 24,
        lw: 9,
        rw: 9,
        gy: -1,
      });
      break;
    case "blocked":
      Object.assign(p, {
        x: 5 * entry,
        r: -8,
        lean: -6,
        sx: 0.82,
        sy: 1.05,
        top: 2,
        bottom: -2,
        shoulder: -2,
        gx: 4,
        gy: 0,
        lh: 8,
        rh: 19,
        ls: 1.7,
      });
      break;
    case "retrying": {
      const back = hump(c, 0.02, 0.42),
        push = hump(c, 0.45, 0.85);
      Object.assign(p, {
        x: -5 * back + 3 * push,
        r: 11 * back - 5 * push,
        lean: -5 * back + 4 * push,
        sx: 1 - 0.1 * back,
        sy: 1 + 0.08 * back,
        gx: -3 * back + 3 * push,
        lh: 12,
        rh: 15,
        gy: 1,
      });
      break;
    }
    case "settling": {
      const a = still ? 0 : 1 - smooth(time / 3.4);
      Object.assign(p, {
        r: 10 * a * Math.cos(time * 2.8),
        lean: 3 * a,
        y: -2 * a,
        sx: 1 + 0.04 * a,
        sy: 1 - 0.04 * a,
        lh: 16,
        rh: 16,
      });
      break;
    }
    case "completed":
      Object.assign(p, {
        y: -2,
        sy: 1.05,
        sx: 1.02,
        top: -1,
        bottom: 0,
        lh: 4,
        rh: 4,
        lw: 12,
        rw: 12,
        la: 5,
        ra: 5,
      });
      if (!still) p.y -= 2 * hump(time, 0, 0.6);
      break;
    case "partial":
      Object.assign(p, {
        r: -4,
        shoulder: 8,
        lean: -2,
        top: -1,
        sy: 1.02,
        lh: 4,
        rh: 17,
        lw: 11,
        la: 4,
        gx: 1,
      });
      break;
    case "failed":
      Object.assign(p, {
        y: 6,
        sx: 1.12,
        sy: 0.78,
        top: 3,
        bottom: -4,
        shoulder: 1,
        lh: 9,
        rh: 9,
        ls: -2,
        rs: 2,
        gy: 4,
      });
      break;
    case "cancelled":
      Object.assign(p, {
        y: 3,
        sx: 1.04,
        sy: 0.89,
        lean: 0,
        top: 0,
        bottom: 0,
        lh: 4,
        rh: 4,
        lw: 12,
        rw: 12,
        gy: 1,
      });
      if (!still) {
        p.x = -5 * hump(time, 0, 0.45);
        p.r = 7 * hump(time, 0, 0.45);
      }
      break;
    case "paused":
      Object.assign(p, {
        r: -12,
        y: -3,
        yaw: 38,
        sx: 0.92,
        sy: 1.05,
        gx: -2,
        lh: 7,
        rh: 7,
        lw: 9,
        rw: 9,
      });
      break;
    case "sleeping":
      Object.assign(p, {
        r: 10,
        y: 7,
        sx: 1.14,
        sy: 0.7,
        top: 4,
        bottom: -4,
        lh: 2.2,
        rh: 2.2,
        lw: 12,
        rw: 12,
        la: -2,
        ra: -2,
        gy: 3,
      });
      break;
  }
  if (s.group !== "state") {
    const q = still
        ? id === "celebrate"
          ? 0.84
          : 0.46
        : clamp(time / s.duration),
      a = Math.sin(q * Math.PI);
    if (id === "appear")
      Object.assign(p, {
        sx: 0.6 + 0.4 * smooth(q / 0.7),
        sy: 0.6 + 0.4 * smooth(q / 0.7),
        y: 8 * (1 - smooth(q / 0.8)),
        lh: 2 + 16 * smooth((q - 0.1) / 0.6),
        rh: 2 + 16 * smooth((q - 0.1) / 0.6),
      });
    if (id === "acknowledge")
      Object.assign(p, {
        r: -3 * a,
        lean: -2 * a,
        y: 4 * a,
        sx: 1 + 0.04 * a,
        sy: 1 - 0.06 * a,
        gy: 3 * a,
        lh: 18 - 7 * a,
        rh: 18 - 7 * a,
      });
    if (id === "dispatch")
      Object.assign(p, {
        r: 14 * a,
        lean: 7 * a,
        yaw: 50 * a,
        x: 4 * a,
        gx: 4 * a,
        lh: 16,
        rh: 16,
      });
    if (id === "receive-result")
      Object.assign(p, {
        r: -9 * a,
        lean: -4 * a,
        x: -3 * a,
        y: 3 * a,
        sx: 1 + 0.12 * a,
        sy: 1 - 0.15 * a,
        gx: -4 * a,
        gy: 2 * a,
      });
    if (id === "milestone")
      Object.assign(p, {
        r: -8 * a,
        shoulder: 5 * a,
        y: -3 * a,
        lh: 18 - 13 * a,
        rh: 18 - 13 * a,
        la: 4 * a,
        ra: 4 * a,
      });
    if (id === "notify")
      Object.assign(p, {
        y: -5 * a,
        sx: 1 - 0.09 * a,
        sy: 1 + 0.15 * a,
        lh: 18 + 7 * a,
        rh: 18 + 7 * a,
        top: -2 * a,
      });
    if (id === "recover") {
      const back = 1 - smooth(q),
        release = hump(q, 0.15, 0.85);
      Object.assign(p, {
        sx: 1 - 0.18 * back + 0.06 * release,
        sy: 1 + 0.1 * back - 0.04 * release,
        lean: -5 * back,
        r: -8 * back,
        y: -2 * release,
        lh: 18 - 8 * back,
        rh: 18,
      });
    }
    if (id === "celebrate") {
      const coil = hump(q, 0, 0.18),
        jump = hump(q, 0.18, 0.8),
        turn = smooth((q - 0.2) / 0.54);
      Object.assign(p, {
        y: 4 * coil - 10 * jump,
        r: -12 * jump,
        sy: 1 - 0.12 * coil + 0.09 * jump,
        sx: 1 + 0.1 * coil - 0.07 * jump,
        yaw: 360 * turn,
        lh: 18 - 14 * smooth((q - 0.65) / 0.25),
        rh: 18 - 14 * smooth((q - 0.65) / 0.25),
        lw: 8 + 4 * smooth((q - 0.65) / 0.25),
        rw: 8 + 4 * smooth((q - 0.65) / 0.25),
        la: 5 * smooth((q - 0.65) / 0.25),
        ra: 5 * smooth((q - 0.65) / 0.25),
      });
    }
    if (id === "blink") {
      const f = still
        ? 1
        : q < 0.25
          ? smooth(q / 0.25)
          : q < 0.43
            ? 1
            : 1 - smooth((q - 0.43) / 0.57);
      Object.assign(p, {
        lh: 18 - 15.8 * f,
        rh: 18 - 15.8 * f,
        lw: 8 + 2 * f,
        rw: 8 + 2 * f,
      });
    }
    if (id === "glance")
      Object.assign(p, { gx: 4 * a, gy: -a, r: 2 * a, yaw: 9 * a });
    if (id === "curious")
      Object.assign(p, {
        r: -10 * a,
        shoulder: 4 * a,
        lean: -2 * a,
        lh: 18 - 8 * a,
        rh: 18 + 5 * a,
        gx: -2 * a,
      });
    if (id === "content")
      Object.assign(p, {
        y: -2 * a,
        sy: 1 + 0.035 * a,
        lh: 18 - 14 * a,
        rh: 18 - 14 * a,
        lw: 8 + 3 * a,
        rw: 8 + 3 * a,
        la: 4 * a,
        ra: 4 * a,
      });
    if (q >= 1 && id !== "celebrate") Object.assign(p, REST_POSE);
  }
  return p;
}
export function eyePath(
  cx: number,
  cy: number,
  w: number,
  h: number,
  slope: number,
  arch: number,
): string {
  const l = cx - w / 2,
    r = cx + w / 2,
    top = cy - h / 2,
    bot = cy + h / 2,
    k = Math.min(w * 0.46, h * 0.5);
  return `M${l} ${cy - slope}C${l} ${top - slope} ${cx - k} ${top - arch} ${cx} ${top - arch}C${cx + k} ${top - arch} ${r} ${top + slope} ${r} ${cy + slope}C${r} ${bot + slope} ${cx + k} ${bot - arch} ${cx} ${bot - arch}C${cx - k} ${bot - arch} ${l} ${bot - slope} ${l} ${cy - slope}Z`;
}
export function bodyPath(p: BotPose): string {
  const points: Point[] = [
    [14 + p.top + p.lean, 14 - p.shoulder],
    [86 - p.top + p.lean, 14 + p.shoulder],
    [86 - p.bottom - p.lean, 86],
    [14 + p.bottom - p.lean, 86],
  ];
  const mix = (a: Point, b: Point, k: number): Point => [
    a[0] + (b[0] - a[0]) * k,
    a[1] + (b[1] - a[1]) * k,
  ];
  let d = "";
  for (let i = 0; i < 4; i++) {
    const cur = points[i]!,
      prev = points[(i + 3) % 4]!,
      next = points[(i + 1) % 4]!,
      a = mix(cur, prev, 0.224),
      b = mix(cur, next, 0.224);
    d += `${i ? "L" : "M"}${a[0]} ${a[1]}Q${cur[0]} ${cur[1]} ${b[0]} ${b[1]}`;
  }
  return d + "Z";
}

export const POSE_KEYS = Object.keys(REST_POSE) as (keyof BotPose)[];
