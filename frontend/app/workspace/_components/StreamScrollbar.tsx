"use client";

import { useShortScrollbar } from "@/components/scrollbar/useShortScrollbar";

// 消息浮窗内的细滚动条。刻意做成一个组件而不是挂在常驻的 ShortScrollbars 上：
// useShortScrollbar 只在挂载时 querySelector(".stream-scroll") 一次，依赖数组里没有
// 任何会变的东西，永不重试。浮窗收成胶囊时 .stream-scroll 会被卸载（那是刻意的——
// 省掉流式期每帧几百个 memo'd turn 的 reconcile），所以必须让「重挂载」本身成为
// 重新挂钩的时机。本组件是滚动容器的后序兄弟，React 先提交全部 DOM 再跑 effect，顺序安全。
//
// 滚动条本体 appendChild 到 document.body、position:fixed，不是浮窗的后代，
// 因此浮窗的 overflow:hidden / 圆角 / contain 都裁不到它；位置由 getBoundingClientRect
// 实时算，改档时它自己的 ResizeObserver 会把它带着走。
export function StreamScrollbar() {
  useShortScrollbar(".stream-scroll", {
    shrink: 0.36,
    min: 72,
    gutter: 16,
    right: 8,
  });
  return null;
}
