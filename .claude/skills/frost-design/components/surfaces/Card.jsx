import React from "react";

/* Frost Card — the basic raised surface. White background, level-1 elevation,
   card radius. `material` swaps the solid fill for glass (sits on the
   wallpaper): "lens" refracts (control layer), "soft" is frosted (chrome).
   `thickness` sets blur / lens strength / shadow together. `inset` uses the
   recessed gray fill instead of a raised surface. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "card");
  el.textContent = `
.frost-card{
  background:var(--surface,#fff);border-radius:var(--r-card,14px);
  box-shadow:var(--elev-1);padding:24px;
}
.frost-card--inset{background:var(--surface-2,#f5f6f8);box-shadow:inset 0 0 0 1px var(--separator);}
.frost-card--raised{box-shadow:var(--elev-2);}
.frost-card--panel{border-radius:var(--r-panel,18px);padding:32px;}
.frost-card--pad-sm{padding:16px;}
.frost-card--pad-lg{padding:36px;}
.frost-card__title{margin:0 0 8px;font-size:16px;font-weight:700;color:var(--label,#1d1d1f);letter-spacing:var(--tracking-title,-.014em);}
.frost-card__body{margin:0;color:var(--label-2,#55555e);font-size:14px;line-height:1.6;}
.frost-glass .frost-card__title{color:inherit;}
`;
  document.head.appendChild(el);
}

export function Card({
  material,        // "lens" | "soft"
  thickness,       // "thin" | "regular" | "thick"
  interactive = false,
  inset = false,
  raised = false,
  panel = false,
  pad,             // "sm" | "lg"
  title,
  children,
  className = "",
  style,
  ...rest
}) {
  ensureStyles();
  const glass = material ? `frost-glass frost-glass--${material}${interactive ? " frost-glass--interactive" : ""}` : "";
  const cls = [
    glass ? "" : "frost-card",
    glass,
    inset ? "frost-card--inset" : "",
    raised ? "frost-card--raised" : "",
    panel ? "frost-card--panel" : "",
    pad === "sm" ? "frost-card--pad-sm" : pad === "lg" ? "frost-card--pad-lg" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");
  // Lens panels take 20px: the rim needs room to turn the corner (18 pinches it).
  const glassStyle = glass
    ? { borderRadius: panel ? "20px" : "var(--r-card,14px)", padding: pad === "sm" ? 16 : pad === "lg" ? 36 : 24 }
    : undefined;
  const thick = glass ? thickness || (panel ? "thick" : "regular") : undefined;
  return (
    <div className={cls} data-thick={thick} style={{ ...glassStyle, ...style }} {...rest}>
      {title ? <h3 className="frost-card__title">{title}</h3> : null}
      {title ? <div className="frost-card__body">{children}</div> : children}
    </div>
  );
}
