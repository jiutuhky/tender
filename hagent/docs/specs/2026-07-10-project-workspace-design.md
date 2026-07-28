# Design Spec: Project Workspace 与 Run 执行模型（项目工作区持久层 + 沙箱租约上移）

**Date**: 2026-07-10
**Repo**: `/home/han/workplace/tender`（`hagent/` 为主，含前端契约变更）
**Status**: DRAFT（方向经 2026-07-10 grilling 确认，见 ADR 0007；细节实现期回写）
**承接关系**: 修订 `2026-07-06-smolvm-sandbox-design.md` 的 **D6**（会话绑数据 → 项目绑数据）与 **D13**（快照持久化 → 快照缓存），其余 smolvm spec 决策（准入账本/孤儿治理/健康巡检/审计）**原样沿用**；与 ADR 0004（共享结构入库）合流。
**决策依据**: `docs/adr/0007-项目工作区与沙箱租约.md`；调研见 `docs/research/2026-07-09-agent-project-session-sandbox-workspace-lifecycle.md` + 2026-07-10 交叉验证（Manus sandbox 官方博客 / Claude Code & Cowork 官方文档 / Codex worktrees & cloud / Devin snapshot / Replit task system / Lovart / E2B·Modal·Fly 基础设施层）。

## 1. Problem Statement

现状三个错位（file:line 为 2026-07-10 调研时点）：

1. **workspace 绑 session**：sandbox 与文件全挂 session_id（`pool.py:251` acquire 以 session_id 为键），session 间互为孤岛；「一份标书跨会话持续演进」无落点。
2. **无稳定持久层**：文件只活在 VM 磁盘（CoW isolated）与一次性 DISK 快照里；快照是 idle 驱逐路径的临时产物，session 删除即清（`manager.py:119-123`）。VM 意外死亡只有 health 抢救 best-effort（上限 200 文件，`health.py:94-130`）。
3. **前端一次性链路**：每次拖文件 = 新建 project + 新建 session 一一对应（`lib/store/workspace.ts:233` startParse）；resumeProject 只读 latest session 的矩阵 JSON。

目标产品语义：**Project = 一次投标工作**，工作区跨会话共享持续演进；画布支持**多节点 Agent 并行生成**（章节级 fan-out，用户随时独立启动/查看单个节点）。

## 2. 关键决策（W1–W8，均已经 grilling 确认）

| # | 决策 | 选择 | 理由 / 否决备选 |
| --- | --- | --- | --- |
| W1 | 所有权模型 | Project 绑逻辑工作区（canonical workspace，唯一事实来源）；VM 是可替换租约，不拥有不可再生数据 | 业界共识三层结构；否决「project 常驻 VM」（容量/故障域/漂移，零先例）与「维持 session 绑定」（产品语义缺失） |
| W2 | 持久层形态 | 宿主目录 `{workspace_root}/projects/<pid>/workspace/` + **host 侧 git 仓**；checkpoint 即 commit；git 完全在宿主跑，VM 无需感知 | revision/diff/三方合并白拿，Phase 2 的 base_revision/changeset 直接铺路；否决纯 manifest（后期重造 git）、DISK 快照链（不可检视、把业务数据锁进镜像格式）、对象存储（单机阶段过度设计） |
| W3 | checkpoint 时机 | 每个 Run 的 SSE 流结束即增量 checkpoint（正常/异常/打断三路归一进 finally）+ 生命周期时点（pause/快照/evict/release 前）强制兜底 | 丢数据窗口 = 正在执行的一轮；无变更轮次是 no-op；commit 粒度天然对齐交互历史。否决仅生命周期回写（活跃期意外丢整段）、定时器（commit 到半成品）、显式保存（MVP 交互成本高） |
| W4 | 回写范围 | 全量回写 + 排除名单（`tmp/`、`.cache/`、`__pycache__/` 等 .gitignore 语义）；base prompt 约定临时产物写 `tmp/` | 宁可多存不可错丢（agent 写错位置最多脏不会丢）；否决白名单目录（写到名单外即丢）与显式登记（漏登记即丢，Manus 教训的反面） |
| W5 | 租约粒度 | VM 租约绑**活跃 Project**：项目内首个 Run 触发租用，所有并行 Run 与会话共享一台；idle 降档/回收沿用 | 画布 fan-out 场景下容量友好（1 活跃项目 1 VM，生成任务 LLM-bound，2 vCPU 可承载多 agent 文件操作）；否决每节点独立 VM + 合并（池上限 4 台，单项目 fan-out 即超容，合并 UI 提前）与单轮编排子代理（交互被绑成批处理，与「随时独立启停节点」冲突） |
| W6 | 执行单元 | `runs` 表一等实体；对话轮 = `Run(kind=chat_turn)`，节点生成 = `Run(kind=node_generation)`；锁/checkpoint/SSE/审计统一挂 Run；session 回归纯对话容器 | 一套机制不分叉；否决隐藏 session（语义污染，债迟早要还）与会话内消息轮（与并行正面冲突） |
| W7 | 快照角色 | DISK 快照降级为 **project 键的 best-effort 唤醒缓存**：idle 驱逐先兜底 checkpoint 再落快照；恢复失败/容量不足**静默冷启动 + 注入**，拆掉「503 保快照」等数据事故语义 | 持久化职责已移交 workspace；快照剩余价值 = 唤醒速度 + agent 自装环境增量。对齐 Codex 12h 容器缓存 / CC web 环境快照的 best-effort 定位；否决砍掉（代码已存在且加固过，环境增量有真实价值） |
| W8 | 并发写策略 | 三层：① 节点 Run 启动登记名下路径，自研文件工具对被锁路径拒绝并返回可读错误；② 对话轮之间互斥（第二个对话轮 409）；对话轮与节点 Run 自由并发；③ host 侧 git commit 操作短互斥。Run 启动时 VM 落后 HEAD 先注入差异追平 | 同 VM 同文件系统，写冲突发生在写入时刻，靠 commit 阶段防不住 → 利用「自研全部文件工具」的抓手在工具层拦截（Lovart「结构上不可能互踩」思路的文件层落地）。否决对话轮一律独占（问答被挡，两个核心交互打架）与完全放任（内容交错无提示） |

**业界锚点**（速查）：Manus 每任务一 VM、回收只恢复 artifacts、Projects=指令+知识注入新沙箱；Claude Code cloud 每 session 新 VM + 环境快照缓存 + git 持久层 + transcript 独立存储；Codex 每任务容器 + per-repo 环境 + 12h 缓存 +「Local=前台单占」；Devin org 级机器快照模板 + session 一次性克隆不回写；Replit 主版本唯一写入路径 = apply（独占阶段）；Lovart 共享画布 append-only 消解冲突。共同不变量：**没有两个不受控写者同时命中主状态**。

## 3. 数据模型

### 3.1 新表 `runs`

```sql
CREATE TABLE runs (
    id            TEXT PRIMARY KEY,          -- uuid4().hex[:16]
    project_id    TEXT NOT NULL,
    kind          TEXT NOT NULL,             -- 'chat_turn' | 'node_generation'
    session_id    TEXT,                      -- 发起源会话（chat_turn 必填；node_generation 可空）
    node_id       TEXT,                      -- 画布节点 ID（node_generation 必填）
    status        TEXT NOT NULL,             -- 见 §5 状态机
    base_revision TEXT,                      -- 开跑时 project HEAD SHA
    commit_sha    TEXT,                      -- checkpoint 产出（可空：无变更轮次）
    owned_paths   TEXT,                      -- JSON 数组，node run 的路径登记（chat_turn 为 null）
    error         TEXT,
    created_at    TEXT NOT NULL,
    finished_at   TEXT,
    metadata_json TEXT
);
CREATE INDEX idx_runs_project ON runs(project_id, created_at);
CREATE INDEX idx_runs_active  ON runs(project_id, status);
```

### 3.2 新表 `sandbox_leases`（sandbox 状态从 sessions 迁出）

```sql
CREATE TABLE sandbox_leases (
    project_id            TEXT PRIMARY KEY,
    sandbox_id            TEXT,              -- vm_id
    sandbox_kind          TEXT,
    sandbox_state         TEXT,              -- 沿用 smolvm spec §4.3 状态机
    sandbox_desired_state TEXT,
    snapshot_id           TEXT,              -- W7：project 键快照
    materialized_revision TEXT,              -- 当前 VM 内 workspace 对应的 HEAD SHA（追平判定用）
    node                  TEXT,
    last_activity_at      TEXT,
    metadata_json         TEXT
);
```

- vm_id 命名约定改为 `hagent-<pid8>-<rand6>`（对账键从 sid 换 pid；reconciler/reaper 逻辑不变，仅换键源）。
- `sessions` 表：`sandbox_*`、`container_id`、`image_tag`、`snapshot_id` 等列废弃（dev 阶段直接删，不做兼容迁移）；`project_id` 改 **NOT NULL**；`workspace_dir` 废弃。
- `projects` 表不变（ADR 0004 的本体表按其自身计划推进）。

### 3.3 Workspace 布局与 git 约定

```text
{workspace_root}/projects/<pid>/workspace/     ← git 仓（host 侧）
├── sources/          招标文件原件 / MinerU markdown / 补遗澄清
├── structured/       响应矩阵、本体对象 JSON（过渡期；按 ADR 0004 逐步入库后此处存导出投影）
├── deliverables/     标书章节、附件、导出物
├── tmp/              约定 scratch 区（.gitignore 排除）
└── .gitignore        tmp/ .cache/ __pycache__/ *.pyc node_modules/ .venv/
```

- commit 元信息用 trailer 结构化：`Run-ID:`、`Session-ID:`、`Kind:`、`Interrupted: true`（异常/打断轮）；message 首行为人类可读摘要（如 `chat_turn: 生成关键技术章节初稿`，取 run 摘要或首条用户消息截断）。
- git 身份固定为 `hagent <hagent@local>`；仓库禁 gc 自动化之外的手工操作假设——它是数据结构不是协作仓，**不 push、无 remote**。

## 4. 运行时架构

### 4.1 租约与物化（materialize）

```text
Run 提交
 └─ LeaseManager.ensure(project_id)
     ├─ lease 活跃(running/paused) → resume（若 paused）→ 复用
     ├─ lease snapshotted → restore（W7：失败静默降级冷启动）
     └─ 无 lease → pool.acquire(project_id) 冷启动
 └─ 追平检查：lease.materialized_revision != HEAD ?
     ├─ 冷启动/恢复失败 → 全量注入 workspace（upload），guest 内 `git init && add -A && commit`（临时探测仓）
     └─ 落后 → `git diff --name-status <rev> HEAD` → upload 变更 / 删除移除项 → 更新 materialized_revision
```

- 全量注入排除 `.git/` 与 `.gitignore` 命中项；guest 内 `/workspace` 的临时 git 仅作**变更探测**（非持久层），与 host canonical 仓无对象共享。
- idle 判定：`last_activity_at` 上移到 lease，任何 Run 的消息/工具交互都续期（`store.touch_activity` 改写 lease）；两级降档（pause 300s / evict 1800s）阈值沿用。

### 4.2 Checkpoint 管道（每 Run）

```text
finally:  # SSE 流退出三路归一（正常耗尽 / 异常 / 打断·断连 GeneratorExit）
  1. guest: `git status --porcelain /workspace` → 变更清单（含删除）
  2. 无变更 → run.status=committed(commit_sha=null)，直接收尾
  3. 有变更 → 按 run 归属过滤：
       chat_turn        → 全部变更 − 其它活跃 node run 的 owned_paths
       node_generation  → 仅 owned_paths ∩ 变更
  4. download 变更文件 → 写入 host workspace（删除项同步删）
  5. 持 commit 互斥锁：`git add -A <paths> && git commit`（trailer 见 §3.3）
  6. guest: 临时仓 `git add -A && git commit`（推进探测基线）
  7. lease.materialized_revision = 新 HEAD；run.commit_sha 落库
  8. SSE `workspace.checkpointed {run_id, commit_sha, files_changed}`（在 done 之前）
```

- 生命周期兜底：pause/snapshot/evict/release/健康杀重建 前，对该 project **所有非终态 Run** 依次走同一管道（此时 run 标记 interrupted）。health 抢救逻辑（`on_unhealthy`）保留为最后防线，但目标目录改 host workspace + commit。
- 步骤 3 的归属过滤保证：run A 完成时不会把 run B 写到一半的文件拖进 commit。

### 4.3 锁体系（W8）

| 锁 | 粒度 | 实现 | 冲突行为 |
| --- | --- | --- | --- |
| 对话轮互斥 | project 级，仅 chat_turn 之间 | server 内存 asyncio 锁 + runs 表 active 兜底（重启恢复） | 第二个对话轮 409 `{code: chat_turn_active}`，前端提示「项目内另一对话执行中」 |
| 节点锁 | node 级 | runs 表：同 node_id 存在非终态 run 即拒 | 409 `{code: node_generating}`，节点 UI 本就显示生成中 |
| 路径锁 | 文件级 | node run 启动登记 owned_paths → 注入该 project 所有活跃 agent 的文件工具检查点（自研 Write/Edit/Bash 的写路径校验） | 工具返回错误「该章节正在生成中（run <id>），请稍后再改」，agent 转述用户 |
| commit 互斥 | project 级，毫秒级 | host 侧 asyncio 锁包住 git add/commit | 排队，无用户可见影响 |

- `owned_paths` 由节点→文件映射规则生成（如 `deliverables/chapters/<node_slug>.md` + 该节点的导出附件路径）；矩阵/大纲等共享结构走 ADR 0004 的 DB 行级更新，不在文件锁范围。
- Bash 工具的写路径无法静态判定：MVP 约束为 base prompt 声明 + 不做 Bash 级拦截（已知缺口，记 §8 风险）。

### 4.4 API 契约变更

| 端点 | 变更 |
| --- | --- |
| `POST /sessions` | `project_id` 必填；**不再触发 pool.acquire**（租约由首个 Run 惰性触发）；不再创建 session workspace 目录 |
| `POST /sessions/{sid}/messages` | 内部升格为 `Run(kind=chat_turn)`：建 run → 抢对话轮锁 → ensure lease + 追平 → 执行 → checkpoint。对外 SSE 事件增加 `run.started {run_id}` 与 `workspace.checkpointed` |
| `POST /projects/{pid}/runs`（新） | 启动节点生成：`{kind: node_generation, node_id, prompt/skill, owned_paths?}`；返回 run_id；SSE 在 `GET /projects/{pid}/runs/{run_id}/events` |
| `GET /projects/{pid}/runs`（新） | 活跃/历史 run 列表（画布节点状态源） |
| `POST /sessions/{sid}/files` | 废弃 → `POST /projects/{pid}/files`：写 host workspace `sources/` + commit（kind=upload 的系统 Run 或直接 commit）+ 若 lease 活跃同步注入 VM |
| `GET /projects/{pid}/workspace/...`（新） | 读 canonical workspace（文件列表/内容/git log），前端画布与 resumeProject 数据源 |
| `/ops/state` | lease 行从 session 视角改 project 视角；补 runs 活跃统计 |

### 4.5 前端契约变更（frontend/）

- `startParse`：createProject → createSession(project_id) → **uploadFile 到 project** → 跑 skill（chat_turn run）。拖文件 = 新建 project 流程保留。
- project 页新增「新建会话」入口：createSession(project_id) 即得，共享同一工作区；会话列表 = `GET /sessions?project_id=`。
- `resumeProject`：改读 `GET /projects/{pid}/workspace/`（矩阵过渡期读 `structured/` 投影，入库后读本体 API）；不再依赖 latest session。
- store 消费 `workspace.checkpointed` 刷新画布产物；`chat_turn_active`/`node_generating` 409 的 toast 文案。

## 5. Run 状态机

```text
pending → running → checkpointing → committed
                 └→ checkpointing → interrupted   （异常/打断/断连，best-effort commit）
pending → rejected（409：锁冲突 / 容量 503）
```

- 终态：committed / interrupted / rejected。interrupted 带 commit_sha 时表示部分成果已保全。
- server 重启对账：startup 时非终态 run 一律标 interrupted（其 VM 内未 checkpoint 的增量由 lease 兜底路径尽力抢救）。

## 6. 分期

| 期 | 范围 | 出口判据 |
| --- | --- | --- |
| **M1 工作区上移** | workspace 目录 + git 模块；lease 表 + pool/manager/reconciler 键从 session 换 project；轮末 checkpoint 管道（对话轮先作为匿名 run 内联实现亦可，但 **runs 表第一天建好**）；追平注入；快照改键降级；files API 迁移；前端 startParse/resumeProject/新建会话 | 同 project 两个先后会话看到并共同演进同一工作区；kill -9 VM 后重发消息项目无损；`git log` 呈现交互史 |
| **M2 Run 实体化** | runs API + SSE 按 run；对话轮锁 + commit 互斥落 runs 表；ops console 补 run 视图 | 两个 tab 并发发消息，一个 409 一个正常，无 lost update |
| **M3 节点并行** | node_generation run + 节点锁 + 路径锁（文件工具检查点）+ 选择性 checkpoint + 画布节点 UI | 3 节点并行生成 + 对话问答同时进行，互不阻塞、commit 互不污染 |

依赖：M3 的共享结构（矩阵/大纲）行级更新依赖 ADR 0004 本体入库进度；未就绪前节点 run 对 `structured/` 按路径锁全文件处理（降级可用）。

## 7. 测试要点

- workspace/git 模块单测（初始化、增量 commit、trailer、排除名单、并发 commit 互斥）。
- checkpoint 管道：正常/异常/打断三路 + 无变更 no-op + 归属过滤（伪造两个 run 的变更集）。
- 追平注入：HEAD 前进后新 run 的 diff 注入与删除同步。
- 租约迁移：`pool.acquire(project_id)` 后孤儿对账/reaper/健康杀重建全链路回归（`HAGENT_TEST_SMOLVM=1 pytest -m smolvm`）。
- 快照降级：恢复失败注入路径的静默降级（故意删快照文件断言冷启动）。
- 锁：对话轮 409、路径锁工具报错文案、commit 串行。

## 8. 风险与开放问题

1. **Bash 写路径不可静态判定**：路径锁只覆盖自研文件工具；agent 用 Bash 重定向绕过锁的场景靠 base prompt 约束。若成为实际问题，候选：Bash 工具 cwd 级 chroot 到 run 专属子目录（重）或 checkpoint 时冲突检测报警（轻）。
2. **git 仓膨胀**：sources 原件（大 PDF）通常一次写入，风险低；若补遗版本频繁，后续引入按大小阈值改存对象区 + workspace 内软链的策略，不引 LFS。
3. **guest 临时 git 探测对大量小文件的开销**：MinerU 输出上千小文件时 status/diff 变慢；必要时探测基线换成 hash 清单。
4. **同 VM 并行 run 的资源争抢**：2 vCPU 下多 agent 并行执行重型 Bash（如文档转换）会互相拖慢；观察后可调 per-VM 配额或引入 run 级 nice。
5. **SQLite 写并发**：runs 表高频状态写入与现有 sessions 写共库；沿用现状（单机小并发），恶化时开 WAL。
6. **多宿主**：lease.node 字段与 NodeClient 接缝保留，本 spec 不推进多机。
