import { clamp, eyePath, type BotPose, type Point } from "./pose";
import { turnFrame } from "./geometry";
import { BOT_DEFINITIONS, type BotState, type RibbonKind } from "./states";

const NS = "http://www.w3.org/2000/svg";
function el<K extends keyof SVGElementTagNameMap>(
  tag: K,
  attrs: Record<string, string | number> = {},
): SVGElementTagNameMap[K] {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  return node;
}
export interface RibbonPose {
  strength: number;
  speed: number;
  tilt: number;
  length: number;
  lanes: number;
}
const style = (
  strength = 0,
  speed = 1,
  tilt = 0,
  length = 2.7,
  lanes = 2,
): RibbonPose => ({ strength, speed, tilt, length, lanes });
export const RIBBON_STYLES: Record<RibbonKind, RibbonPose> = {
  none: style(),
  orbit: style(0.7, 0.7, -15),
  drive: style(0.8, 1.9, -12, 2.8),
  weave: style(0.82, 1.3, 24, 2.5),
  cross: style(0.88, 1.05, 32, 3, 3),
  join: style(0.72, 1.15, -22, 2.5),
  inward: style(0.9, -1.15, 20, 3.5),
  outward: style(0.9, 1.5, -24, 3.5),
  rewind: style(0.65, -1.4, -14),
  settle: style(0.75, 0.9, 18, 3.1),
  arc: style(0.8, 1.3, -20, 2.4, 1),
  celebrate: style(1, 2.5, 30, 4.1, 3),
};
export const RIBBON_KEYS = Object.keys(style()) as (keyof RibbonPose)[];
let serial = 0;

/** 只管理自己添加的 SVG 节点，不接管 React 的静态占位节点。 */
export class BotPainter {
  private root = el("g", { "data-bot-dynamic": "" });
  private defs = el("defs");
  private group = el("g");
  private body = el("path", { fill: "var(--bot-ink)" });
  private side = el("path", {
    fill: "color-mix(in srgb, var(--bot-ink) 86%, var(--bot-eye))",
    "data-bot-side": "",
  });
  private outerClip = el("path");
  private faceClip = el("path");
  private face = el("g", { "data-bot-face": "" });
  private eyes = [
    el("path", { fill: "var(--bot-eye)" }),
    el("path", { fill: "var(--bot-eye)" }),
  ] as const;
  private back = el("g", { "data-ribbons": "back" });
  private front = el("g", { "data-ribbons": "front" });
  private paths: { front: SVGPathElement; back: SVGPathElement }[] = [];
  private rest: SVGGElement | null;

  private svg: SVGSVGElement;
  constructor(svg: SVGSVGElement) {
    this.svg = svg;
    const id = `agent-bot-${++serial}`;
    const gradient = el("linearGradient", {
      id,
      x1: "0%",
      y1: "85%",
      x2: "100%",
      y2: "15%",
    });
    ["cyan", "blue", "violet", "pink", "gold"].forEach((color, i) =>
      gradient.append(
        el("stop", {
          offset: `${i * 25}%`,
          "stop-color": `var(--bot-ribbon-${color})`,
        }),
      ),
    );
    const outer = el("clipPath", { id: `${id}-body` });
    outer.append(this.outerClip);
    const faceClip = el("clipPath", { id: `${id}-face` });
    faceClip.append(this.faceClip);
    this.defs.append(gradient, outer, faceClip);
    const details = el("g", { "clip-path": `url(#${id}-body)` });
    const window = el("g", { "clip-path": `url(#${id}-face)` });
    this.face.append(...this.eyes);
    window.append(this.face);
    details.append(this.side, window);
    this.group.append(this.body, details);
    for (let i = 0; i < 3; i++) {
      const back = el("path", { fill: `url(#${id})` });
      const front = el("path", { fill: `url(#${id})` });
      this.paths.push({ back, front });
      this.back.append(back);
      this.front.append(front);
    }
    this.root.append(this.defs, this.back, this.group, this.front);
    this.rest = svg.querySelector<SVGGElement>("[data-bot-rest]");
    if (this.rest) this.rest.style.display = "none";
    svg.append(this.root);
  }

  paint(
    p: BotPose,
    state: BotState,
    ribbon: RibbonPose,
    phase: number,
    time: number,
    size: number,
  ): void {
    const frame = turnFrame(p);
    this.group.setAttribute("transform", frame.transform);
    this.body.setAttribute("d", frame.body);
    this.outerClip.setAttribute("d", frame.body);
    this.side.setAttribute("d", frame.side);
    this.side.setAttribute("opacity", String(frame.sideOpacity));
    this.faceClip.setAttribute("d", frame.faceClip);
    this.face.setAttribute("transform", frame.faceTransform);
    this.face.setAttribute("opacity", String(frame.faceOpacity));
    this.eyes[0].setAttribute(
      "d",
      eyePath(40, 46, p.lw, Math.max(2, p.lh), p.ls, p.la),
    );
    this.eyes[1].setAttribute(
      "d",
      eyePath(60, 46, p.rw, Math.max(2, p.rh), p.rs, p.ra),
    );
    this.svg.dataset.botExpression = state;
    const definition = BOT_DEFINITIONS[state];
    const progress = definition.period
      ? (time % definition.period) / definition.period
      : clamp(time / (definition.duration || 3.4));
    const hump = (x: number, a: number, b: number) =>
      x < a || x > b ? 0 : Math.sin((Math.PI * (x - a)) / (b - a));
    const drift =
      (definition.ribbon === "inward"
        ? -6 * hump(progress, 0.05, 0.95)
        : definition.ribbon === "outward"
          ? 7 * hump(progress, 0.1, 0.9)
          : definition.ribbon === "join"
            ? -5 * hump(progress, 0.05, 0.85)
            : 0) +
      (1 - p.sy) * 12;
    this.paths.forEach((path, lane) => {
      const alpha = ribbon.strength * clamp(ribbon.lanes - lane);
      const paths: { front: string[]; back: string[] } = {
        front: [],
        back: [],
      };
      if (alpha > 0.004) {
        const tilt =
          ((ribbon.tilt * (lane === 1 ? -1 : 1) + lane * 9 + p.r * 0.4) *
            Math.PI) /
          180;
        const radius = 51 + lane * 3 + drift,
          ry = 17 + lane * 3;
        const steps = size < 80 ? 30 : 54;
        const points = Array.from({ length: steps + 1 }, (_, i) => {
          const u = i / steps,
            a = phase + lane * 2.3 - (1 - u) * ribbon.length,
            x = radius * Math.cos(a),
            y = ry * Math.sin(a);
          return {
            x: 50 + x * Math.cos(tilt) - y * Math.sin(tilt) + p.x * 0.35,
            y: 58 + x * Math.sin(tilt) + y * Math.cos(tilt) + p.y * 0.35,
            z: Math.sin(a),
            u,
          };
        });
        const edges = points.map((point, i) => {
          const a = points[Math.max(0, i - 1)]!,
            b = points[Math.min(steps, i + 1)]!;
          const dx = b.x - a.x,
            dy = b.y - a.y,
            len = Math.hypot(dx, dy) || 1;
          const width =
            0.08 +
            2.4 *
              Math.pow(Math.sin(Math.PI * point.u), 0.7) *
              (0.4 + 0.6 * point.u);
          return {
            left: [
              point.x - (dy / len) * width,
              point.y + (dx / len) * width,
            ] as Point,
            right: [
              point.x + (dy / len) * width,
              point.y - (dx / len) * width,
            ] as Point,
          };
        });
        let start = 0;
        while (start < steps) {
          const front = points[start]!.z + points[start + 1]!.z > 0;
          let end = start + 1;
          while (
            end < steps &&
            points[end]!.z + points[end + 1]!.z > 0 === front
          )
            end++;
          const slice = edges.slice(start, end + 1);
          const outline = [
            ...slice.map((p) => p.left),
            ...slice.map((p) => p.right).reverse(),
          ];
          paths[front ? "front" : "back"].push(
            outline.map((p, i) => `${i ? "L" : "M"}${p[0]} ${p[1]}`).join("") +
              "Z",
          );
          start = end;
        }
      }
      path.front.setAttribute("d", paths.front.join(""));
      path.back.setAttribute("d", paths.back.join(""));
      path.front.setAttribute("opacity", String(alpha * 0.95));
      path.back.setAttribute("opacity", String(alpha * 0.62));
    });
  }

  destroy(): void {
    this.root.remove();
    if (this.rest) this.rest.style.removeProperty("display");
  }
}
