# Card

The basic raised surface: white fill, level-1 shadow, 14px radius. Depth and radius scale together — use `panel` for large surfaces, `inset` for recessed gray fills, `raised` for level-2, `material` to render it as glass on the wallpaper.

```jsx
<Card title="字标与组合">字标使用系统字体 Semibold，字距 -2%。</Card>
<Card inset>recessed fill</Card>
<Card panel raised>large surface</Card>
<Card material="lens">凝 · refracting glass — a floating control surface</Card>
<Card material="lens" thickness="thin" interactive>a pill that lights up under the pointer</Card>
<Card material="soft" panel>霜 · frosted chrome panel</Card>
```

`material`: `lens` (凝 — refracts, rim light, for the control layer: floating windows, boards, pills) · `soft` (霜 — frosted, for large chrome: drawers, sheets). `thickness`: `thin` · `regular` (default) · `thick` (default when `panel`). `interactive` adds the pointer specular and press response — only on things that can be clicked. Glass cards are never content: keep tables, documents and the composer solid. Don't add your own border — elevation (or the rim) carries the edge. Include `assets/frost-lens.js` once per page for the refraction.
