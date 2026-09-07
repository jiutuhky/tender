"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS: { href: string; label: string }[] = [
  { href: "/home", label: "首页" },
  { href: "/projects", label: "项目" },
  { href: "/knowledge", label: "知识库" },
];

export function NavTabs() {
  const pathname = usePathname();
  return (
    <nav className="prose-navigation" aria-label="主导航">
      {TABS.map((tab) => {
        const active =
          pathname === tab.href || pathname?.startsWith(`${tab.href}/`) ||
          (tab.href === "/projects" && (pathname === "/workspace" || pathname === "/preview"));
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={active ? "active" : undefined}
            aria-current={active ? "page" : undefined}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
