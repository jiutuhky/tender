# 主流 Agent 产品的 Project、Session、Sandbox 与 Workspace 生命周期研究

> **状态（2026-07-10）**：本调研的架构结论已经 grilling 会话确认并落 [ADR 0007](../adr/0007-项目工作区与沙箱租约.md)，实施契约见 hagent spec `2026-07-10-project-workspace-design.md`。相对本文的修订：VM 租约上移到「活跃 Project」一台共享（而非每 Run 独立）、并行以节点路径分区 + 工具层路径锁实现（隔离副本 + merge 推迟）；2026-07-10 补充调研（Manus Projects 更新语义、CC/Cowork/Codex/Replit/Lovart 重叠执行策略）与本文结论互相印证。

- 日期：2026-07-09
- 研究范围：Manus、Claude.ai / Claude Cowork / Claude Code、ChatGPT Projects / Codex、Devin、Replit Agent
- 资料范围：仅采用产品官方帮助中心、官方文档、官方博客；不使用媒体报道或第三方逆向分析
- 目的：为 Prose 标书 Project 的持久工作区与 smolvm 生命周期设计提供架构依据

## 结论先行

主流产品并没有收敛到“一个 Project 永久绑定同一台物理 VM”。更稳定的共同模式是把三种生命周期拆开：

1. **Project 是长期业务边界和持久状态边界**：持有共享文件/来源、指令、知识或记忆、正式产物以及历史版本。
2. **Session / Chat / Task 是交互与工作边界**：持有自己的对话、任务目标、执行记录和临时上下文。
3. **Sandbox / VM 是按需计算资源**：通常由 task 或 session 租用，可休眠、回收、重建；物理实例不是业务身份。

真正值得 Prose 采用的不是简单的“Project 共用一个可写目录”，而是更完整的混合模型：

> **Project-owned canonical workspace（项目主工作区） + Run-owned isolated working copy（运行隔离副本） + on-demand sandbox lease（按需沙箱租约） + explicit publish/merge（显式发布/合并）。**

这比“所有会话同时直接写同一块磁盘”更可靠：顺序工作时仍能获得 Claude Code 那样的项目连续性；并发编制不同章节、重跑解析、尝试不同方案时，又能像 Replit/Codex worktree 一样避免相互覆盖。

因此，对原问题的进一步修正是：

> 创建 Project 时应立即创建唯一的**逻辑工作环境和持久存储身份**，但不应立即或永久占用一台 smolvm。每次 Run 按需取得 VM，并从 Project 当前 revision 创建工作副本；Run 的结果通过 checkpoint/merge 更新 Project 主状态。可以复用同一台热 VM，但这只是优化，不是产品语义。

## 研究口径与术语

为了避免各产品同名异义，本文统一使用以下术语：

- **Project**：长期工作主题或业务对象；对 Prose 即一次具体投标工作。
- **Session / Chat / Thread**：连续对话及其模型上下文。
- **Task / Run**：一次有明确目标的执行；一个 Session 可包含多个 Run，也可以一开始就以 Task 为顶层。
- **Workspace**：Agent 可读写的文件/数据视图。它可能是持久主工作区，也可能只是任务副本。
- **Sandbox / VM / Runtime**：实际执行命令、浏览器或代码的计算环境。
- **Artifact**：应被长期保存、浏览、审阅和交付的产物，不等同于 sandbox 中所有文件。

下文每个产品都区分：

- **官方明示事实**：官方资料直接说明的产品行为。
- **分析判断**：基于这些公开行为得出的架构含义；不声称知道厂商未公开的内部实现。

## 横向对照

| 产品 | Workspace 是否跨聊天/任务共享 | Sandbox 归属 | 跨会话共享状态 | 并发与恢复 | 公开模型的核心特征 |
|---|---|---|---|---|---|
| Manus Projects | 共享指令和知识文件；任务的完整可写文件系统不共享 | 默认 task/session-owned | Project 配置、知识库；重要产物可恢复 | 每任务隔离 sandbox，可休眠/回收，部分重要文件恢复 | “Project 配置层”与“Task 运行层”明确分离 |
| Claude.ai Projects | 共享项目知识、文件、指令、项目记忆；无公开的项目持久文件系统 | 代码执行容器不是 Project 身份，时长受限 | 知识、文件、跨聊天记忆/检索 | 容器有限时，未公开项目级并发写模型 | Project 主要是语义上下文边界 |
| Claude Cowork | 是；项目文件夹、指令、记忆跨 session | session 中的隔离 VM 执行，持久文件在项目文件夹 | 文件夹、项目记忆、指令、链接 | 官方未说明多 session 同写冲突策略 | 最接近“持久目录与计算环境解耦” |
| Claude Code | 同一目录下不同 session 看到当前工作树；对话各自独立 | 本地进程或 cloud-session-owned VM | 仓库文件、CLAUDE.md、项目级 memory | 并发用 worktree；云环境过期后重建并恢复对话 | 目录/仓库是项目身份，session 不是文件所有者 |
| ChatGPT Projects | 共享文件、来源、指令和项目内聊天记忆 | 普通 Projects 未公开持久 sandbox | 项目文件/来源、指令、项目聊天 | 项目本身偏上下文组织，不是共享 VM | Project 是长期上下文空间 |
| Codex | 本地 Project 的任务可读同一目录；并行任务用 worktree | cloud task 创建容器；本地 task 可绑定 worktree | 仓库、AGENTS.md、任务 transcript；变更靠 branch/diff | worktree 隔离；删除前保存 snapshot，可恢复 | “主项目 + 每任务工作副本 + merge” |
| Devin | 不跨 session 共享 session 变更；从同一环境 snapshot 起步 | session-owned isolated VM | 环境模板、repo knowledge、Git/PR 中正式变更 | session 可 sleep/wake；并行 session 各自 VM | 环境模板共享，运行状态隔离，结果外部化 |
| Replit Agent | 是；Project 持有代码、数据、artifacts；主状态长期存在 | 普通主线程使用项目环境；并行 task 使用隔离副本 | 完整 Project 状态、checkpoint、Agent context/memory、可选数据库 | 最多多任务并行，完成后 review/apply，自动处理冲突 | 公开资料中最完整的“持久主状态 + 隔离分支”模型 |

## 1. Manus：Project 共享“配置”，Sandbox 仍属于 Task

### 官方明示事实

Manus 把 Projects 描述为“persistent workspaces”，但其具体内容是 **master instruction + knowledge base**；每个新 task 自动继承 Project 配置。[Manus Projects 文档](https://manus.im/docs/features/projects)

配置更新具有明确的快照语义：

- 指令更新会在当前 task 下一次发消息时生效；
- 文件更新只影响更新之后创建的新 task；
- 已存在 task 继续使用创建时的配置。[Manus Projects 文档](https://manus.im/docs/features/projects)

Manus 官方对 Sandbox 的定义则是每个 task/session 分配的隔离云电脑。官方生命周期说明为：新 session 按需创建，空闲可 sleep，唤醒后文件不变；长时间休眠后可被 recycle，再打开时新建 sandbox，并恢复 artifacts、上传附件及 Slides/WebDev 等重要文件，但不保证恢复中间代码和临时文件。[Manus Sandbox 官方博客](https://manus.im/blog/manus-sandbox)

另一篇官方帮助把默认 sandbox 概括为 temporary：task 完成后底层环境最终关闭，输出保存在聊天历史；只有 Cloud Computer 才是跨 session 保留文件、工具和进程的 24/7 持久 VM。[Manus Cloud Computer 帮助](https://help.manus.im/en/articles/15392111-what-is-the-cloud-computer)

### 分析判断

Manus 的“Project workspace”不是“所有 task 共用同一块持续变化的磁盘”。它至少公开体现了三层：

```text
Project：共享指令 + 知识文件
Task：对话 + 任务产物
Sandbox：Task 的隔离执行环境，可回收并部分恢复
```

这说明“persistent workspace”在产品文案中可能只代表可复用上下文，并不自动等于持久可写文件系统。对 Prose 而言，仅照搬 Manus Projects 会不足以支撑“一份标书在多次会话中持续演进”，因为标书正文、响应矩阵和证据链需要一个跨 task 的正式主状态，而不是只把原始文件作为知识库注入。

Manus 最值得借鉴的是：**sandbox 的回收不应影响重要产物，但中间 scratch 可以被丢弃**；同时应明确哪些文件属于可恢复资产，不能把整个 VM 磁盘都当成产品数据。

## 2. Claude：三个产品面体现三种不同边界

### 2.1 Claude.ai Projects：语义上下文空间，不是项目磁盘

#### 官方明示事实

Claude.ai Projects 持有项目知识库和项目指令，项目成员可在其中创建多个 chat。[Claude Projects 帮助](https://support.claude.com/en/articles/9517075-what-are-projects)

当前 Claude 还支持在单个 Project 边界内搜索历史对话，并为每个 Project 维护独立的项目记忆/摘要；项目之间的记忆隔离。[Claude 聊天搜索与记忆帮助](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)

Claude 的代码执行与文件创建使用 sandboxed computing environment。项目文件可以被该计算环境访问，但官方同时说明单个 sandbox container 的使用时长受限，且不会在不同用户间共享 sandbox。[Claude 文件创建帮助](https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude)

#### 分析判断

Claude.ai Project 跨 chat 共享的是**知识、指令和记忆**，官方没有把它定义为持续可写的项目文件系统，也没有承诺所有 chat 复用同一容器。因此它适合“多个对话围绕同一资料集”，但不能单独作为 Prose 的产物一致性模型。

需要特别区分：

- 项目记忆用于帮助模型回忆；
- 正式标书状态用于审计、版本对比和交付；
- 两者不能由同一个不可解释的“memory”承担。

### 2.2 Claude Cowork Projects：持久文件夹归 Project，VM 只是执行器

#### 官方明示事实

Claude Cowork Project 收纳本地文件夹、长期指令、参考链接以及独立的项目记忆。新 session 在 Project 中启动时会挂载相同文件夹、应用相同指令；Claude 创建的文件落到项目文件夹，session 中学到的信息进入项目记忆供以后使用。[Claude Cowork Projects 文档](https://claude.com/docs/cowork/guide/projects)

Cowork 执行代码和 shell 命令时使用用户电脑上的隔离 VM，但它可以对用户授权的文件夹做真实读写。[Claude Cowork 入门](https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork)

#### 分析判断

这是对 Prose 最直接的参考之一：

```text
Project-owned folders/memory/instructions
             ↑ mounted into
Session-owned isolated execution VM
```

持久身份在 Project 文件夹，不在 VM。VM 换掉并不破坏 Project 连续性。官方没有公开多个 Cowork session 同时写同一文件夹时的冲突策略，因此不能据此断言“多会话直接共享写盘”已经安全解决。

### 2.3 Claude Code：目录是 Project，Session 是对话；并发时主动分叉

#### 官方明示事实

Claude Code 明确定义 session 是“绑定项目目录的已保存对话”；session transcript 单独保存，可 resume、branch 和切换。[Claude Code sessions 文档](https://code.claude.com/docs/en/sessions)

项目的长期共享状态主要来自工作目录/仓库、`CLAUDE.md` 以及项目级 auto memory。项目 memory 按 Git repository 派生，同一 repo 下不同 worktree 和子目录共享该 memory，但 memory 文件不会跨机器或云环境自动共享。[Claude Code memory 文档](https://code.claude.com/docs/en/memory)

并行 session 官方建议使用独立 Git worktree，使文件修改不相互碰撞。[Claude Code worktrees 文档](https://code.claude.com/docs/en/worktrees)

Claude Code cloud 中，每个 `--cloud` 命令创建独立 cloud session 并可并行运行；环境空闲过期后会被回收，再打开时重新 provision，并恢复 conversation history，而不是承诺原 VM 永久存在。[Claude Code on the web 文档](https://code.claude.com/docs/en/claude-code-on-the-web)

#### 分析判断

Claude Code 的核心不是“一 repo 一 VM”，而是“一 repo 是长期事实来源；多个 session 可读写它；产生并发时，为每个工作流创建隔离 worktree”。这正好揭示了“全 Project 共享同一 sandbox”方案缺失的一环：

- 单人顺序工作时，直接看最新 Project 状态最自然；
- 多任务并行时，直接共写会产生覆盖和半成品可见性；
- 所以要分叉工作副本，再 merge 回主状态。

## 3. ChatGPT Projects 与 Codex：共享 Project 上下文，但把执行副本交给 Task

### 3.1 ChatGPT Projects

#### 官方明示事实

ChatGPT Project 将 chats、files、instructions 和 sources 组织在一起；Project 内 chat 可访问相同上传文件、项目指令和连接来源。官方建议长期、会产生多个 output、依赖同一批文件的工作使用 Project，并让每个不同 outcome 使用独立 chat/task。[ChatGPT Projects、chats 与 tasks 文档](https://learn.chatgpt.com/docs/projects)

ChatGPT Project 的 project-only memory 可允许 chat 引用同 Project 的其他对话，并阻止引用 Project 外的对话。[ChatGPT Projects 帮助](https://help.openai.com/en/articles/10169521-projects-in-chatgpt)

#### 分析判断

这再次支持“Project 管共同背景，Chat 管单个 outcome”。但 ChatGPT Project 本身仍偏向知识与上下文容器；它没有公开承诺一个 Project 对应一台持久计算机。

### 3.2 Codex local / desktop / cloud

#### 官方明示事实

OpenAI 当前文档说明：Codex CLI 把启动目录视为 Project；task 保存自己的 transcript 和 working directory，而每次读取的是当前 working tree。IDE 中同 Project 的 tasks 可以访问相同文件，但各自持有独立 transcript。[ChatGPT/Codex Projects 文档](https://learn.chatgpt.com/docs/projects)

Codex desktop 用 Git worktree 让同一 Project 中多个独立 task 并行且互不干扰。通常一个 Codex-managed worktree 专属于一个 task；task 在 Local 与 Worktree 之间 handoff 后再次返回时，仍回到其关联 worktree。系统会限制保留的工作树数量，删除前先保存 snapshot，再打开旧 task 时可恢复。[Codex worktrees 文档](https://learn.chatgpt.com/docs/environments/git-worktrees)

Codex cloud task 启动时创建 container、检出指定 branch/commit、运行 setup，然后执行任务；结束时给出 diff 并允许继续追问或开 PR。容器 setup state 最多缓存 12 小时以加速新 task 与 follow-up，但缓存是运行优化，不是 Project 的长期身份。[Codex cloud environments 文档](https://learn.chatgpt.com/docs/environments/cloud-environment)

#### 分析判断

Codex 提供了非常清晰的双模式：

- **共享当前树**：适合前台、顺序协作；
- **task 专属 worktree**：适合后台和并行执行；
- **branch/diff/PR 或 handoff**：把结果显式带回主工作区；
- **snapshot restore**：允许销毁物理工作目录但保留逻辑 task。

对 Prose，worktree 不必真的使用 Git，但其语义应保留：每个 Run 记录 `base_revision`，在 Copy-on-Write 工作副本中修改，最后以可审阅 changeset 发布到 Project HEAD。

## 4. Devin：共享环境模板，不共享 Session 的脏状态

### 官方明示事实

Devin 把 environment 定义为 Linux VM 配置，包括仓库、工具、依赖和设置，并把它保存为可启动 snapshot。每个 session 从 snapshot 启动一个 fresh copy；所有 session 从同一已知良好状态开始，但 session 的修改不会回写 snapshot。[Devin environment 文档](https://docs.devin.ai/onboard-devin/environment)

Devin session 空闲后会 sleep，发新消息即可 wake；官方建议大项目拆成多个 session，并说明没有并发 session 数量限制。[Devin usage 文档](https://docs.devin.ai/admin/billing/usage)

Devin 的并行 managed sessions 各自运行在隔离 VM，协调 session 负责划分工作、监控和汇总结果。[Devin advanced capabilities 文档](https://docs.devin.ai/work-with-devin/advanced-capabilities)

### 分析判断

Devin 区分了两个经常被混淆的概念：

- **Environment template/snapshot**：让每次运行有一致工具链；
- **Session working state**：本次任务的变化，默认不污染模板。

其长期成果主要应通过 repository/branch/PR、Knowledge 等外部持久层承载，而不是依赖 session VM 永不销毁。对 Prose 的启发是，smolvm 的 base image、工具安装和 Project data snapshot 也应拆开：更新 Agent 工具链不应重写项目资料；恢复项目资料也不应要求复活同一物理 VM。

## 5. Replit Agent：最接近 Prose 所需的混合模型

### 官方明示事实

Replit 将 Project 定义为全部代码、数据和 artifacts 的容器；一个 Project 可包含多个 artifact，并共享数据库、后端和存储。[Replit Projects 文档](https://docs.replit.com/references/projects-and-artifacts/projects)

Replit checkpoint 会保存完整 Project 状态，包括项目文件、AI conversation context、环境配置、Agent memory，以及可选的数据库内容；可以回滚和向前恢复。[Replit checkpoints 文档](https://docs.replit.com/references/version-control/checkpoints-and-rollbacks)

Replit 的后台 task 在 Project 的隔离副本中运行，主版本在用户选择 Apply 之前不变。不同 task 可以并发执行，完成后展示 work log、测试和 preview，再 merge 到主版本；官方说明 Apply 多个 task 时会处理冲突。[Replit task system 文档](https://docs.replit.com/core-concepts/agent/task-system)

### 分析判断

Replit 的公开产品模型最完整地覆盖了 Prose 的核心矛盾：用户需要“同一个长期项目”，系统又需要“并发任务不互相污染”。其答案不是永远共用一台 VM，而是：

```text
Project main state
├── Task A isolated copy → review/apply ┐
├── Task B isolated copy → review/apply ├──> new Project revision
└── checkpoints <───────────────────────┘
```

标书产品的章节生成、商务要求解析、技术方案编制、评分自检天然可以并行，因此 Replit 的主状态/任务副本/合并模型比 Manus 的纯 task sandbox 或简单共享磁盘都更合适。

## 跨产品共同规律

### 规律一：没有必要让 Project 拥有一台永生 VM

Manus 默认 sandbox、Claude Code cloud、Codex cloud 和 Devin 都把计算环境做成可创建、休眠、回收或重建的资源。即使产品提供真正 24/7 VM（如 Manus Cloud Computer），也是面向持续运行服务的特殊能力，而不是普通 Project 的默认语义。

**对 Prose 的含义**：物理 `vm_id` 不应成为 Project 的业务主键或不可替换外键。Project 应绑定 `workspace_id` / `environment_id`，运行时再解析为当前 lease。

### 规律二：持久状态有多层，不能只保存文件夹

优秀产品至少区分：

- 原始输入与知识来源；
- 可交付 artifacts；
- 项目指令/规则；
- 项目 memory/knowledge；
- chat transcript；
- runtime scratch；
- 可恢复 checkpoint/revision。

**对 Prose 的含义**：Sandbox 磁盘只是这些状态的一个临时投影，不能成为唯一事实来源。

### 规律三：跨会话连续性不等于把全部聊天历史塞给模型

Claude、ChatGPT、Claude Code 和 Devin 都使用项目知识、结构化指令、项目 memory 或 repository docs 提供跨 session 连续性，同时让每个 session 保持独立 transcript。

**对 Prose 的含义**：应维护可审计的“项目记忆/决策账本”，例如投标策略、术语约束、已确认承诺、否决方案，而不是在新 session 中无差别加载全部旧消息。

### 规律四：一旦允许并发，共享可写工作区就必须有隔离与合并

Claude Code、Codex 和 Replit 都明确采用 worktree/isolated copy；Devin 并行 session 也各自使用隔离 VM。原因不是代码产品特有，而是所有可变产物都会遇到相同问题：覆盖、脏读、半成品可见和冲突。

**对 Prose 的含义**：两次“技术方案生成”和“商务条款修订”即使编辑不同文件，也可能同时改总目录、摘要、响应矩阵或引用索引，不能默认安全共写。

### 规律五：恢复的是逻辑状态，不是原进程

Manus 回收后恢复重要文件，Claude Code cloud 重建环境并恢复对话，Codex 删除 worktree 前保存 snapshot，Replit 从 checkpoint 恢复完整 Project。它们都把恢复目标放在用户可感知状态，而不是 VM PID。

**对 Prose 的含义**：可接受的恢复 SLO 应定义为“资料、产物、revision、对话和任务状态恢复”，而不是“同一台 microVM 继续运行”。

## 对 Prose 的推荐架构

### 1. 核心所有权模型

```text
Bid Project（一次投标工作）
├── Canonical Workspace（持久主状态，唯一 HEAD）
│   ├── sources/              原始招标文件与版本
│   ├── structured/           解析结果、响应矩阵、本体对象
│   ├── deliverables/         标书章节、表格、附件、导出物
│   ├── project-rules/        写作规范、投标策略、术语和约束
│   └── manifest              文件/Artifact ID、版本、hash、来源关系
├── Project Memory            已确认决策、事实、风险和未决项
├── Artifact Registry         稳定 ID、版本、状态、引用与审批记录
├── Sessions[]                各自独立的聊天与模型上下文
└── Runs[]
    ├── base_revision
    ├── isolated working copy / overlay
    ├── sandbox lease
    ├── changeset + execution log
    └── merge/publish result
```

所有权应是：

- `Project` owns `Workspace`、`Artifact`、`ProjectMemory`；
- `Session` owns transcript、UI thread、用户临时意图；
- `Run` owns sandbox lease、working copy、临时文件和执行日志；
- `Sandbox` 不拥有任何不可替代的业务数据。

### 2. Project 创建语义

创建 Project 时立即完成：

1. 创建 `workspace_id` 和 revision 0；
2. 创建持久对象存储/卷的逻辑 namespace；
3. 创建 Artifact Registry 和 Project Memory 空间；
4. 固化权限、加密域、审计策略和默认模板版本；
5. 不启动 VM。

首次上传、解析、对话调用工具或生成产物时才创建 Run 并租用 smolvm。

### 3. Run 与 Sandbox 生命周期

建议状态机：

```text
queued → provisioning → running → waiting/idle → checkpointed
                                      │               │
                                      └─ wake ────────┘
checkpointed → merged | conflict | discarded
checkpointed/merged → sandbox released
```

关键规则：

- 每个 Run 记录开始时的 `base_revision`；
- VM 从 base image 启动，再挂载/恢复 Project revision 的工作副本；
- Run 中的 scratch 不自动进入 Project；
- 只有 changeset 中被分类为 source/structured/artifact/project-rule 的内容才可持久化；
- sandbox 可 pause、snapshot 或直接销毁，选择取决于恢复成本；
- 热 VM 复用和 snapshot 只是基础设施优化，对 API 使用者透明。

### 4. 顺序工作与并行工作的双路径

不需要所有工作一开始都走复杂 merge：

- **单写者快速路径**：Project 当前无其他 writer 时，Run 基于 HEAD，完成后可自动 fast-forward merge。
- **并行隔离路径**：存在其他 active writer 或任务显式要求试验/并行时，为 Run 建立 Copy-on-Write overlay；完成后生成可审阅 changeset。
- **冲突路径**：若 HEAD 已前进，按 Artifact/结构化对象做三方合并；不能安全合并时要求用户选择，不直接覆盖。

不要只做文件级冲突。标书平台拥有比 Git 更丰富的领域对象，可以实现：

- 章节按 block/段落合并；
- 响应矩阵按 requirement ID 合并；
- 引用按 source span ID 合并；
- 项目策略、资格承诺等高风险对象要求显式审批。

### 5. Artifact 不应等同于任意文件

Manus 的回收规则已经显示“重要 artifact”和“中间代码”必须区别对待。Prose 应为 Artifact 建立稳定身份：

```text
ArtifactVersion
- artifact_id
- project_id
- version
- content_uri / structured_payload
- created_by_session_id
- created_by_run_id
- base_revision
- source_refs[]
- status: draft | reviewed | approved | superseded
- checksum
```

这样即使 sandbox 整体丢失，用户仍能获得完整可追溯产物；也能回答“这一段由哪次会话、依据哪个招标条款生成”。

### 6. Project Memory 要可见、可编辑、可追责

可以借鉴 Claude/ChatGPT 的 project-scoped memory，但标书是高风险业务，不能只维护黑盒摘要。建议把 memory 拆成：

- 自动候选记忆：Agent 提议，尚未成为约束；
- 已确认项目决策：用户确认后跨 session 注入；
- 已提取事实：带 source citation 和版本；
- 风险与未决项：有责任人、状态和截止时间；
- 废弃/被取代决策：保留历史但不再注入。

新 session 默认获取精炼的 Project Context Pack，而不是全部 transcript：

```text
当前 Project revision
+ 已确认规则/决策
+ 相关来源与 Artifact 摘要
+ 当前任务所需的历史片段（检索）
```

### 7. 更新传播语义必须产品化

Manus 明确区分“指令更新何时影响当前 task”和“文件更新只影响新 task”。Prose 也应在数据模型和 UI 中明确：

- Run 开始时记录 `base_revision`，保证可复现；
- Project 新资料上传后，已运行中的 Run 不静默换输入；
- 用户可选择“继续旧 revision”“刷新/rebase 到最新资料”或“终止重跑”；
- 已完成 Artifact 不因 Project 新资料而被静默改写，只标记为 `possibly_stale` 并触发影响分析。

这对招标文件补遗、澄清函和版本替换尤其重要。

## 不建议的三个方案

### 方案 A：Project 永久绑定一台物理 VM

问题：空项目占资源；VM 故障/升级变成业务灾难；物理实例寿命限制泄漏到产品模型；难以弹性扩缩；并发仍未解决。

可以保留 `preferred_warm_sandbox_id` 作为缓存，但不能把它当所有权。

### 方案 B：所有 Session 各有独立 Workspace，互不合并

这正是当前设计错位的根源：用户无法确定哪个 session 的目录是“项目最新版”，产物会分叉，前端只能猜最新 session。

### 方案 C：所有 Session 直接读写同一个 Project 目录

顺序使用体验好，但并发时会出现覆盖、脏读、半成品暴露和不可恢复冲突。它只适合 MVP 的单写者约束，不能作为最终不变量。

## 推荐的产品不变量

建议最终确认以下七条：

1. **每个 Bid Project 有且仅有一个逻辑 Canonical Workspace 和一个当前 revision。**
2. **Session 不拥有 Workspace；Session 只属于 Project 并拥有自己的 transcript。**
3. **每次有副作用的执行属于 Run；Run 从明确的 Project revision 开始。**
4. **Sandbox 是 Run 的可替换租约，按需创建，可暂停、回收和重建。**
5. **Run 默认在隔离工作副本中写入，结果以 changeset 合并/发布到 Project。**
6. **Artifact、来源、项目决策和审计记录独立于 Sandbox 持久化并版本化。**
7. **用户可感知的恢复承诺针对 Project 逻辑状态，不针对同一物理 VM。**

## 最终判断

最初提出的“Project 内不管新建多少会话，都在同一个 sandbox 进行”抓住了关键问题的一半：**Workspace 确实必须从 Session 上移到 Project**。但调研后的更优答案是：

> 同一 Project 的所有 Session 应工作在同一个**逻辑项目空间**里，却不应默认同时写同一个物理 sandbox。Project 保有唯一主状态；每个执行 Run 按需使用隔离 sandbox/工作副本；通过版本化 changeset 把正式成果合回 Project。

如果近期只做最小改造，可以先实现“Project-owned workspace + 单写者锁 + VM 按需恢复”；但数据模型应从第一天保留 `Run`、`base_revision`、`workspace_revision` 和 `changeset` 的位置，避免未来引入并行编制时再次迁移所有权。

