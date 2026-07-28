import React from "react";

/* Frost Button — macOS control semantics.
   primary: blue gradient + top highlight · default: white raised · plain: text-blue.
   Styling rides the Frost CSS custom properties; interactive states are real
   CSS pseudo-classes injected once. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "button");
  el.textContent = `
.frost-btn{
  display:inline-flex;align-items:center;justify-content:center;gap:7px;
  height:var(--control-h,32px);padding:0 16px;border:none;
  border-radius:var(--r-control,7px);
  font-family:var(--font-ui);font-size:13px;font-weight:600;
  letter-spacing:var(--tracking-ui,-.008em);white-space:nowrap;cursor:pointer;
  transition:transform var(--t-micro,120ms) var(--ease-std),
             background var(--t-micro,120ms) var(--ease-std),
             box-shadow var(--t-micro,120ms) var(--ease-std);
}
.frost-btn:active{transform:scale(.97);}
.frost-btn[disabled]{opacity:.4;pointer-events:none;}
.frost-btn--sm{height:var(--control-h-sm,28px);padding:0 12px;font-size:12px;}
.frost-btn--lg{height:38px;padding:0 20px;font-size:14px;}
.frost-btn--primary{
  color:#fff;background:linear-gradient(180deg,#1979f2 0%,var(--blue,#0064e1) 100%);
  box-shadow:0 1px 2px rgba(0,80,190,.35),inset 0 1px 0 rgba(255,255,255,.25);
}
.frost-btn--primary:hover{background:linear-gradient(180deg,#1571e4 0%,var(--blue-press,#0052bc) 100%);}
.frost-btn--default{color:var(--label,#1d1d1f);background:var(--surface,#fff);box-shadow:var(--elev-1);}
.frost-btn--default:hover{background:var(--surface-2,#f5f6f8);}
.frost-btn--plain{color:var(--blue,#0064e1);background:transparent;}
.frost-btn--plain:hover{background:var(--blue-soft,rgba(0,100,225,.1));}
.frost-btn--danger{
  color:#fff;background:linear-gradient(180deg,#ff5247 0%,var(--red,#ff3b30) 100%);
  box-shadow:0 1px 2px rgba(190,0,20,.3),inset 0 1px 0 rgba(255,255,255,.25);
}
.frost-btn--danger:hover{filter:brightness(.95);}
`;
  document.head.appendChild(el);
}

export function Button({
  variant = "default",
  size = "md",
  icon,
  iconRight,
  disabled = false,
  type = "button",
  children,
  style,
  ...rest
}) {
  ensureStyles();
  const cls = [
    "frost-btn",
    `frost-btn--${variant}`,
    size === "sm" ? "frost-btn--sm" : size === "lg" ? "frost-btn--lg" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <button type={type} className={cls} disabled={disabled} style={style} {...rest}>
      {icon ? <i className={`ph ph-${icon}`} style={{ fontSize: "15px" }} /> : null}
      {children}
      {iconRight ? <i className={`ph ph-${iconRight}`} style={{ fontSize: "15px" }} /> : null}
    </button>
  );
}
