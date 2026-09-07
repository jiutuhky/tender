import type { TimelineEvent } from "@/lib/hagent/matrix";

export const DEADLINE_WARN_DAYS = 7;
const DEFAULT_ZONE = "Asia/Shanghai";
export interface DeadlineInfo {
  text: string;
  at: number | null;
  daysLeft: number | null;
  expired: boolean;
  timezone: string;
  zoneLabel: string;
  precise: boolean;
}

/** 文件未给时区时按中国采购项目的北京时间解释，并在界面明确标注这一假设。 */
export function deadlineZone(raw: string, zone?: string | null): string {
  if (zone?.trim()) {
    const z = zone.trim();
    if (["北京时间", "中国标准时间", "UTC+8", "GMT+8", "UTC+08:00"].includes(z)) return DEFAULT_ZONE;
    return z;
  }
  const offset = raw.match(/(?:T|\s)\d{1,2}:\d{2}.*?([+-]\d{2}:?\d{2}|Z)$/i)?.[1];
  if (offset) return offset.toUpperCase() === "Z" ? "UTC" : offset.replace(/([+-]\d{2})(\d{2})$/, "$1:$2");
  return DEFAULT_ZONE;
}
export function deadlineZoneLabel(raw: string, zone?: string | null): string {
  const z = deadlineZone(raw, zone);
  if (z === DEFAULT_ZONE || z === "+08:00") return zone || /(?:[+-]\d{2}:?\d{2}|Z)$/i.test(raw) ? "北京时间" : "按北京时间";
  return /^[+-]/.test(z) ? `UTC${z}` : z;
}
function parts(at: number, zone: string) {
  const p = new Intl.DateTimeFormat("en-CA", { timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" }).formatToParts(at);
  const n = (k: string) => Number(p.find((v) => v.type === k)?.value);
  return [n("year"), n("month"), n("day"), n("hour"), n("minute"), n("second")] as const;
}
const hasClock = (raw: string) => /\d{1,2}\s*[:时点]\s*\d{1,2}/.test(raw);

/** 只接受完整日期，校验越界。无偏移时间按文件时区解析，绝不使用浏览器时区。 */
export function parseDeadline(raw: string, timezone?: string | null): number | null {
  const normalized = raw.trim().replace(/[年/.]/g, "-").replace(/月/g, "-").replace(/日/g, " ").replace(/[时点]/g, ":").replace(/分/g, "").trim();
  const m = normalized.match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:[T\s]+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?(?:\s*(Z|[+-]\d{2}:?\d{2}))?$/i);
  if (!m) return null;
  const [y, month, d, h, minute, sec] = [Number(m[1]), Number(m[2]), Number(m[3]), Number(m[4] ?? 0), Number(m[5] ?? 0), Number(m[6] ?? 0)];
  const wall = Date.UTC(y!, month! - 1, d!, h!, minute!, sec!);
  const check = new Date(wall);
  if (check.getUTCFullYear() !== y || check.getUTCMonth() !== month! - 1 || check.getUTCDate() !== d || h! > 23 || minute! > 59 || sec! > 59) return null;
  if (m[7]) {
    const offset = m[7].toUpperCase();
    if (offset === "Z") return wall;
    const digits = offset.slice(1).replace(":", "");
    const hh = Number(digits.slice(0, 2)), mm = Number(digits.slice(2));
    if (hh > 23 || mm > 59) return null;
    return wall - (offset.startsWith("-") ? -1 : 1) * (hh * 60 + mm) * 60_000;
  }
  try {
    const zone = deadlineZone(raw, timezone);
    let at = wall;
    for (let i = 0; i < 3; i++) {
      const p = parts(at, zone);
      at += wall - Date.UTC(p[0], p[1] - 1, p[2], p[3], p[4], p[5]);
    }
    const p = parts(at, zone);
    return p[0] === y && p[1] === month && p[2] === d && p[3] === h && p[4] === minute ? at : null;
  } catch { return null; }
}
export function calendarDaysBetween(from: number, to: number, zone = DEFAULT_ZONE): number {
  const a = parts(from, zone), b = parts(to, zone);
  return Math.round((Date.UTC(b[0], b[1] - 1, b[2]) - Date.UTC(a[0], a[1] - 1, a[2])) / 86_400_000);
}
export function bidDeadline(timeline: TimelineEvent[] | undefined, now = Date.now()): DeadlineInfo | null {
  const ev = timeline?.find((e) => e.event === "bid_deadline" && e.datetime);
  if (!ev?.datetime) return null;
  const timezone = deadlineZone(ev.datetime, ev.timezone);
  const at = parseDeadline(ev.datetime, ev.timezone);
  let daysLeft: number | null = null;
  try { if (at !== null) daysLeft = calendarDaysBetween(now, at, timezone); } catch { /* 无效时区保留原文，不推断倒计时。 */ }
  const precise = hasClock(ev.datetime);
  return { text: ev.datetime, at, daysLeft, expired: daysLeft !== null && (daysLeft < 0 || (precise && at !== null && now >= at)), timezone, zoneLabel: deadlineZoneLabel(ev.datetime, ev.timezone), precise };
}
export function deadlineCountdown(daysLeft: number | null, expired = false): { label: string; tone: "normal" | "warn" | "past" } | null {
  if (daysLeft === null) return null;
  if (expired || daysLeft < 0) return { label: "已截止", tone: "past" };
  if (daysLeft === 0) return { label: "今日截止", tone: "warn" };
  return { label: `剩 ${daysLeft} 天`, tone: daysLeft <= DEADLINE_WARN_DAYS ? "warn" : "normal" };
}
export function bidWindow(timeline: TimelineEvent[] | undefined, now = Date.now()): { elapsed: number; left: number } | null {
  const end = bidDeadline(timeline, now);
  if (!end?.at || !end.precise) return null;
  const times = (timeline ?? []).map((e) => e.datetime ? parseDeadline(e.datetime, e.timezone) : null).filter((t): t is number => t !== null);
  const start = Math.min(...times);
  if (start >= end.at) return null;
  const span = end.at - start, elapsed = Math.min(span, Math.max(0, now - start));
  return { elapsed, left: span - elapsed };
}
export function fmtShortDeadline(at: number, zone = DEFAULT_ZONE, precise = true): string {
  try {
    const p = parts(at, zone), pad = (n: number) => String(n).padStart(2, "0");
    return `${pad(p[1])}-${pad(p[2])}${precise ? ` ${pad(p[3])}:${pad(p[4])}` : "（时刻未注明）"}`;
  } catch { return "时间待核实"; }
}
