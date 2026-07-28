import React from "react";

/* Frost ToolChip — the agent execution chip. A recessed pill with a blue icon,
   a short label, and an optional mono datum (file name, tool id). `running`
   shows a spinning loader; `done` a check. Self-aligns to the start. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "tool-chip");
  el.textContent = `
@keyframes frost-spin{to{transform:rotate(360deg);}}
.frost-toolchip{
  display:inline-flex;align-items:center;gap:8px;align-self:flex-start;
  padding:6px 12px;border-radius:999px;
  background:var(--surface-2,#f5f6f8);box-shadow:inset 0 0 0 1px var(--separator);
  font-family:var(--font-ui);font-size:12px;color:var(--label-2,#55555e);
}
.frost-toolchip__icon{color:var(--blue,#0064e1);font-size:14px;display:grid;place-items:center;}
.frost-toolchip__icon.is-spinning{animation:frost-spin 1s linear infinite;}
.frost-toolchip__mono{
  font-family:var(--font-mono);font-size:11px;color:var(--label-3,#6b6b76);letter-spacing:0;
}
.frost-toolchip--done .frost-toolchip__icon{color:var(--green-text,#1d8f45);}
`;
  document.head.appendChild(el);
}

export function ToolChip({ icon = "sparkle", label, mono, running = false, done = false, style, ...rest }) {
  ensureStyles();
  const resolved = running ? "circle-notch" : done ? "check-circle" : icon;
  const cls = ["frost-toolchip", done ? "frost-toolchip--done" : ""].filter(Boolean).join(" ");
  return (
    <span className={cls} style={style} {...rest}>
      <span className={`frost-toolchip__icon${running ? " is-spinning" : ""}`}>
        <i className={`ph ph-${resolved}`} />
      </span>
      {label}
      {mono ? <span className="frost-toolchip__mono">{mono}</span> : null}
    </span>
  );
}
