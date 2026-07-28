# Card

The basic raised surface: white fill, level-1 shadow, 14px radius. Depth and radius scale together — use `panel` for large surfaces, `inset` for recessed gray fills, `raised` for level-2, `material` to render it as glass on the wallpaper.

```jsx
<Card title="字标与组合">字标使用系统字体 Semibold，字距 -2%。</Card>
<Card inset>recessed fill</Card>
<Card panel raised>large surface</Card>
<Card material="popover">glass popover on wallpaper</Card>
```

`material`: `sidebar` · `toolbar` · `popover` · `sheet`. Don't add your own border — elevation carries the edge.
