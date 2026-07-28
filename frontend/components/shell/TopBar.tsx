import { Fragment, type ReactNode } from "react";
import { BrandMark } from "@/components/ui/icons";
import { NavTabs } from "./NavTabs";

type Crumb = { label: string; current?: boolean };

interface TopBarProps {
  crumbs: Crumb[];
  actions?: ReactNode;
}

export function TopBar({ crumbs, actions }: TopBarProps) {
  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark">
          <BrandMark />
        </div>
        Prose
      </div>
      <div className="topbar-divider" />
      <div className="breadcrumb">
        {crumbs.map((c, i) => (
          <Fragment key={i}>
            {i > 0 && <span className="breadcrumb-sep">/</span>}
            <span className={c.current ? "crumb-current" : undefined}>
              {c.label}
            </span>
          </Fragment>
        ))}
      </div>
      <NavTabs />
      <div className="topbar-actions">
        {actions}
        <div className="avatar">LH</div>
      </div>
    </header>
  );
}
