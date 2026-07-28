# Tickets: M1 项目工作区上移

把沙箱/工作区的绑定从 session 上移到 Project：宿主侧 canonical workspace（git 持久层）+ 项目级 VM 租约 + 轮末 checkpoint。源契约：`hagent/docs/specs/2026-07-10-project-workspace-design.md`（W1–W8 + §6 M1），决策记录 `docs/adr/0007-项目工作区与沙箱租约.md`。

沿**边界（frontier）**开工：任何一张 blockers 全部完成的票都可开跑。本组结构：1、2 可并行起步 → 3 汇合 → 4→5 与 6 并行 → 7 收口。

## 1. 项目工作区模块（host 侧 git 持久层）

**What to build:** 创建 Project 时同步创建它的 canonical workspace——宿主侧目录骨架（sources/ structured/ deliverables/ tmp/）并初始化 git 仓（.gitignore 按 spec W4 排除名单）；提供带 Run-ID / Session-ID / Kind trailer 的提交能力（同项目提交串行互斥）、文件列举 / 读取 / 历史查询能力，供后续 checkpoint 与 HTTP 端点复用。

**Blocked by:** None — can start immediately

- [x] 通过 API 创建项目后，宿主存在该项目的 workspace git 仓，含目录骨架与 .gitignore
- [x] 提交 API 产生带 trailer 的 commit；并发提交被串行化，仓不损坏
- [x] 文件列举 / 读取 / git log 查询可用
- [x] 软删项目不删除 workspace（数据保留）

## 2. 租约上移：沙箱全链路按 project 键

**What to build:** 沙箱租约从 session 上移到 project——同一项目的所有会话共享同一台 VM，不同项目各自租用；租约状态、快照引用、活跃时间迁入项目级租约存储（sandbox_leases），runs 表同期建好（本期仅记录、不承载锁）；会话创建必须归属项目、不再持有沙箱状态；启动对账 / reaper / 健康治理 / 运维视图在新键下照常工作。

**Blocked by:** None — can start immediately（与 1 并行）

- [x] 同项目两个会话先后发消息复用同一 VM；不同项目各自 VM
- [x] 会话创建必须携带 project_id；session 不再持有沙箱状态字段（破坏性迁移，dev 阶段不做兼容）
- [x] vm_id 以项目前缀命名；重启对账 / reaper / 健康杀重建在新键下全链路回归（门控 smolvm 测试通过）
- [x] runs 与 sandbox_leases 表按 spec §3 DDL 落库
- [x] /ops/state 以项目视角呈现租约行

## 3. 物化与追平注入

**What to build:** 租约建立时把项目 workspace 当前状态物化进 VM（guest 侧建立临时变更探测基线）；当 VM 内容落后于项目最新 revision（如宿主直接更新过 workspace）时，下一轮开始前按差异注入 / 删除追平，agent 永远工作在项目最新状态上。

**Blocked by:** 1. 项目工作区模块、2. 租约上移

- [x] 冷启动后 agent 在 VM 内读到项目 workspace 全部文件（排除名单外）
- [x] 宿主侧推进项目 revision 后，下一轮对话 agent 所见与最新一致（含被删除文件消失）
- [x] 租约记录的 materialized_revision 随注入 / 追平更新
- [x] 注入跳过 .gitignore 命中项与 git 元数据

## 4. 轮末 checkpoint 管道 + 生命周期兜底

**What to build:** 每轮对话结束时自动把 VM 内变更回写项目 workspace 并形成提交——正常走完、异常、用户打断、客户端断连四种退出路径归一处理；提交完成后、done 事件前向前端发出 checkpointed 事件；沙箱 pause / 快照 / 驱逐 / 释放前强制兜底 checkpoint；每轮在 runs 表落一行 chat_turn 记录（base_revision → commit_sha）。

**Blocked by:** 3. 物化与追平注入

- [x] 消息轮写文件后，done 事件前收到 workspace.checkpointed（含 commit sha），宿主 git log 出现带 trailer 的对应提交
- [x] 无文件变更的轮次不产生 commit（no-op）
- [x] 异常 / 打断轮 best-effort 提交并标注 interrupted
- [x] idle pause / evict / release 前触发兜底 checkpoint
- [x] 活跃对话中 kill -9 VM，重发消息后此前各轮成果完整无损
- [x] 每轮 runs 表有记录：kind=chat_turn、base_revision、commit_sha

## 5. 快照降级：project 键 + 静默冷启动回退

**What to build:** DISK 快照改为项目级 best-effort 唤醒缓存：idle 驱逐先兜底 checkpoint（真持久）再落快照（缓存）；唤醒时快照不可用（损坏 / 被清 / 容量不足）一律静默冷启动 + 物化注入，用户无感——拆除「容量不足 503 保快照」等数据事故语义。

**Blocked by:** 4. 轮末 checkpoint 管道 + 生命周期兜底

- [x] idle 驱逐路径先 checkpoint 后快照，快照键为 project
- [x] 手动删除快照文件后发消息：无错误，冷启动且 workspace 完整
- [x] 恢复容量不足不再 503，静默走冷启动回退
- [x] 快照恢复成功路径保留 agent 自装的环境增量

## 6. 文件上传归属 project + workspace 读取端点

**What to build:** 上传招标文件（含后续补遗追加）落项目 workspace 的 sources/ 并形成提交；项目租约活跃时同步注入 VM，无租约时不触发 VM 创建。提供项目 workspace 的文件列举 / 读取 / 历史 HTTP 端点作为前端数据源；session 级上传路径废弃。

**Blocked by:** 1. 项目工作区模块、3. 物化与追平注入

- [x] 上传后文件出现在宿主 workspace sources/ 且有对应提交（trailer 标注上传来源）
- [x] 租约活跃时上传文件同步出现在 VM 内；无租约时不创建 VM
- [x] workspace 列举 / 读取 / 历史端点可用且走 API key 鉴权
- [x] session 级上传端点移除或返回 410

## 7. 前端：项目工作区链路接通

**What to build:** M1 出口判据的端到端兑现——拖文件建项目改走「项目上传」；项目内可新建会话，新会话看到并可续写此前会话的产物（同一工作区）；回到项目读取的是项目 workspace 而非最新 session；画布消费 checkpointed 事件刷新产物。

**Blocked by:** 4. 轮末 checkpoint 管道 + 生命周期兜底、6. 文件上传归属 project + workspace 读取端点

- [x] Home 拖文件 → 建项目 + 上传到项目 + 首会话解析全链路可用
- [x] 项目内「新建会话」入口：新会话看得到并可修改此前会话的产物
- [x] resumeProject 改从项目 workspace 端点取数（矩阵产物按 `bid_response_matrix_*/final/` 在 workspace 任意层级匹配；skill 现写根目录，后续迁 structured/ 投影无需改前端）
- [x] 收到 workspace.checkpointed 后画布产物刷新
- [x] pnpm typecheck + pnpm lint 通过

## 验收记录（2026-07-11）

双轴评审（Standards + Spec，基线 ec07f75...57e148c）逐票核验通过，三项保留已闭环：

1. 门控回归实跑：`HAGENT_TEST_SMOLVM=1 pytest -m smolvm` 14 passed / 4 skipped（e2e 无 key 按设计 skip）。
2. 补 `GET /sessions?project_id=`（spec §4.5 契约端点，store 层过滤早已就位，router 接参 + 单测）。
3. 补票 4 直接用例 `test_kill9_vm_mid_conversation_preserves_checkpointed_turns`：checkpoint 落 canonical → SIGKILL VM → 真健康探活三连败清场 → 重发消息冷重建物化，前轮成果无损（真 Firecracker 实跑通过）。

已知限度（记录备查，不阻塞验收）：客户端断连轮（GeneratorExit）只兜底 checkpoint 不发 `workspace.checkpointed` 帧——彼时无人在听，属客观语义；打断/异常提交本身有测试覆盖。评审全文见当次会话 /code-review 报告。
