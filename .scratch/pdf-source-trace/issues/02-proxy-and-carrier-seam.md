Status: ready-for-agent
Blocked by: 01

# 02 前端：取数打通与载体解耦（预勾）

## Parent

`.scratch/pdf-source-trace/PRD.md`

## What to build

**用户视角零变化**——md 预览、块级高亮、对照条与人工动作、来源步进器、Esc 逐层退、动效与 reduced-motion 全部照旧，一处回归都不能有。本票只做两件让下一票变简单的事：把取数打通，把壳与载体拆开。

取数：新增两条同源读代理（预览版 PDF 字节流、sidecar JSON），透传上游状态码与 Content-Type，API key 继续只在服务端持有。数据层提供取数函数与缓存——预览版与 sidecar 按 document_id 缓存，sha256 作内容版本键，项目切换时失效。

解耦：现在预览层把「浮层编排 + 对照条 + 来源步进器 + 容错黄条 + 动效 + Esc 逐层退」和「md 渲染 + 块级高亮」焊在一起。把前者留作**壳**，把后者收成一个**可替换的载体**，让第二种载体能以同样的形状插进来。壳负责的东西不该知道载体是 md 还是 PDF。

这是「先让改动变容易，再做容易的改动」的预勾——完成后功能不多一分，但下一票只需写新载体。

## Acceptance criteria

- [ ] 两条同源读代理可用：预览版字节流、sidecar JSON，透传上游状态码与 Content-Type
- [ ] 取数缓存就位：同一 document_id 重复打开不重复请求；sha256 变化或项目切换后失效
- [ ] 预览层的壳与载体分离，壳不感知载体种类；md 载体是其中一个实现
- [ ] `line_span → 命中目标` 的判定留在 `lib/trace/` 纯模块，组件只消费
- [ ] 现有 md 预览零回归：点签开层、块级高亮、滚动定位、对照条人工动作、多来源步进、Esc 逐层退、reduced-motion 即时切换逐项手验通过
- [ ] `pnpm typecheck` + `pnpm lint` 通过

## Blocked by

- 01 后端：PDF 入库管线（需要真实的预览版与 sidecar 才能验证取数）
