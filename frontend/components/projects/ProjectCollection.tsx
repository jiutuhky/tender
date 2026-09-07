"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRightIcon, FileIcon, PlusIcon, SearchIcon } from "@/components/ui/icons";
import { projectHref, projectStatus, useProjects } from "@/lib/hagent/projects";
import "./projects.css";

const FILTERS = [{ key: "all", label: "全部项目" }, { key: "parsed", label: "已提取" }, { key: "active", label: "进行中" }] as const;

function dateLabel(epoch: number): string {
  if (!Number.isFinite(epoch)) return "时间未记录";
  return new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric", year: "numeric" }).format(new Date(epoch * 1000));
}

export function ProjectCollection({ recent = false }: { recent?: boolean }) {
  const { projects, status, retry } = useProjects();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<string>("all");
  const term = query.trim().toLocaleLowerCase();
  const filtered = projects.filter((p) => (filter === "all" || p.status === filter) &&
    `${p.name} ${typeof p.metadata?.doc_name === "string" ? p.metadata.doc_name : ""}`.toLocaleLowerCase().includes(term));
  const visible = recent ? filtered.slice(0, 3) : filtered;

  return (
    <section className={`prose-projects${recent ? " is-recent" : ""}`} aria-label={recent ? "最近项目" : "项目列表"}>
      {recent ? (
        <div className="projects-section-head"><h2>继续你的项目</h2><Link href="/projects">全部项目 <ArrowRightIcon width={14} height={14} /></Link></div>
      ) : (
        <div className="projects-controls">
          <div className="projects-filters" role="group" aria-label="按项目状态筛选">
            {FILTERS.map((f) => <button key={f.key} type="button" aria-pressed={filter === f.key} onClick={() => setFilter(f.key)}>{f.label}{status === "ready" && <span>{projects.filter((p) => f.key === "all" || p.status === f.key).length}</span>}</button>)}
          </div>
          <label className="projects-search"><SearchIcon width={16} height={16} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索项目或文件" aria-label="搜索项目或文件" type="search" /></label>
        </div>
      )}
      {status === "loading" ? <div className="projects-loading" role="status"><span className="projects-loading-line" /><span className="projects-loading-line" /><span>正在加载项目…</span></div>
        : status === "error" ? <div className="projects-empty is-error" role="status"><div><h3>暂时无法加载项目</h3><p>项目列表未能加载，请重试。</p></div><button className="prose-button" type="button" onClick={retry}>重新加载</button></div>
        : projects.length === 0 ? <div className="projects-empty"><div className="projects-empty-icon"><FileIcon width={22} height={22} /></div><div><h3>从第一份招标文件开始</h3><p>解析后的项目会保存在这里，随时继续核验。</p></div>{!recent && <Link className="prose-button" href="/home"><PlusIcon />新建项目</Link>}</div>
        : visible.length === 0 ? <div className="projects-empty" role="status"><div><h3>没有匹配的项目</h3><p>试试其他关键词，或清除筛选条件。</p></div><button type="button" className="prose-button" onClick={() => { setQuery(""); setFilter("all"); }}>清除筛选</button></div>
        : <div className="projects-rows">
          {!recent && <div className="projects-columns" aria-hidden="true"><span>项目与招标文件</span><span>状态</span><span>最近更新</span><span /></div>}
          {visible.map((p) => {
            const badge = projectStatus(p.status);
            const fileName = typeof p.metadata?.doc_name === "string" ? p.metadata.doc_name : "招标文件解析项目";
            return <Link key={p.id} href={projectHref(p)} className="projects-entry">
              <span className="projects-entry-main"><span className="projects-file-icon"><FileIcon width={20} height={20} /></span><span><strong>{p.name}</strong><small title={fileName}>{fileName}</small></span></span>
              <span className={`projects-status is-${badge.tone}`}>{badge.label}</span>
              <span className="projects-entry-date">{dateLabel(p.updated_at)}</span>
              <ArrowRightIcon className="projects-entry-arrow" width={16} height={16} />
            </Link>;
          })}
        </div>}
      {!recent && status === "ready" && projects.length > 0 && <p className="projects-count" role="status">{filtered.length} 个项目{term || filter !== "all" ? ` · 共 ${projects.length} 个` : ""}</p>}
    </section>
  );
}
