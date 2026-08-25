"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  BrandMark,
  ChartLineIcon,
  ChatCircleIcon,
  FileTextIcon,
  GearSixIcon,
  GridFourIcon,
  PlusIcon,
  QuestionIcon,
  SearchIcon,
  SidebarSimpleIcon,
} from "@/components/ui/icons";
import { ContextPanel } from "./ContextPanel";

const STORAGE_KEY = "prose.projects.railExpanded";

/**
 * 应用外壳：统一一个 grid 同时管行（52px 顶栏 + 1fr 主区）和列（窄栏 + 二级面板 + 内容）。
 * 最左 .nav-rail 跨满两行 —— 从页面最顶延伸到底；topbar 退到侧栏右侧（grid 第 2~3 列）。
 * 侧栏顶部 .rail-head：展开时左侧产品标 + 右侧 toggle，收起时只剩居中 toggle。
 * push 模式 —— 展开把右侧内容推开，不做悬浮覆盖。
 * chrome（窄栏 / 顶栏 / 二级面板）为霜玻璃（soft·thick·flush），坐在 body 壁纸上；内容主列实底。
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
      {/* ===== 最左窄栏（延伸到页面最顶，霜玻璃 chrome） ===== */}
      <aside
        className="nav-rail frost-glass frost-glass--soft frost-glass--flush"
        data-thick="thick"
      >
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
                <SidebarSimpleIcon />
              </span>
            </button>
          </div>

          <button className="rail-cta" title="新建项目 ⌘N" type="button">
            <span className="rail-ico">
              <span className="rail-chip">
                <PlusIcon />
              </span>
            </span>
            <span className="rail-label">新建项目</span>
            <span className="rail-kbd">⌘N</span>
          </button>

          <nav className="rail-group">
            <Link href="/projects" className="rail-item active">
              <span className="rail-ico">
                <GridFourIcon />
              </span>
              <span className="rail-label">工作台</span>
              <span className="rail-kbd">G W</span>
            </Link>
            <Link href="/knowledge" className="rail-item">
              <span className="rail-ico">
                <FileTextIcon />
              </span>
              <span className="rail-label">知识库</span>
              <span className="rail-kbd">G K</span>
            </Link>
            <Link href="/workspace" className="rail-item">
              <span className="rail-ico">
                <ChatCircleIcon />
                <span className="badge-dot" />
              </span>
              <span className="rail-label">对话 / 智能体</span>
              <span className="rail-kbd">⌘K</span>
            </Link>
            <a href="#" className="rail-item">
              <span className="rail-ico">
                <ChartLineIcon />
              </span>
              <span className="rail-label">洞察 · 复盘</span>
            </a>
          </nav>

          <div className="rail-spacer" />

          <nav className="rail-group">
            <a href="#" className="rail-item">
              <span className="rail-ico">
                <SearchIcon />
              </span>
              <span className="rail-label">搜索</span>
              <span className="rail-kbd">⌘K</span>
            </a>
            <a href="#" className="rail-item">
              <span className="rail-ico">
                <QuestionIcon />
              </span>
              <span className="rail-label">帮助</span>
            </a>
            <a href="#" className="rail-item">
              <span className="rail-ico">
                <GearSixIcon />
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

      {/* ===== 顶栏（侧栏右侧，霜玻璃 chrome） ===== */}
      <header
        className="topbar frost-glass frost-glass--soft frost-glass--flush"
        data-thick="thick"
      >
        {topbar}
      </header>

      {/* ===== 二级面板（已存在） ===== */}
      <ContextPanel />

      {/* ===== 内容 ===== */}
      <main className="content">{children}</main>
    </div>
  );
}
