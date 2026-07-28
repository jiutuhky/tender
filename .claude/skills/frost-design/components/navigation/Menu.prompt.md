# Menu

Popover-glass context menu. Each row takes an icon, label, and optional keyboard hint; the hovered (or `active`) row fills full-width blue.

```jsx
<Menu items={[
  { icon: "file-text", label: "新建标书", kbd: "N" },
  { icon: "sparkle", label: "解析招标文件", kbd: "E", active: true },
  { icon: "stack", label: "插入知识库条目", kbd: "K" },
  "---",
  { icon: "clock-counter-clockwise", label: "版本历史" },
]} />
```

Pass `items` or compose with `Menu.Item` / `Menu.Separator`. Mark destructive rows with `danger`. Sits on the wallpaper or a real surface so the glass reads.
