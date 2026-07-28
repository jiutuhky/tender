import React from "react";

/* Frost Field — text/search input. Inset hairline ring at rest, blue ring +
   soft halo on focus. Optional leading icon and trailing slot (e.g. a send
   button). Controlled or uncontrolled. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "field");
  el.textContent = `
.frost-field{
  display:flex;align-items:center;gap:9px;
  height:var(--field-h,36px);padding:0 13px;
  background:var(--surface,#fff);border-radius:var(--r-field,9px);
  box-shadow:inset 0 0 0 1px var(--separator,rgba(60,60,67,.12));
  transition:box-shadow var(--t-micro,120ms) var(--ease-std);
}
.frost-field:focus-within{
  box-shadow:inset 0 0 0 1px var(--blue,#0064e1),0 0 0 3px rgba(0,100,225,.18);
}
.frost-field--lg{height:var(--field-h-lg,44px);border-radius:14px;box-shadow:var(--elev-1);}
.frost-field--lg:focus-within{box-shadow:var(--elev-1),0 0 0 3px rgba(0,100,225,.18);}
.frost-field__icon{color:var(--label-3,#6b6b76);font-size:15px;display:grid;place-items:center;}
.frost-field input{
  border:none;outline:none;background:transparent;flex:1;min-width:0;
  font-family:var(--font-ui);font-size:13px;color:var(--label,#1d1d1f);
}
.frost-field input::placeholder{color:var(--label-3,#6b6b76);}
.frost-field[data-disabled="true"]{opacity:.5;pointer-events:none;}
`;
  document.head.appendChild(el);
}

export function Field({
  icon,
  trailing,
  size = "md",
  type = "text",
  value,
  defaultValue,
  onChange,
  placeholder,
  disabled = false,
  style,
  inputProps = {},
  ...rest
}) {
  ensureStyles();
  const cls = ["frost-field", size === "lg" ? "frost-field--lg" : ""].filter(Boolean).join(" ");
  return (
    <label className={cls} data-disabled={disabled} style={style} {...rest}>
      {icon ? <span className="frost-field__icon"><i className={`ph ph-${icon}`} /></span> : null}
      <input
        type={type}
        value={value}
        defaultValue={defaultValue}
        placeholder={placeholder}
        disabled={disabled}
        onChange={onChange}
        {...inputProps}
      />
      {trailing}
    </label>
  );
}
