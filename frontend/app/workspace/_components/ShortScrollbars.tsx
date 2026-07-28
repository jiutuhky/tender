"use client";

import { useShortScrollbar } from "@/components/scrollbar/useShortScrollbar";

// 注意：消息流（.stream-scroll）的细滚动条**不在这里**注册。它随消息浮窗的胶囊态
// 一起挂载/卸载，而 useShortScrollbar 只在挂载时 querySelector 一次、永不重试；
// 挂在这个常驻组件上会在第一次收胶囊后永久失效。它由浮窗内部的 <StreamScrollbar/>
// 负责，那个组件的挂载/卸载正是重挂钩点。
export function ShortScrollbars() {
  // 画布右侧抽屉内的滚动内容（替代旧 .doc-pane / .canvas-expanded-card）
  useShortScrollbar(".cv-drawer-body", {
    shrink: 0.36,
    min: 92,
    gutter: 14,
    right: 12,
  });
  return null;
}
