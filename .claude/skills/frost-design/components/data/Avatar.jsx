import React from "react";

/* Frost Avatar — a rounded-square (continuous-corner) identity tile, in keeping
   with the icon language rather than a circle. Renders an image, or initials on
   a soft-blue tint. Optional status dot. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "avatar");
  el.textContent = `
.frost-avatar{
  position:relative;display:inline-grid;place-items:center;flex:none;
  border-radius:30%;overflow:visible;
  background:var(--blue-soft,rgba(0,100,225,.1));color:var(--blue,#0064e1);
  font-family:var(--font-ui);font-weight:600;
  box-shadow:inset 0 0 0 .5px rgba(18,24,38,.08);
}
.frost-avatar img{width:100%;height:100%;object-fit:cover;border-radius:inherit;display:block;}
.frost-avatar--circle{border-radius:50%;}
.frost-avatar__status{
  position:absolute;right:-1px;bottom:-1px;border-radius:50%;
  box-shadow:0 0 0 2px var(--surface,#fff);
}
`;
  document.head.appendChild(el);
}

const STATUS = { online: "var(--green,#34c759)", busy: "var(--red,#ff3b30)", away: "var(--orange,#ff9500)", offline: "#b6b6bd" };

export function Avatar({ src, name = "", size = 32, shape = "squircle", status, style, ...rest }) {
  ensureStyles();
  const initials = name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((s) => s[0])
    .join("")
    .toUpperCase() || (name ? name[0] : "");
  const dot = Math.max(8, Math.round(size * 0.3));
  return (
    <span
      className={`frost-avatar${shape === "circle" ? " frost-avatar--circle" : ""}`}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.4), ...style }}
      {...rest}
    >
      {src ? <img src={src} alt={name} /> : <span>{initials}</span>}
      {status ? (
        <span className="frost-avatar__status" style={{ width: dot, height: dot, background: STATUS[status] }} />
      ) : null}
    </span>
  );
}
