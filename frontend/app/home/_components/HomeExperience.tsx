"use client";

import { useRouter } from "next/navigation";
import { useRef } from "react";
import { ProjectCollection } from "@/components/projects/ProjectCollection";
import { Composer } from "@/app/workspace/_components/Composer";
import { useWorkspaceStore } from "@/lib/store/workspace";
import { FileIcon, CheckIcon, TableIcon } from "@/components/ui/icons";

const SUGGESTIONS = ["标出所有实质性条款和废标风险。", "梳理需要准备的资质、业绩和证明材料。"];

export function HomeExperience() {
  const router = useRouter();
  const rootRef = useRef<HTMLDivElement>(null);
  const setDraft = useWorkspaceStore((s) => s.setComposerDraft);
  return <div className="home-entry" ref={rootRef}>
    <div className="home-entry-col">
      <header className="home-hero"><span className="home-eyebrow">从招标文件开始</span><h1>理清每份要求，写好每次应答。</h1><p>上传文件，提取项目概要、商务条款、技术要求与评分办法。<br />让每一条应答，都能回到原文核验。</p></header>
      <Composer entry onStart={() => router.push("/workspace")} />
      <div className="home-suggestions"><span>可以这样补充</span>{SUGGESTIONS.map((text) => <button type="button" key={text} onClick={() => { setDraft(text); rootRef.current?.querySelector("textarea")?.focus(); }}>{text}</button>)}</div>
      <div className="home-process" aria-label="项目工作流程"><span><FileIcon width={16} height={16} />添加招标文件</span><i aria-hidden="true" /><span><TableIcon width={16} height={16} />生成应答矩阵</span><i aria-hidden="true" /><span><CheckIcon width={16} height={16} />对照原文核验</span></div>
      <ProjectCollection recent />
    </div>
  </div>;
}
