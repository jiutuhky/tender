# Toast

Floating notification on popover glass. Leading status icon in the semantic color; title, optional detail, inline action, and dismiss.

```jsx
<Toast tone="success" title="技术需求清单已生成" detail="已归档至右侧大纲" onClose={dismiss} />
<Toast tone="warning" title="检测到 3 项技术偏差" action="查看偏差表" onAction={open} onClose={dismiss} />
```

Tones: `info` · `success` · `warning` · `danger`. Place toasts over a real surface so the glass blur has something to sample.
