import React from "react";

/* Frost IconButton — the bare toolbar / inline icon control. Square, transparent
   at rest, soft gray fill on hover. Use for window-toolbar actions and inline
   affordances. Always pass an aria-label. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "icon-button");
  el.textContent = `
.frost-iconbtn{
  display:inline-grid;place-items:center;border:none;background:transparent;
  color:var(--label-2,#55555e);cursor:pointer;
  width:30px;height:30px;border-radius:var(--r-control,7px);font-size:16px;
  transition:background var(--t-micro,120ms) var(--ease-std),
             color var(--t-micro,120ms) var(--ease-std),
             transform var(--t-micro,120ms) var(--ease-std);
}
.frost-iconbtn:hover{background:rgba(60,60,67,.09);color:var(--label,#1d1d1f);}
.frost-iconbtn:active{transform:scale(.92);}
.frost-iconbtn[disabled]{opacity:.4;pointer-events:none;}
.frost-iconbtn--active{background:var(--blue-soft,rgba(0,100,225,.1));color:var(--blue,#0064e1);}
.frost-iconbtn--lg{width:36px;height:36px;font-size:18px;}
.frost-iconbtn--filled{
  color:#fff;background:linear-gradient(180deg,#1979f2,var(--blue,#0064e1));
}
.frost-iconbtn--filled:hover{filter:brightness(.97);background:linear-gradient(180deg,#1979f2,var(--blue,#0064e1));color:#fff;}
[data-appearance="dark"] .frost-iconbtn:hover{background:rgba(255,255,255,.08);}
`;
  document.head.appendChild(el);
}

export function IconButton({
  icon,
  label,
  size = "md",
  active = false,
  filled = false,
  disabled = false,
  style,
  ...rest
}) {
  ensureStyles();
  const cls = [
    "frost-iconbtn",
    size === "lg" ? "frost-iconbtn--lg" : "",
    active ? "frost-iconbtn--active" : "",
    filled ? "frost-iconbtn--filled" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <button
      type="button"
      className={cls}
      aria-label={label}
      title={label}
      disabled={disabled}
      style={style}
      {...rest}
    >
      <i className={`ph ph-${icon}`} />
    </button>
  );
}
