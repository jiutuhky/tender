// shared.jsx — building blocks reused across all 4 design system artboards.
// Each system component sets its own CSS variables + font on a root wrapper,
// then composes these layout primitives. The primitives only structure the
// page; the system-specific look comes from each system's own CSS block.

const { useState } = React;

// ──────────────────────────────────────────────────────
// SystemPage — fixed-size root of an artboard.
// Provides the gridded layout used by every system.
// ──────────────────────────────────────────────────────
function SystemPage({ className, style, children }) {
  return (
    <div
      className={"sys " + (className || "")}
      style={{
        width: 1280,
        position: "relative",
        boxSizing: "border-box",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

// SystemHeader — top band: code (A/B/C/D), big name, tagline, philosophy.
function SystemHeader({ code, name, cn, tagline, philosophy, headerStyle, codeStyle, nameStyle, taglineStyle, philStyle }) {
  return (
    <div className="sys-header" style={{ padding: "44px 56px 32px", ...headerStyle }}>
      <div className="sys-code" style={codeStyle}>{code}</div>
      <div className="sys-title-row" style={{ display: "flex", alignItems: "baseline", gap: 18, marginTop: 8, flexWrap: "wrap" }}>
        <div className="sys-name" style={nameStyle}>{name}</div>
        {cn ? <div className="sys-cn" style={{ ...(nameStyle || {}), opacity: 0.5, fontWeight: 400 }}>{cn}</div> : null}
      </div>
      {tagline ? <div className="sys-tagline" style={{ marginTop: 14, ...taglineStyle }}>{tagline}</div> : null}
      {philosophy ? <div className="sys-philosophy" style={{ marginTop: 18, maxWidth: 820, ...philStyle }}>{philosophy}</div> : null}
    </div>
  );
}

// SystemRule — horizontal divider; style overridable
function SystemRule({ style }) {
  return <div className="sys-rule" style={{ height: 1, background: "currentColor", opacity: 0.12, ...style }} />;
}

// Block — labeled content section with a small caption.
function Block({ caption, title, children, style }) {
  return (
    <section style={{ padding: "28px 56px 8px", ...style }}>
      <div className="block-cap" style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 18 }}>
        <span className="block-caption-label">{caption}</span>
        {title ? <span className="block-caption-title">{title}</span> : null}
      </div>
      {children}
    </section>
  );
}

// Swatch — one color chip. Variant: 'card' (with text below) | 'flat' (full bleed)
function Swatch({ color, name, hex, role, textColor, variant = "card", height = 92, style }) {
  if (variant === "flat") {
    return (
      <div style={{ background: color, color: textColor || "white", padding: "14px 14px 14px", display: "flex", flexDirection: "column", justifyContent: "space-between", minHeight: height, ...style }}>
        <div style={{ fontSize: 11, opacity: 0.7, letterSpacing: "0.04em", textTransform: "uppercase" }}>{role}</div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500 }}>{name}</div>
          <div className="mono" style={{ fontSize: 11, opacity: 0.7, marginTop: 2 }}>{hex}</div>
        </div>
      </div>
    );
  }
  return (
    <div style={style}>
      <div style={{ background: color, height, borderRadius: 6, border: "1px solid rgba(0,0,0,0.06)" }} />
      <div style={{ marginTop: 8, display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
        <div style={{ fontSize: 12, fontWeight: 500 }}>{name}</div>
        <div className="mono" style={{ fontSize: 10.5, opacity: 0.55 }}>{hex}</div>
      </div>
      {role ? <div style={{ fontSize: 11, opacity: 0.55, marginTop: 2 }}>{role}</div> : null}
    </div>
  );
}

// TypeRow — one line of typography: meta on the left, big sample on the right.
function TypeRow({ label, meta, sample, sampleStyle, style }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: 24, alignItems: "baseline", padding: "16px 0", borderTop: "1px solid currentColor", borderColor: "rgba(0,0,0,0.08)", ...style }}>
      <div>
        <div style={{ fontSize: 12, fontWeight: 500 }}>{label}</div>
        <div className="mono" style={{ fontSize: 10.5, opacity: 0.55, marginTop: 4, lineHeight: 1.5 }}>{meta}</div>
      </div>
      <div style={sampleStyle}>{sample}</div>
    </div>
  );
}

// MicroLabel — small uppercase mono caption used as block labels.
function MicroLabel({ children, style }) {
  return (
    <div className="mono" style={{ fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", opacity: 0.55, ...style }}>{children}</div>
  );
}

// IconStub - tiny inline svg helpers
const I = {
  arrow:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M5 12h14M13 5l7 7-7 7"/></svg>,
  search:   <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.35-4.35"/></svg>,
  doc:      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>,
  check:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 6L9 17l-5-5"/></svg>,
  plus:     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 5v14M5 12h14"/></svg>,
  sparkle:  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/></svg>,
  bolt:     <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z"/></svg>,
  clock:    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>,
};

Object.assign(window, {
  SystemPage, SystemHeader, SystemRule, Block, Swatch, TypeRow, MicroLabel, I,
});
