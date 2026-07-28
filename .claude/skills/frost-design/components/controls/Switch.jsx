import React from "react";

/* Frost Switch — macOS toggle. 42×26 track, white knob with a soft shadow,
   track turns blue when on. Controlled or uncontrolled. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "switch");
  el.textContent = `
.frost-switch{
  width:var(--switch-w,42px);height:var(--switch-h,26px);border-radius:999px;
  border:none;padding:2px;background:rgba(60,60,67,.26);display:inline-flex;
  cursor:pointer;flex:none;
  transition:background var(--t-float,200ms) var(--ease-std);
}
.frost-switch .frost-switch__knob{
  width:var(--switch-knob,22px);height:var(--switch-knob,22px);border-radius:50%;
  background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.25);
  transition:transform var(--t-float,200ms) var(--ease-std);
}
.frost-switch.is-on{background:var(--blue,#0064e1);}
.frost-switch.is-on .frost-switch__knob{transform:translateX(16px);}
.frost-switch[disabled]{opacity:.4;pointer-events:none;}
.frost-switch-row{display:inline-flex;align-items:center;gap:14px;}
.frost-switch-row .frost-switch__label{font-size:14px;color:var(--label,#1d1d1f);}
`;
  document.head.appendChild(el);
}

export function Switch({
  checked,
  defaultChecked = false,
  onChange,
  disabled = false,
  label,
  id,
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
  const sw = (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={on}
      aria-label={!label ? rest["aria-label"] : undefined}
      className={`frost-switch${on ? " is-on" : ""}`}
      disabled={disabled}
      onClick={toggle}
      style={!label ? style : undefined}
      {...rest}
    >
      <span className="frost-switch__knob" />
    </button>
  );
  if (!label) return sw;
  return (
    <span className="frost-switch-row" style={style}>
      {sw}
      <span className="frost-switch__label" onClick={toggle} style={{ cursor: "pointer" }}>
        {label}
      </span>
    </span>
  );
}
