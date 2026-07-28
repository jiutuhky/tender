# Deep Agents 文档索引

LangChain Deep Agents 框架官方文档导航。Deep Agents 是用于构建可执行长时任务、可调度子代理、可访问文件系统/沙箱的通用代理框架，覆盖 Python/JavaScript SDK、CLI、前端集成全栈。

---

## 一、入门与概览

| 文档 | 内容简介 |
|------|---------|
| [overview.mdx](./overview.mdx) | Deep Agents 框架总览，介绍核心能力与生态 |
| [quickstart.mdx](./quickstart.mdx) | 几分钟内构建首个 Deep Agent 的入门指南 |
| [comparison.mdx](./comparison.mdx) | 与 Claude Agent SDK 的功能与架构对比 |
| [harness.mdx](./harness.mdx) | Deep Agents Harness 提供的能力模块总览 |
| [customization.mdx](./customization.mdx) | 模型、工具、子代理、后端等核心定制选项总览 |

## 二、核心能力（Harness Capabilities）

| 文档 | 内容简介 |
|------|---------|
| [models.mdx](./models.mdx) | 配置 LangChain 兼容模型提供商与参数 |
| [profiles.mdx](./profiles.mdx) | 按提供商或模型打包默认配置的 Harness 配置文件 |
| [memory.mdx](./memory.mdx) | 基于文件系统的跨会话长期记忆配置 |
| [skills.mdx](./skills.mdx) | 通过 Agent Skills 规范扩展代理领域能力 |
| [subagents.mdx](./subagents.mdx) | 同步子代理委派任务与上下文隔离机制 |
| [async-subagents.mdx](./async-subagents.mdx) | 后台并行运行、可中途指令与取消的异步子代理 |
| [context-engineering.mdx](./context-engineering.mdx) | 控制代理上下文来源与长任务上下文管理 |
| [permissions.mdx](./permissions.mdx) | 通过声明式规则控制文件系统读写权限 |
| [human-in-the-loop.mdx](./human-in-the-loop.mdx) | 为敏感工具调用配置人工审批与中断 |
| [backends.mdx](./backends.mdx) | 可插拔文件系统后端的选择、路由与策略配置 |
| [sandboxes.mdx](./sandboxes.mdx) | 隔离环境中执行代码的沙箱后端配置 |

## 三、流式输出与协议

| 文档 | 内容简介 |
|------|---------|
| [streaming.mdx](./streaming.mdx) | 使用 LangGraph 子图流式输出主代理与子代理事件 |
| [event-streaming.mdx](./event-streaming.mdx) | 类型化流式输出协调器、子代理、工具调用与最终结果 |
| [acp.mdx](./acp.mdx) | 通过 Agent Client Protocol (ACP) 接入代码编辑器 |
| [a2a.mdx](./a2a.mdx) | LangSmith A2A 服务文档重定向 |
| [mcp.mdx](./mcp.mdx) | LangChain MCP（Model Context Protocol）文档重定向 |

## 四、部署与生产化

| 文档 | 内容简介 |
|------|---------|
| [deploy.mdx](./deploy.mdx) | 使用 CLI 一键部署代理到 LangSmith Deployment |
| [going-to-production.mdx](./going-to-production.mdx) | 推向生产环境的内存、沙箱、防护与部署考量 |
| [data-locations.mdx](./data-locations.mdx) | CLI 配置、会话、技能等本地数据存储路径说明 |

## 五、教程（端到端示例）

| 文档 | 内容简介 |
|------|---------|
| [data-analysis.mdx](./data-analysis.mdx) | 构建可分析 CSV、生成图表的数据分析代理 |
| [content-builder.mdx](./content-builder.mdx) | 构建带品牌记忆与图像生成的内容写作代理 |
| [deep-research.mdx](./deep-research.mdx) | 构建多步骤网络研究并合成报告的代理 |

## 六、CLI（终端编码代理）

位于 [`cli/`](./cli/) 子目录。

| 文档 | 内容简介 |
|------|---------|
| [cli/overview.mdx](./cli/overview.mdx) | 基于 SDK 构建的终端编码代理快速上手 |
| [cli/configuration.mdx](./cli/configuration.mdx) | CLI 的 config.toml、hooks 与 MCP 服务器配置详解 |
| [cli/providers.mdx](./cli/providers.mdx) | 为 CLI 配置任意 LangChain 兼容模型提供商 |
| [cli/memory-and-skills.mdx](./cli/memory-and-skills.mdx) | CLI 的 AGENTS.md 持久化记忆与可复用技能机制 |
| [cli/subagents.mdx](./cli/subagents.mdx) | 通过 Markdown 文件定义 CLI 自定义子代理 |
| [cli/mcp-tools.mdx](./cli/mcp-tools.mdx) | 通过 .mcp.json 为 CLI 加载外部 MCP 工具 |
| [cli/remote-sandboxes.mdx](./cli/remote-sandboxes.mdx) | 在 LangSmith、Daytona 等远程沙箱中执行工具调用 |

## 七、前端集成

位于 [`frontend/`](./frontend/) 子目录。

| 文档 | 内容简介 |
|------|---------|
| [frontend/overview.mdx](./frontend/overview.mdx) | 实时可视化协调器与子代理工作流的前端构建模式 |
| [frontend/sandbox.mdx](./frontend/sandbox.mdx) | 为沙箱编码代理构建 IDE 风格三栏界面 |
| [frontend/subagent-streaming.mdx](./frontend/subagent-streaming.mdx) | 分离协调器与子代理流以渲染进度卡片 |
| [frontend/todo-list.mdx](./frontend/todo-list.mdx) | 从代理状态实时同步任务清单的进度面板 |

## 八、变更日志

| 文档 | 内容简介 |
|------|---------|
| [changelog-py.mdx](./changelog-py.mdx) | Python 版本更新日志 |
| [changelog-js.mdx](./changelog-js.mdx) | JavaScript 版本更新日志 |

---

## 快速定位指南

- **第一次接触 Deep Agents** → `overview.mdx` → `quickstart.mdx`
- **想构建终端编码代理** → `cli/overview.mdx`
- **想了解某项能力如何配置** → 第二节「核心能力」对应条目
- **想做端到端示例** → 第五节「教程」三选一
- **要做前端 UI 集成** → `frontend/overview.mdx`
- **准备上线** → `going-to-production.mdx` + `deploy.mdx`
- **与 Claude Agent SDK 选型对比** → `comparison.mdx`
