import { AppShell } from "@/components/shell/AppShell";
import { TopBar } from "@/components/shell/TopBar";
import { CoolingDiagram } from "./_components/CoolingDiagram";
import { PreviewReader } from "./_components/PreviewReader";
import "./styles.css";

export default function PreviewPage() {
  return <AppShell><TopBar crumbs={[{ label: "项目", href: "/projects" }, { label: "文档排版示例", current: true }]} />
    <PreviewReader>
            <article className="preview-paper" id="p42">
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
              <div className="preview-table-scroll" role="region" aria-label="关键指标对比，可横向滚动" tabIndex={0}><table>
                <thead>
                  <tr>
                    <th style={{ width: "26%" }}>指标</th>
                    <th>招标要求</th>
                    <th>张江二期（实测）</th>
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
                    <td style={{ color: "var(--green-text)" }}>优于</td>
                  </tr>
                  <tr>
                    <td>WUE (L/kWh)</td>
                    <td>≤ 0.5</td>
                    <td>0.31</td>
                    <td style={{ fontWeight: 500 }}>≤ 0.32</td>
                    <td style={{ color: "var(--green-text)" }}>优于</td>
                  </tr>
                  <tr>
                    <td>可再生能源占比</td>
                    <td>≥ 30%</td>
                    <td>34.2%</td>
                    <td style={{ fontWeight: 500 }}>≥ 35%</td>
                    <td style={{ color: "var(--green-text)" }}>优于</td>
                  </tr>
                  <tr>
                    <td>余热回收率</td>
                    <td>—</td>
                    <td>62%</td>
                    <td style={{ fontWeight: 500 }}>≥ 60%</td>
                    <td style={{ color: "var(--label-2)" }}>增项</td>
                  </tr>
                  <tr>
                    <td>制冷冗余等级</td>
                    <td>N+1</td>
                    <td>N+1</td>
                    <td style={{ fontWeight: 500 }}>N+1</td>
                    <td style={{ color: "var(--label-2)" }}>符合</td>
                  </tr>
                </tbody>
              </table></div>

              <div className="preview-example-annotation" style={{ top: 380 }}>
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

              <div className="page-num">— 示例第 1 页 —</div>
            </article>

            {/* 第 43 页 */}
            <article className="preview-paper" id="p43">
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

              <div className="preview-example-annotation">
                此节已对照招标文件扣分项 <strong>T-42.3 冗余等级</strong> 与{" "}
                <strong>T-43.1 可靠性承诺</strong>，具体评分影响仍需人工核实。
              </div>

              <p>
                从实际部署角度，本方案将在机房 A 区优先投用，B、C
                区在二期扩容时同步接入，避免一次性停机带来的业务中断。详细施工窗口见第五章「实施与交付」。
              </p>

              <div className="page-num">— 示例第 2 页 —</div>
            </article>
    </PreviewReader>
  </AppShell>;
}
