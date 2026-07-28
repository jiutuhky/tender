/* @ds-bundle: {"format":3,"namespace":"FrostDesignSystemProse_5680eb","components":[{"name":"Button","sourcePath":"components/controls/Button.jsx"},{"name":"Checkbox","sourcePath":"components/controls/Checkbox.jsx"},{"name":"IconButton","sourcePath":"components/controls/IconButton.jsx"},{"name":"Segmented","sourcePath":"components/controls/Segmented.jsx"},{"name":"Switch","sourcePath":"components/controls/Switch.jsx"},{"name":"Avatar","sourcePath":"components/data/Avatar.jsx"},{"name":"Badge","sourcePath":"components/feedback/Badge.jsx"},{"name":"Toast","sourcePath":"components/feedback/Toast.jsx"},{"name":"ToolChip","sourcePath":"components/feedback/ToolChip.jsx"},{"name":"Tooltip","sourcePath":"components/feedback/Tooltip.jsx"},{"name":"Field","sourcePath":"components/forms/Field.jsx"},{"name":"Menu","sourcePath":"components/navigation/Menu.jsx"},{"name":"SidebarGroup","sourcePath":"components/navigation/SidebarItem.jsx"},{"name":"SidebarItem","sourcePath":"components/navigation/SidebarItem.jsx"},{"name":"Card","sourcePath":"components/surfaces/Card.jsx"},{"name":"Window","sourcePath":"components/surfaces/Window.jsx"}],"sourceHashes":{"components/controls/Button.jsx":"0b1f092ee372","components/controls/Checkbox.jsx":"3e5a3c2f3c59","components/controls/IconButton.jsx":"169c81fbe8f0","components/controls/Segmented.jsx":"09b3a48a9fe6","components/controls/Switch.jsx":"3a93dedcf5d8","components/data/Avatar.jsx":"9676281b0b97","components/feedback/Badge.jsx":"d5a8a3002c0e","components/feedback/Toast.jsx":"8c64cf4f317c","components/feedback/ToolChip.jsx":"ae1ddf9923c7","components/feedback/Tooltip.jsx":"ab1a28069fde","components/forms/Field.jsx":"e3c4a20fdfa8","components/navigation/Menu.jsx":"f9cc87323741","components/navigation/SidebarItem.jsx":"b11a90c7f19c","components/surfaces/Card.jsx":"d24d6e3f0cc4","components/surfaces/Window.jsx":"197cc7635024","ui_kits/prose/AgentStream.jsx":"0024bbac4023","ui_kits/prose/DocOutline.jsx":"d769d577eefa","ui_kits/prose/ProseApp.jsx":"ef9ab51323ae","ui_kits/prose/Sidebar.jsx":"70a5cf8b59a2","ui_kits/prose/data.js":"a9a87264ddaa"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.FrostDesignSystemProse_5680eb = window.FrostDesignSystemProse_5680eb || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/controls/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Frost Button — macOS control semantics.
   primary: blue gradient + top highlight · default: white raised · plain: text-blue.
   Styling rides the Frost CSS custom properties; interactive states are real
   CSS pseudo-classes injected once. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "button");
  el.textContent = `
.frost-btn{
  display:inline-flex;align-items:center;justify-content:center;gap:7px;
  height:var(--control-h,32px);padding:0 16px;border:none;
  border-radius:var(--r-control,7px);
  font-family:var(--font-ui);font-size:13px;font-weight:600;
  letter-spacing:var(--tracking-ui,-.008em);white-space:nowrap;cursor:pointer;
  transition:transform var(--t-micro,120ms) var(--ease-std),
             background var(--t-micro,120ms) var(--ease-std),
             box-shadow var(--t-micro,120ms) var(--ease-std);
}
.frost-btn:active{transform:scale(.97);}
.frost-btn[disabled]{opacity:.4;pointer-events:none;}
.frost-btn--sm{height:var(--control-h-sm,28px);padding:0 12px;font-size:12px;}
.frost-btn--lg{height:38px;padding:0 20px;font-size:14px;}
.frost-btn--primary{
  color:#fff;background:linear-gradient(180deg,#1979f2 0%,var(--blue,#0064e1) 100%);
  box-shadow:0 1px 2px rgba(0,80,190,.35),inset 0 1px 0 rgba(255,255,255,.25);
}
.frost-btn--primary:hover{background:linear-gradient(180deg,#1571e4 0%,var(--blue-press,#0052bc) 100%);}
.frost-btn--default{color:var(--label,#1d1d1f);background:var(--surface,#fff);box-shadow:var(--elev-1);}
.frost-btn--default:hover{background:var(--surface-2,#f5f6f8);}
.frost-btn--plain{color:var(--blue,#0064e1);background:transparent;}
.frost-btn--plain:hover{background:var(--blue-soft,rgba(0,100,225,.1));}
.frost-btn--danger{
  color:#fff;background:linear-gradient(180deg,#ff5247 0%,var(--red,#ff3b30) 100%);
  box-shadow:0 1px 2px rgba(190,0,20,.3),inset 0 1px 0 rgba(255,255,255,.25);
}
.frost-btn--danger:hover{filter:brightness(.95);}
`;
  document.head.appendChild(el);
}
function Button({
  variant = "default",
  size = "md",
  icon,
  iconRight,
  disabled = false,
  type = "button",
  children,
  style,
  ...rest
}) {
  ensureStyles();
  const cls = ["frost-btn", `frost-btn--${variant}`, size === "sm" ? "frost-btn--sm" : size === "lg" ? "frost-btn--lg" : ""].filter(Boolean).join(" ");
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    className: cls,
    disabled: disabled,
    style: style
  }, rest), icon ? /*#__PURE__*/React.createElement("i", {
    className: `ph ph-${icon}`,
    style: {
      fontSize: "15px"
    }
  }) : null, children, iconRight ? /*#__PURE__*/React.createElement("i", {
    className: `ph ph-${iconRight}`,
    style: {
      fontSize: "15px"
    }
  }) : null);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/controls/Button.jsx", error: String((e && e.message) || e) }); }

// components/controls/Checkbox.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
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
function Checkbox({
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
  const cls = ["frost-check", on && !indeterminate ? "is-on" : "", indeterminate ? "is-indeterminate" : ""].filter(Boolean).join(" ");
  return /*#__PURE__*/React.createElement("label", _extends({
    className: "frost-check-row",
    "data-disabled": disabled,
    style: style,
    onClick: toggle
  }, rest), /*#__PURE__*/React.createElement("span", {
    className: cls,
    role: "checkbox",
    "aria-checked": indeterminate ? "mixed" : on
  }, /*#__PURE__*/React.createElement("i", {
    className: `ph ph-${indeterminate ? "minus" : "check"}`,
    style: {
      fontWeight: 700
    }
  })), label ? /*#__PURE__*/React.createElement("span", {
    className: "frost-check__label"
  }, label) : null);
}
Object.assign(__ds_scope, { Checkbox });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/controls/Checkbox.jsx", error: String((e && e.message) || e) }); }

// components/controls/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Frost IconButton — the bare toolbar / inline icon control. Square, transparent
   at rest, soft gray fill on hover. Use for window-toolbar actions and inline
   affordances. Always pass an aria-label. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "icon-button");
  el.textContent = `
.frost-iconbtn{
  display:inline-grid;place-items:center;border:none;background:transparent;
  color:var(--label-2,#55555e);cursor:pointer;
  width:30px;height:30px;border-radius:var(--r-control,7px);font-size:16px;
  transition:background var(--t-micro,120ms) var(--ease-std),
             color var(--t-micro,120ms) var(--ease-std),
             transform var(--t-micro,120ms) var(--ease-std);
}
.frost-iconbtn:hover{background:rgba(60,60,67,.09);color:var(--label,#1d1d1f);}
.frost-iconbtn:active{transform:scale(.92);}
.frost-iconbtn[disabled]{opacity:.4;pointer-events:none;}
.frost-iconbtn--active{background:var(--blue-soft,rgba(0,100,225,.1));color:var(--blue,#0064e1);}
.frost-iconbtn--lg{width:36px;height:36px;font-size:18px;}
.frost-iconbtn--filled{
  color:#fff;background:linear-gradient(180deg,#1979f2,var(--blue,#0064e1));
}
.frost-iconbtn--filled:hover{filter:brightness(.97);background:linear-gradient(180deg,#1979f2,var(--blue,#0064e1));color:#fff;}
[data-appearance="dark"] .frost-iconbtn:hover{background:rgba(255,255,255,.08);}
`;
  document.head.appendChild(el);
}
function IconButton({
  icon,
  label,
  size = "md",
  active = false,
  filled = false,
  disabled = false,
  style,
  ...rest
}) {
  ensureStyles();
  const cls = ["frost-iconbtn", size === "lg" ? "frost-iconbtn--lg" : "", active ? "frost-iconbtn--active" : "", filled ? "frost-iconbtn--filled" : ""].filter(Boolean).join(" ");
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    className: cls,
    "aria-label": label,
    title: label,
    disabled: disabled,
    style: style
  }, rest), /*#__PURE__*/React.createElement("i", {
    className: `ph ph-${icon}`
  }));
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/controls/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/controls/Segmented.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
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
function Segmented({
  options = [],
  value,
  defaultValue,
  onChange,
  style,
  ...rest
}) {
  ensureStyles();
  const norm = options.map(o => typeof o === "string" ? {
    value: o,
    label: o
  } : o);
  const [internal, setInternal] = React.useState(defaultValue ?? (norm[0] && norm[0].value));
  const current = value !== undefined ? value : internal;
  const pick = v => {
    if (value === undefined) setInternal(v);
    onChange && onChange(v);
  };
  return /*#__PURE__*/React.createElement("div", _extends({
    className: "frost-seg",
    role: "tablist",
    style: style
  }, rest), norm.map(o => /*#__PURE__*/React.createElement("button", {
    key: o.value,
    role: "tab",
    "aria-selected": current === o.value,
    className: current === o.value ? "is-active" : "",
    onClick: () => pick(o.value)
  }, o.label)));
}
Object.assign(__ds_scope, { Segmented });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/controls/Segmented.jsx", error: String((e && e.message) || e) }); }

// components/controls/Switch.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
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
function Switch({
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
  const sw = /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    role: "switch",
    id: id,
    "aria-checked": on,
    "aria-label": !label ? rest["aria-label"] : undefined,
    className: `frost-switch${on ? " is-on" : ""}`,
    disabled: disabled,
    onClick: toggle,
    style: !label ? style : undefined
  }, rest), /*#__PURE__*/React.createElement("span", {
    className: "frost-switch__knob"
  }));
  if (!label) return sw;
  return /*#__PURE__*/React.createElement("span", {
    className: "frost-switch-row",
    style: style
  }, sw, /*#__PURE__*/React.createElement("span", {
    className: "frost-switch__label",
    onClick: toggle,
    style: {
      cursor: "pointer"
    }
  }, label));
}
Object.assign(__ds_scope, { Switch });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/controls/Switch.jsx", error: String((e && e.message) || e) }); }

// components/data/Avatar.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
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
const STATUS = {
  online: "var(--green,#34c759)",
  busy: "var(--red,#ff3b30)",
  away: "var(--orange,#ff9500)",
  offline: "#b6b6bd"
};
function Avatar({
  src,
  name = "",
  size = 32,
  shape = "squircle",
  status,
  style,
  ...rest
}) {
  ensureStyles();
  const initials = name.trim().split(/\s+/).slice(0, 2).map(s => s[0]).join("").toUpperCase() || (name ? name[0] : "");
  const dot = Math.max(8, Math.round(size * 0.3));
  return /*#__PURE__*/React.createElement("span", _extends({
    className: `frost-avatar${shape === "circle" ? " frost-avatar--circle" : ""}`,
    style: {
      width: size,
      height: size,
      fontSize: Math.round(size * 0.4),
      ...style
    }
  }, rest), src ? /*#__PURE__*/React.createElement("img", {
    src: src,
    alt: name
  }) : /*#__PURE__*/React.createElement("span", null, initials), status ? /*#__PURE__*/React.createElement("span", {
    className: "frost-avatar__status",
    style: {
      width: dot,
      height: dot,
      background: STATUS[status]
    }
  }) : null);
}
Object.assign(__ds_scope, { Avatar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/Avatar.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
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
const DOT = {
  neutral: "#8a8a93",
  blue: "var(--blue,#0064e1)",
  green: "var(--green,#34c759)",
  orange: "var(--orange,#ff9500)",
  red: "var(--red,#ff3b30)"
};
function Badge({
  tone = "neutral",
  solid = false,
  dot = false,
  children,
  style,
  ...rest
}) {
  ensureStyles();
  const cls = ["frost-badge", `frost-badge--${tone}`, solid ? "frost-badge--solid" : ""].filter(Boolean).join(" ");
  return /*#__PURE__*/React.createElement("span", _extends({
    className: cls,
    style: style
  }, rest), dot ? /*#__PURE__*/React.createElement("span", {
    className: "frost-badge__dot",
    style: {
      background: solid ? "rgba(255,255,255,.9)" : DOT[tone]
    }
  }) : null, children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Badge.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Toast.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
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
const ICON = {
  info: "info",
  success: "check-circle",
  warning: "warning",
  danger: "x-circle"
};
function Toast({
  tone = "info",
  icon,
  title,
  detail,
  action,
  onAction,
  onClose,
  style,
  ...rest
}) {
  ensureStyles();
  return /*#__PURE__*/React.createElement("div", _extends({
    className: `frost-toast frost-glass-popover frost-toast--${tone}`,
    role: "status",
    style: style
  }, rest), /*#__PURE__*/React.createElement("span", {
    className: "frost-toast__icon"
  }, /*#__PURE__*/React.createElement("i", {
    className: `ph ph-${icon || ICON[tone]}`
  })), /*#__PURE__*/React.createElement("div", {
    className: "frost-toast__body"
  }, title ? /*#__PURE__*/React.createElement("div", {
    className: "frost-toast__title"
  }, title) : null, detail ? /*#__PURE__*/React.createElement("div", {
    className: "frost-toast__detail"
  }, detail) : null, action ? /*#__PURE__*/React.createElement("button", {
    className: "frost-toast__action",
    onClick: onAction
  }, action) : null), onClose ? /*#__PURE__*/React.createElement("button", {
    className: "frost-toast__close",
    "aria-label": "\u5173\u95ED",
    onClick: onClose
  }, /*#__PURE__*/React.createElement("i", {
    className: "ph ph-x"
  })) : null);
}
Object.assign(__ds_scope, { Toast });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Toast.jsx", error: String((e && e.message) || e) }); }

// components/feedback/ToolChip.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
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
function ToolChip({
  icon = "sparkle",
  label,
  mono,
  running = false,
  done = false,
  style,
  ...rest
}) {
  ensureStyles();
  const resolved = running ? "circle-notch" : done ? "check-circle" : icon;
  const cls = ["frost-toolchip", done ? "frost-toolchip--done" : ""].filter(Boolean).join(" ");
  return /*#__PURE__*/React.createElement("span", _extends({
    className: cls,
    style: style
  }, rest), /*#__PURE__*/React.createElement("span", {
    className: `frost-toolchip__icon${running ? " is-spinning" : ""}`
  }, /*#__PURE__*/React.createElement("i", {
    className: `ph ph-${resolved}`
  })), label, mono ? /*#__PURE__*/React.createElement("span", {
    className: "frost-toolchip__mono"
  }, mono) : null);
}
Object.assign(__ds_scope, { ToolChip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/ToolChip.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Tooltip.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Frost Tooltip — a small dark label that appears on hover/focus of its child.
   Wraps a single trigger; positions above by default. Pure CSS show/hide so it
   works without timers. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "tooltip");
  el.textContent = `
.frost-tip{position:relative;display:inline-flex;}
.frost-tip__bubble{
  position:absolute;z-index:60;pointer-events:none;
  padding:4px 9px;border-radius:7px;white-space:nowrap;
  font-family:var(--font-ui);font-size:12px;font-weight:500;color:#fff;
  background:rgba(28,28,32,.92);box-shadow:var(--elev-2);
  opacity:0;transform:translateY(2px) scale(.96);transform-origin:center bottom;
  transition:opacity var(--t-float,200ms) var(--ease-std),transform var(--t-float,200ms) var(--ease-std);
}
.frost-tip:hover .frost-tip__bubble,
.frost-tip:focus-within .frost-tip__bubble{opacity:1;transform:translateY(0) scale(1);}
.frost-tip__bubble--top{left:50%;bottom:calc(100% + 7px);translate:-50% 0;}
.frost-tip__bubble--bottom{left:50%;top:calc(100% + 7px);translate:-50% 0;transform-origin:center top;}
.frost-tip__bubble--left{right:calc(100% + 7px);top:50%;translate:0 -50%;}
.frost-tip__bubble--right{left:calc(100% + 7px);top:50%;translate:0 -50%;}
`;
  document.head.appendChild(el);
}
function Tooltip({
  label,
  side = "top",
  children,
  style,
  ...rest
}) {
  ensureStyles();
  return /*#__PURE__*/React.createElement("span", _extends({
    className: "frost-tip",
    style: style
  }, rest), children, /*#__PURE__*/React.createElement("span", {
    className: `frost-tip__bubble frost-tip__bubble--${side}`,
    role: "tooltip"
  }, label));
}
Object.assign(__ds_scope, { Tooltip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Tooltip.jsx", error: String((e && e.message) || e) }); }

// components/forms/Field.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
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
function Field({
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
  return /*#__PURE__*/React.createElement("label", _extends({
    className: cls,
    "data-disabled": disabled,
    style: style
  }, rest), icon ? /*#__PURE__*/React.createElement("span", {
    className: "frost-field__icon"
  }, /*#__PURE__*/React.createElement("i", {
    className: `ph ph-${icon}`
  })) : null, /*#__PURE__*/React.createElement("input", _extends({
    type: type,
    value: value,
    defaultValue: defaultValue,
    placeholder: placeholder,
    disabled: disabled,
    onChange: onChange
  }, inputProps)), trailing);
}
Object.assign(__ds_scope, { Field });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Field.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Menu.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Frost Menu — a popover-glass context menu. Items take an icon, label, and an
   optional keyboard hint; the hovered row fills full-width blue. Pass items, or
   compose with Menu.Item / Menu.Separator. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "menu");
  el.textContent = `
.frost-menu{
  width:248px;border-radius:var(--r-field,9px);padding:5px;
}
.frost-menu__item{
  display:flex;align-items:center;gap:10px;
  padding:6px 10px;border-radius:6px;font-size:13px;color:var(--label,#1d1d1f);
  cursor:default;user-select:none;
  transition:background var(--t-micro,120ms) var(--ease-std);
}
.frost-menu__item i{font-size:15px;color:var(--label-2,#55555e);width:18px;text-align:center;}
.frost-menu__item .frost-menu__kbd{margin-left:auto;font-family:var(--font-mono);font-size:11px;color:var(--label-3,#6b6b76);}
.frost-menu__item:hover,
.frost-menu__item[data-active="true"]{background:var(--blue,#0064e1);color:#fff;}
.frost-menu__item:hover i,.frost-menu__item[data-active="true"] i,
.frost-menu__item:hover .frost-menu__kbd,.frost-menu__item[data-active="true"] .frost-menu__kbd{color:rgba(255,255,255,.85);}
.frost-menu__item--danger{color:var(--red-text,#d70015);}
.frost-menu__item--danger:hover{background:var(--red,#ff3b30);color:#fff;}
.frost-menu__item--danger:hover i{color:rgba(255,255,255,.85);}
.frost-menu__item[data-disabled="true"]{opacity:.4;pointer-events:none;}
.frost-menu__sep{height:1px;background:var(--separator);margin:5px 10px;}
`;
  document.head.appendChild(el);
}
function Item({
  icon,
  label,
  kbd,
  danger = false,
  active = false,
  disabled = false,
  onSelect,
  ...rest
}) {
  ensureStyles();
  return /*#__PURE__*/React.createElement("div", _extends({
    className: `frost-menu__item${danger ? " frost-menu__item--danger" : ""}`,
    "data-active": active,
    "data-disabled": disabled,
    onClick: onSelect,
    role: "menuitem"
  }, rest), icon ? /*#__PURE__*/React.createElement("i", {
    className: `ph ph-${icon}`
  }) : null, /*#__PURE__*/React.createElement("span", null, label), kbd ? /*#__PURE__*/React.createElement("span", {
    className: "frost-menu__kbd"
  }, kbd) : null);
}
function Separator() {
  return /*#__PURE__*/React.createElement("div", {
    className: "frost-menu__sep"
  });
}
function Menu({
  items,
  children,
  style,
  ...rest
}) {
  ensureStyles();
  return /*#__PURE__*/React.createElement("div", _extends({
    className: "frost-menu frost-glass-popover",
    role: "menu",
    style: style
  }, rest), items ? items.map((it, i) => it === "---" || it.separator ? /*#__PURE__*/React.createElement(Separator, {
    key: i
  }) : /*#__PURE__*/React.createElement(Item, _extends({
    key: i
  }, it))) : children);
}
Menu.Item = Item;
Menu.Separator = Separator;
Object.assign(__ds_scope, { Menu });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Menu.jsx", error: String((e && e.message) || e) }); }

// components/navigation/SidebarItem.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Frost SidebarItem — a row in the glass sidebar. Icon + label, optional
   trailing badge/count; the active row gets the soft-blue backing and a blue
   icon. Use `group` for a section header above a run of items. */

let injected = false;
function ensureStyles() {
  if (injected || typeof document === "undefined") return;
  injected = true;
  const el = document.createElement("style");
  el.setAttribute("data-frost", "sidebar-item");
  el.textContent = `
.frost-sbgroup{font-size:11px;font-weight:600;color:var(--label-3,#6b6b76);padding:12px 10px 5px;}
.frost-sbitem{
  display:flex;align-items:center;gap:9px;
  padding:6px 10px;border-radius:var(--r-control,7px);
  font-size:13px;color:var(--label,#1d1d1f);cursor:default;
  transition:background var(--t-micro,120ms) var(--ease-std);
}
.frost-sbitem:hover:not(.is-active){background:rgba(60,60,67,.07);}
.frost-sbitem i{font-size:15px;color:var(--label-2,#55555e);flex:none;}
.frost-sbitem__label{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.frost-sbitem__trail{margin-left:auto;flex:none;}
.frost-sbitem.is-active{background:var(--blue-soft,rgba(0,100,225,.14));font-weight:600;}
.frost-sbitem.is-active i{color:var(--blue,#0064e1);}
[data-appearance="dark"] .frost-sbitem:hover:not(.is-active){background:rgba(255,255,255,.06);}
`;
  document.head.appendChild(el);
}
function SidebarGroup({
  children
}) {
  ensureStyles();
  return /*#__PURE__*/React.createElement("div", {
    className: "frost-sbgroup"
  }, children);
}
function SidebarItem({
  icon,
  label,
  active = false,
  trailing,
  onClick,
  style,
  ...rest
}) {
  ensureStyles();
  return /*#__PURE__*/React.createElement("div", _extends({
    className: `frost-sbitem${active ? " is-active" : ""}`,
    onClick: onClick,
    style: style
  }, rest), icon ? /*#__PURE__*/React.createElement("i", {
    className: `ph ph-${icon}`
  }) : null, /*#__PURE__*/React.createElement("span", {
    className: "frost-sbitem__label"
  }, label), trailing ? /*#__PURE__*/React.createElement("span", {
    className: "frost-sbitem__trail"
  }, trailing) : null);
}
Object.assign(__ds_scope, { SidebarGroup, SidebarItem });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/SidebarItem.jsx", error: String((e && e.message) || e) }); }

// components/surfaces/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Frost Card — the basic raised surface. White background, level-1 elevation,
   card radius. `material` swaps the solid fill for a glass grade (sits on the
   wallpaper). `inset` uses the recessed gray fill instead of a raised surface. */

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
`;
  document.head.appendChild(el);
}
function Card({
  material,
  // "sidebar" | "toolbar" | "popover" | "sheet"
  inset = false,
  raised = false,
  panel = false,
  pad,
  // "sm" | "lg"
  title,
  children,
  className = "",
  style,
  ...rest
}) {
  ensureStyles();
  const glass = material ? `frost-glass-${material}` : "";
  const cls = [glass ? "" : "frost-card", glass, inset ? "frost-card--inset" : "", raised ? "frost-card--raised" : "", panel ? "frost-card--panel" : "", pad === "sm" ? "frost-card--pad-sm" : pad === "lg" ? "frost-card--pad-lg" : "", className].filter(Boolean).join(" ");
  const glassStyle = glass ? {
    borderRadius: panel ? "var(--r-panel,18px)" : "var(--r-card,14px)",
    padding: pad === "sm" ? 16 : pad === "lg" ? 36 : 24
  } : undefined;
  return /*#__PURE__*/React.createElement("div", _extends({
    className: cls,
    style: {
      ...glassStyle,
      ...style
    }
  }, rest), title ? /*#__PURE__*/React.createElement("h3", {
    className: "frost-card__title"
  }, title) : null, title ? /*#__PURE__*/React.createElement("div", {
    className: "frost-card__body"
  }, children) : children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/surfaces/Card.jsx", error: String((e && e.message) || e) }); }

// components/surfaces/Window.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Frost Window — macOS window chrome. A glass toolbar with traffic-light dots,
   title + subtitle, and a trailing actions slot; rounded window corners and a
   level-3 floating shadow. Children render in the body below the toolbar. */

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
  border-bottom:1px solid var(--separator);
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
function Window({
  title,
  subtitle,
  actions,
  traffic = true,
  toolbarClassName = "frost-glass-toolbar",
  children,
  style,
  ...rest
}) {
  ensureStyles();
  return /*#__PURE__*/React.createElement("div", _extends({
    className: "frost-window",
    style: style
  }, rest), /*#__PURE__*/React.createElement("div", {
    className: `frost-window__toolbar ${toolbarClassName}`
  }, traffic ? /*#__PURE__*/React.createElement("span", {
    className: "frost-window__traffic"
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      background: "var(--traffic-close,#ff5f57)"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      background: "var(--traffic-min,#febc2e)"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      background: "var(--traffic-max,#28c840)"
    }
  })) : null, title ? /*#__PURE__*/React.createElement("span", {
    className: "frost-window__title"
  }, title) : null, subtitle ? /*#__PURE__*/React.createElement("span", {
    className: "frost-window__sub"
  }, subtitle) : null, /*#__PURE__*/React.createElement("span", {
    className: "frost-window__spacer"
  }), actions ? /*#__PURE__*/React.createElement("span", {
    className: "frost-window__actions"
  }, actions) : null), /*#__PURE__*/React.createElement("div", {
    className: "frost-window__body"
  }, children));
}
Object.assign(__ds_scope, { Window });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/surfaces/Window.jsx", error: String((e && e.message) || e) }); }

// ui_kits/prose/AgentStream.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Prose · AgentStream — the center column. User bubbles, agent messages with
   tool chips, a suggestions row, and the composer field. */
(function () {
  const {
    ToolChip,
    Field,
    IconButton,
    Button
  } = window.FrostDesignSystemProse_5680eb;
  const {
    useState,
    useRef,
    useEffect
  } = React;

  // Render **bold** spans inside agent text.
  function RichText({
    text
  }) {
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return /*#__PURE__*/React.createElement("p", {
      style: {
        fontSize: 14,
        lineHeight: 1.75,
        color: "var(--label)",
        margin: 0
      }
    }, parts.map((p, i) => p.startsWith("**") ? /*#__PURE__*/React.createElement("strong", {
      key: i,
      style: {
        fontWeight: 600
      }
    }, p.slice(2, -2)) : /*#__PURE__*/React.createElement(React.Fragment, {
      key: i
    }, p)));
  }
  function UserBubble({
    text
  }) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        alignSelf: "flex-end",
        maxWidth: "78%",
        background: "var(--blue)",
        color: "#fff",
        padding: "9px 15px",
        borderRadius: "16px 16px 4px 16px",
        fontSize: 14,
        lineHeight: 1.65
      }
    }, text);
  }
  function AgentMessage({
    msg
  }) {
    return /*#__PURE__*/React.createElement("div", {
      style: {
        maxWidth: "88%",
        display: "flex",
        flexDirection: "column",
        gap: 10
      }
    }, (msg.chips || []).map((c, i) => /*#__PURE__*/React.createElement(ToolChip, _extends({
      key: i
    }, c))), msg.text ? /*#__PURE__*/React.createElement(RichText, {
      text: msg.text
    }) : null);
  }
  function AgentStream({
    data
  }) {
    const [thread, setThread] = useState(data.thread);
    const [draft, setDraft] = useState("");
    const [busy, setBusy] = useState(false);
    const scrollRef = useRef(null);
    useEffect(() => {
      const el = scrollRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    }, [thread]);
    function send(text) {
      const value = (text != null ? text : draft).trim();
      if (!value || busy) return;
      setDraft("");
      setBusy(true);
      setThread(t => [...t, {
        role: "user",
        text: value
      }]);
      // Fake the agent working, then drop in the canned reply.
      setTimeout(() => {
        setThread(t => [...t, data.reply]);
        setBusy(false);
      }, 950);
    }
    return /*#__PURE__*/React.createElement("div", {
      style: {
        background: "var(--surface)",
        display: "flex",
        flexDirection: "column",
        minHeight: 0
      }
    }, /*#__PURE__*/React.createElement("div", {
      ref: scrollRef,
      style: {
        flex: 1,
        overflow: "auto",
        padding: "26px 30px 12px",
        display: "flex",
        flexDirection: "column",
        gap: 18
      }
    }, thread.map((m, i) => m.role === "user" ? /*#__PURE__*/React.createElement(UserBubble, {
      key: i,
      text: m.text
    }) : /*#__PURE__*/React.createElement(AgentMessage, {
      key: i,
      msg: m
    })), busy ? /*#__PURE__*/React.createElement("div", {
      style: {
        maxWidth: "88%"
      }
    }, /*#__PURE__*/React.createElement(ToolChip, {
      running: true,
      label: "\u6B63\u5728\u751F\u6210\u2026"
    })) : null), /*#__PURE__*/React.createElement("div", {
      style: {
        padding: "10px 22px 4px",
        display: "flex",
        gap: 8,
        flexWrap: "wrap"
      }
    }, data.suggestions.map(s => /*#__PURE__*/React.createElement(Button, {
      key: s,
      variant: "default",
      size: "sm",
      onClick: () => send(s)
    }, s))), /*#__PURE__*/React.createElement("div", {
      style: {
        padding: "8px 22px 18px"
      }
    }, /*#__PURE__*/React.createElement(Field, {
      size: "lg",
      icon: "plus-circle",
      placeholder: "\u5411\u667A\u80FD\u4F53\u63CF\u8FF0\u4E0B\u4E00\u6B65\u2026",
      value: draft,
      onChange: e => setDraft(e.target.value),
      inputProps: {
        onKeyDown: e => {
          if (e.key === "Enter") send();
        }
      },
      trailing: /*#__PURE__*/React.createElement(IconButton, {
        icon: "paper-plane-tilt",
        label: "\u53D1\u9001",
        filled: true,
        onClick: () => send()
      })
    })));
  }
  window.ProseAgentStream = AgentStream;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/prose/AgentStream.jsx", error: String((e && e.message) || e) }); }

// ui_kits/prose/DocOutline.jsx
try { (() => {
/* Prose · DocOutline — right inspector. The bid-document outline as a tree;
   nodes carry an optional status Badge. */
(function () {
  const {
    Badge
  } = window.FrostDesignSystemProse_5680eb;
  function Node({
    node
  }) {
    const isChild = node.lvl !== 1;
    return /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: isChild ? "6px 9px 6px 28px" : "6px 9px",
        borderRadius: "var(--r-control)",
        fontSize: 12.5,
        color: node.active ? "var(--label)" : "var(--label-2)",
        fontWeight: node.active ? 600 : 400,
        background: node.active ? "var(--surface)" : "transparent",
        boxShadow: node.active ? "var(--elev-1)" : "none"
      }
    }, !isChild ? /*#__PURE__*/React.createElement("i", {
      className: `ph ph-caret-${node.open ? "down" : "right"}`,
      style: {
        fontSize: 12,
        color: node.active ? "var(--blue)" : "var(--label-3)"
      }
    }) : null, /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap"
      }
    }, node.label), node.badge ? /*#__PURE__*/React.createElement(Badge, {
      tone: node.badgeTone || "neutral"
    }, node.badge) : null);
  }
  function DocOutline({
    data
  }) {
    return /*#__PURE__*/React.createElement("aside", {
      style: {
        background: "var(--surface-2)",
        borderLeft: "1px solid var(--separator)",
        padding: "20px 18px",
        overflow: "auto"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        alignItems: "center",
        gap: 8,
        fontSize: 13,
        fontWeight: 700,
        marginBottom: 14
      }
    }, /*#__PURE__*/React.createElement("i", {
      className: "ph ph-tree-structure",
      style: {
        color: "var(--blue)"
      }
    }), "\u6295\u6807\u6587\u4EF6\u5927\u7EB2"), /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        flexDirection: "column",
        gap: 1
      }
    }, data.outline.map((n, i) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: i
    }, /*#__PURE__*/React.createElement(Node, {
      node: n
    }), n.open && n.children ? n.children.map((c, j) => /*#__PURE__*/React.createElement(Node, {
      key: `${i}-${j}`,
      node: {
        ...c,
        lvl: 2
      }
    })) : null))));
  }
  window.ProseDocOutline = DocOutline;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/prose/DocOutline.jsx", error: String((e && e.message) || e) }); }

// ui_kits/prose/ProseApp.jsx
try { (() => {
/* Prose · App — composes the macOS Window with the three columns, the toolbar
   (mode segmented + appearance toggle), all on the cold-blue wallpaper. */
(function () {
  const {
    Window,
    IconButton,
    Segmented,
    Tooltip
  } = window.FrostDesignSystemProse_5680eb;
  const {
    useState
  } = React;
  const data = window.PROSE_DATA;
  function ProseApp() {
    const [project, setProject] = useState("sim");
    const [appearance, setAppearance] = useState("light");
    const activeName = data.projects.find(p => p.id === project).name;
    function toggleAppearance() {
      const next = appearance === "light" ? "dark" : "light";
      setAppearance(next);
      document.documentElement.setAttribute("data-appearance", next === "dark" ? "dark" : "");
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "frost-wallpaper",
      style: {
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: 40
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        width: "min(1180px, 100%)"
      }
    }, /*#__PURE__*/React.createElement(Window, {
      title: activeName,
      subtitle: "\u6295\u6807\u6587\u4EF6",
      actions: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Tooltip, {
        label: "\u5207\u6362\u4FA7\u680F"
      }, /*#__PURE__*/React.createElement(IconButton, {
        icon: "sidebar-simple",
        label: "\u5207\u6362\u4FA7\u680F"
      })), /*#__PURE__*/React.createElement(Tooltip, {
        label: appearance === "light" ? "深色外观" : "浅色外观"
      }, /*#__PURE__*/React.createElement(IconButton, {
        icon: appearance === "light" ? "moon" : "sun",
        label: "\u5207\u6362\u5916\u89C2",
        onClick: toggleAppearance
      })), /*#__PURE__*/React.createElement(Segmented, {
        options: ["编制", "预览", "对照"],
        defaultValue: "\u7F16\u5236"
      })),
      style: {
        height: 640
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        display: "grid",
        gridTemplateColumns: "216px 1fr 296px",
        flex: 1,
        minHeight: 0
      }
    }, /*#__PURE__*/React.createElement(window.ProseSidebar, {
      data: data,
      activeProject: project,
      onSelectProject: setProject
    }), /*#__PURE__*/React.createElement(window.ProseAgentStream, {
      data: data
    }), /*#__PURE__*/React.createElement(window.ProseDocOutline, {
      data: data
    })))));
  }
  window.ProseApp = ProseApp;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/prose/ProseApp.jsx", error: String((e && e.message) || e) }); }

// ui_kits/prose/Sidebar.jsx
try { (() => {
/* Prose · Sidebar — glass navigation: projects + knowledge base.
   Composes SidebarItem / SidebarGroup / Badge from the Frost bundle. */
(function () {
  const {
    SidebarItem,
    SidebarGroup,
    Badge
  } = window.FrostDesignSystemProse_5680eb;
  function Sidebar({
    data,
    activeProject,
    onSelectProject
  }) {
    return /*#__PURE__*/React.createElement("aside", {
      className: "frost-glass-sidebar",
      style: {
        padding: "14px 10px",
        display: "flex",
        flexDirection: "column",
        gap: 2,
        borderRight: "1px solid rgba(60,60,67,.10)",
        overflow: "hidden"
      }
    }, /*#__PURE__*/React.createElement(SidebarGroup, null, "\u9879\u76EE"), data.projects.map(p => /*#__PURE__*/React.createElement(SidebarItem, {
      key: p.id,
      icon: p.icon,
      label: p.name,
      active: activeProject === p.id,
      onClick: () => onSelectProject(p.id)
    })), /*#__PURE__*/React.createElement(SidebarGroup, null, "\u77E5\u8BC6\u5E93"), data.knowledge.map(k => /*#__PURE__*/React.createElement(SidebarItem, {
      key: k.id,
      icon: k.icon,
      label: k.name,
      trailing: /*#__PURE__*/React.createElement(Badge, {
        tone: "neutral"
      }, k.count)
    })));
  }
  window.ProseSidebar = Sidebar;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/prose/Sidebar.jsx", error: String((e && e.message) || e) }); }

// ui_kits/prose/data.js
try { (() => {
/* Prose UI kit — mock data. Assigned to window for the babel-scoped kit files. */
window.PROSE_DATA = {
  projects: [{
    id: "sim",
    icon: "folder-simple",
    name: "仿真软件开发服务采购"
  }, {
    id: "park",
    icon: "folder-simple",
    name: "智慧园区运维服务"
  }, {
    id: "lab",
    icon: "folder-simple",
    name: "实验室设备购置"
  }],
  knowledge: [{
    id: "qual",
    icon: "identification-card",
    name: "资质证照",
    count: 12
  }, {
    id: "case",
    icon: "buildings",
    name: "业绩案例",
    count: 38
  }, {
    id: "cv",
    icon: "files",
    name: "人员简历",
    count: 24
  }],
  // The opening agent conversation for the active project.
  thread: [{
    role: "user",
    text: "解析这份招标文件的技术需求，生成技术需求清单。"
  }, {
    role: "agent",
    chips: [{
      icon: "file-text",
      label: "已读取",
      mono: "招标文件.md"
    }, {
      done: true,
      label: "技术需求解析完成"
    }],
    text: "已从第三章提取全部技术需求条目，按 **功能、性能、接口、安全** 四类归档，并标出了需要逐条响应的实质性条款。偏差项已同步到右侧大纲的「技术偏差表」，可以逐项确认。"
  }],
  // Canned follow-up the fake agent "produces" when you send a message.
  reply: {
    role: "agent",
    chips: [{
      running: true,
      label: "正在比对需求条目"
    }, {
      done: true,
      label: "技术偏差表已生成"
    }],
    text: "已将技术需求清单与现有产品能力逐条比对：**完全响应 18 项、部分响应 5 项、偏差 3 项**。三处偏差均已附上替代方案说明，建议在投标前与技术负责人确认。"
  },
  outline: [{
    label: "投标函及附录",
    lvl: 1
  }, {
    label: "法定代表人授权书",
    lvl: 1
  }, {
    label: "商务响应",
    lvl: 1
  }, {
    label: "技术方案",
    lvl: 1,
    active: true,
    open: true,
    children: [{
      label: "技术需求响应",
      badge: "已生成",
      badgeTone: "green"
    }, {
      label: "技术偏差表",
      badge: "草稿",
      badgeTone: "neutral"
    }, {
      label: "实施与验收方案"
    }]
  }, {
    label: "资质证明材料",
    lvl: 1
  }, {
    label: "报价表",
    lvl: 1
  }],
  suggestions: ["生成技术偏差表", "插入资质证照", "核对报价表"]
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/prose/data.js", error: String((e && e.message) || e) }); }

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Checkbox = __ds_scope.Checkbox;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.Segmented = __ds_scope.Segmented;

__ds_ns.Switch = __ds_scope.Switch;

__ds_ns.Avatar = __ds_scope.Avatar;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Toast = __ds_scope.Toast;

__ds_ns.ToolChip = __ds_scope.ToolChip;

__ds_ns.Tooltip = __ds_scope.Tooltip;

__ds_ns.Field = __ds_scope.Field;

__ds_ns.Menu = __ds_scope.Menu;

__ds_ns.SidebarGroup = __ds_scope.SidebarGroup;

__ds_ns.SidebarItem = __ds_scope.SidebarItem;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Window = __ds_scope.Window;

})();
