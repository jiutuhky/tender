import { AppShell } from "@/components/shell/AppShell";
import { TopBar } from "@/components/shell/TopBar";
import { DownloadIcon, ShareIcon } from "@/components/ui/icons";
import { Outline } from "./_components/Outline";
import { CoolingDiagram } from "./_components/CoolingDiagram";
import "./styles.css";

const stroke = {
  fill: "none" as const,
  stroke: "currentColor" as const,
};

export default function PreviewPage() {
  return (
    <AppShell>
      <TopBar
        crumbs={[
          { label: "工作台" },
          { label: "2026 年度项目" },
          { label: "华东数据中心绿色改造工程 · 投标书", current: true },
        ]}
        actions={
          <>
            <button className="btn-ghost" type="button">
              <ShareIcon />
              分享
            </button>
            <button className="btn-primary" type="button">
              <DownloadIcon />
              导出完整标书
            </button>
          </>
        }
      />

      <div className="main">
        <Outline />

        <section className="center">
          <div className="doc-toolbar">
            <div className="zoom-controls">
              <button className="icon-btn" title="缩小" type="button">
                <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6}>
                  <circle cx="11" cy="11" r="7" />
                  <path d="M21 21l-4.35-4.35M8 11h6" />
                </svg>
              </button>
              <span style={{ minWidth: 40, textAlign: "center" }}>100%</span>
              <button className="icon-btn" title="放大" type="button">
                <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6}>
                  <circle cx="11" cy="11" r="7" />
                  <path d="M21 21l-4.35-4.35M11 8v6M8 11h6" />
                </svg>
              </button>
            </div>

            <div
              style={{
                width: 1,
                height: 20,
                background: "var(--border)",
              }}
            />

            <div className="page-indicator">
              页 <strong>42</strong> / 78 &nbsp;·&nbsp; 第 4 章 第 3 页
            </div>

            <div className="doc-toolbar-right">
              <div className="view-toggle">
                <button className="active" type="button">单页</button>
                <button type="button">双页</button>
                <button type="button">连续</button>
              </div>
              <button className="btn-ghost" type="button">
                <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6}>
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  <path d="M18 2l4 4-10 10H8v-4L18 2z" />
                </svg>
                请求修改
              </button>
            </div>
          </div>

          <div className="pages-viewport centered">
            {/* Page 42 */}
            <article className="page" id="p42">
              <div className="page-running-head">
                <span>华东数据中心绿色改造工程 · 投标书</span>
                <span>第四章 绿色技术方案</span>
              </div>

              <h1 className="doc-h1">第四章 · 绿色技术方案</h1>
              <p className="doc-deck">
                本章对应招标文件第三部分「技术要求」第 36–58
                页，围绕 PUE、WUE、可再生能源占比三项核心指标，结合投标方在华东地区已落地的同类项目经验，提出适配本工程地理与气候条件的绿色技术方案。
              </p>

              <h2>4.1 总体技术路线</h2>
              <p>
                本工程采用「冷板式液冷为主、风冷为辅」的混合制冷架构，在 IT
                负载侧实现端到端的高效散热，在基础设施侧通过余热回收与光储一体化将综合
                PUE 控制在 <strong>1.18 以下</strong>（招标要求 ≤ 1.25
                <span className="cite">T-36</span>），WUE 控制在{" "}
                <strong>0.32 L/kWh 以下</strong>（行业平均 1.8），可再生能源占比不低于{" "}
                <strong>35%</strong>（招标要求 ≥ 30%
                <span className="cite">T-38</span>）。
              </p>

              <p>
                整体技术路线已在投标方 2025 年 8
                月完成的「上海张江绿色数据中心二期」项目中得到完整验证
                <span className="cite">R-07</span>，该项目实测年均 PUE
                1.184，与本工程在气候条件、IT 负载密度、网架结构上具备 87%
                以上相似度。
              </p>

              <h3>关键指标对比</h3>
              <table>
                <thead>
                  <tr>
                    <th style={{ width: "26%" }}>指标</th>
                    <th>招标要求</th>
                    <th>张江二期 (实测)</th>
                    <th>本工程承诺</th>
                    <th style={{ width: "14%" }}>响应</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>年均 PUE</td>
                    <td>≤ 1.25</td>
                    <td>1.184</td>
                    <td style={{ fontWeight: 500 }}>≤ 1.18</td>
                    <td style={{ color: "var(--success)" }}>优于</td>
                  </tr>
                  <tr>
                    <td>WUE (L/kWh)</td>
                    <td>≤ 0.5</td>
                    <td>0.31</td>
                    <td style={{ fontWeight: 500 }}>≤ 0.32</td>
                    <td style={{ color: "var(--success)" }}>优于</td>
                  </tr>
                  <tr>
                    <td>可再生能源占比</td>
                    <td>≥ 30%</td>
                    <td>34.2%</td>
                    <td style={{ fontWeight: 500 }}>≥ 35%</td>
                    <td style={{ color: "var(--success)" }}>优于</td>
                  </tr>
                  <tr>
                    <td>余热回收率</td>
                    <td>—</td>
                    <td>62%</td>
                    <td style={{ fontWeight: 500 }}>≥ 60%</td>
                    <td style={{ color: "var(--fg-2)" }}>增项</td>
                  </tr>
                  <tr>
                    <td>制冷冗余等级</td>
                    <td>N+1</td>
                    <td>N+1</td>
                    <td style={{ fontWeight: 500 }}>N+1</td>
                    <td style={{ color: "var(--fg-2)" }}>符合</td>
                  </tr>
                </tbody>
              </table>

              <div className="annotation" style={{ top: 380 }}>
                此处交叉引用招标第 38 页。系统已检测到指标{" "}
                <strong>全部达标或优于要求</strong>。
              </div>

              <h2>4.2 液冷子系统设计</h2>
              <p>
                液冷子系统采用 <strong>冷板式液冷 + 25℃ 高温冷冻水</strong>
                方案，可在华东地区年均 5,840 小时实现自然冷却
                <span className="cite">R-07</span>，相较传统压缩制冷节能约
                38%。系统遵循 N+1
                冗余设计，关键管路采用双路独立环网，任一管段故障不影响整体运行。
              </p>

              <div className="page-num">— 42 —</div>
            </article>

            {/* Page 43 */}
            <article className="page" id="p43">
              <div className="page-running-head">
                <span>华东数据中心绿色改造工程 · 投标书</span>
                <span>第四章 绿色技术方案</span>
              </div>

              <h3>4.2.1 冷板液冷循环</h3>
              <p>
                服务器侧采用微通道铜质冷板，与
                CPU、GPU、内存、电源模块直接接触，带走机柜{" "}
                <strong>约 85%</strong> 的热负荷。冷板出水温度 32–34℃，进入一次侧板式换热器后，由二次侧冷冻水回路将热量输送至室外干冷器或水冷塔。
              </p>

              <div className="figure">
                <div className="figure-body">
                  <CoolingDiagram />
                </div>
                <div className="figure-caption">
                  <strong>图 4.2-1</strong> 冷板液冷循环示意
                  <span>源：投标方 / 上海张江二期工程图（脱敏）</span>
                </div>
              </div>

              <h3>4.2.2 冗余与可靠性</h3>
              <ul>
                <li>冷却塔 N+1 冗余，单塔检修期间总制冷量下降不超过 5%。</li>
                <li>
                  关键泵组 2+1 配置，VFD 变频驱动，年均能耗较定频降低 24%
                  <span className="cite">W-02</span>。
                </li>
                <li>
                  冷却液采用专利单相氟化液，20 年内泄漏概率 &lt; 0.01%（厂家承诺，含合同附件）。
                </li>
              </ul>

              <div className="annotation" style={{ top: 570 }}>
                此节已对照招标文件扣分项 <strong>T-42.3 冗余等级</strong> 与{" "}
                <strong>T-43.1 可靠性承诺</strong>，0 扣分风险。
              </div>

              <p>
                从实际部署角度，本方案将在机房 A 区优先投用，B、C
                区在二期扩容时同步接入，避免一次性停机带来的业务中断。详细施工窗口见第五章「实施与交付」。
              </p>

              <div className="page-num">— 43 —</div>
            </article>
          </div>
        </section>

        <aside className="right-export">
          <div className="section">
            <h4>合规与校对</h4>
            <div className="check-summary">
              <div className="check-row pass">
                <div className="status-icon" />
                <div className="check-body">
                  <div className="check-name">招标技术要求逐条响应</div>
                  <div className="check-name-sub">19 / 19 条 · 全部响应</div>
                </div>
                <span className="count">通过</span>
              </div>
              <div className="check-row pass">
                <div className="status-icon" />
                <div className="check-body">
                  <div className="check-name">历史扣分点规避</div>
                  <div className="check-name-sub">47 条 · 全部规避</div>
                </div>
                <span className="count">通过</span>
              </div>
              <div className="check-row pass">
                <div className="status-icon" />
                <div className="check-body">
                  <div className="check-name">引用资料交叉核验</div>
                  <div className="check-name-sub">23 处 · 全部指向有效来源</div>
                </div>
                <span className="count">通过</span>
              </div>
              <div className="check-row live">
                <div className="status-icon" />
                <div className="check-body">
                  <div className="check-name">格式与排版规范</div>
                  <div className="check-name-sub">
                    GB/T 9704-2012 · 部分章节待生成
                  </div>
                </div>
                <span className="count">运行中</span>
              </div>
              <div className="check-row warn">
                <div className="status-icon" />
                <div className="check-body">
                  <div className="check-name">报价表双盲一致性</div>
                  <div className="check-name-sub">第 6.1 节待撰写后复核</div>
                </div>
                <span className="count">待审</span>
              </div>
            </div>
          </div>

          <div className="section">
            <h4>导出</h4>
            <div className="export-card">
              <div className="format-row">
                <div className="format active">
                  <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6}>
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <path d="M14 2v6h6M9 15h6M9 11h2" />
                  </svg>
                  <div className="format-name">PDF / A</div>
                  <div className="format-size">~ 14.2 MB</div>
                </div>
                <div className="format">
                  <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6}>
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <path d="M14 2v6h6M10 13l2 4 2-4" />
                  </svg>
                  <div className="format-name">Word</div>
                  <div className="format-size">.docx</div>
                </div>
                <div className="format">
                  <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.6}>
                    <rect x="3" y="3" width="7" height="7" />
                    <rect x="14" y="3" width="7" height="7" />
                    <rect x="3" y="14" width="7" height="7" />
                    <rect x="14" y="14" width="7" height="7" />
                  </svg>
                  <div className="format-name">分册 ZIP</div>
                  <div className="format-size">6 册</div>
                </div>
              </div>

              <div className="export-options">
                <div className="option">
                  <span>嵌入水印 · 投标编号</span>
                  <div className="toggle on" />
                </div>
                <div className="option">
                  <span>保留智能体批注</span>
                  <div className="toggle" />
                </div>
                <div className="option">
                  <span>附加合规性证明</span>
                  <div className="toggle on" />
                </div>
                <div className="option">
                  <span>按章节拆分 PDF</span>
                  <div className="toggle" />
                </div>
              </div>

              <button className="export-btn" type="button">
                <svg viewBox="0 0 24 24" {...stroke} strokeWidth={1.8}>
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
                </svg>
                生成 · PDF / A (78 页)
              </button>
            </div>
          </div>

          <div className="section">
            <h4>修订记录</h4>
            <div className="timeline">
              <div className="timeline-item active">
                <div className="time">10:14</div>
                <div className="line" />
                <div className="label">
                  <strong>智能体</strong> 正在撰写 § 4.2 液冷子系统
                </div>
              </div>
              <div className="timeline-item done">
                <div className="time">09:57</div>
                <div className="line" />
                <div className="label">
                  <strong>李慧</strong> 采纳图 4.2-1 原理示意图
                </div>
              </div>
              <div className="timeline-item done">
                <div className="time">09:42</div>
                <div className="line" />
                <div className="label">
                  <strong>智能体</strong> 完成 § 4.1 总体技术路线初稿
                </div>
              </div>
              <div className="timeline-item done">
                <div className="time">08:30</div>
                <div className="line" />
                <div className="label">
                  <strong>智能体</strong> 从知识库匹配 4 个历史项目
                </div>
              </div>
              <div className="timeline-item done">
                <div className="time">昨 22:10</div>
                <div className="line" />
                <div className="label">
                  <strong>张工</strong> 上传招标补遗文件
                </div>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </AppShell>
  );
}
