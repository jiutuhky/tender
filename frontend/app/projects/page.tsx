import Link from "next/link";
import { AppShell } from "@/components/shell/AppShell";
import { TopBar } from "@/components/shell/TopBar";
import { ProjectCollection } from "@/components/projects/ProjectCollection";
import { PlusIcon } from "@/components/ui/icons";
import "./styles.css";

export default function ProjectsPage() {
  return <AppShell>
    <TopBar crumbs={[{ label: "项目", current: true }]} />
    <main className="projects-page" id="main-content" tabIndex={-1}>
      <div className="projects-page-inner">
        <header className="projects-page-head"><div><span className="projects-page-eyebrow">每份要求，都有回应</span><h1>项目</h1><p>从招标文件到应答矩阵，接着上次的进度继续。</p></div><Link className="prose-button is-primary" href="/home"><PlusIcon />新建项目</Link></header>
        <ProjectCollection />
      </div>
    </main>
  </AppShell>;
}
