/* Prose · DocOutline — right inspector. The bid-document outline as a tree;
   nodes carry an optional status Badge. */
(function () {
  const { Badge } = window.FrostDesignSystemProse_5680eb;

  function Node({ node }) {
    const isChild = node.lvl !== 1;
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: isChild ? "6px 9px 6px 28px" : "6px 9px",
          borderRadius: "var(--r-control)",
          fontSize: 12.5,
          color: node.active ? "var(--label)" : "var(--label-2)",
          fontWeight: node.active ? 600 : 400,
          background: node.active ? "var(--surface)" : "transparent",
          boxShadow: node.active ? "var(--elev-1)" : "none",
        }}
      >
        {!isChild ? (
          <i
            className={`ph ph-caret-${node.open ? "down" : "right"}`}
            style={{ fontSize: 12, color: node.active ? "var(--blue)" : "var(--label-3)" }}
          />
        ) : null}
        <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {node.label}
        </span>
        {node.badge ? <Badge tone={node.badgeTone || "neutral"}>{node.badge}</Badge> : null}
      </div>
    );
  }

  function DocOutline({ data }) {
    return (
      <aside
        style={{
          background: "var(--surface-2)",
          borderLeft: "1px solid var(--separator)",
          padding: "20px 18px",
          overflow: "auto",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 700, marginBottom: 14 }}>
          <i className="ph ph-tree-structure" style={{ color: "var(--blue)" }} />
          投标文件大纲
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
          {data.outline.map((n, i) => (
            <React.Fragment key={i}>
              <Node node={n} />
              {n.open && n.children
                ? n.children.map((c, j) => <Node key={`${i}-${j}`} node={{ ...c, lvl: 2 }} />)
                : null}
            </React.Fragment>
          ))}
        </div>
      </aside>
    );
  }

  window.ProseDocOutline = DocOutline;
})();
