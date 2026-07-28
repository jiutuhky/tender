# PRD：结构化资产管理面（对象库 + MCP 工具面）

Status: ready-for-agent

> 源自 2026-07-13 grilling 会话共识；决策依据 ADR 0008，实施契约 `hagent/docs/specs/2026-07-13-structured-assets-mcp.md`，领域词汇见 `hagent/CONTEXT.md`。

## Problem Statement

应答矩阵目前是 skill 自由写进 project workspace 的普通 JSON 文件：变更无校验、无审计、无并发裁决；用户在编制期做出的确认与偏离标注没有安全落点（文件一重写即丢）；补遗/澄清只能全量重抽；schema 契约在 skill 文档与三个校验脚本里各存一份必然漂移；前端靠扫目录取数。

## Solution

结构化资产升格为受管对象：hagent 内立「结构化资产服务」为唯一写入口（对象库 = SQLite 扩表 = 唯一事实来源），FastMCP adapter 供 agent 读写（loopback Streamable HTTP / CLI stdio，15 个 `prose_*` 工具），REST adapter 供前端读与人工动作。抽取全程工具化（草稿区 → 批量提交 → 行级修复 → 服务端校验 → publish 门禁），发布后矩阵是活对象，补遗默认行级增量维护。skill 瘦身为编排 + 认知指南。前端双轨过渡：过渡期发布物化旧路径文件，切换后关闭。

## Scope

首发仅应答矩阵域；偏离表为应答状态投影（无独立实体）；大纲推迟。对外 MCP 开放（auth）不在本 feature。

## Tickets

| 票 | 内容 | 依赖 |
| --- | --- | --- |
| 01 | 对象库 + 结构化资产服务（表/乐观锁/审计/document registry） | — |
| 02 | 校验器上移（三脚本逻辑 → validators.py） | 01 |
| 03 | FastMCP 工具面 + 挂载 + stdio 入口 | 01, 02 |
| 04 | agent MCP client 接入（loopback + CLI 双链路） | 03 |
| 05 | skill 重构（瘦身 + resource 镜像） | 04 |
| 06 | 发布物化双轨（导出投影 + 开关） | 03 |
| 07 | REST adapter（前端读端点 + 人工动作） | 01, 02 |
| 08 | 前端切换（REST 读/SSE 槽位推导/关物化） | 05, 06, 07 |
