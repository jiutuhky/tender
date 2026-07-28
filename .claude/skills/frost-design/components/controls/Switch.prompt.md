# Switch

macOS toggle. Blue track when on, white knob slides on the float easing. Controlled or uncontrolled; pass `label` for a clickable labelled row.

```jsx
<Switch defaultChecked label="自动保存" />
<Switch checked={auto} onChange={setAuto} aria-label="自动保存" />
```

Use for instant-effect binary settings. For a confirmable choice in a form, use Checkbox instead.
