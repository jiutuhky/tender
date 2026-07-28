# Segmented

macOS segmented control for 2–4 mutually exclusive modes. Recessed gray track; the active segment rides a white slider. Works controlled or uncontrolled.

```jsx
<Segmented options={["编制", "预览", "对照"]} defaultValue="编制" onChange={setMode} />
```

Pass `options` as strings or `{ value, label }`. Provide `value` + `onChange` to control it. Keep labels short — it's not a tab bar for long titles.
