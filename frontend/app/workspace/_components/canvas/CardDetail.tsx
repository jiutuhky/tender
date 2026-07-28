import type { ReactNode } from "react";
import { Chip, Dot, StatusBadge } from "./bits";
import { dotColor, isMatrixCardType, type CardType, type StatusColor } from "./cardMeta";
import { MatrixCardDetail } from "./matrixViews";
import {
  BuildingsIcon,
  CircleDashedIcon,
  CircleHalfIcon,
  CredCheckIcon,
  FileIcon,
  IdCardIcon,
} from "@/components/ui/icons";

// 抽屉详情正文（完整视图）。逐型号还原 .design 原型的 detail()。

export type DetailType = CardType | "__outline";

export interface Col {
  t: string;
  f: string;
}

export function SecTitle({ t, sub }: { t: string; sub?: string }) {
  return (
    <div style={{ margin: "2px 0 10px" }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: "var(--label)" }}>{t}</div>
      {sub && <div style={{ fontSize: 12, color: "var(--label-3)", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

export function Table({ head, rows }: { head: Col[]; rows: ReactNode[][] }) {
  return (
    <div style={{ border: "1px solid var(--separator)", borderRadius: 10, overflow: "hidden" }}>
      <div style={{ display: "flex", background: "var(--surface-2)" }}>
        {head.map((c) => (
          <span key={c.t} style={{ flex: c.f, padding: "9px 11px", fontSize: 11.5, fontWeight: 600, color: "var(--label-2)" }}>
            {c.t}
          </span>
        ))}
      </div>
      {rows.map((r, i) => (
        <div key={i} style={{ display: "flex", borderTop: "1px solid var(--separator)" }}>
          {r.map((cell, j) => (
            <span
              key={j}
              style={{
                flex: head[j]?.f,
                padding: "10px 11px",
                fontSize: 12.5,
                color: "var(--label)",
                display: "flex",
                alignItems: "center",
                gap: 6,
                minWidth: 0,
              }}
            >
              {cell}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}

/** 带连点的内联单元（应答方式 / 偏离） */
export function DotCell({ sc, t }: { sc: StatusColor; t: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <Dot sc={sc} />
      {t}
    </span>
  );
}

const KNOL_ICON = { idcard: IdCardIcon, buildings: BuildingsIcon, files: FileIcon } as const;
const CH_ICON: Record<StatusColor, typeof CredCheckIcon> = {
  green: CredCheckIcon,
  blue: CircleHalfIcon,
  gray: CircleDashedIcon,
  orange: CircleHalfIcon,
};

export function CardDetail({ type }: { type: DetailType }) {
  // 真实矩阵卡:数据订阅自 store,委托专用详情组件
  if (type !== "__outline" && isMatrixCardType(type)) return <MatrixCardDetail type={type} />;
  if (type === "req") {
    const groups: Array<[string, number, number, string, string]> = [
      ["功能需求", 18, 2, "3.1.2 支持多物理场（结构/流体/电磁）耦合建模", "3.1.7 提供参数化建模与批量工况管理"],
      ["性能需求", 9, 1, "3.2.1 单次求解网格规模 ≥ 1000 万", "3.2.4 支持国产 CPU 并行加速"],
      ["接口需求", 7, 2, "3.3.2 与 PLM / PDM 系统双向集成", "3.3.5 开放 REST 求解调度 API"],
      ["安全需求", 11, 1, "3.4.1 满足等保三级要求", "3.4.3 全链路数据加密与审计"],
    ];
    return (
      <div>
        <SecTitle t="技术需求清单" sub="从招标文件第三章提取，共 45 条，按四类归档" />
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {groups.map(([name, count, substantive, a, b]) => (
            <div key={name} style={{ border: "1px solid var(--separator)", borderRadius: 12, padding: "12px 14px", background: "var(--surface)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: "var(--label)" }}>{name}</span>
                <span style={{ fontSize: 11, color: "var(--label-3)" }}>{count} 条</span>
                {substantive ? (
                  <span
                    style={{
                      marginLeft: "auto",
                      fontSize: 10.5,
                      fontWeight: 600,
                      color: "var(--orange-text)",
                      background: "rgba(255,149,0,.15)",
                      padding: "1px 8px",
                      borderRadius: 999,
                    }}
                  >
                    实质性 {substantive}
                  </span>
                ) : null}
              </div>
              {[a, b].map((it) => (
                <div key={it} style={{ display: "flex", gap: 8, padding: "5px 0", fontSize: 12.5, color: "var(--label-2)" }}>
                  <span className="cv-bullet" />
                  {it}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (type === "matrix") {
    const head: Col[] = [
      { t: "#", f: "0 0 30px" },
      { t: "招标需求条目", f: "2.4" },
      { t: "应答方式", f: "1.1" },
      { t: "偏离", f: "1.2" },
      { t: "引用来源", f: "1.3" },
    ];
    const rows: ReactNode[][] = [
      ["1", "多物理场耦合求解", <DotCell key="r" sc="green" t="完全满足" />, "无偏离", "业绩 A-203"],
      ["2", "网格规模 ≥ 1000 万", <DotCell key="r" sc="green" t="完全满足" />, "无偏离", "性能测试报告"],
      ["3", "国产化适配（鲲鹏/麒麟）", <DotCell key="r" sc="green" t="满足" />, "正偏离", "资质 · 适配证明"],
      ["4", "7×24 运维响应 ≤ 2h", <DotCell key="r" sc="green" t="满足" />, "无偏离", "服务承诺函"],
      ["5", "与 PLM 系统接口", <DotCell key="r" sc="orange" t="部分满足" />, "负偏离", "方案 4.3"],
      ["6", "数据加密 · 等保三级", <DotCell key="r" sc="green" t="满足" />, "无偏离", "资质 · 等保"],
    ];
    return (
      <div>
        <SecTitle t="应答矩阵" sub="逐条映射招标需求与投标响应 · 生成 32 / 45" />
        <Table head={head} rows={rows} />
      </div>
    );
  }

  if (type === "outline" || type === "__outline") {
    const rows: Array<[string, StatusColor, string, string]> = [
      ["一  投标函与投标函附录", "green", "已生成", "1.2k"],
      ["二  商务及报价响应", "green", "已生成", "3.4k"],
      ["三  技术方案", "blue", "编写中", "—"],
      ["　3.1  总体技术架构", "gray", "草稿", "1.2k"],
      ["　3.2  技术需求逐条响应", "green", "已生成", "5.1k"],
      ["　3.3  技术偏差表", "gray", "草稿", "0.6k"],
      ["四  项目实施与服务", "gray", "待生成", "—"],
      ["五  资质证明材料", "green", "已生成", "—"],
      ["六  拟投入人员", "gray", "待生成", "—"],
    ];
    return (
      <div>
        <SecTitle t="投标大纲" sub="8 章 · 引用 12 处 · 与招标评分项一一对应" />
        <div style={{ display: "flex", flexDirection: "column" }}>
          {rows.map(([t, sc, status, size], i) => (
            <div
              key={t}
              style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 4px", borderTop: i ? "1px solid var(--separator)" : "none" }}
            >
              <Dot sc={sc} />
              <span style={{ flex: 1, fontSize: 13, color: "var(--label)", fontWeight: t.includes("　") ? 400 : 600 }}>{t}</span>
              <span style={{ fontSize: 11, color: "var(--label-3)", fontVariantNumeric: "tabular-nums", width: 42, textAlign: "right" }}>
                {size}
              </span>
              <StatusBadge sc={sc} label={status} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (type === "chapter") {
    return (
      <div>
        <SecTitle t="技术方案 · 总体设计" />
        <div style={{ fontSize: 15, fontWeight: 700, margin: "4px 0 8px" }}>3.1  总体技术架构</div>
        <p style={{ fontSize: 13.5, lineHeight: 1.85, color: "var(--label)", margin: "0 0 14px" }}>
          本项目采用分层微服务架构，将仿真求解、前后处理、数据管理与协同设计四个域解耦。求解层基于国产 CPU 与异构加速实现并行扩展，前后处理层提供 Web
          端可视化建模，数据层以统一仿真数据中台支撑版本与权限治理。
        </p>
        <div style={{ fontSize: 14, fontWeight: 600, margin: "2px 0 6px" }}>3.1.1  求解引擎</div>
        <p style={{ fontSize: 13.5, lineHeight: 1.85, color: "var(--label)", margin: "0 0 14px" }}>
          求解引擎支持结构、流体、电磁多物理场耦合，单次求解网格规模可达 1000 万以上，并通过区域分解实现近线性并行加速，满足招标第 3.2 条性能指标。
        </p>
        <Table
          head={[
            { t: "技术指标", f: "1.6" },
            { t: "招标要求", f: "1" },
            { t: "本方案", f: "1" },
          ]}
          rows={[
            ["网格规模", "≥1000万", "1600万"],
            ["并行效率", "—", "≥85%"],
            ["国产化", "要求", "全栈适配"],
          ]}
        />
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "14px 0 4px" }}>
          <Chip>引用 业绩案例 A-203</Chip>
          <Chip>引用 ISO9001</Chip>
          <Chip>引用 性能测试报告</Chip>
        </div>
        <div style={{ fontSize: 11.5, color: "var(--label-3)", marginTop: 8 }}>约 1,240 字 · 引用 6 处 · 草稿</div>
      </div>
    );
  }

  if (type === "knowledge") {
    const groups: Array<[string, keyof typeof KNOL_ICON, Array<[string, string]>]> = [
      [
        "资质证照",
        "idcard",
        [
          ["营业执照", "长期有效"],
          ["ISO 9001 质量体系", "2026-08"],
          ["信息系统集成二级", "2027-03"],
          ["等保三级备案", "有效"],
        ],
      ],
      [
        "业绩案例",
        "buildings",
        [
          ["某航空院所仿真平台", "¥1,860万 · 2024"],
          ["某车企 CAE 云", "¥920万 · 2023"],
          ["某高校多物理场中心", "¥540万 · 2023"],
        ],
      ],
      [
        "人员简历",
        "files",
        [
          ["项目经理 · PMP", "12 年经验"],
          ["技术负责人 · 博士", "流体仿真"],
          ["国产化适配工程师", "鲲鹏认证"],
        ],
      ],
    ];
    return (
      <div>
        <SecTitle t="知识库素材" sub="按需引用至章节，自动生成脚注与附件清单" />
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {groups.map(([name, iconKey, items]) => {
            const Icon = KNOL_ICON[iconKey];
            return (
              <div key={name}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <Icon width={15} height={15} style={{ color: "var(--blue)" }} />
                  <span style={{ fontSize: 13, fontWeight: 700 }}>{name}</span>
                  <span style={{ fontSize: 11, color: "var(--label-3)" }}>{items.length} 项</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {items.map(([it, meta]) => (
                    <div
                      key={it}
                      style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 11px", background: "var(--surface-2)", borderRadius: 10 }}
                    >
                      <span style={{ flex: 1, fontSize: 12.5, color: "var(--label)" }}>{it}</span>
                      <span style={{ fontSize: 11, color: "var(--label-3)" }}>{meta}</span>
                      <button type="button" className="cv-cite-btn">引用</button>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (type === "chart") {
    const tasks: Array<[string, number, number, StatusColor]> = [
      ["需求与方案设计", 0, 0.22, "green"],
      ["核心求解开发", 0.18, 0.36, "blue"],
      ["前后处理与集成", 0.4, 0.3, "blue"],
      ["国产化适配测试", 0.62, 0.2, "gray"],
      ["试运行与交付", 0.8, 0.18, "gray"],
    ];
    const months = ["M1", "M2", "M3", "M4", "M5", "M6"];
    const legend: Array<[StatusColor, string]> = [
      ["green", "已完成"],
      ["blue", "进行中"],
      ["gray", "计划"],
    ];
    return (
      <div>
        <SecTitle t="实施进度计划" sub="总周期 6 个月 · 4 个里程碑" />
        <div style={{ display: "flex", paddingLeft: 128, marginBottom: 6 }}>
          {months.map((m) => (
            <span key={m} style={{ flex: 1, fontSize: 10.5, color: "var(--label-3)", textAlign: "center" }}>
              {m}
            </span>
          ))}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          {tasks.map(([name, left, width, sc]) => (
            <div key={name} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 120, fontSize: 12, color: "var(--label)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {name}
              </span>
              <div style={{ flex: 1, height: 14, borderRadius: 7, background: "var(--surface-2)", position: "relative" }}>
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    bottom: 0,
                    left: `${left * 100}%`,
                    width: `${width * 100}%`,
                    borderRadius: 7,
                    background: dotColor(sc),
                    opacity: sc === "gray" ? 0.45 : 0.9,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: 14, marginTop: 14, fontSize: 11, color: "var(--label-3)" }}>
          {legend.map(([sc, label]) => (
            <span key={label} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
              <Dot sc={sc} />
              {label}
            </span>
          ))}
        </div>
      </div>
    );
  }

  if (type === "deviation") {
    const head: Col[] = [
      { t: "招标条目", f: "1.2" },
      { t: "招标要求", f: "1.4" },
      { t: "投标响应", f: "1.4" },
      { t: "偏离", f: "1" },
    ];
    const rows: ReactNode[][] = [
      ["国产化适配", "建议支持", "全栈适配", <DotCell key="d" sc="blue" t="正偏离" />],
      ["接口协议", "OPC-UA 1.04", "OPC-UA 1.05", <DotCell key="d" sc="orange" t="负偏离" />],
      ["运维响应", "≤4h", "≤2h", <DotCell key="d" sc="blue" t="正偏离" />],
      ["数据加密", "等保三级", "等保三级", <DotCell key="d" sc="green" t="无偏离" />],
    ];
    return (
      <div>
        <SecTitle t="技术偏差表" sub="逐项说明响应与招标要求的偏离情况" />
        <Table head={head} rows={rows} />
      </div>
    );
  }

  if (type === "assemble") {
    const chs: Array<[string, StatusColor]> = [
      ["一  投标函与附录", "green"],
      ["二  商务及报价响应", "green"],
      ["三  技术方案", "blue"],
      ["四  项目实施与服务", "gray"],
      ["五  资质证明材料", "green"],
      ["六  拟投入人员", "gray"],
    ];
    const badge = (sc: StatusColor) => (sc === "green" ? "已编制" : sc === "blue" ? "编写中" : "待补");
    return (
      <div>
        <SecTitle t="投标文件 · 成稿" sub="汇编各章节为最终投标文件" />
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 6 }}>
          <span style={{ fontSize: 30, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>33%</span>
          <span style={{ fontSize: 12, color: "var(--label-3)" }}>4 / 12 章已编制 · 约 1.2 万字</span>
        </div>
        <div style={{ height: 8, borderRadius: 999, background: "var(--surface-2)", overflow: "hidden", marginBottom: 16 }}>
          <div style={{ width: "33%", height: "100%", background: "var(--blue)" }} />
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          {chs.map(([name, sc], i) => {
            const Icon = CH_ICON[sc];
            return (
              <div
                key={name}
                style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 4px", borderTop: i ? "1px solid var(--separator)" : "none" }}
              >
                <Icon width={16} height={16} style={{ color: dotColor(sc) }} />
                <span style={{ flex: 1, fontSize: 13, color: "var(--label)" }}>{name}</span>
                <StatusBadge sc={sc} label={badge(sc)} />
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  return null;
}
