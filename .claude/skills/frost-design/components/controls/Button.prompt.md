# Button

A macOS-style control. Use `primary` for the single affirmative action in a view (it owns the only accent color), `default` for neutral actions, `plain` for low-emphasis text actions, `danger` for destructive ones.

```jsx
<Button variant="primary" icon="sparkle">生成投标文件</Button>
<Button variant="default">取消</Button>
<Button variant="plain" icon="arrow-square-out">查看来源</Button>
```

Variants: `primary` · `default` · `plain` · `danger`. Sizes: `sm` (28px) · `md` (32px) · `lg` (38px). Pass `icon` / `iconRight` as a Phosphor name. Press scales to .97; only one `primary` per view.
