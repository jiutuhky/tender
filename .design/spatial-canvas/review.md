# 新画布质量审查与修复

本轮由两个审查 Agent 分别检查动画与 UI、性能与资源生命周期，主 Agent 交叉复现并整合修复。保留既定空间风格、760ms 文件夹过渡及真实业务接口。

## 已修复问题

| 类别 | 触发与影响 | 修复 |
| --- | --- | --- |
| 慢网络轮询 | 请求超过轮询间隔时，连续有效结果被后发请求丢弃；首次还会重复读取 | 合并在途请求，上传结束后排队补读；组件卸载取消读取和上传 |
| 视口裁剪 | effect 清理后的定时器标识未复位，重挂后可能停止更新可见窗口 | 完整清理定时器状态，增加真实手势 hook 生命周期回归 |
| 拖拽尺寸 | 抓取动画中的卡片会跳大，并把临时缩放写成永久尺寸 | 保留逻辑尺寸和内容抓取点，松手后从当前变换归位；点击抑制只覆盖本次释放 |
| 集合对齐 | 旋转包围框被重复计算，折回终点偏差最高约 11.58px；父卡额外入场又引入漂移 | 统一矩阵与未旋转尺寸测量，空间迁移接管父卡入场；三个缩略片实测误差均小于 0.0001px |
| 快速关闭 | 阅读层尚在入场时关闭，退场目标遗漏当前位移与缩放 | 在同一坐标系中计算退场；入场 83.3ms 时关闭的逐帧验证通过 |
| 窄屏对齐 | 关联面板与缩放工具重叠 26–28px | 保留 12px 净距，关联列表限高并内部滚动 |
| 减少动态效果 | 文件夹纸片使用 transform 位移，原规则清除 translate 无效 | 悬停和拖入保持静态位置，保留边框接受反馈 |
| 导航与键盘 | 撤销当前集合后停留空白上下文；返回后焦点落到 body；概览快捷键可修改隐藏画布 | 自动回到有效上层并恢复焦点；概览仅保留搜索等只读操作 |
| 卡片重复渲染 | 相机刷新重建成员数组和回调，穿透 memo | 相机状态与内容场景分离，稳定成员和事件 props；连续平移中 24 张已有卡片的 props 保持稳定 |
| PDF 重复解析 | PDF 离开视口再进入会重复启动解析；临时 Blob 随多次上传累积 | 最多缓存 24 张、每张不超过 400×640 的完成位图；限制 2 个并发解析，正式预览就绪后回收临时 URL |
| 文稿缓存 | 同一路径的生成文稿可长期读到旧内容 | 缩略缓存有效期 15 秒，完整阅读每次强制取得最新内容 |

## 优化过程补充的生命周期防护

PDF.js 取消慢下载后，其加载 Promise 可能仍然不结束。加载、取页、渲染分别响应取消，并统一等待一次销毁，避免两个取消任务占满整个解析队列。预览任务在通知失败前从队列索引中移除，保证消费者立即重试能够创建新任务。

本地 PDF 使用稳定的文件标识缓存，解析器独立管理临时 URL。浏览器往返视口验证：再次挂载只创建展示所需 URL，直接复用位图，不重新创建解析 URL。

## 验证

- `pnpm typecheck`、`pnpm lint`、`pnpm test:canvas`、`pnpm test:trace`、`pnpm build`。
- 画布测试 29 项，覆盖慢请求、取消、Blob 回收、缓存时效、effect 重挂、导航恢复、坐标、解析并发、失败立即重试和 PDF 底层 Promise 不结束的情况。
- 浏览器验证：撤销当前集合、来源焦点恢复、概览操作隔离、动画中途抓取、200 条评分连续滚动、卡片 props 稳定性、本地 PDF 缩略图复用。
- 390×844 下验证关联面板与缩放工具相隔 12px，四个关联入口均无遮挡；减少动态效果模式下纸片变换前后一致。
- 动画/UI Agent 使用独立浏览器交叉验证。所有浏览器写操作限于隔离的演示空间，前后端真实服务保持运行。窄屏与系统偏好使用浏览器模拟验证，未进行实体触屏测试。

窄屏证据：[修复前](verification/review-mobile-before.png) · [修复后](verification/review-mobile-after.png)。

## 真实工作台性能修复（2026-09-10）

执行流使用单层 `blur(8px) saturate(125%)` 毛玻璃，保留渐变遮罩、高光、阴影、圆角和开合动效。`WorkspaceChrome` 以无参数的 memo 边界承载消息窗、看板和输入坞，各自的业务订阅正常工作。

验收采用两份隔离源码快照，修复前后生产构建使用同一契约服务。四矩阵包含 60 条商务要求、60 条技术要求和 80 条评分项，另有 100 项资料元数据；内容包括长中文、Markdown 表格、原文引用、可解析的一页 PDF 和图片。执行流通过真实 SSE 客户端载入 20 次工具调用、长回复和任务清单；未调用模型或写入真实项目。

环境为 Linux / WSL2、Chromium 151 无头软件渲染、1440×1000、DPR 1、约 60 Hz。生产构建预热后，平移和拖拽各执行 5 秒、三轮，表内平均值是三轮平均帧间隔的算术平均；原始逐帧数据与长任务记录均已保留。

| 操作 | 修复前平均 | 修复后平均 | 帧间隔降幅 | 修复后 P95 | 修复后 >50 ms 帧 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 连续平移 | 87.30 ms | 16.92 ms | 80.6% | ≤16.8 ms | 0 |
| 卡片拖拽 | 75.38 ms | 16.67 ms | 77.9% | ≤16.8 ms | 0 |

评分集合实际挂载 24 张卡片，两份构建一致。修复后首轮平移有 13 帧约 33.3 ms，P95 仍为 16.8 ms；后两轮平移与三轮拖拽均无 >25 ms 帧。两份构建的平移、拖拽均无 >50 ms 主线程长任务，修复前却出现大量长帧，与折射绘制瓶颈相符。

阅读层首次/再次打开的平均帧间隔分别为修复前 17.04/17.86 ms、修复后 17.24/17.42 ms；此负载下两版阅读均基本流畅，未据此宣称阅读速度显著提升。修复后阅读样本最大帧间隔 33.4 ms。持续输出按每秒 10 次事件回放，执行流展开、收起各测 3 秒，平均均为 16.67 ms，P95 ≤16.8 ms，无 >25 ms 帧。

React 渲染计数在独立开发实例记录，与生产帧率采样分开：同一组平移、缩放、选择和拖拽操作，修复前画布更新 28 次，消息窗、执行流、看板、输入坞、输入框各连带渲染 28 次；修复后画布更新 37 次，上述组件及 `WorkspaceChrome` 连带渲染均为 0。随后发送新消息，所有业务组件均正常更新。

质量门：`pnpm typecheck`、`pnpm lint`、`pnpm test:canvas`（29 项）、`pnpm test:trace`（5 项）、`pnpm build` 全部通过。20 项浏览器回归覆盖草稿与滚动位置保留、单选/多选拖拽、撤销重做、集合导航、真实条目核验、阅读焦点恢复、快速反向开合、持续输出、项目切换、PDF/图片以及三种实底回退。另检查演示评分集合、桌面与窄屏深浅主题、窄屏执行流展开材质。

本次数据用于同环境前后比较，尚未取得硬件加速及实体触屏的测量结果。矩阵来自隔离契约服务，真实模型生成的项目数据仍需后续同路径抽查。

### 复现入口与证据

在仓库根目录启动 `python3 .design/spatial-canvas/performance-fixture.py`，服务只监听 `127.0.0.1:8108`。两份前端生产构建分别以 `HAGENT_API_BASE=http://127.0.0.1:8108 pnpm start --port 3101` 和 `--port 3102` 运行；构建时复制当前工作区源码与依赖到隔离目录，排除 `.next`、本地环境文件。修复前快照保留本轮开始时的代码，修复后快照只叠加本轮产品修改，以排除并行开发对对比的影响。

通过独立的 browser-use 本地 CDP 连接运行以下命令；示例 CDP 端口为 9222，浏览器仅使用验收临时配置目录。

```bash
BU_NAME=canvasperf BU_CDP_URL=http://127.0.0.1:9222 PERF_URL=http://127.0.0.1:3101 PERF_LABEL=before browser-use < .design/spatial-canvas/performance-browser.py
BU_NAME=canvasperf BU_CDP_URL=http://127.0.0.1:9222 PERF_URL=http://127.0.0.1:3102 PERF_LABEL=after browser-use < .design/spatial-canvas/performance-browser.py
BU_NAME=canvasperf BU_CDP_URL=http://127.0.0.1:9222 PERF_URL=http://127.0.0.1:3102 PERF_LABEL=after browser-use < .design/spatial-canvas/performance-regression.py
```

渲染计数使用两份源码的独立开发服务（本轮端口 3103/3104），把 `PERF_URL` 改为对应的 `http://localhost:<端口>`，执行 `performance-renders.py`。结果默认写入 `/tmp/prose-canvas-perf-implementation/results`，可用 `PERF_OUTPUT` 指定目录。重复核验回归前重启契约服务，恢复条目的初始核验状态。

- 原始数据：[修复前](verification/performance/before.json)、[修复后](verification/performance/after.json)、[20 项回归及流式采样](verification/performance/regression.json)。
- 渲染计数：[修复前](verification/performance/before-renders.json)、[修复后](verification/performance/after-renders.json)。
- 性能轨迹：[修复前](verification/performance/before-trace.json.gz)、[修复后](verification/performance/after-trace.json.gz)，解压后可导入 Chrome DevTools Performance。
- 桌面截图：[修复前](verification/performance/before-desktop-light.png)、[修复后浅色](verification/performance/after-desktop-light.png)、[修复后深色](verification/performance/after-desktop-dark.png)。
- 窄屏截图：[浅色](verification/performance/after-mobile-light.png)、[深色](verification/performance/after-mobile-dark.png)、[展开执行流浅色](verification/performance/after-mobile-glass-light.png)、[展开执行流深色](verification/performance/after-mobile-glass-dark.png)。
- 资料加载：[PDF 与图片](verification/performance/after-materials.png)。
