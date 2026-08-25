import Link from "next/link";
import { ArrowRightIcon, BellIcon, SearchIcon } from "@/components/ui/icons";
import { AppearanceMenu } from "@/components/shell/AppearanceMenu";
import { SidebarFrame } from "./_components/SidebarFrame";
import { HAGENT_BASE, authHeaders } from "@/lib/server/upstream";
import type { ProjectInfo } from "@/lib/hagent/api";
import "./styles.css";

// 在投项目列表:服务端直连 hagent GET /projects(key 不出服务端)。
// 后端不可达/列表为空时给出引导空态;行点击带 project id 进工作台恢复矩阵结果。

export const dynamic = "force-dynamic";

/** 项目状态 → 状态胶囊(沿用既有 s-* 语义:蓝=进行中/评审中,灰=草稿) */
function statusPill(status: string): { key: string; label: string } {
  switch (status) {
    case "parsed":
      return { key: "s-review", label: "解析完成" };
    case "active":
      return { key: "s-writing", label: "进行中" };
    default:
      return { key: "s-draft", label: status || "草稿" };
  }
}

/** epoch 秒 → 「MM-DD HH:mm」 */
function fmtTime(epochSec: number): string {
  const d = new Date(epochSec * 1000);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

async function fetchProjects(): Promise<{ projects: ProjectInfo[]; error: boolean }> {
  try {
    const r = await fetch(`${HAGENT_BASE}/projects`, {
      headers: authHeaders(),
      cache: "no-store",
    });
    if (!r.ok) return { projects: [], error: true };
    return { projects: (await r.json()) as ProjectInfo[], error: false };
  } catch {
    return { projects: [], error: true };
  }
}

export default async function ProjectsPage() {
  const { projects, error } = await fetchProjects();

  return (
    <SidebarFrame
      topbar={
        <>
          <div className="breadcrumb">
            <span>工作台</span>
            <span className="breadcrumb-sep">/</span>
            <span className="crumb-current">在投项目</span>
          </div>

          <div className="topbar-actions">
            <button className="icon-btn" title="搜索 ⌘K" type="button">
              <SearchIcon />
            </button>
            <button className="icon-btn" title="通知" type="button">
              <BellIcon />
            </button>
            <AppearanceMenu />
            <div className="avatar">LH</div>
          </div>
        </>
      }
    >
      <header className="page-header">
        <div className="eyebrow">Bids · 2026</div>
        <h1>
          在投项目 <em>—— {projects.length} 项</em>
        </h1>
        <p className="deck">从首页上传招标文件创建项目，解析完成后可随时回到工作台查看应答矩阵。</p>
      </header>

      {projects.length > 0 ? (
        <>
          <div className="list-head is-real">
            <span>项目</span>
            <span>创建时间</span>
            <span>状态</span>
          </div>

          <div className="project-list">
            {projects.map((p) => {
              const pill = statusPill(p.status);
              const docName =
                typeof p.metadata?.doc_name === "string" ? p.metadata.doc_name : null;
              return (
                <Link
                  key={p.id}
                  className="project-row is-real"
                  href={`/workspace?project=${encodeURIComponent(p.id)}&name=${encodeURIComponent(p.name)}`}
                >
                  <span className={`pr-status-rail ${pill.key}`} />

                  <div className="pr-main">
                    <div className="pr-title-row">
                      <div className="pr-title">{p.name}</div>
                    </div>
                    <div className="pr-meta">
                      <span className="buyer">{docName ?? `项目 ${p.id.slice(-6)}`}</span>
                    </div>
                  </div>

                  <div className="pr-deadline-cell">
                    <div className="pr-deadline-date">{fmtTime(p.created_at)}</div>
                  </div>

                  <div className="pr-scoring-cell">
                    <span className={`pr-status ${pill.key}`}>
                      <span className="sb-dot" />
                      {pill.label}
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        </>
      ) : (
        <div className="project-list">
          <div className="projects-empty">
            <b>暂无在投项目</b>
            <span>
              {error
                ? "解析服务暂不可达，请确认 hagent 已在 8000 端口启动后刷新。"
                : "回到首页上传一份招标文件，即可创建项目并开始解析。"}
            </span>
            <Link href="/home" className="projects-empty-link">
              去首页上传招标文件
              <ArrowRightIcon />
            </Link>
          </div>
        </div>
      )}
    </SidebarFrame>
  );
}
