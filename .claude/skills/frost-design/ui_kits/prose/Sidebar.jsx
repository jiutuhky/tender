/* Prose · Sidebar — soft-glass (霜, embedded chrome) navigation: projects + knowledge base.
   Composes SidebarItem / SidebarGroup / Badge from the Frost bundle. */
(function () {
  const { SidebarItem, SidebarGroup, Badge } = window.FrostDesignSystemProse_5680eb;

  function Sidebar({ data, activeProject, onSelectProject }) {
    return (
      <aside
        className="frost-glass frost-glass--soft frost-glass--flush"
        style={{
          padding: "14px 10px",
          display: "flex",
          flexDirection: "column",
          gap: 2,
          boxShadow: "inset -0.5px 0 0 var(--separator)",
          overflow: "hidden",
        }}
      >
        <SidebarGroup>项目</SidebarGroup>
        {data.projects.map((p) => (
          <SidebarItem
            key={p.id}
            icon={p.icon}
            label={p.name}
            active={activeProject === p.id}
            onClick={() => onSelectProject(p.id)}
          />
        ))}
        <SidebarGroup>知识库</SidebarGroup>
        {data.knowledge.map((k) => (
          <SidebarItem
            key={k.id}
            icon={k.icon}
            label={k.name}
            trailing={<Badge tone="neutral">{k.count}</Badge>}
          />
        ))}
      </aside>
    );
  }

  window.ProseSidebar = Sidebar;
})();
