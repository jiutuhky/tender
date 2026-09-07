import type { Metadata } from "next";
import Script from "next/script";
import { APPEARANCE_BOOT_SCRIPT } from "@/lib/appearance";
import "./globals.css";

/* Lightning CSS 会把 backdrop-filter 与其 -webkit- 前缀按 targets 合并，实测 dev 管线
   只留前缀版；而 Chrome 已移除 -webkit-backdrop-filter（CSS.supports 为 false），
   于是 .frost-glass 整层的磨砂与折射全部失效。这段内联样式不经 CSS 构建管线，
   把标准属性原样补回来——dev 与 prod 都生效。
   只补 backdrop-filter，其余光学层仍由 frost-materials.css 提供，
   材质样式统一在该文件维护。
   降低透明度的兜底带 !important，仍压过这里。 */
const GLASS_BACKDROP_SHIM = `
html .frost-glass{backdrop-filter:blur(var(--_blur)) saturate(var(--glass-sat))}
html[data-warp="1"]:not([data-glass="soft"]) .frost-glass--lens{backdrop-filter:var(--_lens)}
html .frost-scroll-edge::before{backdrop-filter:blur(10px)}
`;

export const metadata: Metadata = {
  title: "Prose · 智能体工作台",
  description: "AI 原生标书编制平台",
};

/* Frost：全站走系统字体栈（macOS 即 SF Pro + 苹方），不加载任何 Web 字体。
   frost-lens.js（同步自设计系统 assets/）注入凝玻璃的 SVG 折射滤镜、
   写 html[data-warp]/[data-glass]/[data-spot] 与指针高光 --mx/--my，每页一次。 */
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        {/* 首帧同步落外观，避免浅色闪一下再切深色（FOUC）。必须先于 body 执行。 */}
        <script dangerouslySetInnerHTML={{ __html: APPEARANCE_BOOT_SCRIPT }} />
        <style dangerouslySetInnerHTML={{ __html: GLASS_BACKDROP_SHIM }} />
      </head>
      <body>
        {children}
        <Script src="/frost-lens.js" strategy="afterInteractive" />
      </body>
    </html>
  );
}
