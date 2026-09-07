"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useWorkspaceStore } from "@/lib/store/workspace";
import { isRunning } from "./runStatus";

/** 地址是项目入口；运行中保留当前任务，结束后再处理用户选择的项目。 */
export function ResumeBoot() {
  const params = useSearchParams();
  const pid = params.get("project");
  const name = params.get("name") ?? undefined;
  const demo = params.get("demo");
  const phase = useWorkspaceStore((s) => s.phase);
  useEffect(() => {
    if (demo || isRunning(phase)) return;
    const state = useWorkspaceStore.getState();
    if (pid) { void state.resumeProject(pid, name); return; }
    if (state.projectId) {
      const url = new URL(window.location.href);
      url.searchParams.set("project", state.projectId);
      if (state.projectName) url.searchParams.set("name", state.projectName);
      window.history.replaceState(null, "", url);
    }
  }, [pid, name, phase, demo]);
  return null;
}
