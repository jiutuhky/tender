# Badge

Small status pill. The default (soft) variant follows the system's graphic/text color rule: darkened text on a tint of the saturated color.

```jsx
<Badge tone="green">已生成</Badge>
<Badge tone="orange" dot>待确认</Badge>
<Badge tone="blue" solid>进行中</Badge>
```

Tones: `neutral` · `blue` · `green` · `orange` · `red`. `solid` fills with the graphic color + white text; `dot` adds a leading status dot.
