import { bodyPath, smooth, type BotPose } from "./pose";

export const REST_BODY_PATH =
  "M30.13 14H69.87Q86 14 86 30.13V69.87Q86 86 69.87 86H30.13Q14 86 14 69.87V30.13Q14 14 30.13 14Z";
export const REST_EYES_PATH =
  "M36 41Q36 37 40 37Q44 37 44 41V51Q44 55 40 55Q36 55 36 51ZM56 41Q56 37 60 37Q64 37 64 41V51Q64 55 60 55Q56 55 56 51Z";
export const BOT_VIEWBOX = "-12 -12 124 124";

/** 侧向保留 90% 宽度；正面缩小的面积由侧面接住，不把整个人物压成薄片。 */
export function turnFrame(v: BotPose) {
  const angle = (v.yaw * Math.PI) / 180;
  const front = Math.cos(angle);
  const direction = Math.sin(angle) >= 0 ? 1 : -1;
  const faceWidth = Math.abs(front);
  const width = 0.9 + 0.1 * faceWidth;
  const edge =
    direction > 0 ? 14 + 72 * (1 - faceWidth) : 86 - 72 * (1 - faceWidth);
  const seam = `M${edge} -20C${edge - 2 * direction} 25 ${edge + 2 * direction} 75 ${edge} 120`;
  const center = 50 + direction * 36 * (1 - faceWidth);
  return {
    width,
    body: bodyPath(v),
    transform: `translate(${v.x} ${v.y}) translate(50 50) rotate(${v.r}) scale(${v.sx * width} ${v.sy}) translate(-50 -50)`,
    side: seam + (direction > 0 ? "H-20V-20Z" : "H120V-20Z"),
    sideOpacity: smooth((1 - faceWidth) / 0.12) * 0.65,
    faceClip: seam + (direction > 0 ? "H120V-20Z" : "H-20V-20Z"),
    faceTransform: `translate(${center + v.gx * faceWidth} ${v.gy}) scale(${faceWidth} 1) translate(-50 0)`,
    faceOpacity: smooth((front - 0.12) / 0.28),
  };
}
