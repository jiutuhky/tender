"use client";

import { useState } from "react";
import Link from "next/link";
import { ASSETS } from "@/lib/mock/knowledge";
import { ArrowRightIcon, FileIcon, SearchIcon } from "@/components/ui/icons";

const CATEGORIES = ["全部资料", ...new Set(ASSETS.map((a) => a.tagLabel))];

export function KnowledgeLibrary() {
  const [example, setExample] = useState(false);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("全部资料");
  const items = ASSETS.filter((a) => (category === "全部资料" || a.tagLabel === category) && `${a.name} ${a.sub}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
  return <div className="knowledge-container">
    <header className="knowledge-heading"><div><p>可复用的投标资料</p><h1>知识库</h1><span>让资质、业绩与技术资料有序归集，为每次投标做好准备。</span></div>{example && <button className="prose-button" type="button" onClick={() => setExample(false)}>退出示例</button>}</header>
    {!example ? <section className="knowledge-empty">
      <div className="knowledge-empty-icon"><FileIcon width={28} height={28} /></div>
      <h2>企业资料库尚未开放</h2>
      <p>当前可在项目中上传招标文件、解析要求并核验来源。<br />企业资料上传、检索与跨项目引用将在接入后开放。</p>
      <div><Link className="prose-button is-primary" href="/projects">前往项目<ArrowRightIcon width={15} height={15} /></Link><button type="button" className="prose-button" onClick={() => setExample(true)}>浏览资料示例</button></div>
    </section> : <>
      <div className="knowledge-example-note" role="status">示例资料 · 以下内容仅展示资料组织方式，不包含可下载的源文件，也不会被智能体引用。</div>
      <div className="knowledge-toolbar"><label><SearchIcon width={18} height={18} /><input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索名称或关键词" aria-label="搜索示例资料" /></label><span role="status">{items.length} 份示例</span></div>
      <div className="knowledge-categories" role="group" aria-label="资料类别">{CATEGORIES.map((c) => <button type="button" key={c} aria-pressed={category === c} onClick={() => setCategory(c)}>{c}</button>)}</div>
      <div className="knowledge-assets">{items.map((a) => <details key={a.name} className="knowledge-asset"><summary><span className="knowledge-file-kind">{a.kind.toUpperCase()}</span><span className="knowledge-asset-name"><strong>{a.name}</strong><span>{a.tagLabel}</span></span><span className="knowledge-asset-date">{a.date}</span><span className="knowledge-asset-open">详情</span></summary><div className="knowledge-asset-detail"><p>{a.sub}</p><p>示例条目信息，不代表当前企业的资质或真实项目成果。</p></div></details>)}{items.length === 0 && <div className="knowledge-no-results"><h2>没有匹配的资料</h2><p>试试更短的关键词，或查看全部类别。</p><button type="button" className="prose-button" onClick={() => { setQuery(""); setCategory("全部资料"); }}>清除筛选</button></div>}</div>
    </>}
  </div>;
}
