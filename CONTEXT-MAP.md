# CONTEXT-MAP

本仓库为多上下文布局。各上下文的领域词汇表按主题查对应文件（暂缺的由 `/domain-modeling` 惰性创建）：

- `frontend/CONTEXT.md` —— 产品前端（Next.js，工作台画布 / 对话执行流 / Frost 设计语言）
- `hagent/CONTEXT.md` —— Agent 后端（FastAPI + SSE，Project / Session / Run / 沙箱租约 / 工作区）

全局/跨端架构决策在根 `docs/adr/`（0001 起）；上下文专属决策在 `frontend/docs/adr/`、`hagent/docs/adr/`（按需创建）。

消费规则见 `docs/agents/domain.md`。
