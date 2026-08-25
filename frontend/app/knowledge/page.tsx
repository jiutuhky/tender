import { AppShell } from "@/components/shell/AppShell";
import { TopBar } from "@/components/shell/TopBar";
import {
  ArrowRightIcon,
  ArrowUpIcon,
  DownloadIcon,
  EyeIcon,
  PlusIcon,
  SearchIcon,
  UploadIcon,
} from "@/components/ui/icons";
import { ASSETS, CASES, TEMPLATES } from "@/lib/mock/knowledge";
import { CategoryNav } from "./_components/CategoryNav";
import "./styles.css";

function FileIconBadge({ kind }: { kind: "pdf" | "doc" | "xls" | "zip" }) {
  return <div className={`file-icon ${kind}`}>{kind.toUpperCase()}</div>;
}

export default function KnowledgePage() {
  return (
    <AppShell>
      <TopBar
        crumbs={[{ label: "工作台" }, { label: "知识库", current: true }]}
        actions={
          <>
            <button className="icon-btn" title="搜索" type="button">
              <SearchIcon />
            </button>
            <button className="btn-ghost" type="button">
              <UploadIcon />
              批量上传
            </button>
            <button className="btn-primary" type="button">
              <PlusIcon />
              新建条目
            </button>
          </>
        }
      />

      <div className="page-wrap">
        <CategoryNav />

        <main className="content">
          <header className="page-header">
            <div className="eyebrow">Knowledge Base · 资料总览</div>
            <h1>知识库 — 全部资料</h1>
            <p className="deck">
              智能体在撰写标书时，从这里自动匹配最合适的历史项目、资质材料、技术白皮书与模板。每份资料都会追踪被引用次数，帮助你识别高价值素材与需要更新的内容。
            </p>
          </header>

          <section className="kpi-strip">
            <div className="kpi">
              <div className="label">资料总数</div>
              <div className="value">1,284</div>
              <div className="delta up">
                <ArrowUpIcon />
                +34 近 7 天
              </div>
            </div>
            <div className="kpi">
              <div className="label">本月被智能体引用</div>
              <div className="value">2,847</div>
              <div className="delta up">
                <ArrowUpIcon />
                +18% 环比
              </div>
              <svg
                className="sparkline"
                viewBox="0 0 100 24"
                preserveAspectRatio="none"
              >
                <polyline
                  points="0,18 8,16 16,17 24,14 32,15 40,12 48,13 56,10 64,11 72,8 80,7 88,5 96,4"
                  fill="none"
                  stroke="var(--label-3)"
                  strokeWidth={1.4}
                />
              </svg>
            </div>
            <div className="kpi">
              <div className="label">高频资料</div>
              <div className="value">
                36<span className="unit">份</span>
              </div>
              <div className="delta">被引用 &gt; 10 次</div>
            </div>
            <div className="kpi">
              <div className="label">存储</div>
              <div className="value">
                87.4<span className="unit">GB</span>
              </div>
              <div className="delta">向量索引 12.1 GB</div>
            </div>
          </section>

          <div className="insight-card">
            <div className="eyebrow">
              <span className="dot" />
              智能体建议
            </div>
            <h3>3 份高频资料已过时，建议更新</h3>
            <p>
              <strong>《公司综合业绩表 2024Q4》</strong>在近 14
              份投标中被引用，但本月已有两份业绩更新未纳入。智能体建议将「轨道交通信号系统」（中标金额
              ¥3,400 万）与「智慧园区运维平台」合并入业绩表，避免下轮投标信息滞后。
            </p>
            <a className="insight-cta" href="#">
              查看建议详情
              <ArrowRightIcon />
            </a>
          </div>

          <div className="list-toolbar">
            <h3>已入库历史项目</h3>
            <div className="search">
              <SearchIcon />
              <input placeholder="搜索项目、甲方、关键词……" defaultValue="" />
            </div>
            <div className="filter-chips">
              <span className="chip active">全部</span>
              <span className="chip">中标</span>
              <span className="chip">未中标</span>
              <span className="chip">2025</span>
              <span className="chip">华东</span>
            </div>
          </div>

          <section className="case-grid">
            {CASES.map((c) => (
              <div key={c.id} className="case-card">
                <div className="case-meta">
                  <span>{c.id}</span>
                  <span className={`status${c.status === "lost" ? " lost" : ""}`}>
                    <span className="dot" />
                    {c.status === "won" ? "中标" : "未中标"}
                  </span>
                </div>
                <h4 className="case-title">{c.title}</h4>
                <div className="case-client">{c.client}</div>
                <div className="case-metrics">
                  {c.metrics.map((m) => (
                    <div key={m.label} className="case-metric">
                      <div className="m-label">{m.label}</div>
                      <div
                        className="m-value"
                        style={m.small ? { fontSize: 13 } : undefined}
                      >
                        {m.value}
                        {m.unit && <span className="unit">{m.unit}</span>}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="case-footer">
                  {c.footer.citeCount !== undefined && (
                    <>
                      <span className="cite-count">
                        本月被引 {c.footer.citeCount} 次
                      </span>
                      <span>·</span>
                      <span>配套资料 {c.footer.assets} 份</span>
                    </>
                  )}
                  {c.footer.cites && <span>{c.footer.cites}</span>}
                </div>
              </div>
            ))}
          </section>

          <div className="list-toolbar">
            <h3>最近活跃资料</h3>
            <div className="filter-chips">
              <span className="chip active">全部</span>
              <span className="chip">技术白皮书</span>
              <span className="chip">资质证书</span>
              <span className="chip">业绩表</span>
              <span className="chip">规范标准</span>
            </div>
          </div>

          <div className="table-card">
            <table className="asset-table">
              <thead>
                <tr>
                  <th style={{ width: "40%" }}>名称</th>
                  <th>类别</th>
                  <th>被引用</th>
                  <th>更新</th>
                  <th style={{ width: 80 }} />
                </tr>
              </thead>
              <tbody>
                {ASSETS.map((a) => (
                  <tr key={a.name}>
                    <td>
                      <div className="name-cell">
                        <FileIconBadge kind={a.kind} />
                        <div>
                          <div className="name-main">{a.name}</div>
                          <div className="name-sub">{a.sub}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className={`tag ${a.tag}`}>{a.tagLabel}</span>
                    </td>
                    <td>
                      <div className="citation-text">
                        <span>{a.citations} 次</span>
                        <div className="citation-bar">
                          <div
                            className="fill"
                            style={{ width: `${a.fillPct}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="date">{a.date}</span>
                    </td>
                    <td>
                      <div className="row-actions">
                        <button className="icon-btn" type="button">
                          <EyeIcon />
                        </button>
                        <button className="icon-btn" type="button">
                          <DownloadIcon />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="list-toolbar">
            <h3>标书模板</h3>
            <div className="filter-chips">
              <span className="chip active">全部</span>
              <span className="chip">政府采购</span>
              <span className="chip">央企招标</span>
              <span className="chip">国际项目</span>
            </div>
          </div>

          <section className="tpl-grid">
            {TEMPLATES.map((tpl) => (
              <div key={tpl.name} className="tpl-card">
                <div className="tpl-preview">
                  <div className="tpl-thumb">
                    {tpl.thumb.map((kind, i) =>
                      kind === "divider" ? (
                        <div key={i} className="divider" />
                      ) : (
                        <div key={i} className={`line ${kind}`} />
                      ),
                    )}
                  </div>
                </div>
                <div className="tpl-body">
                  <div className="tpl-name">{tpl.name}</div>
                  <div className="tpl-meta">{tpl.meta}</div>
                </div>
              </div>
            ))}
          </section>
        </main>
      </div>
    </AppShell>
  );
}
