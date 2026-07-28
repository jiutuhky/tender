"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS: { href: string; label: string }[] = [
  { href: "/home", label: "首页" },
  { href: "/workspace", label: "工作台" },
  { href: "/preview", label: "文档预览" },
  { href: "/knowledge", label: "知识库" },
];

export function NavTabs() {
  const pathname = usePathname();
  return (
    <nav className="nav-tabs">
      {TABS.map((tab) => {
        const active =
          pathname === tab.href || pathname?.startsWith(`${tab.href}/`);
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={active ? "active" : undefined}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
