import { Fragment, type ReactNode } from "react";
import Link from "next/link";
import { BrandMark } from "@/components/ui/icons";
import { NavTabs } from "./NavTabs";
import { AppearanceMenu } from "./AppearanceMenu";

type Crumb = { label: string; current?: boolean; href?: string };

interface TopBarProps {
  crumbs: Crumb[];
  actions?: ReactNode;
}

export function TopBar({ crumbs, actions }: TopBarProps) {
  return (
    <header className="prose-topbar">
      <Link className="prose-brand" href="/home" aria-label="Prose 首页">
        <span className="prose-brand-mark">
          <BrandMark />
        </span>
        Prose
      </Link>
      <NavTabs />
      {crumbs.length > 1 && <nav className="prose-breadcrumb" aria-label="当前位置">
        {crumbs.map((c, i) => (
          <Fragment key={i}>
            {i > 0 && <span aria-hidden="true">/</span>}
            {c.href ? <Link href={c.href}>{c.label}</Link> : <span aria-current={c.current ? "page" : undefined}>{c.label}</span>}
          </Fragment>
        ))}
      </nav>}
      <div className="prose-topbar-actions">
        {actions}
        <AppearanceMenu />
      </div>
    </header>
  );
}
