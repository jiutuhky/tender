# 「Prose 标书编制全流程」分页原型

已发布画布：https://claude.ai/code/artifact/616e143f-3788-44c3-a87d-2757c43b859c

- `lib/tokens.mjs` Frost token 与共享样式（值取自 frost-design skill 与 frontend/app/globals.css 实测）
- `lib/parts.mjs` 顶栏 / 工具栏 / 停靠列矩阵卡 / 消息窗 / 子代理看板 / 输入坞 等片段
- `lib/outline.mjs` 骨架数据（记分卡投影）与章节卡布局
- `boards/*.mjs` 各画板：g1 定策 · g2 备料 · g3 成文 · g4 合规 · g5 成册 · overview 总览与架构
- `canvas.json` 六页布局与便签

改动后：

```bash
node build.mjs                     # 组装出 *.dc.html
# 拼装画布（模板来自 /design 技能目录，B 为其 base directory）
node "$B/seed-canvas.mjs" --template "$B/payload.template.html" --out prose-bid-authoring.html \
  --title "Prose 标书编制全流程" $(printf -- '--artboard %s ' *.dc.html) --canvas canvas.json
```

`prose-bid-authoring.html`（约 3 MB）是拼装产物，不入库；用同一路径重新发布即可保持画布链接不变。
