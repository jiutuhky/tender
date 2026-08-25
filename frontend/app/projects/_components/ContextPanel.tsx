"use client";

import { useState } from "react";
import {
  ChatCircleIcon,
  ClockIcon,
  EyeIcon,
  ListDashesIcon,
  UsersIcon,
} from "@/components/ui/icons";

/** 视图 / 状态过滤项 —— 单选高亮，纯前端 mockup（迁移自原型 projects.html）。 */
type FilterItem = {
  key: string;
  label: string;
  count: number;
  icon?: React.ReactNode;
  dot?: string;
};

const VIEWS: FilterItem[] = [
  { key: "all", label: "全部在投", count: 12, icon: <ListDashesIcon /> },
  { key: "mine", label: "我负责的", count: 9, icon: <UsersIcon /> },
  { key: "week", label: "本周到期", count: 3, icon: <ClockIcon /> },
  { key: "review", label: "等我审阅", count: 2, icon: <EyeIcon /> },
];

const STATUSES: FilterItem[] = [
  { key: "s-bid", label: "Bid/No-Bid 待决策", count: 2, dot: "s-bid" },
  { key: "s-parse", label: "立项中 · 解析", count: 1, dot: "s-draft" },
  { key: "s-draft", label: "草稿", count: 1, dot: "s-draft" },
  { key: "s-writing", label: "撰写中", count: 6, dot: "s-writing" },
  { key: "s-review", label: "评审中", count: 2, dot: "s-review" },
];

const SYS_PRIMARY: FilterItem[] = [
  { key: "gov", label: "政务中台 / 一网通办", count: 2 },
  { key: "data", label: "数据中台 / 数据治理", count: 2 },
  { key: "boss", label: "电信 BOSS / 业务支撑", count: 1 },
  { key: "fin", label: "金融 · 保险业务系统", count: 1 },
  { key: "xc", label: "信创 · 国产化适配", count: 1 },
];

const SYS_EXTRA: FilterItem[] = [
  { key: "sec", label: "数据安全 · 合规科技", count: 1 },
  { key: "erp", label: "ERP · 财务共享", count: 1 },
  { key: "scada", label: "工控软件 · SCADA", count: 1 },
  { key: "itom", label: "ITOM · 运维一体化", count: 1 },
  { key: "llm", label: "智能客服 · 大模型", count: 1 },
  { key: "his", label: "医疗信息化 · HIS / EMR", count: 1 },
];

export function ContextPanel() {
  const [active, setActive] = useState("all");
  const [sysOpen, setSysOpen] = useState(false);

  return (
    <aside
      className="nav-panel frost-glass frost-glass--soft frost-glass--flush"
      data-thick="thick"
    >
      {/* 计数细目不再重复：视图行右侧已逐项带数，页头 deck 也有同信息 */}
      <h2 className="panel-head">
        工作台 <span className="pct">12 在投</span>
      </h2>

      <button className="panel-cta" type="button">
        <ChatCircleIcon />
        <span>新对话</span>
        <span className="kbd">⌘K</span>
      </button>

      <h5>最近对话</h5>
      <a href="#" className="recent-row">
        <span className="rt">浦东一网通办 · 偏离项澄清</span>
        <span className="when">12m</span>
      </a>
      <a href="#" className="recent-row">
        <span className="rt">税务 V4 · 终轮合稿</span>
        <span className="when">2h</span>
      </a>
      <a href="#" className="recent-row">
        <span className="rt">华润 ERP · 招标文件解析</span>
        <span className="when">昨</span>
      </a>

      {/* 对话域 / 过滤域分界 */}
      <div className="panel-sep" role="separator" />

      <h5>视图</h5>
      {VIEWS.map((it) => (
        <div
          key={it.key}
          className={`nav-item${active === it.key ? " active" : ""}`}
          onClick={() => setActive(it.key)}
        >
          {it.icon}
          <span>{it.label}</span>
          <span className="count">{it.count}</span>
        </div>
      ))}

      <h5>按状态</h5>
      {STATUSES.map((it) => (
        <div
          key={it.key}
          className={`nav-item${active === it.key ? " active" : ""}`}
          onClick={() => setActive(it.key)}
        >
          <span className={`dot-status ${it.dot}`} />
          <span>{it.label}</span>
          <span className="count">{it.count}</span>
        </div>
      ))}

      <h5>
        按系统类型{" "}
        <span
          className="more"
          onClick={(e) => {
            e.stopPropagation();
            setSysOpen((v) => !v);
          }}
        >
          {sysOpen ? "收起" : "+6 更多"}
        </span>
      </h5>
      {SYS_PRIMARY.map((it) => (
        <div
          key={it.key}
          className={`nav-item indent${active === it.key ? " active" : ""}`}
          onClick={() => setActive(it.key)}
        >
          <span>{it.label}</span>
          <span className="count">{it.count}</span>
        </div>
      ))}
      <div className={`panel-sys-extra${sysOpen ? " is-open" : ""}`}>
        {SYS_EXTRA.map((it) => (
          <div
            key={it.key}
            className={`nav-item indent${active === it.key ? " active" : ""}`}
            onClick={() => setActive(it.key)}
          >
            <span>{it.label}</span>
            <span className="count">{it.count}</span>
          </div>
        ))}
      </div>

      <p className="nav-side-pin">
        在「
        <a href="/knowledge" style={{ color: "var(--blue)" }}>
          知识库
        </a>
        」沉淀过的方案章节、技术架构图与人员资质，会自动进入新立项的应答框架。
      </p>
    </aside>
  );
}
