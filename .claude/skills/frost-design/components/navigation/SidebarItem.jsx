import React from "react";

/* Frost SidebarItem — a row in the soft-glass (霜) sidebar. Icon + label, optional
   trailing badge/count; the active row gets the soft-blue backing and a blue
   icon. Use `group` for a section header above a run of items. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "sidebar-item");
  el.textContent = `
.frost-sbgroup{font-size:11px;font-weight:600;color:var(--label-3,#6b6b76);padding:12px 10px 5px;}
.frost-sbitem{
  display:flex;align-items:center;gap:9px;
  padding:6px 10px;border-radius:var(--r-control,7px);
  font-size:13px;color:var(--label,#1d1d1f);cursor:default;
  transition:background var(--t-micro,120ms) var(--ease-std);
}
.frost-sbitem:hover:not(.is-active){background:rgba(60,60,67,.07);}
.frost-sbitem i{font-size:15px;color:var(--label-2,#55555e);flex:none;}
.frost-sbitem__label{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.frost-sbitem__trail{margin-left:auto;flex:none;}
.frost-sbitem.is-active{background:var(--blue-soft,rgba(0,100,225,.14));font-weight:600;}
.frost-sbitem.is-active i{color:var(--blue,#0064e1);}
[data-appearance="dark"] .frost-sbitem:hover:not(.is-active){background:rgba(255,255,255,.06);}
`;
  document.head.appendChild(el);
}

export function SidebarGroup({ children }) {
  ensureStyles();
  return <div className="frost-sbgroup">{children}</div>;
}

export function SidebarItem({ icon, label, active = false, trailing, onClick, style, ...rest }) {
  ensureStyles();
  return (
    <div className={`frost-sbitem${active ? " is-active" : ""}`} onClick={onClick} style={style} {...rest}>
      {icon ? <i className={`ph ph-${icon}`} /> : null}
      <span className="frost-sbitem__label">{label}</span>
      {trailing ? <span className="frost-sbitem__trail">{trailing}</span> : null}
    </div>
  );
}
