import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Prose · 智能体工作台",
  description: "AI 原生标书编制平台",
};

/* Frost：全站走系统字体栈（macOS 即 SF Pro + 苹方），不加载任何 Web 字体。 */
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
