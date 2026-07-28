# Plan: SmolVM Sandbox Provider 实现任务分解

**Spec**: `docs/specs/2026-07-06-smolvm-sandbox-design.md`
**Date**: 2026-07-06

每个 Task 一个 commit(Conventional Commits),严格 TDD:先写失败测试再实现。SDK 行为存疑时以 `.venv/lib/python3.12/site-packages/smolvm/` 实际源码为准(spec §2 硬事实表),发现偏差回写 spec 并同步本 plan。

## 文件结构

新增:`src/hagent/sandbox/smolvm/{__init__,image,lifecycle,sandbox,reconciler,audit}.py`、`src/hagent/sandbox/{ledger,supervisor}.py`、`tests/sandbox/test_smolvm_*.py`、`tests/sandbox/test_{ledger,supervisor}.py`、`docs/deploy/smolvm.md`。
修改:`pyproject.toml`、`sandbox/protocol.py`(SandboxKind)、`sandbox/pool.py`、`config.py`(预检)、`server/{sessions,manager,app}.py`、`server/routers/sessions.py`(503 语义)、`cli.py`、`tests/sandbox/test_tool_parity.py`、`tests/sandbox/test_pool.py`、`CLAUDE.md`、`AGENTS.md`。

## Phase A — P0 正确性底座(全部完成才可切默认)

- **Task A1** 依赖与门控:`pyproject.toml` 加 `smolvm==0.0.25`(锁死,不带 `>=`)+ pytest marker `smolvm`;`tests/sandbox/conftest` 加 `HAGENT_TEST_SMOLVM=1` skip 门控 fixture。测试:markers 注册断言。
- **Task A2** `sandbox/protocol.py`:`SandboxKind.SMOLVM`。测试:`from_str("smolvm")` 往返(现有 test_protocol_types 扩展)。
- **Task A3** `sandbox/smolvm/image.py`:`HAGENT_DOCKERFILE`(python3.12-slim + rg/git/bash/coreutils + guest-agent COPY + sshd,`/workspace` 内建)+ `ensure_boot_image()`(DockerRootfsBuilder 封装、指纹缓存、进程内单飞防并发重复构建)。测试:Dockerfile 内容断言(含 python3/rg/agent/sshd 四要素)、builder mock 的缓存命中/单飞;`@pytest.mark.smolvm` 真构建冒烟。
- **Task A4** `sandbox/smolvm/lifecycle.py`:`SmolVMLifecycle.start()`(VMConfig 装配 ← env 配额;`from_image` → `start(boot_timeout)` → `wait_for_ready` → `run("python3 -c ...")` 探针;失败 `delete()` 全清理重试 ≤2)、`stop()`(stop+delete+close 幂等)、`pause()/resume()`、`adopt(vm_id)`(`from_id` + 活性/探针校验);vm_id 生成 `hagent-<sid8>-<rand6>`;SDK 异常 → `SandboxStartError` 等 hagent 异常映射表。测试:全 mock SDK——重试计数与清理调用序、探针失败路径、adopt 死 VM 抛错、异常映射表驱动。
- **Task A5** `sandbox/smolvm/sandbox.py`:`HagentSmolVMSandbox(BaseSandbox, HagentSandboxProtocol)`——`execute()`(per-instance RLock;`vm.run(command, timeout, shell="raw")`;stdout/stderr 合并格式、`[stderr] ` 前缀、截断 marker 与 docker provider **byte-equal**;`OperationTimeoutError`→exit 124、其他 SmolVMError→exit 137)、`upload_files`/`download_files`(tempfile 桥接、部分成功语义、mkdir -p 行为对齐)、`id`/`kind`/`workspace_dir`/`manifest`(复用 `SandboxManifest`,`container_id` 存 vm_id)/`close`。`config.py` 的 `_SANDBOX_BACKEND_NAMES` 加 `HagentSmolVMSandbox`。测试:输出格式逐字段对照 docker provider 断言、两线程并发 execute 串行化断言、tempfile 清理、空文件/大文件(>128KB)上传。
- **Task A6** `sandbox/ledger.py`:`AdmissionLedger.try_reserve/commit/release` + `CapacityExceeded`;容量 = 宿主内存 ×(1−reserve%)− Σ(committed+reserved),CPU 按超卖比;宿主探测可注入(测试用)。测试:占位-提交-释放全生命周期、并发 reserve 不超放、耗尽抛错、env 覆盖。
- **Task A7** `sandbox/pool.py` 改造:acquire 先 `ledger.try_reserve`(无 ledger 时行为不变,docker 路径零影响);release/evict 归还额度;认领后异步补货至 min;补货连续 3 败熔断(冷却 300s 后重试);池空且额度足 → 冷启动。测试:现有 test_pool.py 全绿(无 ledger 回归)+ 新增占位/补货/熔断/额度归还用例。
- **Task A8** `server/sessions.py`:migration 加列 `sandbox_state`/`sandbox_desired_state`/`last_activity_at` + `touch_activity()`;`server/manager.py` create/delete 写状态机,消息路由挂 touch。测试:migration 幂等(现有 schema_migration 测试模式)、状态转移写入、touch 只在消息/工具事件更新。
- **Task A9** `sandbox/supervisor.py` + `sandbox/smolvm/reconciler.py`:Reconciler 协议(`plan() -> list[Action]`、`reap_errors()`);`SmolVMReconciler` 实现 spec §4.4 对账矩阵(收养/清场/标 orphaned 三类动作);`SandboxSupervisor.startup_reclaim()`(同步一轮)+ `reaper_loop()`(60s 线程,失败计数告警)+ `shutdown()`。测试:对账矩阵 8 分支表驱动(mock SmolVM DB + mock sessions)、reaper 清理失败连续 3 次升 ERROR 日志、shutdown 幂等。
- **Task A10** 接线:`config.py` `preflight_sandbox_kind()`(kvm 可读写 / firecracker 二进制 / sudoers 文件 / smolvm 可导入 → 逐项 WARNING + 降级链 smolvm→docker→none;`HAGENT_SANDBOX_REQUIRE` 强制);`server/app.py` `_build_smolvm_pool()` + lifespan 挂 supervisor(startup_reclaim → reaper;shutdown 先 supervisor 后 pool);routers 的 `CapacityExceeded`/`PoolExhausted` → 503 + Retry-After;`cli.py` `--sandbox smolvm`。测试:预检各失败分支降级断言(monkeypatch 探测)、app lifespan 装配顺序、503 语义。
- **Task A11** tool parity 三方化:`tests/sandbox/test_tool_parity.py` 扩展 host/docker/smolvm 对照(smolvm 侧 `@pytest.mark.smolvm` 门控)。
- **Task A12** L3 集成测试 `tests/sandbox/test_smolvm_integration.py`(`@pytest.mark.smolvm`):start→exec(python3 探针)→upload→cat 回读→download→timeout(exit 124)→pause/resume→close 全链;**孤儿治理端到端**:起 VM 后模拟进程内崩溃(不调 close 直接丢句柄 + 新起 supervisor)断言收养;伪造无主 `hagent-` VM 断言清场;`hagent sandbox ls` 可见性。
- **Task A13**(实现期补,A5/A11 盲区)Bash 工具旁路适配:`SandboxShellProvider.command_argv` 原为 docker 专用(取 `sandbox._container.id` 拼 `docker exec`),smolvm 下 Bash 工具全挂(e2e 报 `_container` AttributeError)。修复:argv 构造下放 provider——`HagentSmolVMSandbox.shell_exec_argv()` 生成 SSH argv(vsock 无流式 F4,SSH 是 spec D4 兜底通道;ControlMaster 复用);docker 分支零改动。测试:shell_provider 分派 unit ×3 + L3 `test_bash_tool_through_sandbox_shell_provider`(host parity + cwd 哨兵持久化)。第二层根因(spec F13):vsock 就绪不担保 sshd 就绪 + 运行期 keygen 熵阻塞 → 镜像改烘焙期 `ssh-keygen -A` + argv 加 ConnectionAttempts。教训:spec §7 的 Bash byte-equal 由 execute() 与 shell-provider 两条通道共同承担,门控测试必须双通道都盖。

## Phase B — P1 运营能力(依赖 Phase A)

- **Task B1** `sandbox/smolvm/audit.py`:命令审计 JSONL(spec §4.5 schema,append-only,按 sid 分文件)+ `sandbox_events` 事件表(SQLite migration);`HagentSmolVMSandbox` 埋点(execute/upload/download)+ lifecycle 埋点(created/evicted/create_failed)。测试:JSONL 逐字段快照、事件表写入、审计失败不影响主链路(best-effort)。
- **Task B2** 健康巡检:supervisor 加 `health_loop()`(10–20s,`vm.run("true", timeout=5)` 或进程活性;连续 3 败 → 杀重建流程:清残留 → session 标 orphaned → 事件 health_fail);orphaned session 首条新消息触发重建(新 VM + files 重灌接口,artifacts 尽力 download 抢救)。测试:mock 连败计数与重建触发、抢救 best-effort 失败不阻断。
- **Task B3** idle 治理补全:`max_lifetime`(86400s)驱逐挂进 pool GC;活跃度只认 API 交互(touch 路径复核,SSE 心跳不触发)。测试:寿命到期驱逐、心跳不续期。
- **Task B4** 指标采样:supervisor 内 5–10s 读 `/proc/<pid>/stat|statm` → 事件表 metrics 行(降采样)。测试:mock /proc 解析。
- **Task B5** graceful drain:SIGTERM/lifespan shutdown → 拒新建(503)→ 存量 pause → supervisor/pool 有序退出。测试:drain 时序断言。
- **Task B6** CLI 运维:`hagent sandbox {ls,stop,logs}` 识别 smolvm(ls 走 SDK `list_vms` 过滤前缀 + 状态;logs 读 `data_dir/{vm_id}.log`;stop 走 lifecycle.stop)。测试:mock SDK 的子命令输出。
- **Task B7** SSE 事件:`sandbox.created/adopted/evicted/orphaned/health_fail` 补进 `server/sse.py` 并在对应路径发射。测试:事件序列断言(现有 sse 测试模式)。
- **Task B8** e2e + 冒烟:`tests/test_demo_e2e_sandbox.py` 加 smolvm 参数化(`HAGENT_TEST_SMOLVM` + `ANTHROPIC_API_KEY` 双门控);`scripts/curl_smoke.sh` 加 smolvm 段(可用性探测,缺环境跳过)。
- **Task B9**(实现期补,L3 连跑暴露)通道时序健壮性(spec F15):adopt 的 `from_id` 重连句柄探针前须 `wait_for_ready`(否则 churn 下收养误判失败转清场);`execute()` 对 vsock CONNECT 握手类**连接期**瞬时错误有界重试(命令未送达 guest,安全);L3 崩溃模拟修正为 `vm.close()` + del(裸 del 留给 GC,新旧句柄同进程争通道,非真实崩溃形态)。教训:单跑绿≠稳,smolvm 门控套件必须整套连跑验证。
- **Task B10**(实现期补,生产 500 事故)reaper 创建窗口防误杀(spec §4.4):周期轮对无主/残留 VM 两轮复核才清场,pid 死不缓刑,启动首轮立即清。事故链:VM 启动 1–2s 窗口未进保护集且 session 元数据未写 → reaper 误清 → 池发死句柄 → 上传 500。附带修复 dev server reaper 误杀并行门控测试 VM 的干扰(B9 的部分间歇失败即此因)。

> Phase B 状态:B1–B9 全部完成(2026-07-07)。验证:默认套件全绿;`HAGENT_TEST_SMOLVM=1 pytest -m smolvm` 连跑 3 轮全绿;`HAGENT_TEST_DOCKER=1 pytest -m docker` 全绿无回归。

## Phase C — P2 性能与纵深(依赖 Phase B,每项独立可选)

- **Task C1** 预热池:`HAGENT_SANDBOX_PREWARM` 下 min_size 预启动;golden base 构建移至启动期(smolvm 生效即构建,失败即启动失败,spec §6 镜像语义);池实例定期 recycle(防漂移,`HAGENT_SANDBOX_RECYCLE_SECONDS` 默认 3600,只针对 warm idle);附带:smolvm 池的 GC 循环常开,不再依赖 PREWARM 开关。
- **Task C2** DISK 快照持久化:paused 超阈值 → DISK snapshot + delete VM(释放内存额度)→ resume 时从快照重建;快照 `force`/一次性语义处理。实现要点:persist 快照先行(失败保 VM 完好退驱逐);restore 走 `from_snapshot(resume_vm=True)` 回原 vm_id + readiness 门;一次性语义靠清理链兜住(恢复即清引用、restored VM 拆除/被新快照取代/session 删除时删快照);`SandboxState.SNAPSHOTTED` 不入 reconciler 主张集(VM 消失是常态);恢复失败回退 orphaned 全新重建;`HAGENT_SMOLVM_SNAPSHOT_PERSIST=0` 可关。
- **Task C3** 部署纵深文档 + 配置:`docs/deploy/smolvm.md`(KVM/kvm 组/sudoers/Docker/WSL2 固化/btrfs 建议/systemd unit 样例含 `SupplementaryGroups=kvm` 与 `AmbientCapabilities=CAP_NET_ADMIN` 快路径)+ `SMOLVM_DATABASE_URL` Postgres 说明。
- **Task C4** 出口白名单策略化:`HAGENT_SMOLVM_ALLOWED_DOMAINS` 接 `internet_settings`(dict 交 SDK 规范化;空串视同不启用,防手滑全断网);文档写明 IP 固化局限(spec F6)。
- **Task C5** 多机接缝:pool 的 sandbox_factory 抽为 `NodeClient` 协议(`sandbox/node.py`,LocalNodeClient 包裸工厂,现有调用方零改动)+ sessions 表 `node` 列预留(仅接口与迁移,无实现;manager 建会话打点,单机恒 local)。

> Phase C 状态:C1–C5 全部完成(2026-07-08)。验证:默认套件全绿(956 passed);`HAGENT_TEST_SMOLVM=1 pytest -m smolvm` 连跑 3 轮全绿(含新增快照往返 L3);双门控真实模型 e2e 过;`HAGENT_TEST_DOCKER=1 pytest -m docker` 全绿无回归;`curl_smoke.sh` 过(sg kvm 下 smolvm 段真跑:建 session → 上传 → vsock 列目录);spec §4.3/§5/D13 已回写 snapshotted 态与新 env。前端人工链路验证待人工执行。

## 验收(对应 spec §8)

1. `pytest -v` 全绿(默认套件,无外部依赖)。
2. `HAGENT_TEST_SMOLVM=1 pytest -m smolvm -v` 全绿(WSL2 本机)。
3. `HAGENT_TEST_DOCKER=1 pytest -m docker -v` 全绿(docker provider 无回归)。
4. 孤儿治理 L3 场景过(收养 + 清场 + ls 无泄漏)。
5. 预检降级链验证(mock 无 kvm → docker + WARNING)。
6. `./scripts/curl_smoke.sh` 过;前端人工链路验证。
7. `CLAUDE.md` / `AGENTS.md` / `docs/deploy/smolvm.md` 同步入仓。
