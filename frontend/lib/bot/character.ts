import {
  BOT_DEFINITIONS,
  URGENT_STATES,
  isWorkingState,
  type BotState,
  type BotCue,
} from "./states";
import {
  clamp,
  smooth,
  poseFor,
  REST_POSE,
  POSE_KEYS,
  type BotPose,
} from "./pose";
import {
  BotPainter,
  RIBBON_STYLES,
  RIBBON_KEYS,
  type RibbonPose,
} from "./painter";
import {
  registerBot,
  wakeBot,
  sleepBot,
  type BotFrameClient,
} from "./scheduler";

export interface BotEngineOptions {
  state?: BotState;
  entrance?: boolean;
  size?: number;
  intensity?: "normal" | "quiet";
  motion?: "full" | "reduced" | "static";
  paused?: boolean;
  ribbons?: boolean;
  idleMoods?: boolean;
  seed?: number;
  /** 真实工作轮次的身份；历史恢复不提供此值，就不会播放完成庆祝。 */
  completionKey?: string;
  celebrateOnComplete?: boolean;
}
// 主角色与子角色共用播放倍率；状态防抖和自然眨眼的触发间隔仍按真实时间计。
const PLAYBACK_RATE = 1.5;

const defaults: Required<BotEngineOptions> = {
  state: "idle",
  entrance: false,
  size: 40,
  intensity: "normal",
  motion: "full",
  paused: false,
  ribbons: true,
  idleMoods: false,
  seed: 0,
  completionKey: "",
  celebrateOnComplete: true,
};
export interface BotSnapshot {
  state: BotState;
  displayed: BotState;
  expression: BotState;
  reduced: boolean;
  visible: boolean;
  timerPending: boolean;
  pose: BotPose;
}

/** 基础态、插播态、显示相位分别持有；插播结束永远回到最新基础态。 */
export class ProseBotEngine implements BotFrameClient {
  private svg: SVGSVGElement;
  private painter: BotPainter;
  private options: Required<BotEngineOptions>;
  private base: BotState;
  private displayed: BotState;
  private candidate: { state: BotState; at: number } | null = null;
  private cue: { state: BotCue; at: number } | null = null;
  private pose: BotPose = { ...REST_POSE };
  private velocity: BotPose = Object.fromEntries(
    POSE_KEYS.map((k) => [k, 0]),
  ) as BotPose;
  private ribbon: RibbonPose = { ...RIBBON_STYLES.none };
  private phase = 0;
  private stateAt: number;
  private paintAt = 0;
  private last = 0;
  private settleUntil = 0;
  private visible = true;
  private systemReduced = false;
  private destroyed = false;
  private observer: IntersectionObserver | null = null;
  private unregister: () => void = () => {};
  private ambient: ReturnType<typeof setTimeout> | null = null;
  private nextMood = Infinity;
  private pointer = { x: 0, y: 0 };
  private pauseAt = 0;
  private seenWorkKey = "";
  private completedKey = "";
  private eventKey: string | number | undefined;
  private lastBlink = -Infinity;
  private appeared = false;

  constructor(svg: SVGSVGElement, options: BotEngineOptions = {}) {
    this.svg = svg;
    this.options = { ...defaults, ...options };
    this.base = this.displayed = this.options.state;
    this.stateAt = performance.now();
    this.phase = ((this.options.seed % 97) / 97) * Math.PI * 2;
    this.painter = new BotPainter(svg);
    this.systemReduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    this.unregister = registerBot(this);
    if (typeof IntersectionObserver !== "undefined") {
      this.visible = false;
      this.observer = new IntersectionObserver((entries) => {
        const visible = entries[0]?.isIntersecting ?? false;
        if (visible === this.visible) return;
        this.visible = visible;
        this.resumeOrSleep();
      });
      this.observer.observe(svg);
    }
    this.paintStatic();
    this.resumeOrSleep();
  }
  private get reduced(): boolean {
    return this.systemReduced || this.options.motion !== "full";
  }
  private get active(): boolean {
    return (
      !this.destroyed &&
      this.visible &&
      !document.hidden &&
      !this.reduced &&
      !this.options.paused
    );
  }
  private now(): number {
    return performance.now();
  }

  configure(options: Omit<BotEngineOptions, "state">): void {
    const previous = this.options;
    this.options = { ...previous, ...options };
    const now = this.now();
    if (previous.completionKey !== this.options.completionKey)
      this.seenWorkKey = "";
    if (!previous.paused && this.options.paused) this.pauseAt = now;
    if (previous.paused && !this.options.paused) {
      const pausedFor = now - this.pauseAt;
      this.stateAt += pausedFor;
      if (this.cue) this.cue.at += pausedFor;
      if (this.candidate) this.candidate.at += pausedFor;
      this.settleUntil += pausedFor;
      this.last = 0;
    }
    if (this.options.paused) {
      this.clearAmbient();
      sleepBot(this);
      return;
    }
    if (this.reduced) {
      this.cue = null;
      this.candidate = null;
      this.displayed = this.base;
      this.paintStatic();
      this.clearAmbient();
      sleepBot(this);
      return;
    }
    // 颜色通过 CSS 变量即时更新；尺寸、强度与偏好改变只重绘，不重建 SVG。
    this.settleUntil = Math.max(this.settleUntil, now + 700 / PLAYBACK_RATE);
    this.last = 0;
    if (this.active) wakeBot(this);
    this.scheduleAmbient();
  }

  setState(state: BotState): void {
    if (this.destroyed || state === this.base) return;
    const wasWorking = isWorkingState(this.base);
    this.base = state;
    this.options.state = state;
    this.cue = null;
    this.clearAmbient();
    if (!this.active) {
      this.displayed = state;
      this.candidate = null;
      this.stateAt = this.now();
      this.paintStatic();
      return;
    }
    const now = this.now();
    if (URGENT_STATES.has(state)) {
      this.applyState(state, now);
      const key = this.options.completionKey;
      if (
        state === "completed" &&
        wasWorking &&
        key &&
        this.seenWorkKey === key &&
        this.completedKey !== key &&
        this.options.celebrateOnComplete
      ) {
        this.completedKey = key;
        this.playOnce("celebrate");
      }
      if (state !== "completed") this.seenWorkKey = "";
    } else if (state === this.displayed) {
      this.candidate = null;
    } else {
      this.candidate = { state, at: Math.max(now + 180, this.stateAt + 600) };
    }
    this.settleUntil = now + 800 / PLAYBACK_RATE;
    wakeBot(this);
  }
  private applyState(state: BotState, now: number): void {
    this.displayed = state;
    this.stateAt = now;
    this.candidate = null;
    this.settleUntil = now + 800 / PLAYBACK_RATE;
    this.nextMood = now + 25000 + (this.options.seed % 20) * 1000;
  }

  playOnce(state: BotCue, key?: string | number): void {
    if (this.destroyed || !this.active) return;
    if (key !== undefined && key === this.eventKey) return;
    if (key !== undefined) this.eventKey = key;
    // 提醒、微表情不能掩盖待回应、失败、停止等关键姿态。
    if (
      URGENT_STATES.has(this.base) &&
      !(state === "celebrate" && this.base === "completed")
    )
      return;
    this.cue = { state, at: this.now() };
    this.settleUntil =
      this.now() + (BOT_DEFINITIONS[state].duration * 1000 + 800) / PLAYBACK_RATE;
    this.clearAmbient();
    wakeBot(this);
  }
  blinkOnce(): void {
    const now = this.now();
    if (now - this.lastBlink < 2000 || this.cue) return;
    this.lastBlink = now;
    this.playOnce("blink");
  }
  setPointer(x: number, y: number): void {
    if (this.base !== "idle" || !this.active) return;
    this.pointer = { x: clamp(x, -3, 3), y: clamp(y, -2, 2) };
    this.settleUntil = this.now() + 700 / PLAYBACK_RATE;
    wakeBot(this);
  }
  reducedMotion(reduced: boolean): void {
    this.systemReduced = reduced;
    if (this.destroyed || !this.painter) return;
    this.cue = null;
    this.candidate = null;
    this.displayed = this.base;
    this.paintStatic();
    this.resumeOrSleep();
  }
  pageVisibility(): void {
    this.resumeOrSleep();
  }
  private resumeOrSleep(): void {
    this.clearAmbient();
    sleepBot(this);
    this.last = 0;
    this.cue = null;
    this.candidate = null;
    this.displayed = this.base;
    this.seenWorkKey = "";
    this.stateAt = this.now();
    this.settleUntil = this.stateAt + 800 / PLAYBACK_RATE;
    this.paintStatic();
    if (this.active) {
      if (!this.appeared) {
        this.appeared = true;
        if (this.options.entrance && isWorkingState(this.base))
          this.playOnce("appear");
      }
      wakeBot(this);
      this.scheduleAmbient();
    }
  }
  private clearAmbient(): void {
    if (this.ambient !== null) {
      clearTimeout(this.ambient);
      this.ambient = null;
    }
  }
  private scheduleAmbient(): void {
    this.clearAmbient();
    if (
      !this.active ||
      this.base !== "idle" ||
      this.cue ||
      this.options.intensity === "quiet"
    )
      return;
    if (!Number.isFinite(this.nextMood))
      this.nextMood = this.now() + 25000 + (this.options.seed % 20) * 1000;
    this.ambient = setTimeout(
      () => {
        this.ambient = null;
        if (!this.active || this.base !== "idle") return;
        if (this.options.idleMoods && this.now() >= this.nextMood) {
          this.nextMood = this.now() + 30000 + (this.options.seed % 15) * 1000;
          this.playOnce(this.options.seed % 2 ? "curious" : "content");
        } else this.blinkOnce();
        this.scheduleAmbient();
      },
      7000 + (this.options.seed % 5) * 1000,
    );
  }

  frame(now: number): boolean {
    if (!this.active) return false;
    if (this.options.intensity === "quiet" && now - this.paintAt < 32)
      return true;
    const dt = this.last ? Math.min((now - this.last) / 1000, 0.1) * PLAYBACK_RATE : 0;
    this.last = now;
    this.paintAt = now;
    if (this.candidate && now >= this.candidate.at)
      this.applyState(this.candidate.state, now);
    if (
      this.cue &&
      (now - this.cue.at) * PLAYBACK_RATE >= BOT_DEFINITIONS[this.cue.state].duration * 1000
    )
      this.cue = null;
    if (isWorkingState(this.displayed) && this.displayed === this.base)
      this.seenWorkKey = this.options.completionKey;
    const expression = this.cue?.state ?? this.displayed;
    const time = ((now - (this.cue?.at ?? this.stateAt)) / 1000) * PLAYBACK_RATE;
    const t = poseFor(expression, time, expression === "idle");
    if (expression === "blink") {
      const lid = t.lh / 18;
      Object.assign(
        t,
        poseFor(
          this.displayed,
          ((now - this.stateAt) / 1000) * PLAYBACK_RATE,
          this.displayed === "idle",
        ),
      );
      t.lh = Math.max(2.2, t.lh * lid);
      t.rh = Math.max(2.2, t.rh * lid);
    }
    if (expression === "idle") {
      Object.assign(t, REST_POSE);
      t.gx = this.pointer.x;
      t.gy = this.pointer.y;
    }
    const intensity =
      this.options.intensity === "quiet"
        ? 0.55
        : this.options.size < 32
          ? 0.4
          : 1;
    for (const k of ["x", "y", "r", "lean", "shoulder"] as const)
      t[k] *= intensity;
    t.sx = 1 + (t.sx - 1) * Math.max(0.6, intensity);
    t.sy = 1 + (t.sy - 1) * Math.max(0.6, intensity);
    if (this.options.size < 32) {
      t.lw = Math.max(t.lw, 160 / this.options.size);
      t.rw = Math.max(t.rw, 160 / this.options.size);
    }
    for (const k of POSE_KEYS) {
      let target = t[k];
      if (k === "yaw")
        target =
          this.pose[k] + ((((target - this.pose[k]) % 360) + 540) % 360) - 180;
      const freq =
        (k === "lh" || k === "rh") && expression === "blink"
          ? 65
          : [
                "gx",
                "gy",
                "lh",
                "rh",
                "lw",
                "rw",
                "la",
                "ra",
                "ls",
                "rs",
              ].includes(k)
            ? 30
            : 20;
      const damping = ["sx", "sy", "y"].includes(k) ? 0.83 : 0.96;
      for (let left = dt; left > 0;) {
        const h = Math.min(left, 1 / 120);
        this.velocity[k] +=
          (freq * freq * (target - this.pose[k]) -
            2 * damping * freq * this.velocity[k]) *
          h;
        this.pose[k] += this.velocity[k] * h;
        left -= h;
      }
    }
    const visualState = expression === "blink" ? this.displayed : expression;
    const definition = BOT_DEFINITIONS[visualState];
    const targetRibbon = { ...RIBBON_STYLES[definition.ribbon] };
    if (definition.duration)
      targetRibbon.strength *= Math.sin(
        Math.PI * clamp(time / definition.duration),
      );
    if (expression === "settling") {
      const fade = 1 - smooth(time / 3.4);
      targetRibbon.strength *= fade;
      targetRibbon.speed *= fade;
    }
    if (!this.options.ribbons || this.options.size < 48)
      targetRibbon.strength = 0;
    for (const k of RIBBON_KEYS)
      this.ribbon[k] +=
        (targetRibbon[k] - this.ribbon[k]) * (1 - Math.exp(-dt * 12));
    this.phase += dt * this.ribbon.speed;
    this.painter.paint(
      this.pose,
      visualState,
      this.ribbon,
      this.phase,
      time,
      this.options.size,
    );
    this.svg.dataset.botState = this.base;
    const looping = definition.period > 0 && expression !== "idle";
    const continuing =
      looping ||
      Boolean(this.cue || this.candidate) ||
      now < this.settleUntil ||
      (expression === "settling" && time < 4.2) ||
      (definition.duration > 0 && time < definition.duration + 0.8);
    if (!continuing) this.scheduleAmbient();
    return continuing;
  }
  private paintStatic(): void {
    const expression = this.base;
    this.pose =
      expression === "idle" ? { ...REST_POSE } : poseFor(expression, 0, true);
    this.velocity = Object.fromEntries(POSE_KEYS.map((k) => [k, 0])) as BotPose;
    this.ribbon = { ...RIBBON_STYLES.none };
    this.painter.paint(
      this.pose,
      expression,
      this.ribbon,
      this.phase,
      0,
      this.options.size,
    );
    this.svg.dataset.botState = this.base;
  }
  snapshot(): BotSnapshot {
    return {
      state: this.base,
      displayed: this.displayed,
      expression: this.cue?.state ?? this.displayed,
      reduced: this.reduced,
      visible: this.visible,
      timerPending: this.ambient !== null,
      pose: { ...this.pose },
    };
  }
  destroy(): void {
    if (this.destroyed) return;
    this.destroyed = true;
    this.clearAmbient();
    this.observer?.disconnect();
    this.unregister();
    this.painter.destroy();
  }
}
