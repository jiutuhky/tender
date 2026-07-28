import type { TimelineEvent } from "@/lib/hagent/matrix";

// 投标截止时间的纯推导工具(概要卡决策触发器)。
// datetime 由 LLM 产出、格式不保证:容错解析,解析不动一律返回 null,由卡面「—」兜底。
// 无 DOM 依赖,未来引入测试框架时与 choreography 同为单元可测点。

/** 临近截止阈值(含当日):剩余天数 ≤ 7 天翻警示色 */
export const DEADLINE_WARN_DAYS = 7;

export interface DeadlineInfo {
  /** 原文时间串,展示用 */
  text: string;
  /** 距截止的整日历天数:今日为 0,已过为负;解析失败为 null */
  daysLeft: number | null;
}

/** 容错解析 datetime → 时间戳。兼容 ISO、「2026-07-24 09:30」与「2026年7月24日」等常见写法。
 *  注:纯日期 ISO 串按 UTC 解析,在 UTC+8(目标市场)折算本地日不偏移;负时区环境会早一天,可接受。 */
export function parseDeadline(raw: string): number | null {
  const s = raw.trim();
  if (!s) return null;
  const normalized = s
    .replace(/[年/.]/g, "-")
    .replace(/月/g, "-")
    .replace(/日/g, " ")
    .replace(/[时点]/g, ":")
    .replace(/分/g, "")
    .trim();
  for (const cand of [s, normalized]) {
    const t = Date.parse(cand);
    if (!Number.isNaN(t)) return t;
  }
  // 兜底:只抽「YYYY-MM-DD」三段数字。构造后回读校验,防越界翻滚(如 13 月滚成次年 1 月)
  const m = normalized.match(/(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (m && m[1] && m[2] && m[3]) {
    const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    if (d.getMonth() === Number(m[2]) - 1 && d.getDate() === Number(m[3])) return d.getTime();
  }
  return null;
}

/** 两个时间戳间的日历天数差(按本地自然日,当日为 0) */
export function calendarDaysBetween(from: number, to: number): number {
  const a = new Date(from);
  const b = new Date(to);
  a.setHours(0, 0, 0, 0);
  b.setHours(0, 0, 0, 0);
  return Math.round((b.getTime() - a.getTime()) / 86_400_000);
}

/** 从 timeline 中取投标截止事件并推导倒计时;无该事件或无时间 → null */
export function bidDeadline(
  timeline: TimelineEvent[] | undefined,
  now: number = Date.now(),
): DeadlineInfo | null {
  const ev = timeline?.find((e) => e.event === "bid_deadline" && e.datetime);
  if (!ev?.datetime) return null;
  const t = parseDeadline(ev.datetime);
  return { text: ev.datetime, daysLeft: t === null ? null : calendarDaysBetween(now, t) };
}

/** 倒计时呈现:文案 + 语气(normal / warn 警示 / past 已过期) */
export function deadlineCountdown(daysLeft: number | null): {
  label: string;
  tone: "normal" | "warn" | "past";
} | null {
  if (daysLeft === null) return null;
  if (daysLeft < 0) return { label: "已截止", tone: "past" };
  if (daysLeft === 0) return { label: "今日截止", tone: "warn" };
  return { label: `剩 ${daysLeft} 天`, tone: daysLeft <= DEADLINE_WARN_DAYS ? "warn" : "normal" };
}
