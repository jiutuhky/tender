# IconButton

Bare icon control for window toolbars and inline actions. Transparent at rest, gray fill on hover. Always supply `label` (accessible name + tooltip).

```jsx
<IconButton icon="sidebar-simple" label="切换侧栏" />
<IconButton icon="magnifying-glass" label="搜索" active />
<IconButton icon="paper-plane-tilt" label="发送" filled />
```

`size`: `md` (30px) · `lg` (36px). `active` tints soft-blue; `filled` gives a solid blue send-style fill.
