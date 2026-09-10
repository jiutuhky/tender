"use client";

import { useCallback, useLayoutEffect, useRef } from "react";

/** 事件保持最新数据，函数身份独立于相机和选区刷新。 */
export function useStableEvent<Args extends unknown[], Result>(
  handler: (...args: Args) => Result,
) {
  const latest = useRef(handler);
  useLayoutEffect(() => {
    latest.current = handler;
  });
  return useCallback((...args: Args) => latest.current(...args), []);
}
