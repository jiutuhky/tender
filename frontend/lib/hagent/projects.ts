"use client";

import { useEffect, useState } from "react";
import { listProjects, type ProjectInfo } from "./api";

export function projectHref(project: Pick<ProjectInfo, "id" | "name">): string {
  return `/workspace?${new URLSearchParams({ project: project.id, name: project.name })}`;
}

export function projectStatus(status: string): { label: string; tone: string } {
  switch (status) {
    case "parsed": return { label: "已提取", tone: "review" };
    case "active": return { label: "进行中", tone: "active" };
    case "draft": return { label: "草稿", tone: "neutral" };
    case "archived": return { label: "已归档", tone: "neutral" };
    case "completed": return { label: "已完成", tone: "neutral" };
    default: return { label: "待处理", tone: "neutral" };
  }
}

/** 首页与项目列表共用读端点；失败不覆盖为“没有项目”。 */
export function useProjects() {
  const [projects, setProjects] = useState<ProjectInfo[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let alive = true;
    listProjects().then((data) => {
      if (!alive) return;
      setProjects([...data].sort((a, b) => b.updated_at - a.updated_at));
      setStatus("ready");
    }).catch(() => { if (alive) setStatus("error"); });
    return () => { alive = false; };
  }, [revision]);
  return { projects, status, retry: () => { setStatus("loading"); setRevision((value) => value + 1); } };
}
