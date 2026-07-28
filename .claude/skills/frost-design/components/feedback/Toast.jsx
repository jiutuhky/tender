import React from "react";

/* Frost Toast — a floating popover-glass notification. Leading status icon in
   the semantic color, title + optional detail, optional action + dismiss. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "toast");
  el.textContent = `
.frost-toast{
  display:flex;align-items:flex-start;gap:11px;
  min-width:280px;max-width:420px;padding:13px 14px;
  border-radius:var(--r-card,14px);
}
.frost-toast__icon{font-size:18px;display:grid;place-items:center;margin-top:1px;flex:none;}
.frost-toast--info .frost-toast__icon{color:var(--blue,#0064e1);}
.frost-toast--success .frost-toast__icon{color:var(--green,#34c759);}
.frost-toast--warning .frost-toast__icon{color:var(--orange,#ff9500);}
.frost-toast--danger .frost-toast__icon{color:var(--red,#ff3b30);}
.frost-toast__body{flex:1;min-width:0;}
.frost-toast__title{font-size:13px;font-weight:600;color:var(--label,#1d1d1f);line-height:1.45;}
.frost-toast__detail{font-size:12px;color:var(--label-2,#55555e);line-height:1.5;margin-top:2px;}
.frost-toast__action{
  margin-top:8px;display:inline-flex;font-size:12px;font-weight:600;
  color:var(--blue,#0064e1);background:none;border:none;padding:0;cursor:pointer;
}
.frost-toast__close{
  flex:none;border:none;background:transparent;cursor:pointer;
  color:var(--label-3,#6b6b76);font-size:15px;display:grid;place-items:center;
  width:22px;height:22px;border-radius:6px;margin:-2px -2px 0 0;
}
.frost-toast__close:hover{background:rgba(60,60,67,.09);color:var(--label,#1d1d1f);}
`;
  document.head.appendChild(el);
}

const ICON = { info: "info", success: "check-circle", warning: "warning", danger: "x-circle" };

export function Toast({ tone = "info", icon, title, detail, action, onAction, onClose, style, ...rest }) {
  ensureStyles();
  return (
    <div className={`frost-toast frost-glass-popover frost-toast--${tone}`} role="status" style={style} {...rest}>
      <span className="frost-toast__icon"><i className={`ph ph-${icon || ICON[tone]}`} /></span>
      <div className="frost-toast__body">
        {title ? <div className="frost-toast__title">{title}</div> : null}
        {detail ? <div className="frost-toast__detail">{detail}</div> : null}
        {action ? <button className="frost-toast__action" onClick={onAction}>{action}</button> : null}
      </div>
      {onClose ? (
        <button className="frost-toast__close" aria-label="关闭" onClick={onClose}>
          <i className="ph ph-x" />
        </button>
      ) : null}
    </div>
  );
}
