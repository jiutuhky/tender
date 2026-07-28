import React from "react";

/* Frost Checkbox — 18px rounded box, blue gradient fill + white check when on,
   hairline-ringed surface when off. Optional trailing label. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "checkbox");
  el.textContent = `
.frost-check-row{display:inline-flex;align-items:center;gap:10px;cursor:pointer;}
.frost-check-row[data-disabled="true"]{opacity:.4;pointer-events:none;}
.frost-check{
  width:var(--checkbox,18px);height:var(--checkbox,18px);border-radius:5px;
  display:inline-grid;place-items:center;flex:none;
  background:var(--surface,#fff);box-shadow:inset 0 0 0 1px var(--separator,rgba(60,60,67,.2));
  color:transparent;font-size:12px;
  transition:background var(--t-micro,120ms) var(--ease-std),
             box-shadow var(--t-micro,120ms) var(--ease-std);
}
.frost-check.is-on{
  background:linear-gradient(180deg,#1979f2,var(--blue,#0064e1));color:#fff;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.25);
}
.frost-check.is-indeterminate{
  background:linear-gradient(180deg,#1979f2,var(--blue,#0064e1));color:#fff;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.25);
}
.frost-check__label{font-size:14px;color:var(--label,#1d1d1f);}
`;
  document.head.appendChild(el);
}

export function Checkbox({
  checked,
  defaultChecked = false,
  indeterminate = false,
  onChange,
  disabled = false,
  label,
  style,
  ...rest
}) {
  ensureStyles();
  const [internal, setInternal] = React.useState(defaultChecked);
  const on = checked !== undefined ? checked : internal;
  const toggle = () => {
    const next = !on;
    if (checked === undefined) setInternal(next);
    onChange && onChange(next);
  };
  const cls = [
    "frost-check",
    on && !indeterminate ? "is-on" : "",
    indeterminate ? "is-indeterminate" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <label
      className="frost-check-row"
      data-disabled={disabled}
      style={style}
      onClick={toggle}
      {...rest}
    >
      <span
        className={cls}
        role="checkbox"
        aria-checked={indeterminate ? "mixed" : on}
      >
        <i className={`ph ph-${indeterminate ? "minus" : "check"}`} style={{ fontWeight: 700 }} />
      </span>
      {label ? <span className="frost-check__label">{label}</span> : null}
    </label>
  );
}
