import React from "react";

/* Frost Menu — a lens-glass (凝 · regular) context menu. Items take an icon,
   label, and an optional keyboard hint; the hovered row fills full-width blue.
   Concentric corners: menu 12 − padding 6 = row 6. Pass items, or compose with
   Menu.Item / Menu.Separator. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "menu");
  el.textContent = `
.frost-menu{
  width:248px;border-radius:var(--r-window,12px);padding:6px;
}
.frost-menu__item{
  display:flex;align-items:center;gap:10px;
  padding:6px 10px;border-radius:6px;font-size:13px;color:var(--label,#1d1d1f);
  cursor:default;user-select:none;
  transition:background var(--t-micro,120ms) var(--ease-std);
}
.frost-menu__item i{font-size:15px;color:var(--label-2,#55555e);width:18px;text-align:center;}
.frost-menu__item .frost-menu__kbd{margin-left:auto;font-family:var(--font-mono);font-size:11px;color:var(--label-3,#6b6b76);}
.frost-menu__item:hover,
.frost-menu__item[data-active="true"]{background:var(--blue,#0064e1);color:#fff;}
.frost-menu__item:hover i,.frost-menu__item[data-active="true"] i,
.frost-menu__item:hover .frost-menu__kbd,.frost-menu__item[data-active="true"] .frost-menu__kbd{color:rgba(255,255,255,.85);}
.frost-menu__item--danger{color:var(--red-text,#d70015);}
.frost-menu__item--danger:hover{background:var(--red,#ff3b30);color:#fff;}
.frost-menu__item--danger:hover i{color:rgba(255,255,255,.85);}
.frost-menu__item[data-disabled="true"]{opacity:.4;pointer-events:none;}
.frost-menu__sep{height:1px;background:var(--separator);margin:5px 10px;}
`;
  document.head.appendChild(el);
}

function Item({ icon, label, kbd, danger = false, active = false, disabled = false, onSelect, ...rest }) {
  ensureStyles();
  return (
    <div
      className={`frost-menu__item${danger ? " frost-menu__item--danger" : ""}`}
      data-active={active}
      data-disabled={disabled}
      onClick={onSelect}
      role="menuitem"
      {...rest}
    >
      {icon ? <i className={`ph ph-${icon}`} /> : null}
      <span>{label}</span>
      {kbd ? <span className="frost-menu__kbd">{kbd}</span> : null}
    </div>
  );
}

function Separator() {
  return <div className="frost-menu__sep" />;
}

export function Menu({ items, children, style, ...rest }) {
  ensureStyles();
  return (
    <div className="frost-menu frost-glass frost-glass--lens" role="menu" style={style} {...rest}>
      {items
        ? items.map((it, i) =>
            it === "---" || it.separator ? <Separator key={i} /> : <Item key={i} {...it} />
          )
        : children}
    </div>
  );
}

Menu.Item = Item;
Menu.Separator = Separator;
