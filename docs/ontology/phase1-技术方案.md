# 本体层 Phase 1 技术方案 —— 矩阵域本体化与评分沙盘

- 状态：草案（评审后按 Matt 契约拆解：spec 落 `hagent/docs/specs/`，工单进仓根 `tickets.md`）
- 日期：2026-07-08
- 关联：ADR 0001–0006、`docs/ontology/glossary.md`
- 约定：本文只描述 Phase 1（首发）；Phase 2 撰写域 / Phase 3 机构记忆仅出现在接缝说明中。

## 0. 范围

**做**：矩阵对象入库（脱离 session 文件）→ Action 网关（唯一写入口 + 审计）→ 对齐引擎（重解析三路分流）→ 漏项 / 覆盖两个确定性 Function → 评分沙盘 UI（主视图 + 状态带 + 裁决抽屉）。

**明确不做**（红线，出处见对应 ADR）：

| 不做 | 出处 |
|------|------|
| 章节正文的 Action 收口（维持 skill 文件流） | ADR 0002 |
| 分数预测（只做覆盖三态） | ADR 0005 |
| org 概念进 UI、登录/多租户 | ADR 0004 |
| 独立本体服务 / Postgres 迁移 | ADR 0004 |
| 证据资产功能（只建表留位） | ADR 0001 |

## 1. 总体数据流

```
skill 流水线（沙箱内，不变）
  └─ bid_response_matrix_*/final/{basic_info,business,technical,scoring}.json
       │  前端发现 run 目录（现状机制不变）
       ▼
POST /ontology/projects/{id}/import        ← 系统级 Action：import_matrix
  ├─ 首次导入：对象 upsert + 覆盖链接播种（scoring.related_requirement_ids）
  └─ 再次导入：对齐引擎三路分流（迁移 / 待复核 / 新增·作废）
       ▼
本体模块（hagent 内，SQLite 同库新表，org_id 预埋）
  ├─ Action 网关：confirm_item / mark_deviation / set_response_status / create_link …
  ├─ 确定性 Function：coverage_check / gap_check
  └─ 审计流水 actions_log
       ▼
GET /ontology/projects/{id}/sandbox        ← 评分沙盘聚合（评分树 + 三态 + 统计 + 警示）
GET /ontology/projects/{id}/queue          ← 裁决队列
       ▼
/workspace 画布：评分沙盘（主视图）+ 状态带 + 裁决抽屉
```

关键判断：hagent 的自研工具在**宿主侧** graph 进程执行（仅 bash / 文件操作代理进沙箱），所以后续给 agent 挂 Action 工具无需打通沙箱网络——Phase 1 先不挂，agent 与本体的边界就是 import_matrix。

## 2. 数据模型（SQLite，同库新表）

沿用 `server/projects.py` 的 Store 模式：`_SCHEMA` + `_MIGRATION_COLUMNS`、每调用新建连接、模块级单例接线。**SQL 保持 Postgres 可迁移写法**（无 SQLite 独有特性；时间戳 REAL epoch 与现状一致）。

```sql
-- 机构（Phase 1 只有种子行 default）
CREATE TABLE IF NOT EXISTS orgs (
    id TEXT PRIMARY KEY,           -- 'default' 种子
    name TEXT NOT NULL,
    created_at REAL NOT NULL
);

-- 抽取运行（对齐引擎的比对单位；workspace run 目录的登记簿）
CREATE TABLE IF NOT EXISTS extract_runs (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    run_dir TEXT NOT NULL,         -- workspace 相对路径
    schema_version TEXT,
    status TEXT NOT NULL,          -- imported | superseded
    imported_at REAL NOT NULL
);

-- 需求项（business + technical 两张矩阵合流，matrix_type 区分）
CREATE TABLE IF NOT EXISTS req_items (
    uid TEXT PRIMARY KEY,          -- 稳定逻辑 id（导入时分配，跨 run 不变）
    org_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    run_id TEXT NOT NULL,          -- 当前版本来自哪次 run
    src_id TEXT NOT NULL,          -- 抽取产物内 id（REQ-T-014，run 内唯一）
    matrix_type TEXT NOT NULL,     -- business | technical
    category TEXT,
    title TEXT NOT NULL,
    requirement_text TEXT NOT NULL,
    mandatory INTEGER NOT NULL DEFAULT 0,
    risk_level TEXT,
    source_refs TEXT NOT NULL,     -- JSON [{document_id, line_span, section}]
    confidence REAL,
    review_status TEXT NOT NULL,   -- unconfirmed | confirmed | recheck（待复核）
    response_status TEXT NOT NULL, -- covered | pending | gap（覆盖三态）
    deviation TEXT,                -- JSON，mark_deviation 写入
    lifecycle TEXT NOT NULL DEFAULT 'active',  -- active | retired（对齐作废）
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

-- 评分项（scoring 矩阵）
CREATE TABLE IF NOT EXISTS scoring_items (
    uid TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    src_id TEXT NOT NULL,
    grp TEXT,                      -- 评分分组（group 是保留字倾向，避开）
    title TEXT NOT NULL,
    max_score REAL,
    scoring_rule TEXT,
    scoring_method TEXT,
    mandatory_gate INTEGER NOT NULL DEFAULT 0,
    source_refs TEXT NOT NULL,
    confidence REAL,
    review_status TEXT NOT NULL,
    lifecycle TEXT NOT NULL DEFAULT 'active',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

-- 链接（Phase 1 只有 kind='coverage'；respond / cite 是 Phase 2/3 接缝）
CREATE TABLE IF NOT EXISTS links (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    kind TEXT NOT NULL,            -- coverage | respond | cite
    from_type TEXT NOT NULL, from_uid TEXT NOT NULL,
    to_type TEXT NOT NULL,   to_uid TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_by_action TEXT NOT NULL,  -- 溯源到 actions_log.id
    created_at REAL NOT NULL
);

-- Action 审计流水（动力层的账本，只增不改）
CREATE TABLE IF NOT EXISTS actions_log (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    actor TEXT NOT NULL,           -- user | system | agent（Phase 1 无 agent）
    target_type TEXT, target_uid TEXT,
    params TEXT NOT NULL,          -- JSON（对齐报告等大对象也放这里）
    status TEXT NOT NULL,          -- applied | pending_confirm | rejected
    result TEXT,                   -- JSON
    created_at REAL NOT NULL,
    resolved_at REAL
);

-- 证据资产（ADR 0001/0004 留位：Phase 1 只建表，不出 API 不出 UI）
CREATE TABLE IF NOT EXISTS evidence_assets (
    uid TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,          -- 注意：无 project_id，天生 org 级
    kind TEXT NOT NULL,            -- case | qualification | resume
    title TEXT NOT NULL,
    meta TEXT,                     -- JSON
    outcome TEXT,                  -- won | lost | null
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
```

既有表迁移：`projects` 经 `_MIGRATION_COLUMNS` 加 `org_id TEXT`（回填 `'default'`）。basic_info 不建对象表——它是单例元数据，整体 JSON 存入 `projects.metadata_json`（现有列），沙盘头部从此处读。

## 3. 本体模块结构（hagent 内）

按「一个文件一个职责」：

```
src/hagent/server/ontology/
├── __init__.py
├── store.py        # OntologyStore：建表/迁移/查询（只读接口 + 内部写接口）
├── actions.py      # Action 网关：类型注册表、参数校验、执行、审计落账、HITL 策略
├── alignment.py    # 对齐引擎：跨 run 匹配 + 三路分流（纯函数为主，可单测）
├── importer.py     # import_matrix：读 run 目录 JSON → 首次播种 / 调 alignment
├── checks.py       # 确定性 Function：coverage_check / gap_check（纯 SQL/Python）
└── schemas.py      # Pydantic 请求/响应模型（含 Action 参数 schema）

src/hagent/server/routers/ontology.py   # HTTP 面，薄层，只做编排
```

**写路径纪律（ADR 0004 纪律 3 的代码化）**：`OntologyStore` 的写方法全部下划线私有，唯一调用方是 `actions.py`；`routers/ontology.py` 与未来任何模块只准 import `execute_action()` 与只读查询。用一条 lint 约定 + 测试断言守住（测试遍历 store 公开方法确认无写方法）。

## 4. Action 网关

### 4.1 Phase 1 Action 类型

| action_type | actor | 效果 | HITL |
|-------------|-------|------|------|
| `import_matrix` | system | 登记 run、对象 upsert、覆盖链接播种、触发对齐 | 否（产出裁决队列） |
| `confirm_item` | user | review_status → confirmed | 即人工动作 |
| `mark_deviation` | user | 写 deviation JSON，response_status → pending | 即人工动作 |
| `set_response_status` | user | 覆盖三态流转（校验：mandatory 项禁止直接 gap→covered，须先 confirm） | 即人工动作 |
| `create_link` | user | 建/断 coverage 链接 | 即人工动作 |
| `resolve_recheck` | user | 待复核裁决：确认迁移 / 改判 | 即人工动作 |
| `retire_item` | system | 对齐无匹配的旧对象 lifecycle → retired | 否 |

Phase 1 全部 Action 要么是系统导入、要么本身就是人工操作，所以 `pending_confirm` 状态机先实现但不会被触发——这是给 Phase 2 agent 直连 Action（draft_section 等需要审批）预埋的，成本是一个状态字段和一个 confirm 端点。

### 4.2 执行流

```
execute_action(type, params, actor, org_id, project_id)
  1. schemas.py 里查该 type 的 Pydantic 参数模型 → 校验（失败即拒，落账 rejected）
  2. 业务校验（如 mandatory 流转规则）
  3. 事务内执行效果（store 私有写方法）
  4. actions_log 落账（params + result）
  5. 重算 checks（见 §6），返回 {action_id, result, checks}
```

每个 Action 的响应都带最新 checks——前端状态带无需二次请求。

## 5. 对齐引擎（alignment.py）

触发：`import_matrix` 发现该 project 已有 `active` 对象时。比对单位：同 `matrix_type` 的新 run 条目集 vs 现存对象集。

匹配打分（纯函数，可离线单测）：

```
score(old, new) = 0.6 * line_overlap + 0.4 * text_sim
  line_overlap = source_refs 行区间 Jaccard（document_id 不同则为 0）
  text_sim     = difflib.SequenceMatcher(requirement_text).ratio()   # 无新依赖
```

三路分流（阈值起步值，进配置不进代码）：

| 条件 | 处置 |
|------|------|
| score ≥ 0.85 且 text_sim ≥ 0.95 | **自动迁移**：uid 不变，run_id/字段更新，确认与链接保留 |
| score ≥ 0.85 且 text_sim < 0.95 | **待复核**：uid 不变，review_status → recheck，进裁决队列 |
| score < 0.85（无匹配） | 新条目 **新增**（新 uid）；旧条目 **retire**（链接标 inactive） |
| （叠加规则）mandatory=1 或 risk_level=high 且 text_sim < 1.0 | **强制待复核**，无视上两行 | 

产出对齐报告（迁移 N / 待复核 M / 新增 K / 作废 J，逐条明细）写入该次 `import_matrix` 的 `actions_log.params`——这就是「变更影响清单」的数据源，Phase 1 先在裁决抽屉顶部展示汇总行，独立页面不做。

匹配用匈牙利算法是过度设计：条目量级数百，贪心按 score 降序配对 + 一对一约束足够，写进注释。

## 6. 确定性 Function（checks.py）

纯查询，不写库，随每次 Action 响应与 sandbox 聚合返回：

- `gap_check`：`mandatory=1 AND lifecycle='active'` 的需求项中 `response_status='gap'` 的清单 → 废标警示（数量 > 0 即红条）。
- `coverage_check`：`active` 评分项中无 `active` coverage 链接的清单 → 状态带「评分覆盖 M/M」。
- 附带统计：待裁决数 = `review_status='recheck'` + `response_status='pending'` 计数。

## 7. HTTP API（routers/ontology.py）

```
POST /ontology/projects/{pid}/import          # body: {session_id, run_dir}
GET  /ontology/projects/{pid}/sandbox         # 沙盘聚合（见下）
GET  /ontology/projects/{pid}/queue           # 裁决队列（recheck + pending + 低置信 unconfirmed）
POST /ontology/projects/{pid}/actions         # body: {type, params}；返回 {action_id, result, checks}
GET  /ontology/projects/{pid}/actions         # 审计流水（分页）
```

`sandbox` 聚合响应形状（一次请求渲染整个主视图）：

```jsonc
{
  "checks": { "mandatory": {"total": 43, "covered": 41}, "coverage": {"total": 62, "linked": 58}, "pending": 7 },
  "alerts": [ {"kind": "gate_fail", "items": ["REQ-…"]} ],
  "groups": [                       // 按 scoring_items.grp 分组的评分树
    { "grp": "技术部分", "max_score": 55,
      "items": [ { "uid": "…", "title": "2.1 网络架构方案", "max_score": 12,
        "reqs": [ { "uid": "…", "src_id": "REQ-T-014", "title": "…",
                     "response_status": "covered", "review_status": "confirmed",
                     "mandatory": true, "source_refs": [ … ] } ] } ] }
  ]
}
```

鉴权、错误形状、同源代理沿用现有 routers 惯例；前端经 `app/api/hagent/**` 代理，API key 不落浏览器（不变）。

## 8. 前端（frontend/）

- `lib/hagent/ontology.ts` —— API 封装 + 类型（对应 §7 响应形状）。
- `lib/store/workspace.ts` —— 新增 ontology slice：`sandbox` 数据、`queue`、`dispatchAction(type, params)`（乐观更新 + 失败回滚；**不碰现有 SSE rAF 合帧路径**）。
- `app/workspace/_components/` 新增：
  - `ScoreSandbox.tsx` —— 主视图：评分树 + 三态 + 展开需求项，行号点击回跳原文（利用现有文件查看能力）。
  - `SandboxStatusStrip.tsx` —— 状态带（三组数字，点「待裁决」开抽屉）。
  - `RulingDrawer.tsx` —— 裁决抽屉：队列 + 逐条 Action 按钮 + 对齐报告汇总行。
- 触发链：现有「run 目录发现」逻辑完成矩阵下载后追加调用 `import` → 成功后拉 `sandbox` → 画布主视图切换为沙盘（矩阵卡片保留为次级 tab）。
- 视觉：沿用现有界面样式出高保真，信息结构与主次以决策画布线框为准（ADR 0005）；三态用语义色 graphic/text 对，蓝色只给交互。

## 9. 测试与验收

按 hagent 严格 TDD，`tests/server/ontology/` 与模块一一对应：

- `test_store.py` —— 建表/迁移/org 种子/无公开写方法断言。
- `test_actions.py` —— 每个 action_type 的校验、效果、审计落账；mandatory 流转禁令。
- `test_alignment.py` —— 三路分流矩阵：同文重跑（高相似）/ 澄清变更（文本漂移）/ 全新条目 / mandatory 强制复核；贪心配对一对一。
- `test_importer.py` —— 真实矩阵 JSON 样本（取自 `.hagent/skills/bid-response-matrix` 测试夹具）首导 + 二次导入。
- `test_checks.py` / `test_router_ontology.py`。

**验收 = demo 剧本跑通**（对应 ADR 0005 的第一分钟）：上传招标文件 → 解析 → import → 沙盘呈现评分树与三态 → 状态带显示缺口 → confirm/link 操作后数字变化 → 模拟澄清文件重解析 → 裁决抽屉出现待复核 + 变更汇总行 → resolve 后废标警示消除。

## 10. 任务切分（无时间估计，依赖显式）

| Task | 内容 | 依赖 |
|------|------|------|
| T1 | ontology/store.py + orgs 种子 + projects.org_id 迁移 | — |
| T2 | actions.py 网关骨架 + actions_log + schemas.py | T1 |
| T3 | importer.py 首次导入 + 覆盖链接播种 | T2 |
| T4 | alignment.py 对齐引擎 + resolve_recheck | T3 |
| T5 | checks.py + routers/ontology.py 全部端点 | T2（sandbox 聚合需 T3） |
| T6 | 前端 ontology.ts + store slice + import 触发链 | T5 |
| T7 | ScoreSandbox / StatusStrip / RulingDrawer（frost 高保真） | T6 |
| T8 | e2e demo 剧本（真实语料样本走全链） | T4 + T7 |

动工前置：本方案评审通过后，T1–T5 先落 spec 到 `hagent/docs/specs/`（契约层），工单经 /to-tickets 进仓根 `tickets.md`；T6–T8 直接按本文执行。
