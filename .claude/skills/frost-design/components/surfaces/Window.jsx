import React from "react";

/* Frost Window — macOS window chrome. A soft-glass (霜) toolbar with
   traffic-light dots, title + subtitle, and a trailing actions slot; rounded
   window corners and a level-3 floating shadow. The toolbar meets the body on
   a .5px contact edge, not a 1px line. Children render in the body below. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "window");
  el.textContent = `
.frost-window{
  border-radius:var(--r-window,12px);overflow:hidden;
  box-shadow:var(--elev-3);display:flex;flex-direction:column;
  background:var(--surface,#fff);
}
.frost-window__toolbar{
  height:var(--toolbar-h,52px);flex:none;
  display:flex;align-items:center;gap:14px;padding:0 16px;
  box-shadow:inset 0 -.5px 0 var(--separator);
}
.frost-window__traffic{display:flex;gap:8px;}
.frost-window__traffic span{width:12px;height:12px;border-radius:50%;display:block;}
.frost-window__title{font-size:13px;font-weight:600;color:var(--label,#1d1d1f);}
.frost-window__sub{font-size:13px;color:var(--label-3,#6b6b76);}
.frost-window__spacer{flex:1;}
.frost-window__actions{display:flex;align-items:center;gap:8px;}
.frost-window__body{flex:1;min-height:0;display:flex;}
`;
  document.head.appendChild(el);
}

export function Window({
  title,
  subtitle,
  actions,
  traffic = true,
  toolbarClassName = "frost-glass frost-glass--soft frost-glass--flush",
  children,
  style,
  ...rest
}) {
  ensureStyles();
  return (
    <div className="frost-window" style={style} {...rest}>
      <div className={`frost-window__toolbar ${toolbarClassName}`}>
        {traffic ? (
          <span className="frost-window__traffic">
            <span style={{ background: "var(--traffic-close,#ff5f57)" }} />
            <span style={{ background: "var(--traffic-min,#febc2e)" }} />
            <span style={{ background: "var(--traffic-max,#28c840)" }} />
          </span>
        ) : null}
        {title ? <span className="frost-window__title">{title}</span> : null}
        {subtitle ? <span className="frost-window__sub">{subtitle}</span> : null}
        <span className="frost-window__spacer" />
        {actions ? <span className="frost-window__actions">{actions}</span> : null}
      </div>
      <div className="frost-window__body">{children}</div>
    </div>
  );
}
