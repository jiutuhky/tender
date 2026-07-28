# ToolChip

The agent execution chip in the Prose stream — surfaces a tool call or a completed step. Recessed pill, blue icon, optional trailing mono datum.

```jsx
<ToolChip icon="file-text" label="已读取" mono="招标文件.md" />
<ToolChip running label="正在比对需求条目" />
<ToolChip done label="技术需求解析完成" />
```

`running` shows a spinner (in-progress), `done` a green check. Keep labels to a short verb phrase.
