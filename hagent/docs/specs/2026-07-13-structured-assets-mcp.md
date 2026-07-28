# Design Spec: 结构化资产管理面（对象库 + MCP 工具面）

**Date**: 2026-07-13
**Repo**: `/home/han/workplace/tender`（`hagent/` 为主，含 skill 重构与前端契约变更）
**Status**: DRAFT（方向经 2026-07-13 grilling 确认，见 ADR 0008；细节实现期回写）
**承接关系**: 建于 ADR 0007 之上（project workspace 仍是源文件与交付物的文件层）；取代 `bid-response-matrix` skill 的文件流水线（chunk/done/merge_plan/final JSON 全部退场）；旧本体层 ADR 0001–0006 已废弃，本 spec 不承接其概念。
**领域词汇**: `hagent/CONTEXT.md`（结构化资产、管理面、对象库、草稿区、发布、增量维护、导出投影、偏离表、document registry）。

## 1. Problem Statement

应答矩阵以 `bid_response_matrix_*/final/*.json` 文件形态活在 project workspace，由 skill 自由写入：变更无校验无审计；确认/偏离等人工状态无处落（文件重写即丢）；schema 契约在 skill 文档与三个校验脚本里各存一份；前端扫目录取数。目标：结构化资产升格为受管对象——对象库为唯一事实来源，agent 经 MCP 工具面读写，人经前端 REST 读写，全链路校验 + 审计 + 并发裁决。

## 2. 关键决策（S1–S11，均已经 grilling 确认）

| # | 决策 | 选择 | 否决备选 |
| --- | --- | --- | --- |
| S1 | 事实来源 | 对象库（hagent SQLite 扩表）；workspace 无 final JSON；文件只是导出投影 | 文件为载体 + server 只管状态（双写、可绕过、指针悬空） |
| S2 | 接入拓扑 | 结构化资产服务唯一写入口；MCP adapter（agent）+ REST adapter（前端）双门 | MCP 唯一网关（UI 查询/订阅模式与 MCP 语义不配） |
| S3 | 首发范围 | 仅应答矩阵域；偏离表 = 条目应答状态投影（无矩阵外行，无独立实体）；大纲推迟 | 同时定义大纲实体（形状未定，双未知下注） |
| S4 | 抽取路径 | 全程工具化：草稿区 staging → 批量提交 → 行级修复 → 服务端校验 → publish 门禁 | 终点一次性导入（治理面外劳动不可审计、长 payload 必拆） |
| S5 | 源文件 | document registry 注册（路径+sha256+类型→doc_id）；源文件本体仍是 workspace 普通文件 | 源文件也入库（它们是输入材料非结构化资产） |
| S6 | 发布语义 | 活对象：publish = 质量门禁 + revision 快照；发布后行级变更持续受管 | 定稿封存（确认/偏离都发生在发布后，冻结即自缚） |
| S7 | 重解析 | 增量维护为默认（行级 add/update/drop，人工状态天然保留）；全量重抽为逃生门（显式 `discard_manual_states=true`） | 对齐迁移（模糊匹配难题）；整版替换为默认（人工劳动灭失） |
| S8 | agent 接入 | 真 MCP client：server 模式 loopback Streamable HTTP；CLI host 模式同一 FastMCP 对象走 stdio | 进程内绑定 + MCP 只对外（agent 面双绑定漂移，MCP 面无人日用） |
| S9 | 读路径 | 对象读取走只读工具（查询式、强制分页）；MCP resources 只放契约文档与抽取指南镜像 | resources 承载对象数据（静态 URI 撑不住过滤/分页，客户端支持弱） |
| S10 | skill | 瘦身保留（编排 + 认知指南），与工具 description 职责剥离；重构遵循 writing-great-skills | 取消 skill 进 MCP prompts（消费链路不存在）；指南塞工具描述（描述失焦） |
| S11 | 前端时序 | 双轨过渡：过渡期 publish 物化旧路径 JSON；前端切 REST 后关物化 | 一刀切（feature 分支过长，canvas 新编排断档） |

实现级默认（报备通过）：条目乐观锁（version 字段，冲突返回可行动错误）；append-only 审计事件（actor = `agent(run_id)` / `user` / `agent-on-behalf`，含前后值与 reason）；dev 阶段存量数据不迁移。

## 3. 数据模型（SQLite，实现期细化）

沿用 ADR 0004 废弃后的干净起点：**一切按 project_id 命名空间**，不预埋机构层。

```sql
-- 源文件注册表（接管 inputs/manifest.json 职责）
CREATE TABLE documents (
    id           TEXT PRIMARY KEY,      -- doc-<hash8>，同 (project_id, sha256) 幂等
    project_id   TEXT NOT NULL,
    path         TEXT NOT NULL,         -- project workspace 相对路径（OCR Markdown）
    sha256       TEXT NOT NULL,
    doc_type     TEXT,                  -- tender / amendment / clarification / other
    registered_at TEXT NOT NULL
);

-- 矩阵聚合根：每 (project, matrix_type) 一行
CREATE TABLE matrices (
    project_id   TEXT NOT NULL,
    matrix_type  TEXT NOT NULL,         -- basic_info / business / technical / scoring
    state        TEXT NOT NULL,         -- empty / drafting / published / published_drafting(逃生门重抽中)
    meta_json    TEXT NOT NULL,         -- envelope + 固定标量结构（project / evaluation）
    draft_meta_json TEXT,
    current_rev  INTEGER NOT NULL DEFAULT 0,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (project_id, matrix_type)
);

-- 条目行：items 与非 items 区段（timeline/contacts/…）统一为行，section 区分
CREATE TABLE matrix_items (
    project_id   TEXT NOT NULL,
    matrix_type  TEXT NOT NULL,
    stage        TEXT NOT NULL,         -- draft / current
    item_id      TEXT NOT NULL,         -- items 区段用业务 id（TECH-001）；非 items 区段生成行 id
    section      TEXT NOT NULL,         -- items / timeline / compliance_overview.* / …
    payload_json TEXT NOT NULL,         -- 条目本体（源 schema 的 item shape，含 source_refs）
    response_status TEXT,               -- pending / compliant / positive_deviation / negative_deviation
    response_note   TEXT,
    confirmed    INTEGER NOT NULL DEFAULT 0,
    version      INTEGER NOT NULL DEFAULT 1,   -- 乐观锁
    PRIMARY KEY (project_id, matrix_type, stage, item_id)
);

-- revision 快照（publish 时整矩阵快照）
CREATE TABLE matrix_revisions (
    project_id   TEXT NOT NULL,
    matrix_type  TEXT NOT NULL,
    rev          INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    published_at TEXT NOT NULL,
    actor        TEXT NOT NULL,
    PRIMARY KEY (project_id, matrix_type, rev)
);

-- append-only 审计事件
CREATE TABLE asset_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   TEXT NOT NULL,
    ts           TEXT NOT NULL,
    actor_kind   TEXT NOT NULL,         -- agent / user / agent_on_behalf / system
    actor_ref    TEXT,                  -- run_id / user 标识
    action       TEXT NOT NULL,         -- 工具名或 REST 动作名
    target       TEXT NOT NULL,         -- matrix_type[/item_id]
    before_json  TEXT,
    after_json   TEXT,
    reason       TEXT
);
```

要点：

- **草稿与当前版共存**（逃生门重抽期间 `stage=draft` 与 `stage=current` 并立），publish 原子切换：校验 → 快照入 revisions → draft 晋升 current → 清 draft。
- 实现期定案（票 01 回写）：revision 快照对象是**晋升后的新当前版**（rev N = 第 N 次发布的完整内容，首个发布即 rev 1 全量）。发布间隙的行级变更与人工状态不产生快照，靠 asset_events 的 before/after 逐笔可恢复；逃生门重发布前的旧当前版以其发布时的 rev N-1 快照 + 其后事件流复原。
- 偏离表投影 = `SELECT ... WHERE response_status IN (…)`，无独立表。
- `validation/unresolved_items` 保留为 `section='unresolved_items'` 的行，随矩阵管理。
- 应答状态字段仅 business / technical 的 items 区段有效。

## 4. 服务层（唯一写入口）

`src/hagent/assets/`（新模块，一个文件一个职责）：

- `store.py` — 表访问；`service.py` — 领域动作（下表工具一一对应的函数）+ 乐观锁 + 审计；`validators.py` — 三脚本逻辑上移：结构校验（原 `validate_response_matrix.py`）、组装一致性（原 `assemble_matrix.py` 的去重/id 唯一/区段合法性）、源文保真（原 `verify_source_fidelity.py`，经 document registry 读 workspace 源文件按 line_span 比对重叠度）；`projection.py` — 导出投影（旧路径 final JSON 物化、偏离表导出）；`router.py` — REST adapter；`mcp.py` — FastMCP adapter。
- 校验报告为结构化对象：每条错误带 `target`（matrix/item）、`code`、`message`、**修复建议**（actionable error 原则，继承三脚本的报错风格）。
- REST 与 MCP 之外**禁止旁路直写**对象表（对齐 store 只从 service 走的模块纪律）。

实现期定案（票 07 回写，REST adapter）：

- 路由面（`assets/router.py`，挂 FastAPI 主 app，`require_api_key` 同其余路由）：
  读——`GET /projects/{pid}/matrices`（四矩阵状态汇总，票 08 恢复路径）、
  `GET /projects/{pid}/matrices/{matrix_type}`（envelope + 分组统计）、
  `GET /projects/{pid}/matrices/{matrix_type}/items`（分页查询，过滤参数对齐
  `prose_query_matrix_items`，偏离表投影同源）；写——`POST …/items/{item_id}/confirm`、
  `PUT …/items/{item_id}/response-status`（人工动作，审计 actor_kind=user）。
- **同参数同结果由共用模型锁定**：读输出模型与转换器（条目/分页 envelope/总览/状态汇总）
  抽到 `assets/schemas.py`，MCP 与 REST adapter 同一来源构造；分页语义（limit 默认 20、
  上限 100、has_more/next_offset/total_count）单一出处。
- 人工动作乐观锁：service 层 `confirm_item` / `set_item_response_status` 增可选
  `expected_version`（与 update_item 同款冲突处理：被拒尝试落审计 + ConflictError）。
  MCP 面的两个代录工具暂不透出该参数（agent 代录发生在对话即时上下文，陈旧读风险
  属前端场景）。
- 错误映射：`ConflictError` → 409（detail 带 `current_version`）；`item_not_found` /
  `matrix_empty` → 404；其余 AssetError → 400；detail 一律 `{code, message, hint}`。
  未知 matrix_type / 应答状态由路径与请求模型的 Literal 拦截（422）。项目不存在按
  projects 路由同款 404（协议层资源检查，非业务逻辑）。

## 5. MCP 工具面（15 个，均 `prose_` 前缀）

经 mcp-builder 最佳实践审查。通例：Pydantic 输入/输出 schema（structured output）；读类标 `readOnlyHint`；无状态（草稿态只在 DB，与 MCP session 无关）；列表读强制分页（`limit` 默认 20，返回 `has_more`/`next_offset`/`total_count`）。

| 工具 | 参数要点 | 注解 |
| --- | --- | --- |
| `prose_register_document` | project_id, path, doc_type | 幂等（同 project+sha256 返回既有 id） |
| `prose_list_documents` | project_id, 分页 | 只读 |
| `prose_start_matrix_draft` | project_id, matrix_type, `discard_manual_states`(默认 false；published 状态下开草稿必须显式 true) | destructive（带 discard 时） |
| `prose_submit_matrix_records` | matrix, records[]（schema 强制 maxItems=10）, section | 仅草稿态可用 |
| `prose_update_matrix_item` | matrix, item_id, set{}, reason, expected_version | 靶点规则：有草稿写草稿，无草稿写当前版（=增量维护） |
| `prose_drop_matrix_item` | matrix, item_id, reason | destructive |
| `prose_move_matrix_item` | from_matrix, to_matrix, item_id, new_id, set{}, reason | |
| `prose_set_matrix_meta` | matrix, set{}（深合并 envelope） | |
| `prose_validate_matrix` | matrix 或 all | 只读；返回结构化错误 + 修复建议 |
| `prose_publish_matrix` | matrix | 门禁：任一校验 error 即拒绝 |
| `prose_get_matrix` | matrix | 只读；envelope + 分组统计（决策触发器数字），**不含条目** |
| `prose_query_matrix_items` | matrix, 过滤（section/category/mandatory/response_status/confirmed/关键词）, 分页 | 只读；偏离表投影即一组过滤参数 |
| `prose_get_matrix_status` | project_id | 只读；四矩阵 state/记录数/最近校验摘要 |
| `prose_set_item_response_status` | matrix, item_id, status, note, reason | 人工动作 agent 代录，审计记 agent_on_behalf |
| `prose_confirm_matrix_item` | matrix, item_id | 同上 |

MCP resources（非对象数据）：`prose://contracts/matrix-schema`（数据契约）、`prose://guides/extraction`（抽取指南镜像，直读 skill 目录同一份 markdown，单一来源两处暴露）。

实现期定案（票 03 回写）：

- 无状态要求下**全部工具显式收 project_id**；矩阵参数名对齐上表字面（start 用 `matrix_type`，其余用 `matrix`，move 用 `from_matrix`/`to_matrix`）。
- `prose_register_document` **不收 sha256**：服务端按 workspace 相对路径读文件计算（`service.register_workspace_document`，含路径穿越防护），返回 `created` 标志区分幂等命中。
- `prose_get_matrix_status` 的「最近校验摘要」= 最近一条 `validate_matrix` 审计事件投影：`validate_matrix` 默认纯读不变，传 actor 时额外落摘要事件（status/error_count/warning_count/checked_items），对象数据仍只读。`publish_gated` 门禁产出的报告（放行或拒绝）同样落摘要，发布后摘要不陈旧。
- MCP 注解是静态的，无法按参数条件化：`prose_start_matrix_draft` 无条件标 `destructiveHint`（spec 表原文「destructive（带 discard 时）」的保守化）。
- `prose_get_matrix` 分组统计口径：`by_section` + items 区段的 `by_response_status`（NULL 计入 `unset` 桶）/`confirmed_count`/`mandatory_count`/`by_category`。
- 发布无旁路由 `service.publish_gated`（publish_gate + publish 组合）落实，adapter 一律走它。
- 错误面：ToolError 文本内嵌 JSON `{code, message, hint, …}`（乐观锁冲突加 `current_version`，publish 拒绝附完整校验报告）；意外异常只透出异常类型名，栈进 server 日志。

## 6. Transport 与安全

- server 模式：FastMCP 挂载到 hagent FastAPI（`/mcp`，Streamable HTTP，stateless JSON）；绑 `127.0.0.1` + 校验 Origin（防 DNS rebinding）。首发只服务 loopback（自家 agent）；**对外开放是独立后续任务，前置条件是 auth（方向 OAuth 2.1）**。
- CLI host 模式：同一 FastMCP 对象以 stdio 起（子进程共享 SQLite，WAL）；日志走 stderr。
- agent 接入：deepagents 侧 MCP client（langchain-mcp-adapters）；**动 core.py 前先读仓内 `deepagents/mcp.mdx` 与官方文档**（CLAUDE.md 既有纪律）。

实现期定案（票 03 回写）：

- 挂载方式：FastMCP 子 app 自带 `/mcp` 路径、整体挂 FastAPI 根做兜底（`app.mount("/mcp", …)` 会对不带尾斜杠的 POST /mcp 返回 307，部分 MCP client 不跟随重定向）；MCP session manager 由父 app lifespan 承载。
- loopback 约束在应用层由 `LoopbackOnlyASGI`（`assets/mcp_guard.py`，与工具面分文件）落实（仅作用于 `/mcp` 路径）：对端 IP 与 Origin（若带）均须 loopback，否则 403——部署绑 127.0.0.1 之外的第二道保险。无 Origin 头的请求放行（DNS rebinding 的载体是浏览器，必带 Origin；curl/SDK 类客户端由对端 IP 校验兜住）。
- stdio 入口：`python -m hagent.assets.mcp`；DB 路径 env 链与 server 相同（`HAGENT_SESSIONS_DB` → `HAGENT_DB_PATH` → `/tmp/hagent/sessions.db`），workspace 按 `HAGENT_WORKSPACE_ROOT` 镜像 ProjectWorkspace 路径约定；对象库连接启 WAL + busy_timeout 支撑 server 进程与 stdio 子进程共享同一 SQLite。
- run 归属：`HAGENT_MCP_ACTOR_REF` 注入审计 actor_ref（票 04 client 接线时闭环）。

实现期定案（票 04 回写）：

- agent 侧 client 收敛在 `src/hagent/mcp_tools.py`：连接构造（`prose_http_connection` / `prose_stdio_connection`）+ `load_prose_mcp_tools()`（langchain-mcp-adapters `MultiServerMCPClient`，每次工具调用新建 MCP session——stateless server 天然匹配，无连接生命周期要管）。接入点为 `create_hagent(mcp_connection=...)`，工具进 parent_tools 故 subagent 自动继承。
- **sync 桥**：deepagents graph 在 server（threadpool 里 `agent.stream`）与 CLI（`agent.invoke`）都同步执行，而 adapter 工具只有 coroutine。模块持一条后台事件循环线程（daemon），给每个工具补阻塞式 `func`；async 路径原样保留。server 模式无自锁：调用方在 worker 线程阻塞，主事件循环仍可服务 `/mcp`。
- **loopback URL 解析链**：显式参数 → `HAGENT_MCP_URL` → `http://127.0.0.1:8000/mcp`（README 规范端口）；server 起在非默认端口时必须设 env（app 无法自知端口）。
- **run 归属闭环**：HTTP 模式经 `X-Hagent-Actor-Ref` header（`assets/mcp_actor.py` 的 ASGI 层收进 ContextVar，stateless FastMCP 的工具任务从请求任务派生、contextvars 随任务复制）；stdio 模式经子进程 env。粒度为 session（agent 按 session 缓存，header 随连接配置固定）：server 记 `agent(session:<sid>)`，CLI 记 `agent(cli-demo)`。
- stdio 子进程 env 不整体继承（对齐 `inherit_env=False` 纪律）：只传 PATH/HOME + DB/workspace/skills 路径 + actor ref；API key 等不进子进程。
- `HAGENT_MCP_DISABLED` 为两个装配点（server/agents.py、cli.py）共同的关断阀（测试与排障用）；加载失败 fail loud，不静默降级成无工具面的 agent。

## 7. skill 重构（bid-response-matrix）

- 删除 `scripts/`（逻辑上移服务层）与 schema reference 的中间文件章节；`references/response-matrix-schema.md` 保留 final 形状部分并声明对象库为权威（或直接指向 MCP resource）。
- SKILL.md 重写为编排指南：注册文档 → `prose_start_matrix_draft` ×4 → 派 4 个 worker（并发或顺序）用 `prose_submit_matrix_records` 提交 → 主 agent 行级修复 → `prose_validate_matrix` → `prose_publish_matrix`。
- `references/worker-instructions.md` 保留认知部分（分类/mandatory 信号/粒度/冲突保守处理/覆盖自检），删除文件写纪律（已被工具 schema 接管）。
- 职责边界：工具 description 只写该工具自身的精确契约；跨工具的方法论一律归 skill / resource 镜像。重构遵循 writing-great-skills 规范。

实现期定案（票 05 回写）：

- SKILL.md 编排以**恢复检查先行**（`prose_get_matrix_status` 做断点续跑与「已发布走增量维护」的分流），随后注册文档 → 开草稿 ×4 → 派 4 worker → 主 agent 复核 → 校验修复环（保真失败集中成批修，一轮一批）→ publish ×4。
- worker 完成自检从 `assemble --check` 换成 `prose_validate_matrix` 自跑到无 error；覆盖清单（逐标题扫源文、mandatory 信号全呈现、评分表逐行）原样保留。
- schema reference 改对象库口径：矩阵 = meta（envelope + 固定标量）+ 区段行；`schema_version` / `generated_at` / `source_documents` 声明为服务端接管，agent 不提交。`packages`、`pass_fail_rules`、`tie_break_rules` 等记录列表明确为区段行、不进 meta。
- `scripts/` 删除后 `tests/assets/test_validators_parity.py` 按预置 skip 条件整体跳过（parity 基准不复存在，等价性由票 02 的移植测试语料继续锁定）。
- eval 流程迁移：`.hagent/skills/bid-response-matrix-workspace/`（三份真实语料 eval 定义 + 对象库口径 `grade.py`），承接原 extract-tech-requirements-workspace 的断言口径；门控 e2e 为 `tests/test_demo_e2e_prose_skill.py`（真实模型 + 真实语料 → 四矩阵 publish → 校验复跑 pass）。

## 8. 前端双轨与切换

1. 过渡期：`prose_publish_matrix` 成功后由 `projection.py` 物化四个 JSON 到 workspace 旧路径（`bid_response_matrix_<slug>_<ts>/final/`），旧读路径（`lib/hagent/matrix.ts` 扫目录）零改动存活；受配置开关控制。

实现期定案（票 06 回写）：

- 物化钩子挂 `service.publish_gated`（发布无旁路的同一入口），MCP / 未来 REST 发布自动覆盖；best-effort——投影异常只记 WARNING，publish 事务不受影响。
- 开关 `HAGENT_PUBLISH_PROJECTION`（默认开；`0/false/no/off` 关闭即零文件写入），调用时读取不缓存。
- 单目录复用而非每次发布新建：目录带 `.prose_projection.json` 标记文件识别归属，首个发布按 `<slug>_<ts>` 创建（slug 取 envelope project_id > project_name > hagent project id），后续发布覆盖写同目录——每次全量重写所有已发布矩阵（幂等自愈），即「重发布即覆盖」。复用条件是「带标记且时间戳全局最新」：被更新时间戳的无标记目录（旧 skill 遗留/外部还原）遮蔽时，改按当前时间戳新建自愈，前端 latestRunDir 不会停在陈旧目录。
- 物化文件由投影自行 `git add + commit`（消息镜像 ProjectWorkspace.commit 的 `Kind: projection` trailer）：前端 `list_files` 走 `git ls-files`，而 sandbox 模式 checkpoint 只提交 guest 变更，host 侧投影不自提交则前端永不可见；workspace 非 git 仓库（CLI host 模式）时跳过提交。与 checkpoint 撞 index.lock 时本次提交失败按 best-effort 兜住，文件已落地、下次发布补提交。
- 文档拼装：meta 深合并 `validators.META_SKELETONS` 骨架（缺省字段以 null/空列表呈现），区段行按 dot-path 嵌回（`unresolved_items` → `validation.unresolved_items`）；envelope 的 `schema_version`（同 revision 快照的 "1.0"）/ `generated_at` / `source_documents`（document registry 全量投影）由服务端接管。条目只物化 payload，发布后的人工状态不回写文件（投影只在 publish 时刻发生）。
- 偏离表接口 `export_deviation_table`：当前版 items 按应答状态过滤的行级投影（数据口径固定，文件格式留后续票）。
2. 前端切换票：读改 REST（envelope+统计、条目分页查询）；触发仍发 `/skill:bid-response-matrix` 消息（skill 名不变）；槽位状态推导改监听 SSE 里的新工具名事件（`prose_submit_matrix_records`/`prose_publish_matrix`），恢复路径改查 `prose_get_matrix_status` 对应 REST。人工动作（确认/偏离）走 REST 写端点。
3. 切换完成后关闭物化开关，删旧扫描代码。过渡期折损（四卡发布时同时点亮）已接受。

实现期定案（票 08 回写）：

- 前端拼装与视图契约不动：`assembleMatrixDocument`（`frontend/lib/hagent/matrix.ts`）把
  overview.meta + 条目行按区段 dot-path 嵌回旧 final JSON 形状（镜像
  `projection.build_matrix_document`，`unresolved_items` → `validation.unresolved_items`），
  四张卡的渲染组件零改动；items 区段的行级管理状态（confirmed/response_status/version）
  另存槽位 `itemRows`，供抽屉人工动作与乐观锁。
- 槽位推导：`tool_call.started` 按 `call_id` 累积 args 分片、正则提取 `matrix`
  （不等 JSON 闭合）；submit 命中即翻「解析中」，publish 的 `tool_call.completed`
  触发该矩阵 REST 装载（publish 被门禁拒绝时装载发现未发布、不落数据）。恢复路径查
  `GET /projects/{pid}/matrices`，只装载 published / published_drafting。
- 人工动作带 `expected_version`；409 冲突时前端重载该矩阵取回当前版本并提示重试。
- 物化开关默认值翻转为**关**（`HAGENT_PUBLISH_PROJECTION` 显式 1/true/yes/on 才物化，
  留作排障/回退旧读路径的逃生门）；`projection.py` 模块保留（偏离表导出接口仍在此）。
  旧扫描代码（`latestRunDir`/`MATRIX_FINAL_RE`/workspace 文件读端点的前端代理与客户端）删除。

## 9. 测试与验收

- `tests/assets/`：服务层单测（校验器逻辑移植原三脚本的测试语料）、乐观锁冲突、publish 原子性、审计完整性。
- MCP 面：MCP Inspector 手测 + pytest 起 stdio client 走全工具链；loopback HTTP 门控测试。
- e2e（门控，真实模型）：真实招标 Markdown → skill 编排 → 四矩阵 publish → 保真校验 pass；对照 `.hagent` 下既有 skill eval 语料。
- 验收锚点：三个校验器行为与原脚本一致（同语料同判定）；旧前端在双轨期无感。
