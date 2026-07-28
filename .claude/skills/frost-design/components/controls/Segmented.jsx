import React from "react";

/* Frost Segmented — macOS segmented control. Recessed gray track, the selected
   segment rides up on a white slider with a soft shadow. Controlled or
   uncontrolled. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "segmented");
  el.textContent = `
.frost-seg{
  display:inline-flex;padding:2px;gap:2px;
  background:rgba(60,60,67,.09);border-radius:var(--r-field,9px);
}
.frost-seg button{
  height:var(--control-h-sm,28px);padding:0 18px;border:none;border-radius:7px;
  font-family:var(--font-ui);font-size:13px;font-weight:500;
  color:var(--label-2,#55555e);background:transparent;cursor:pointer;
  transition:all var(--t-micro,120ms) var(--ease-std);
}
.frost-seg button:hover:not(.is-active){color:var(--label,#1d1d1f);}
.frost-seg button.is-active{
  background:var(--surface,#fff);color:var(--label,#1d1d1f);font-weight:600;
  box-shadow:0 1px 3px rgba(18,24,38,.16),0 0 0 .5px rgba(18,24,38,.05);
}
[data-appearance="dark"] .frost-seg{background:rgba(255,255,255,.08);}
[data-appearance="dark"] .frost-seg button.is-active{background:var(--surface-2,#2a2a30);}
`;
  document.head.appendChild(el);
}

export function Segmented({ options = [], value, defaultValue, onChange, style, ...rest }) {
  ensureStyles();
  const norm = options.map((o) => (typeof o === "string" ? { value: o, label: o } : o));
  const [internal, setInternal] = React.useState(
    defaultValue ?? (norm[0] && norm[0].value)
  );
  const current = value !== undefined ? value : internal;
  const pick = (v) => {
    if (value === undefined) setInternal(v);
    onChange && onChange(v);
  };
  return (
    <div className="frost-seg" role="tablist" style={style} {...rest}>
      {norm.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={current === o.value}
          className={current === o.value ? "is-active" : ""}
          onClick={() => pick(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
