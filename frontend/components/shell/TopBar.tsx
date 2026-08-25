import { Fragment, type ReactNode } from "react";
import { BrandMark } from "@/components/ui/icons";
import { NavTabs } from "./NavTabs";
import { AppearanceMenu } from "./AppearanceMenu";

type Crumb = { label: string; current?: boolean };

interface TopBarProps {
  crumbs: Crumb[];
  actions?: ReactNode;
}

export function TopBar({ crumbs, actions }: TopBarProps) {
  return (
    // 顶栏为嵌入式 chrome:霜 soft·thick,flush(无浮起投影,与内容以 .5px contact edge 相接)
    <header className="topbar frost-glass frost-glass--soft frost-glass--flush" data-thick="thick">
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
        <AppearanceMenu />
        <div className="avatar">LH</div>
      </div>
    </header>
  );
}
