Status: done
Blocked by: 无

# 01 后端：PDF 入库管线

## Parent

`.scratch/pdf-source-trace/PRD.md`

## What to build

用户拖入一份 PDF 招标文件，看着「原文解析 N/M 页」的进度跑完，系统里出现四件互相对得上的产物——原件 blob、预览版、规范化 md、sidecar——agent 在它们就绪之后才起跑。

上传口从只收 `.md` 改为收 PDF。后端把 OCR 作为上传后的确定性前置异步任务：分批调用 PaddleOCR-VL HPS Gateway 的 `/layout-parsing`，页级断点续跑，部分页失败不让整份作废（失败页在 md 里留占位，sidecar 不产出其条目）。**拼装 md 与产出 sidecar 必须是同一段代码的同一次输出**，行号一边追加一边记账——严禁先拼 md 再回头做模糊匹配。

原件与预览版按 sha256 内容寻址存到 project workspace 之外，不进 git；仓内只留 md 与 sidecar 这类可 diff 的文本。预览版由原件重压缩得到，**页数与逐页页面尺寸必须与原件逐页一致**，否则归一化 bbox 全部错位。OCR 产出的 md 与 sidecar 对 agent 只读，写入被工具层拒绝并返回可读错误。

同时提供两条读端点：预览版字节流、sidecar JSON——鉴权、404、分页语义与既有矩阵读端点同构。

sidecar 契约（schema v1，由本票定死）：

```jsonc
{
  "schema": 1,
  "mdSha256": "…",
  "pages": [{ "index": 0, "width": 1190, "height": 1684 }],
  "blocks": [{
    "mdStart": 12, "mdEnd": 12, "label": "table",
    "rects": [{ "page": 3, "bbox": [0.118, 0.207, 0.532, 0.280] }]
  }]
}
```

本票完成后前端无任何变化，验证方式是 pytest + 实跑一份真 PDF + curl 打两条读端点。

## Acceptance criteria

- [~] 装配器是纯函数模块，不碰网络不碰磁盘；喂 `reference/ocr-response-sample.json` 及一份实现期补的多页样本，确定性产出 md 与 sidecar —— **样本换过**，见 Implementation notes 第 3 条
- [x] 装配器用例覆盖：被忽略标签（header/footer/number/footnote）的块不占 md 行号、跨页合并块产出多个 rects、bbox 按各页 `dataInfo.pages[i]` 尺寸归一化到 0–1、`mdSha256` 与产出的 md 一致
- [x] 上传口收 PDF；页数与体积超过硬上限时**立即明确报错**，不进入解析
- [x] OCR 分批调用，页级断点续跑；`use_doc_preprocessor` 保持 false（改为 true 会让 bbox 与原件错位）
- [x] 部分页 OCR 失败时其余页照常产出，失败页可识别，整份不作废
- [x] 解析进度经既有 SSE 通道上报「原文解析 N/M 页」，未开新通道
- [x] md 与 sidecar 就绪后才起 agent
- [x] 原件与预览版按 sha256 存到 workspace 之外，`git status` 在解析后不含任何二进制；仓内只多出 md 与 sidecar
- [~] 预览版与原件的页数、逐页页面尺寸完全一致（用一份真扫描件断言）—— 真件断言已过，但那是**电子版**；扫描件路径用合成位图代替，见 Known gaps
- [x] agent 用文件工具写 `sources/` 下的 md 或 sidecar 被拒绝并收到可读错误；写 `structured/`、`deliverables/` 不受影响
- [x] 预览版字节流与 sidecar 两条读端点可用，用例落在既有 REST adapter TestClient 测试接缝，对齐矩阵 overview/items 用例风格
- [x] hagent pytest 全绿

## Blocked by

- 无——可立即开工。

## Implementation notes

实现期确立的事实，均经真件（`data/信保体系建设数据资源池项目招标文件.pdf`，60 页）实测。

### 1. md 取服务端 `markdown.text`，不由 `block_content` 重拼 —— **这是对 PRD 的偏离，需人工裁定**

PaddleOCR-VL 渲染 md 时会做块数据里根本不存在的加工：标题按层级给 `##`/`###`（同一 `paragraph_title` 标签实测 30 处 `##`、52 处 `###`，层级不在块数据里）、编号后补空格（58 处 `二、招标文件…` → `二、 招标文件…`）、表格 HTML 加样式属性。重拼必然丢掉这些结构信息，而章节层级正是抽取赖以导航的东西。

于是块与 md 的对应改为**顺序游标消费**：把两边都压成比对流（去空白、去 HTML 属性、去行首 `#`），逐块从游标处要求前缀相等；块之间夹的纯标签记号（如把 `figure_title` 裹起来的 `<div>`）可跳过，但**只跳标签、绝不跳正文字符**。整页对不上时该页照常出 md、不产出任何 sidecar 条目。

**说清楚偏离在哪**：PRD 写的是「拼装 md 与产出 sidecar 必须是同一段代码的同一次输出……严禁先拼 md 再回头做模糊匹配」。行号记账确实仍是一趟里边追加边记的；但 md 由服务端先拼好、块再对回去，形态上就是被禁的那一类，而且上面那套归一化是**有损**的（丢空白与属性），说它「精确」并不诚实——准确的说法是**在一套写明的归一化下做有序锚定消费**。之所以还是这么做：不这么做就得重实现 PaddleOCR 的渲染规则，那是照着它内部行为猜、且服务端一升级就静默失配。风险靠「整页要么全对要么不给条目」兜住——错的映射永远不会产出，只会变成「未能定位」。

实测 60 页 800 块**全部对上**，无一页降级。**PRD 未据此修订**，请裁定：认可则修订 PRD 该段，不认可则本条需重做。

### 2. 跨页合并靠 `global_group_id`，且**只**认它

`/restructure-pages` 把被分页切开的表格并成一块：正文落首页，续页块内容为空但各自带本页 bbox，靠 `global_group_id` 归组 → 一条目多矩形。真件上 11 处，最长跨 5 页。

**代码评审抓到的真 bug（已修）**：原实现在没有 `global_group_id` 时会退回块的页内 `group_id`。那是页内序号——各页首块都叫 0，一合并就把毫不相干的块并成一条，把矩形撒到它根本不在的页上。实测三页输入 66 块被并成 23 条、22 条横跨多页，首页标题带着第 1、2 页的矩形。这正是「稳稳地指到错误的地方」。而且这条路径**恰好在任一页解析失败时必被走到**（有失败页就跳过 restructure）——也就是 AC#5 的场景。现已改为只认 `global_group_id`，缺失即不合并，并有回归用例 `test_page_local_group_ids_never_merge_across_pages`。

### 3. 装配器夹具换过

AC 里点名的 `reference/ocr-response-sample.json` 是人工裁剪稿，`block_content` 与 `markdown.text` 双双带「（截断）」标记因而自相矛盾（表格两边对不上），喂进装配器只会走整页降级、产出 0 条目。故改用 `tests/fixtures/ocr/single-page.json`：同一份样本补全被截断的表格，并补入 header/number/footer 三个被忽略标签的块（真实页面必有，原样本恰好没有）。另加 `multipage-crosspage.json`——真件第 21–24 页经 `/restructure-pages` 的响应，含跨 4 页合并表。

## Verification

- `pytest -v` 全绿：**1250 passed, 34 skipped**（基线 1182，新增 68 条）。
- 真件实跑（60 页，OCR 约 50 s）：md 1572 行 / sidecar 773 条目 / 0 条越界行号 / 0 条指向空行 / 0 个 bbox 越界 0–1 / 11 条跨页多矩形；`mdSha256` 与 md 一致。
- **矩形落点独立校验**：把 sidecar 归一化矩形映射回预览版 PDF 用户空间，用 pypdf 取框内文字与 md 正文比对，抽样 25 条 17 条重合 >80%。同一校验器拿**未经本次实现处理的原始 OCR bbox** 量原件，得数完全相同（17/25）——差额来自校验器自身的文字定位口径，不是管线；本实现的落点精度已等于 OCR bbox 本身的上限。
- 预览版：60 页、逐页页面尺寸与原件完全一致，834 KB → 617 KB。
- `git status` 解析后干净，仓内只多出 md 与 sidecar；原件与预览版在 `HAGENT_BLOB_ROOT` 下按 sha256 存放。
- 两条读端点 curl 通过：preview `200 application/pdf`、sidecar `200 application/json`；未知文档/未知项目均 404。

## Known gaps

- **扫描件预览版用合成位图 PDF 断言**，不是真扫描件——手边只有电子版真件。真扫描件到手后应重跑等价实跑，并据此敲定 dpi 档位（当前 150 dpi / JPEG q60）。
- 实跑用的是 `HAGENT_SANDBOX_KIND=none` 的 host 模式；smolvm 下「解析完成后补注入 VM」这条路径只有代码与单测，未实跑。
- `HAGENT_BLOB_ROOT` 默认 `/tmp/hagent/blobs`（与既有 `HAGENT_WORKSPACE_ROOT` 默认同源）。原件的「保留并提供下载」在部署上要求把它指到持久盘，否则重启即失。

## Hand-off to 02

- 上传 PDF 时 `POST /projects/{pid}/files` 返回 `revision: null`（PDF 不进仓、无 commit）并多一个 `parsing: {pages}` 字段。前端 `ProjectUploadResult.revision` 现类型为 `string`，需放宽为 `string | null`——目前无代码读它，故运行期无影响，本票不动前端。
- `documents` 读端点新增 `has_preview` 字段，供 04 的容错分层判定「文档无 PDF 原件 → 降级 md 预览」。
- 新增三个 SSE 事件 `ingest.progress` / `ingest.completed` / `ingest.failed`（走既有消息通道，未开新通道），契约见 `hagent/docs/sse-message-events.md` §4.5.1。
