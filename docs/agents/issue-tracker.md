# Issue tracker：本地 Markdown

本仓库的 issue 与 PRD 以 markdown 文件形式存放在 `.scratch/` 下。无远程 issue 服务，无 PR 请求入口。

## 约定

- 一个特性一个目录：`.scratch/<feature-slug>/`
- PRD 是 `.scratch/<feature-slug>/PRD.md`
- 实现票是 `.scratch/<feature-slug>/issues/<NN>-<slug>.md`，从 `01` 起编号
- triage 状态记在每张票文件头部的 `Status:` 行（角色字符串见 `triage-labels.md`）
- 评论与对话历史追加到文件底部 `## Comments` 标题下

## 当 skill 说「publish to the issue tracker」

在 `.scratch/<feature-slug>/` 下新建文件（目录不存在则创建）。

## 当 skill 说「fetch the relevant ticket」

读取所指路径的文件。用户通常会直接给出路径或票号。

## Wayfinding 操作

供 `/wayfinder` 使用。**map** 是一个文件，每张票对应一个**子文件**。

- **Map**：`.scratch/<effort>/map.md` —— Notes / Decisions-so-far / Fog 正文。
- **子票**：`.scratch/<effort>/issues/NN-<slug>.md`，从 `01` 起编号，问题写在正文里。`Type:` 行记录票型（`research`/`prototype`/`grilling`/`task`）；`Status:` 行记录 `claimed`/`resolved`。
- **阻塞**：文件头部一行 `Blocked by: NN, NN`。所列文件全部 `resolved` 时该票解除阻塞。
- **Frontier**：扫描 `.scratch/<effort>/issues/` 中开放、未阻塞、未认领的文件；编号最小者优先。
- **认领**：动工前先置 `Status: claimed` 并保存。
- **解决**：在 `## Answer` 标题下追加答案，置 `Status: resolved`，再把上下文指针（要点 + 链接）追加到 `map.md` 的 Decisions-so-far。

## 本仓库注记

根目录既有的 `tickets.md`（M1「项目工作区上移」拆票）是此约定确立之前的产物，内容保留有效；此后新工作项一律走 `.scratch/`，M1 票可择机迁移。
