# SidebarItem

A row in the soft-glass sidebar — icon + label, optional trailing slot. The active row gets the soft-blue backing and a blue icon. Pair with `SidebarGroup` for section headers.

```jsx
<SidebarGroup>项目</SidebarGroup>
<SidebarItem icon="folder-simple" label="仿真软件开发服务采购" active />
<SidebarItem icon="folder-simple" label="智慧园区运维服务" />

<SidebarGroup>知识库</SidebarGroup>
<SidebarItem icon="identification-card" label="资质证照" trailing={<Badge tone="green">12</Badge>} />
```

Put these inside a `.frost-glass.frost-glass--soft.frost-glass--flush` surface (霜 · embedded chrome) over the wallpaper; close the sidebar with a .5px contact edge (`box-shadow: inset -.5px 0 0 var(--separator)`), not a 1px border.
