Status: resolved
Blocked by: 无

# 01 契约与数据层打通

## Parent

`.scratch/source-trace-preview/PRD.md`

## What to build

前端能拿到溯源所需的两样东西：文档注册表（document_id → workspace 路径映射）与招标文件 Markdown 原文。hagent 对象库 REST adapter 新增项目级 documents 读端点（document_id / path / sha256 / doc_type，分页），鉴权与既有矩阵读端点一致；前端新增 documents 列表与 project workspace 文件内容两条同源读代理（API key 只在服务端持有）；数据层提供取数函数与文档内容缓存——按 document_id 缓存、sha256 作内容版本键、项目切换失效。

本票完成后无 UI 呈现，验证方式是 pytest + curl（经代理取到注册表与文件原文）。

## Acceptance criteria

- [x] documents 读端点返回注册表记录（id/path/sha256/doc_type），分页语义与既有条目查询端点同构，项目不存在返回 404
- [x] 端点用例落在既有 REST adapter TestClient 测试接缝（对齐矩阵 overview/items 用例风格），hagent pytest 全绿
- [x] 前端两条读代理可用：documents 列表、workspace 文件内容（透传上游状态码与 Content-Type）
- [x] 数据层取数函数与文档内容缓存就位：同一 document_id 重复取数不重复请求，sha256 变化或项目切换后失效
- [x] `pnpm typecheck` + `pnpm lint` 通过

## Blocked by

- 无——可立即开工。

## Comments

**2026-07-16 实现完成（agent）**

- 后端：`assets/router.py` 新增 `GET /projects/{pid}/documents`；`DocumentModel`/`DocumentPage` 从 `mcp.py` 上移 `schemas.py`（REST 与 MCP `prose_list_documents` 同源投影），`DocumentPage` 补 `limit`/`offset` 回显与条目查询 envelope 同构——MCP 结构化输出随之多两个字段（加性变更）。列表读顺带返回 `registered_at`/`created`（共用投影所致，`created` 列表读恒 false）。
- 前端：`app/api/hagent/projects/[pid]/documents/route.ts` 与 `.../workspace/files/[...path]/route.ts` 两条读代理（状态码与 Content-Type 均随上游）；`lib/hagent/api.ts` 增 `listDocuments`/`fetchAllDocuments`/`getWorkspaceFileText`；`lib/hagent/documents.ts` 数据层缓存（注册表 + 内容，按 document_id 缓存、sha256 版本键、in-flight 去重、项目切换整体失效）。
- 验证：hagent pytest 全绿（1182 passed，documents 用例 5 组含 401/404/422/分页边界）；`pnpm typecheck` + `pnpm lint` 通过；实跑验收（隔离栈 8001/3001）curl 经代理取到注册表与招标文件原文，Content-Type 透传 `text/markdown`，直连上游无 key 401。
- 双轴 code review：无硬违规；已修复「documents 代理未透传上游 Content-Type」与翻页常量命名跨域失真两项。
