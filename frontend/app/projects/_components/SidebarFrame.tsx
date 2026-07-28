"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BrandMark } from "@/components/ui/icons";
import { ContextPanel } from "./ContextPanel";

const stroke = {
  fill: "none" as const,
  stroke: "currentColor" as const,
};

const STORAGE_KEY = "prose.projects.railExpanded";

/**
 * 应用外壳：统一一个 grid 同时管行（52px 顶栏 + 1fr 主区）和列（窄栏 + 二级面板 + 内容）。
 * 最左 .nav-rail 跨满两行 —— 从页面最顶延伸到底；topbar 退到侧栏右侧（grid 第 2~3 列）。
 * 侧栏顶部 .rail-head：展开时左侧产品标 + 右侧 toggle，收起时只剩居中 toggle。
 * push 模式 —— 展开把右侧内容推开，不做悬浮覆盖。
 */
export function SidebarFrame({
  topbar,
  children,
}: {
  topbar: React.ReactNode;
  children: React.ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);

  // 挂载后从 localStorage 恢复（SSR 与首帧均为收起态，规避水合不一致）。
  useEffect(() => {
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (localStorage.getItem(STORAGE_KEY) === "1") setExpanded(true);
    } catch {
      /* 隐私模式等场景忽略 */
    }
  }, []);

  const toggle = () =>
    setExpanded((v) => {
      const next = !v;
      try {
        localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      } catch {
        /* 忽略 */
      }
      return next;
    });

  return (
    <div className={`app-shell${expanded ? " rail-expanded" : ""}`}>
      {/* ===== 最左窄栏（延伸到页面最顶） ===== */}
      <aside className="nav-rail">
        <div className="rail-inner">
          {/* 顶部：展开 = 产品标 + toggle；收起 = 仅居中 toggle */}
          <div className="rail-head">
            <Link href="/projects" className="rail-brand" title="Prose · 华信智库">
              <span className="brand-mark"><BrandMark /></span>
            </Link>
            <button
              className="rail-toggle"
              type="button"
              onClick={toggle}
              aria-label={expanded ? "收起侧栏" : "展开侧栏"}
              aria-expanded={expanded}
            >
              <span className="rail-ico">
                <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.5}>
                  <rect x="2" y="2.5" width="12" height="11" rx="1.5" />
                  <path d="M6.5 2.5v11" />
                  <path className="rail-caret" d="M9.4 6.2L11.2 8l-1.8 1.8" />
                </svg>
              </span>
            </button>
          </div>

          <button className="rail-cta" title="新建项目 ⌘N" type="button">
            <span className="rail-ico">
              <span className="rail-chip">
                <svg viewBox="0 0 16 16" {...stroke} strokeWidth={2}>
                  <path d="M8 3.5v9M3.5 8h9" />
                </svg>
              </span>
            </span>
            <span className="rail-label">新建项目</span>
            <span className="rail-kbd">⌘N</span>
          </button>

          <nav className="rail-group">
            <Link href="/projects" className="rail-item active">
              <span className="rail-ico">
                <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.5}>
                  <rect x="2" y="2.5" width="12" height="11" rx="1.5" />
                  <path d="M2 6.5h12M5.5 9.5h2M5.5 11.5h4" />
                </svg>
              </span>
              <span className="rail-label">工作台</span>
              <span className="rail-kbd">G W</span>
            </Link>
            <Link href="/knowledge" className="rail-item">
              <span className="rail-ico">
                <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.5}>
                  <path d="M3 3.5a1 1 0 011-1h5l3 3v7a1 1 0 01-1 1H4a1 1 0 01-1-1v-9z" />
                  <path d="M9 2.5v3h3M5.5 9h5M5.5 11h3" />
                </svg>
              </span>
              <span className="rail-label">知识库</span>
              <span className="rail-kbd">G K</span>
            </Link>
            <Link href="/workspace" className="rail-item">
              <span className="rail-ico">
                <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.5}>
                  <path d="M3 4.5h10v6H8.5L5.5 13v-2.5H3v-6z" />
                </svg>
                <span className="badge-dot" />
              </span>
              <span className="rail-label">对话 / 智能体</span>
              <span className="rail-kbd">⌘K</span>
            </Link>
            <a href="#" className="rail-item">
              <span className="rail-ico">
                <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.5}>
                  <path d="M2.5 12.5l4-6 3 4 4-6" />
                  <path d="M2.5 2.5v11h11" />
                </svg>
              </span>
              <span className="rail-label">洞察 · 复盘</span>
            </a>
          </nav>

          <div className="rail-spacer" />

          <nav className="rail-group">
            <a href="#" className="rail-item">
              <span className="rail-ico">
                <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.5}>
                  <circle cx="7" cy="7" r="4.5" />
                  <path d="M13 13l-2.7-2.7" />
                </svg>
              </span>
              <span className="rail-label">搜索</span>
              <span className="rail-kbd">⌘K</span>
            </a>
            <a href="#" className="rail-item">
              <span className="rail-ico">
                <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.5}>
                  <circle cx="8" cy="8" r="6" />
                  <path d="M8 5.5v3M8 10.5v.5" />
                </svg>
              </span>
              <span className="rail-label">帮助</span>
            </a>
            <a href="#" className="rail-item">
              <span className="rail-ico">
                <svg viewBox="0 0 16 16" {...stroke} strokeWidth={1.5}>
                  <circle cx="8" cy="8" r="2" />
                  <path d="M8 2v1.5M8 12.5V14M2 8h1.5M12.5 8H14M3.8 3.8l1 1M11.2 11.2l1 1M3.8 12.2l1-1M11.2 4.8l1-1" />
                </svg>
              </span>
              <span className="rail-label">设置</span>
            </a>
          </nav>

          <button className="rail-user" title="李慧 · 售前总监" type="button">
            <span className="rail-ico">
              <span className="rail-ava">LH</span>
            </span>
            <span className="rail-id">
              <span className="rail-id-name">李慧</span>
              <span className="rail-id-role">售前总监</span>
            </span>
          </button>
        </div>
      </aside>

      {/* ===== 顶栏（侧栏右侧） ===== */}
      <header className="topbar">{topbar}</header>

      {/* ===== 二级面板（已存在） ===== */}
      <ContextPanel />

      {/* ===== 内容 ===== */}
      <main className="content">{children}</main>
    </div>
  );
}
