"use client";

import { useEffect } from "react";
import { useWorkspaceStore } from "@/lib/store/workspace";

// 从 projects 页带 ?project= 进入工作台时的恢复引导:只恢复矩阵结果,不回放 timeline。
// 挂在 Server Component 页面下、由 searchParams 传参,避免 useSearchParams 的 Suspense 要求。

export function ResumeBoot({ pid, name }: { pid: string; name?: string }) {
  useEffect(() => {
    if (pid) void useWorkspaceStore.getState().resumeProject(pid, name);
  }, [pid, name]);
  return null;
}
