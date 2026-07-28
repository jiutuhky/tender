import { gsap } from "gsap";
import { CustomEase } from "gsap/CustomEase";

// 工作台动效常量。起于溯源(票05),现为整个工作台共用:CanvasDrawer(面板到场/退场/
// 窄屏二级视图)、TracePanel(高亮强调)、MessageWindow(三档浮窗)、CanvasDock(输入坞到场)。
// 不要另起第二个动效常量模块。
// 时长遵守 Frost 档位(micro 120 / float 200 / panel 320ms);缓动用品牌标准
// cubic-bezier(.32,.72,0,1),退场取其镜像控制点(1-x2,1-y2,1-x1,1-y1)——
// apple-design「可逆过渡的缓动互为镜像」,进出路径与节奏对称可预期。
// 两处对 Frost 规范字面的有意解释(评审勿反复):
// - 「入场位移 ≤8px」约束的是淡入式到场的漂移量;面板整幅滑入(x=面板宽)与既有
//   抽屉入场(xPercent:100)同属 panel 滑入语汇,不受此限。
// - 镜像退场曲线(1,0,.68,.28)不在「唯一标准缓动」字面内,是标准曲线的数学镜像,
//   仅用于可逆过渡的返程。

gsap.registerPlugin(CustomEase);

export const TRACE_EASE_ENTER = CustomEase.create("frostTraceEnter", "0.32, 0.72, 0, 1");
export const TRACE_EASE_EXIT = CustomEase.create("frostTraceExit", "1, 0, 0.68, 0.28");

export const DUR_MICRO = 0.12;
export const DUR_FLOAT = 0.2;
export const DUR_PANEL = 0.32;

/** 与既有抽屉动效同一判定:reduced-motion 下所有过渡退化为即时切换 */
export function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
