/** 所有可见 Bot 共用帧时钟；无活动实例时不占用 rAF。 */
export interface BotFrameClient {
  frame(now: number): boolean;
  pageVisibility(hidden: boolean): void;
  reducedMotion(reduced: boolean): void;
}
const clients = new Set<BotFrameClient>();
const active = new Set<BotFrameClient>();
let raf = 0;
let media: MediaQueryList | null = null;

function tick(now: number) {
  raf = 0;
  for (const client of [...active])
    if (!client.frame(now)) active.delete(client);
  if (active.size && !document.hidden) raf = requestAnimationFrame(tick);
}
function visibilityChanged() {
  for (const client of clients) client.pageVisibility(document.hidden);
}
function preferenceChanged(event: MediaQueryListEvent) {
  for (const client of clients) client.reducedMotion(event.matches);
}
export function wakeBot(client: BotFrameClient): void {
  if (!clients.has(client) || document.hidden) return;
  active.add(client);
  if (!raf) raf = requestAnimationFrame(tick);
}
export function sleepBot(client: BotFrameClient): void {
  active.delete(client);
  if (!active.size && raf) {
    cancelAnimationFrame(raf);
    raf = 0;
  }
}
export function registerBot(client: BotFrameClient): () => void {
  if (!clients.size) {
    document.addEventListener("visibilitychange", visibilityChanged);
    media = window.matchMedia("(prefers-reduced-motion: reduce)");
    media.addEventListener("change", preferenceChanged);
  }
  clients.add(client);

  return () => {
    sleepBot(client);
    clients.delete(client);
    if (!clients.size) {
      document.removeEventListener("visibilitychange", visibilityChanged);
      media?.removeEventListener("change", preferenceChanged);
      media = null;
    }
  };
}
export function getBotRuntimeStats() {
  return {
    instances: clients.size,
    active: active.size,
    frameScheduled: Boolean(raf),
  };
}
