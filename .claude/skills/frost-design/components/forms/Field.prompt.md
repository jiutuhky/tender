# Field

Text / search input. Inset hairline ring at rest; blue ring + soft halo on focus. Leading `icon` and a `trailing` slot are both optional.

```jsx
<Field icon="magnifying-glass" placeholder="搜索条款、资质或案例" />

<Field
  size="lg"
  icon="plus-circle"
  placeholder="向智能体描述下一步…"
  trailing={<IconButton icon="paper-plane-tilt" label="发送" filled />}
/>
```

`size="lg"` (44px, raised) is the composer field; default `md` (36px) is the inline search field.
