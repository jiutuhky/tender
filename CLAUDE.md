# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目蓝图

**Prose** —— AI 原生标书编制平台（投标书 / 招标文件编写）。产品形态：用户拖入招标文件，智能体解析并结构化提取，逐步生成投标文件；对话执行流 + artifact 画布是核心交互。

## 目录结构

* `frontend/` —— Next.js 产品前端（本文件主要覆盖此目录）。
* `hagent/` —— Agent 后端（FastAPI + SSE，基于 LangChain deepagents）。**有自己的 `hagent/CLAUDE.md`，改后端前必读**。
* `data/` —— 真实招标文件语料（MinerU 抽取的 Markdown），前端可作为样本上传到 session。
* `.design/prototype/` —— 设计原型草稿，**视觉设计的事实来源**，改视觉风格前先参考。

> main 为主分支，特性开发走 feature 分支（如 `feat/frost-brand`）。

## 常用命令

前端（`frontend/`，包管理器 **pnpm**）：

```bash
pnpm dev / build / start
pnpm lint       # ESLint
pnpm typecheck  # tsc --noEmit（strict + noUncheckedIndexedAccess）
```

前端无测试框架，`pnpm typecheck` + `pnpm lint` 即质量门。

后端联调（`hagent/`，需 8000 端口，详见 `hagent/README.md`）：

```bash
uvicorn hagent.server.app:create\_app --factory --host 0.0.0.0 --port 8000
```

## 技术栈

Next.js 16（App Router）+ React 19 + TypeScript strict；Zustand 做客户端状态；streamdown 渲染智能体 markdown 回复；手写 CSS + className，**无 Tailwind / CSS-in-JS**；路径别名 `@/\*` → `frontend/` 根。

## 架构与规范

### 前后端契约

* **改 message 解析或渲染前，必读** [**`hagent/docs/sse-message-events.md`**](hagent/docs/sse-message-events.md) —— SSE 消息事件的事实契约手册。
* 浏览器不直连后端：`app/api/hagent/\*\*` 做同源代理，API key 只在服务端持有（`lib/server/upstream.ts`）。
* SSE 流量大：store 里的事件批处理（rAF 合帧）是性能关键，改 `lib/store/workspace.ts` 别破坏它。

### 页面组织

* 路由入口 `/` → `/home`（Agent 统一入口）；核心页为 `/workspace`（左 artifact 画布 + 右对话执行流）。
* 每个路由用 `\_components/` 私有目录放专属组件，各自 `import "./styles.css"`；全站共用外壳在 `components/shell/`。

### 品牌与样式（Frost·霜，macOS 风格）

* **设计系统遵循 `frost-design` skill**：做任何界面/视觉产出（生产页面或原型 mock）前先调用该 skill，按其中的色彩、字体、组件规范执行。

## 约定

* 文案、注释、UI 文本一律**简体中文**。
* 交互/状态组件标 `"use client"`；展示型组件保持 Server Component。
* 图标统一从 `components/ui/icons/index.tsx` 导入（内联 SVG）。

## Agent skills

### Issue tracker

工作项以本地 markdown 存放在仓库内 `.scratch/<feature>/` 下（无远程 issue 服务，无 PR 请求入口）。见 `docs/agents/issue-tracker.md`。

### Triage labels

五个 triage 角色均用规范默认名（needs-triage / needs-info / ready-for-agent / ready-for-human / wontfix）。见 `docs/agents/triage-labels.md`。

### Domain docs

多上下文布局：根 `CONTEXT-MAP.md` 指向 `frontend/` 与 `hagent/` 各自的 `CONTEXT.md`；根 `docs/adr/` 存全局决策。见 `docs/agents/domain.md`。

