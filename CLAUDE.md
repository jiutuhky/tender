# Prose 仓库指令

供 Codex、Claude Code 等编码智能体共用；根 `AGENTS.md` 是本文件的符号链接，只维护这一份。

## 项目蓝图

**Prose** —— AI 原生标书编制平台（投标书 / 招标文件编写）。产品形态：用户拖入招标文件，智能体解析并结构化提取，逐步生成投标文件；对话执行流 + artifact 画布是核心交互。

## 目录结构

* `frontend/` —— Next.js 产品前端（本文件主要覆盖此目录）。
* `hagent/` —— Agent 后端（FastAPI + SSE，基于 LangChain deepagents）。后端任务遵循 `hagent/AGENTS.md`；涉及架构和运行机制时按主题查 `hagent/CLAUDE.md`。
* `data/` —— 真实招标文件语料（MinerU 抽取的 Markdown），前端可作为样本上传到 session。

> main 为主分支，特性开发走 feature 分支（如 `feat/frost-brand`）。

## 常用命令

前端（`frontend/`，包管理器 **pnpm**）：

```bash
pnpm dev / build / start
pnpm lint       # ESLint
pnpm typecheck  # tsc --noEmit（strict + noUncheckedIndexedAccess）
```

前端代码改动的质量门是 `pnpm typecheck` + `pnpm lint`，当前无独立测试框架。纯文档或技能指令改动检查内容、链接和格式即可；视觉改动另检查受影响界面。检查通过后，只有新改动、失败或未解决疑点才需要扩大或重复验证。

后端联调（`hagent/`，需 8000 端口，详见 `hagent/README.md`）：

```bash
uvicorn hagent.server.app:create_app --factory --host 0.0.0.0 --port 8000
```

## 技术栈

Next.js 16（App Router）+ React 19 + TypeScript strict；Zustand 做客户端状态；streamdown 渲染智能体 markdown 回复；手写 CSS + className，**无 Tailwind / CSS-in-JS**；路径别名 `@/*` → `frontend/` 根。

## 架构与规范

### 前后端契约

* **改 message 解析或渲染前，必读** [**`hagent/docs/sse-message-events.md`**](hagent/docs/sse-message-events.md) —— SSE 消息事件的事实契约手册。
* 浏览器不直连后端：`app/api/hagent/**` 做同源代理，API key 只在服务端持有（`lib/server/upstream.ts`）。
* SSE 流量大：store 里的事件批处理（rAF 合帧）是性能关键，改 `lib/store/workspace.ts` 别破坏它。

### 页面组织

* 路由入口 `/` → `/home`（Agent 统一入口）；核心页为 `/workspace`（左 artifact 画布 + 右对话执行流）。
* 每个路由用 `_components/` 私有目录放专属组件，各自 `import "./styles.css"`；全站共用外壳在 `components/shell/`。

## 执行与完成

依据当前请求和已有上下文完成授权范围内的修改、相关验证及本次引入问题的修复。常规可逆选择自行判断；只有缺少会实质改变结果且无法推断的信息，或下一步超出已有授权时才询问，同时继续不受影响的工作。

完成以请求的交付物和相关质量门为准；不在第一版实现后默认停下等待审阅，也不扩展成无关重构。简洁说明结果、验证和实际遗留问题。用户的明确要求优先于技能建议；技能若导致暂停，指出具体文件与规则。仅审计、计划或多方案选型请求仍遵守其交付范围。

## 约定

* 文案、注释、UI 文本一律**简体中文**。
* 交互/状态组件标 `"use client"`；展示型组件保持 Server Component。
* 图标统一从 `components/ui/icons/index.tsx` 导入（内联 SVG）。
