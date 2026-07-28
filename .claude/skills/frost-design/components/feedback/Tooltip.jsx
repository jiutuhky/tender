import React from "react";

/* Frost Tooltip — a small dark label that appears on hover/focus of its child.
   Wraps a single trigger; positions above by default. Pure CSS show/hide so it
   works without timers. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "tooltip");
  el.textContent = `
.frost-tip{position:relative;display:inline-flex;}
.frost-tip__bubble{
  position:absolute;z-index:60;pointer-events:none;
  padding:4px 9px;border-radius:7px;white-space:nowrap;
  font-family:var(--font-ui);font-size:12px;font-weight:500;color:#fff;
  background:rgba(28,28,32,.92);box-shadow:var(--elev-2);
  opacity:0;transform:translateY(2px) scale(.96);transform-origin:center bottom;
  transition:opacity var(--t-float,200ms) var(--ease-std),transform var(--t-float,200ms) var(--ease-std);
}
.frost-tip:hover .frost-tip__bubble,
.frost-tip:focus-within .frost-tip__bubble{opacity:1;transform:translateY(0) scale(1);}
.frost-tip__bubble--top{left:50%;bottom:calc(100% + 7px);translate:-50% 0;}
.frost-tip__bubble--bottom{left:50%;top:calc(100% + 7px);translate:-50% 0;transform-origin:center top;}
.frost-tip__bubble--left{right:calc(100% + 7px);top:50%;translate:0 -50%;}
.frost-tip__bubble--right{left:calc(100% + 7px);top:50%;translate:0 -50%;}
`;
  document.head.appendChild(el);
}

export function Tooltip({ label, side = "top", children, style, ...rest }) {
  ensureStyles();
  return (
    <span className="frost-tip" style={style} {...rest}>
      {children}
      <span className={`frost-tip__bubble frost-tip__bubble--${side}`} role="tooltip">
        {label}
      </span>
    </span>
  );
}
