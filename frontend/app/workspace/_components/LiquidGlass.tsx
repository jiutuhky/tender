"use client";

import { useId, useSyncExternalStore, type CSSProperties, type ReactNode } from "react";
import { LIQUID_GLASS_MAPS, type LiquidGlassMode } from "./canvas/liquidGlassMaps";

/**
 * 液态玻璃面（Apple Liquid Glass 的 web 复刻）。
 *
 * 渲染管线**逐层照搬** liquid-glass-react v1.1.1（MIT）的 src/index.tsx，只改了一件事：
 * 它是一颗按 children 收缩、钉在 top/left:50% 上、跟着鼠标弹的"药丸"，而我们要的是
 * **铺满一个定位盒的面板**。所以这里没有 glassSize 状态、没有 mousemove 订阅、没有
 * `transition: all`——尺寸全部交给 CSS（inset:0 + 百分比滤镜区），弹性形变一律不要
 * （画布左上那扇窗是固定面板，不是跟手的按钮；而且它的鼠标处理器每次移动都 setState，
 * 会把整条 transcript 拖进重渲）。
 *
 * 之所以不直接用 npm 包：它靠一串 Tailwind 类名（bg-black / opacity-0 / mix-blend-overlay
 * / pointer-events-none）承担一半样式，本项目无 Tailwind；它按 children 量尺寸、只在挂载与
 * window resize 时量一次，与 GSAP 逐帧改壳尺寸的转场天然打架；渲染期读 navigator 又不能
 * SSR。把它改造成面板需要十几条 `!important` 覆写，不如把这 80 行搬进来。
 *
 * 光学结构（自下而上）：
 *   1. `.lg-warp`  —— 承担全部"玻璃感"的一层，一条 `backdrop-filter: url(#svg)`：SVG 滤镜里
 *      先 feGaussianBlur + saturate（对应上游的 backdrop blur/saturate），再按 R/G/B 三个不同
 *      scale 各 feDisplacementMap 一次、screen 合并——这就是折射与边缘色散；由贴图亮度做的
 *      EDGE_MASK 把色散只留在边缘、中央保持干净。
 *      **与上游的一处关键差异**：上游是 `backdrop-filter: blur()` + 同元素 CSS `filter: url()`
 *      两条链。实测 Chromium（Playwright 内置版）里 CSS filter 只弯元素自身的内容、不弯 backdrop
 *      结果；`backdrop-filter: blur() url()` 混排时 url 那一节又被整个丢掉——只有**单独一条
 *      url() 且模糊也写在 SVG 里**时，位移才真的作用于背景。这也是此前直接用 npm 包
 *      "怎么都到不了原版效果"的原因。Firefox / Safari 不支持 backdrop-filter 里的 url()，
 *      按 UA 退成 blur()+saturate() 的纯毛玻璃（与上游一致：它们本来就没有位移）。
 *   2. children —— 内容层。
 *   3. 边缘光（`.lg-rim`）：1.5px 的环（mask 挖空），沿 135° 走一道两端亮、中段暗的白色渐变——
 *      模拟一块有厚度的玻璃在顶光下的棱：迎光的左上沿与对角的右下沿各亮一段（右下是内部
 *      反射），两侧腰线只剩一丝。再压一圈 .5px 的内侧白线把棱勾实。上游是两条环
 *      （screen + overlay 混合），这里**必须**用普通合成：任何一个 mix-blend-mode 都会让最近
 *      的祖先 stacking context（.cv-msgwin，它靠 z-index 浮在画布上）被隔离成一个 group，
 *      而 backdrop-filter 只能看见到最近 backdrop root 为止的画面——于是玻璃只见到自己，
 *      整面塌成灰板。上游 demo 没这个问题只是因为它的祖先 stacking context 是 root。
 *
 * 只在 Chromium 上是完整效果（Safari 无位移、Firefox 无位移），与上游一致。
 *
 * Frost 2 规范光学栈对齐（合规治理 2026-08）：④ rim 与内环直接取 --glass-rim /
 * --glass-rim-inner token；②/① 由 .lg-illum 层承担（--glass-illum 顶光 + --glass-tint-lens
 * 基底）；⑤ shadow 由外部 CSS 按 --glass-shadow-* 配置。指针 specular 只属交互玻璃，
 * 此固定面板依规范不做。
 */
export interface LiquidGlassProps {
  /** 位移强度（feDisplacementMap 的 scale，px）。上游 demo 卡片用 100。 */
  displacementScale?: number;
  /** 磨砂系数，不是像素：实际模糊 = 4 + blurAmount * 32 px。上游 demo 卡片用 0.5（=20px）。 */
  blurAmount?: number;
  /** backdrop saturate 百分比。 */
  saturation?: number;
  /** 边缘色散强度。0 关掉。 */
  aberrationIntensity?: number;
  /** 圆角 px。 */
  cornerRadius?: number;
  /** 位移贴图。 */
  mode?: LiquidGlassMode;
  className?: string;
  style?: CSSProperties;
  /** 玻璃层（.lg-glass）的 box-shadow。不传则不写内联，交给外部 CSS 按状态定
   *  （内联会压过样式表，MessageWindow 的运行中蓝环就是靠 CSS 切换的）。 */
  shadow?: string;
  children?: ReactNode;
}

/** 边缘光的环：mask 只留外沿 1.5px；内侧再勾一圈 .5px 白线把棱勾实。 */
const RIM_MASK: CSSProperties = {
  padding: "1.5px",
  WebkitMask: "linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0)",
  WebkitMaskComposite: "xor",
  maskComposite: "exclude",
  boxShadow: "var(--glass-rim-inner)",
};

/** 顶光下厚玻璃的棱：左上迎光段最亮，右下是内反射的第二亮段，两侧腰线只剩一丝。
 *  直接消费 frost-materials.css 的 --glass-rim（135°，停靠点 0/12/38/56/80/100），
 *  与设计系统单源同步，暗色外观下 token 自动换挡。 */
const RIM_LIGHT = "var(--glass-rim)";

const subscribeNoop = () => () => {};
const getFalse = () => false;
const getIsBlink = () => /(Chrome|Chromium|CriOS|Edg)\//.test(navigator.userAgent);

export function LiquidGlass({
  displacementScale = 70,
  blurAmount = 0.0625,
  saturation = 140,
  aberrationIntensity = 2,
  cornerRadius = 18,
  mode = "standard",
  className = "",
  style,
  shadow,
  children,
}: LiquidGlassProps) {
  const filterId = useId();
  // 只有 Chromium 系支持 backdrop-filter 里的 url()；其它引擎给 url() 会整层不画（连模糊都没）。
  // 服务端快照恒为 false（没有 navigator），水合后按真实 UA 换一次：首帧纯毛玻璃，随即弯过去。
  const canWarp = useSyncExternalStore(subscribeNoop, getIsBlink, getFalse);

  const radius = `${cornerRadius}px`;
  const blurPx = 4 + blurAmount * 32;
  // 纯毛玻璃版：非 Chromium 的兜底，也是转场期（data-tweening）临时替身——CSS 侧按
  // `backdrop-filter: var(--lg-plain)` 取用，位移滤镜每帧在新尺寸上重跑太贵。
  const plain = `blur(${blurPx}px) saturate(${saturation}%)`;

  return (
    <div
      className={`lg-root ${className}`}
      style={{ position: "absolute", inset: 0, "--lg-plain": plain, ...style } as CSSProperties}
    >
      <svg aria-hidden="true" style={{ position: "absolute", width: 0, height: 0 }}>
        <defs>
          <filter
            id={filterId}
            x="-35%"
            y="-35%"
            width="170%"
            height="170%"
            colorInterpolationFilters="sRGB"
          >
            {/* 上游的 backdrop-filter: blur() saturate()，搬进滤镜链最前面（理由见文件头） */}
            <feGaussianBlur in="SourceGraphic" stdDeviation={blurPx} result="FROSTED" />
            <feColorMatrix in="FROSTED" type="saturate" values={`${saturation / 100}`} result="SRC" />
            <feImage
              x="0"
              y="0"
              width="100%"
              height="100%"
              result="DISPLACEMENT_MAP"
              href={LIQUID_GLASS_MAPS[mode]}
              preserveAspectRatio="xMidYMid slice"
            />
            {/* 贴图亮度 → 边缘强度：中央（≈128 灰）落在 0 档，边缘落在 1 档，中间一档由色散强度决定 */}
            <feColorMatrix
              in="DISPLACEMENT_MAP"
              type="matrix"
              values="0.3 0.3 0.3 0 0  0.3 0.3 0.3 0 0  0.3 0.3 0.3 0 0  0 0 0 1 0"
              result="EDGE_INTENSITY"
            />
            <feComponentTransfer in="EDGE_INTENSITY" result="EDGE_MASK">
              <feFuncA type="discrete" tableValues={`0 ${aberrationIntensity * 0.05} 1`} />
            </feComponentTransfer>
            <feOffset in="SRC" dx="0" dy="0" result="CENTER_ORIGINAL" />
            {/* 三色各位移一次，scale 逐通道递减 → 边缘色散 */}
            <feDisplacementMap
              in="SRC"
              in2="DISPLACEMENT_MAP"
              scale={-displacementScale}
              xChannelSelector="R"
              yChannelSelector="B"
              result="RED_DISPLACED"
            />
            <feColorMatrix
              in="RED_DISPLACED"
              type="matrix"
              values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0"
              result="RED_CHANNEL"
            />
            <feDisplacementMap
              in="SRC"
              in2="DISPLACEMENT_MAP"
              scale={-displacementScale * (1 + aberrationIntensity * 0.05)}
              xChannelSelector="R"
              yChannelSelector="B"
              result="GREEN_DISPLACED"
            />
            <feColorMatrix
              in="GREEN_DISPLACED"
              type="matrix"
              values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0"
              result="GREEN_CHANNEL"
            />
            <feDisplacementMap
              in="SRC"
              in2="DISPLACEMENT_MAP"
              scale={-displacementScale * (1 + aberrationIntensity * 0.1)}
              xChannelSelector="R"
              yChannelSelector="B"
              result="BLUE_DISPLACED"
            />
            <feColorMatrix
              in="BLUE_DISPLACED"
              type="matrix"
              values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0"
              result="BLUE_CHANNEL"
            />
            <feBlend in="GREEN_CHANNEL" in2="BLUE_CHANNEL" mode="screen" result="GB_COMBINED" />
            <feBlend in="RED_CHANNEL" in2="GB_COMBINED" mode="screen" result="RGB_COMBINED" />
            <feGaussianBlur
              in="RGB_COMBINED"
              stdDeviation={Math.max(0.1, 0.5 - aberrationIntensity * 0.1)}
              result="ABERRATED_BLURRED"
            />
            {/* 边缘取色散版，中央取原图 */}
            <feComposite in="ABERRATED_BLURRED" in2="EDGE_MASK" operator="in" result="EDGE_ABERRATION" />
            <feComponentTransfer in="EDGE_MASK" result="INVERTED_MASK">
              <feFuncA type="table" tableValues="1 0" />
            </feComponentTransfer>
            <feComposite in="CENTER_ORIGINAL" in2="INVERTED_MASK" operator="in" result="CENTER_CLEAN" />
            <feComposite in="EDGE_ABERRATION" in2="CENTER_CLEAN" operator="over" />
          </filter>
          {/* 空滤镜，给 .lg-warp 的 CSS `filter` 引用。Chromium 只在元素有 `filter: url()` 时
              才为它建 SVG 资源客户端；单靠 backdrop-filter: url() 引用，feImage 的贴图永远
              不加载、整层画成透明。挂上这个 no-op 引用后 backdrop 那条 url() 才真正生效。
              （实测：换成 0×0 的旁支元素引用无效——它是按元素算的，不是按资源。） */}
          <filter id={`${filterId}-noop`}>
            <feOffset dx="0" dy="0" />
          </filter>
        </defs>
      </svg>

      <div
        className="lg-glass"
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: radius,
          overflow: "hidden",
          boxShadow: shadow,
        }}
      >
        <span
          className="lg-warp"
          aria-hidden="true"
          style={{
            position: "absolute",
            inset: 0,
            // 圆角必须写在 backdrop-filter 元素**自己**身上：GPU 合成路径下 backdrop 层按
            // 自身圆角裁，父层 overflow:hidden 的圆角裁不到它（软件光栅能裁，所以无头
            // 截图看不出来）——否则四角在真机上就是方的。
            borderRadius: radius,
            filter: canWarp ? `url(#${filterId}-noop)` : undefined,
            backdropFilter: canWarp ? `url(#${filterId})` : plain,
            WebkitBackdropFilter: canWarp ? `url(#${filterId})` : plain,
          }}
        />
        {/* 规范光学栈的 ② illumination（固定顶光）+ ① tint（凝玻璃基底 .06 白）。
            指针 specular 依规范只属交互玻璃（--interactive），固定面板不加。 */}
        <span
          className="lg-illum"
          aria-hidden="true"
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: radius,
            pointerEvents: "none",
            backgroundImage: "var(--glass-illum)",
            backgroundColor: "var(--glass-tint-lens)",
          }}
        />
        <div
          className="lg-content"
          // 带上圆角供内容层 `border-radius: inherit`（面板 overflow:hidden 要按同一弧裁）
          style={{ position: "relative", zIndex: 1, height: "100%", borderRadius: radius }}
        >
          {children}
        </div>
      </div>

      {/* 边缘光（普通合成，理由见文件头） */}
      <span
        className="lg-rim"
        aria-hidden="true"
        style={{
          ...RIM_MASK,
          position: "absolute",
          inset: 0,
          borderRadius: radius,
          pointerEvents: "none",
          background: RIM_LIGHT,
        }}
      />
    </div>
  );
}
