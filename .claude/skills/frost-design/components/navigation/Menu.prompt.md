# Menu

Lens-glass (凝 · regular) context menu. Each row takes an icon, label, and optional keyboard hint; the hovered (or `active`) row fills full-width blue. Corners are concentric: menu 12 − padding 6 = row 6.

```jsx
<Menu items={[
  { icon: "file-text", label: "新建标书", kbd: "N" },
  { icon: "sparkle", label: "解析招标文件", kbd: "E", active: true },
  { icon: "stack", label: "插入知识库条目", kbd: "K" },
  "---",
  { icon: "clock-counter-clockwise", label: "版本历史" },
]} />
```

Pass `items` or compose with `Menu.Item` / `Menu.Separator`. Mark destructive rows with `danger`. Sits on the wallpaper or a real surface so the glass has something to refract; when it opens over soft-glass chrome it cannot sample that glass — give it a solid or wallpaper backdrop, never glass on glass.
