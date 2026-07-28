"use client";

import dynamic from "next/dynamic";

// streamdown + shiki 体积偏大，懒加载，避免进入 workspace 路由的初始 chunk。
// 回复正文本就只在客户端 SSE 到达后出现，ssr:false 无副作用。
export const Response = dynamic(() => import("./response-impl").then((m) => m.ResponseImpl), {
  ssr: false,
});
