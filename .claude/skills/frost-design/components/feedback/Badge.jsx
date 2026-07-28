import React from "react";

/* Frost Badge — small status pill. Semantic tones use the TEXT value of each
   pair on a soft tint of the GRAPHIC value, so contrast stays legible.
   `dot` renders a leading status dot in the graphic color. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "badge");
  el.textContent = `
.frost-badge{
  display:inline-flex;align-items:center;gap:5px;
  padding:1px 8px;border-radius:999px;
  font-family:var(--font-ui);font-size:11px;font-weight:600;line-height:1.6;
  white-space:nowrap;
}
.frost-badge__dot{width:6px;height:6px;border-radius:50%;flex:none;}
.frost-badge--neutral{color:var(--label-2,#55555e);background:rgba(60,60,67,.10);}
.frost-badge--blue{color:var(--blue,#0064e1);background:var(--blue-soft,rgba(0,100,225,.1));}
.frost-badge--green{color:var(--green-text,#1d8f45);background:rgba(52,199,89,.15);}
.frost-badge--orange{color:var(--orange-text,#b25e00);background:rgba(255,149,0,.15);}
.frost-badge--red{color:var(--red-text,#d70015);background:rgba(255,59,48,.13);}
.frost-badge--solid{color:#fff;}
.frost-badge--solid.frost-badge--blue{background:var(--blue,#0064e1);}
.frost-badge--solid.frost-badge--green{background:var(--green,#34c759);}
.frost-badge--solid.frost-badge--orange{background:var(--orange,#ff9500);}
.frost-badge--solid.frost-badge--red{background:var(--red,#ff3b30);}
.frost-badge--solid.frost-badge--neutral{background:var(--label-2,#55555e);}
`;
  document.head.appendChild(el);
}

const DOT = { neutral: "#8a8a93", blue: "var(--blue,#0064e1)", green: "var(--green,#34c759)", orange: "var(--orange,#ff9500)", red: "var(--red,#ff3b30)" };

export function Badge({ tone = "neutral", solid = false, dot = false, children, style, ...rest }) {
  ensureStyles();
  const cls = ["frost-badge", `frost-badge--${tone}`, solid ? "frost-badge--solid" : ""].filter(Boolean).join(" ");
  return (
    <span className={cls} style={style} {...rest}>
      {dot ? <span className="frost-badge__dot" style={{ background: solid ? "rgba(255,255,255,.9)" : DOT[tone] }} /> : null}
      {children}
    </span>
  );
}
