# Design Spec: SmolVM Sandbox Provider(企业级 Firecracker microVM 沙箱服务)

**Date**: 2026-07-06
**Repo**: `/home/han/workplace/tender`(`hagent/` 子目录)
**Status**: DRAFT(方向已确认,细节评审中)
**依赖版本**: `smolvm==0.0.25` + `smolvm-core==2026.6.24`(**锁版本**,0.0.x API 演进剧烈,升级走显式任务)
**承接关系**: 扩展 `2026-05-19-hagent-sandbox-design.md` 的抽象层(protocol / pool / SessionManager),**不取代** docker provider;Daytona stub 不受影响。
**调研依据**: SmolVM SDK 源码深读(facade.py 3677 行全文 + storage/network/builder 模块)与企业级 sandbox 架构调研(E2B infra / Daytona / Manus / fly.io flyd / Firecracker prod-host-setup),结论已交叉验证,本 spec 引用处标注来源层级(【源码】/【实测】/【业界】)。

## 1. Problem Statement

hagent 现有 sandbox 是 Docker + gVisor(runsc):共享宿主内核、gVisor syscall 拦截有稳定 I/O 性能税、启动秒级。目标是引入 SmolVM + Firecracker 作为**第三种且默认**的 sandbox provider——KVM 硬件级隔离、冷启动亚秒(WSL2 实测 749ms,vsock 命令通道 1–31ms)【实测】。

**本 spec 不是最小接入**,而是完整的企业级 agent sandbox 服务,覆盖五个能力面:

1. **调度与准入**:容量账本(内存不超卖 / CPU 受控超卖)+ 并发池(认领即补、池空冷启动、补货熔断)。
2. **孤儿 VM 治理**:server 崩溃/重启后的启动对账(收养活跃会话 VM + 清场残留)+ 周期 reaper 兜底。
3. **失败回收**:健康巡检、启动失败带全清理的重试、病 VM 杀掉重建不修复。
4. **日志采集**:宿主侧命令审计 JSONL + VM 运行日志 + 生命周期事件表 + 资源指标采样。
5. **默认切换**:`smolvm` 成为默认 sandbox kind,带启动预检与降级链,任何环境开箱能跑。

**总体策略:Adopt SDK + Extend 服务层。** SmolVM SDK 已解决单 VM 生命周期(进程管理、SQLite 状态库、TAP/nftables 网络、`from_id` 重连、`reconcile()` 对账原语),hagent 不重造;新建的是它明确没有的服务化治理层。

## 2. SmolVM 硬事实(源码级,约束设计)

以下事实来自 SDK 源码深读,是本 spec 各决策的前提;实现期发现与此不符时**以 `.venv` 内 smolvm 实际源码为准**并回写本节:

| # | 事实 | 影响 |
| --- | --- | --- |
| F1 | 每 VM 一个独立 firecracker 进程(`start_new_session=True`),SDK 进程崩溃 VM 照跑;`SmolVM.from_id(vm_id)` 可重连 | 收养式重启对账可行 |
| F2 | 状态库为 SQLite(`~/.local/state/smolvm/smolvm.db`,未开 WAL,EXCLUSIVE 事务);`SMOLVM_DATABASE_URL` 可切 Postgres | 单机小并发够用;高并发逃生门已知 |
| F3 | `SmolVMManager.reconcile()` 扫死 pid 降级 ERROR,但**无后台看门狗**;ERROR 行需显式 `delete()` 才释放 TAP/IP/磁盘租约 | reaper 必须 hagent 自建,且对 ERROR 行补 `delete()` |
| F4 | `run()` 无流式、超时抛 `OperationTimeoutError` 且丢输出;`async_*` 是 `asyncio.to_thread` 包装;**同一 SmolVM 实例非线程安全**;`async_run` 不触发 callbacks | provider 层加锁;审计记在调用点而非 SDK callback |
| F5 | 快照默认只能恢复一次;"golden 派生"正确路径 = 共享 base rootfs + `disk_mode="isolated"` CoW(btrfs/XFS reflink 瞬时,ext4 退化稀疏拷贝,Alpine base 实占 ~84MB) | golden 走 base image 而非快照;ext4 拷贝成本可忍 |
| F6 | `internet_settings.allowed_domains`:创建时宿主解析域名→IP 钉进 per-TAP nftables,fail-closed,仅 TAP(Firecracker)生效 | 出口白名单可用,但 CDN 轮换会误伤,默认不启用 |
| F7 | 默认 Alpine 镜像**无 python3、无 rg**;`DockerRootfsBuilder`(Dockerfile→ext4)不自动注入 guest-agent/sshd | 必须自建镜像且 Dockerfile 显式装 agent + sshd(hagent 的 Grep/Glob/readiness 依赖 python3 + rg) |
| F8 | 文件传输 API 走本地路径单文件(vsock 通道单请求上限 256MiB);hagent 协议传 bytes | provider 内 tempfile 桥接 |
| F9 | 无 cgroup 限额、无 jailer;sudoers 通配宽(`ip *`/`nft *`/`kill -9 *`) | 已知安全缺口,记录于 §9 风险 |
| F10 | 通道:vsock(HTTP over vsock,Rust guest agent,首命令 ~1ms)优先,SSH(paramiko,~43ms)兜底,SDK 自动选择 | readiness 用 `wait_for_ready`(探 agent `/health`) |
| F11 | 库调用路径**不带** CLI 的 `sg kvm` 自动 re-exec;服务用户需在 `kvm` 组 | 部署要求 + 启动预检项 |
| F12 | VM 间 TAP→TAP 转发全局 drop,无共享 L2;guest 无法访问宿主私网段以外资源受 nftables 控制 | 会话间隔离由 SDK 保证 |
| F13 |【实测】init 先起 guest-agent 再配 SSH:`wait_for_ready`(vsock)**不担保 sshd 就绪**;且 init 的运行期 `ssh-keygen` 依赖 boot 后熵,crng 未就绪时 getrandom 阻塞不定长(实测卡数分钟,sshd 一直不起) | host key 改为镜像烘焙期 `ssh-keygen -A` 生成(init 守卫自动跳过);SSH argv 带 ConnectionAttempts 兜毫秒级残余窗口 |
| F14 |【源码+实测】vsock 通道 VM 创建时 `_should_setup_tap_connectivity_for_create` 为假 → **host→guest 路由(`<ip>/32 dev tap`)与出网 NAT 整体跳过**(tap 上仅 /32 地址,无连通路由,宿主发包走默认网关);SDK 仅在自家 SSH 路径经 `ensure_network_connectivity` 懒装配。另:`vm.wait_for_ssh()` 的 paramiko 轮询对 OpenSSH 10 guest(trixie)不可靠(实测 banner 读取失败),裸 TCP/OpenSSH 二进制正常 | provider 在 shell_exec_argv 首调时经公开 API `SmolVMManager.ensure_network_connectivity()` 装配(顺带获得出网 NAT),**不走** wait_for_ssh;连接重试交给 OpenSSH(ConnectionAttempts);guest 出网能力在首次 Bash 调用前不可用 |
| F15 |【实测,Phase B】vsock 通道非持久:每次 `run()` 走 UDS `CONNECT <port>` 新建连接;`from_id` 重连句柄的通道**不担保立刻就绪**,且高 churn(多 VM 起停)下 CONNECT 握手偶发空 ack(`SmolVMError: vsock CONNECT handshake failed: ''`)——两者均发生在命令送达 guest **之前**。L3 全套连跑 ~40% 复现,单跑不现 | adopt 探针前加 `wait_for_ready(ready_timeout)`(已就绪零开销);`execute()` 对连接建立阶段错误白名单有界重试(≤2 次、0.2s 退避,命令未送达故安全);非连接期错误可能已有副作用,**禁止重试** |
| F16 |【源码+实测,Phase C 后】`SmolVM.run()`/`upload_file`/`download_file` 对非 RUNNING VM 均抛 `SmolVMError`(`run()` 是 `_refresh_info()` 后的内联前置断言 `if status != RUNNING: raise`;文件传输经 `_ensure_control_for_operation` 内的 RUNNING 门,facade.py):`pause()` 冻结的 VM 上任何命令**立即抛**,不自动 resume | pause 态在三个子系统间须共识一个真相源(`manifest.paused`):① 健康巡检**豁免** paused(否则 idle_pause 冻结的 VM 会被 15s 探针连败 3 次误判杀重建,~45s 内清场,永远走不到 idle_evict 快照持久化档);② 消息路径拿到活沙箱**先 resume 再用**(否则 execute 打冻结 VM → exit 137,且 paused 永不复位);③ `pause()`/`resume()` 成对维护该标志。resume 复位后健康巡检恢复正常探活,死 VM 仍被抓 → 兜底自愈 |

## 3. 关键决策(决策记录)

| # | 决策 | 选择 | 理由 |
| --- | --- | --- | --- |
| D1 | SDK 采用策略 | Adopt `smolvm==0.0.25`(锁版本)+ Extend 服务层 | SDK 覆盖单 VM 生命周期;0.0.x 演进剧烈,升级必须显式走任务并重跑门控测试 |
| D2 | 隔离底座 | Firecracker backend(Linux/KVM);macOS 开发可手动 `backend=qemu` 但非验收范围 | 生产目标是 Linux;Firecracker 是隔离谱系最强端【业界】 |
| D3 | 镜像策略 | `DockerRootfsBuilder` + hagent 自有 Dockerfile(python3 + rg + bash + git + **smolvm-guest-agent + sshd**),内容指纹缓存;所有 VM `disk_mode="isolated"` CoW 派生 | F7;镜像物料与 docker provider 的 Dockerfile 同源维护;构建依赖宿主 Docker(现状已有,不新增依赖) |
| D4 | 命令通道 | vsock 优先、SSH 兜底(SDK 自动);**例外:Bash 工具走 SSH argv**——BashRuntime 依赖宿主子进程做流式输出/超时杀进程组/后台任务,vsock `run()` 无流式(F4),故 `SandboxShellProvider` 分派到 `HagentSmolVMSandbox.shell_exec_argv()` 自建 ssh 命令(ControlMaster 复用连接;实现期发现的 plan A5 盲区,e2e 曾以 `_container` AttributeError 暴露) | F10;vsock 1ms 级 RTT 优于 docker exec |
| D5 | 默认切换 | server 侧 `HAGENT_SANDBOX_KIND` 默认值改 `smolvm`;启动预检失败按 `smolvm → docker → none` 降级并 WARNING;`HAGENT_SANDBOX_REQUIRE=smolvm` 时预检失败直接启动失败。CLI `demo` 默认仍 `none`(开发权宜,与现状一致) | 复刻 M6 的 runsc→runc 降级哲学:开箱能跑,生产用 env 强约束 |
| D6 | 会话↔VM 映射 | **会话绑数据,不绑 VM**:VM 可置换,病 VM 杀掉重建,会话物料经 files API 重灌 | Manus 哲学【业界】;与 hagent 现有 files 路由架构契合 |
| D7 | 调度与准入 | `AdmissionLedger`(provider 无关):内存**不超卖**(可用 = 宿主内存 − 预留 25% − Σ运行中与创建中 VM 配额),CPU 按 2x 超卖计;不足时快速失败(API 503 + Retry-After),不排队 | Firecracker 不归还 guest 内存,按配额满额计【业界:hocus.dev】;fly.io 快速失败语义 + E2B in-progress 占位【业界】 |
| D8 | 池策略 | 保留 `SandboxPool` acquire/release/GC 接口;改造:创建中占位防并发超放、认领即异步补货、池空退化冷启动、补货连续失败熔断;默认深度 0(纯按需),预热由 `HAGENT_SANDBOX_PREWARM` 显式开启 | 冷启动 749ms 已够快,P0 不押池;Daytona #3289(补货无熔断打爆宿主)教训【业界】 |
| D9 | 孤儿治理 | 清场 + 收养混合:启动对账时**活跃 session 的 RUNNING VM 收养重连(`from_id`),其余清场(`delete()`)**;60s 周期 reaper 双向对账兜底;vm_id 命名约定 `hagent-<sid8>-<rand6>` 即对账键 | E2B startupreclaim(清场)+ Nomad restore(收养)的组合;`from_id` 让对话型产品重启不杀活跃会话;containerd #3971(仅启动清扫不够)教训【业界】 |
| D10 | 失败回收 | 健康巡检(宿主轮询,连续 3 败)→ 杀掉重建新 VM、复用 session;启动失败重试 2 次、每次先走完整 `delete()`;不修复病 VM | Manus 重建哲学 + E2B checks 模式【业界】 |
| D11 | 日志与审计 | 三流:①命令审计 JSONL 记在 `HagentSmolVMSandbox` 调用点(宿主侧);②VM 运行日志复用 SDK 的 `data_dir/{vm_id}.log`;③生命周期事件表落 hagent SQLite。指标:`/proc/<pid>` 采样(5–10s) | F4(SDK callback 在 async 路径不触发,且 guest 内可关);无 cgroup 可读(F9),`/proc` 够单机运营 |
| D12 | 线程安全 | `HagentSmolVMSandbox` 内 per-sandbox `RLock` 串行化 execute/upload/download | F4;子代理并行工具调用会并发打同一沙箱 |
| D13 | pause 语义 | 沿用现有池 GC 两级降档(idle→`pause()`→evict);SmolVM `pause()` = FC vCPU 冻结、内存驻留(不释放内存配额,账本仍满额计);DISK 快照式持久化(释放内存)已于 Phase C 落地——idle_evict 阈值优先快照休眠(snapshotted),失败才退回破坏性驱逐 | F 快照约束;账本正确性优先 |
| D14 | 网络出口 | 默认开放(与 docker provider 对齐);`HAGENT_SMOLVM_ALLOWED_DOMAINS` opt-in 白名单(逗号分隔,启用即 fail-closed) | F6;秘密不入沙箱的现状不变(safe env 集合沿用) |
| D15 | 状态机 | sessions 表加 `sandbox_state` / `sandbox_desired_state` / `last_activity_at` 列;长操作幂等分步 | Daytona 双字段对账模式【业界】;hagent DB 是 session 层事实源,SmolVM DB 是 VM 层事实源 |

## 4. Architecture

### 4.1 分层

```text
┌─ hagent server(FastAPI lifespan)────────────────────────────┐
│ SessionManager(现有,微改:状态机写入 + supervisor 挂接)      │
│   ├─ AdmissionLedger      sandbox/ledger.py(新,provider 无关)│
│   └─ SandboxPool          sandbox/pool.py(改造)              │
│ SandboxSupervisor         sandbox/supervisor.py(新,通用骨架) │
│   ├─ startup_reclaim()    启动清场/收养(调 Reconciler)        │
│   ├─ reaper_loop()        60s 双向对账                        │
│   ├─ health_loop()        10–20s 探活 → 杀重建(Phase B)      │
│   └─ evictor 由现有 pool.start_gc_loop 承担(idle→pause→evict)│
├─ sandbox/smolvm/(新 provider 包)────────────────────────────┤
│ image.py       Dockerfile 烘焙(DockerRootfsBuilder 封装+缓存) │
│ lifecycle.py   VMConfig 装配 + start/ready + 重试 + 异常映射   │
│ sandbox.py     HagentSmolVMSandbox(协议适配 + 锁 + 审计点)    │
│ reconciler.py  SmolVM 侧对账实现(实现 supervisor 的协议)      │
│ audit.py       审计 JSONL + 生命周期事件(Phase B)             │
├─ smolvm SDK(adopt,锁 0.0.25)───────────────────────────────┤
│ facade / SmolVMManager / reconcile / TAP+nftables / SQLite    │
└─ Firecracker + KVM ──────────────────────────────────────────┘
```

### 4.2 新增/修改模块

| 路径 | 职责 |
| --- | --- |
| `sandbox/smolvm/__init__.py` | 导出 `HagentSmolVMSandbox`、`preflight()` |
| `sandbox/smolvm/image.py` | `HAGENT_DOCKERFILE` 常量(python3.12-slim 基座 + rg/git/bash + guest-agent 二进制 COPY + sshd)、`ensure_boot_image() -> BootImage`(DockerRootfsBuilder + 指纹缓存,构建一次全局复用) |
| `sandbox/smolvm/lifecycle.py` | `SmolVMLifecycle`:`start()`(VMConfig 装配 → `SmolVM.from_image` → `start` + `wait_for_ready` + python3 探针;失败 `delete()` 后重试 ≤2)、`stop()`(stop+delete+close)、`pause()/resume()`、`adopt(vm_id)`(`from_id` + 活性校验);SDK 异常 → hagent 异常映射 |
| `sandbox/smolvm/sandbox.py` | `HagentSmolVMSandbox(BaseSandbox, HagentSandboxProtocol)`:`execute()`(RLock + `vm.run(shell="raw")` → `ExecuteResponse`;超时映射 exit_code=124;输出 stderr 前缀/截断逻辑与 docker provider byte-equal)、`upload_files`/`download_files`(tempfile 桥接 SDK 路径 API)、`id`(`smolvm-<vm_id>`)、`kind`(SMOLVM)、`manifest`(复用 `SandboxManifest`,`container_id` 字段存 vm_id)、审计埋点 |
| `sandbox/smolvm/reconciler.py` | `SmolVMReconciler`:枚举 SmolVM DB(`list_vms`)× hagent sessions × `/proc` 活性,输出收养/清场/标失联三类动作;`reap_errors()`(先 `SmolVMManager.reconcile()` 再对 ERROR 行 `delete()`) |
| `sandbox/ledger.py` | `AdmissionLedger`:`try_reserve(mem_mib, vcpus) -> Reservation`(含创建中占位)/`commit`/`release`;宿主容量探测 + env 覆盖;不足抛 `CapacityExceeded` |
| `sandbox/supervisor.py` | `SandboxSupervisor`:持 `Reconciler` 协议对象;`startup_reclaim()` 同步跑一次;`reaper_loop()` 后台线程 60s;清理失败计数、连续失败 ERROR 日志告警;`shutdown()` 幂等 |
| `sandbox/pool.py`(改) | acquire 走 ledger 占位;释放/驱逐归还额度;认领后异步补货至 min;补货连续 3 败熔断(冷却 300s);池空且 ledger 有余量 → 冷启动 |
| `sandbox/protocol.py`(改) | `SandboxKind` 加 `SMOLVM = "smolvm"` |
| `server/sessions.py`(改) | migration 加列:`sandbox_state TEXT`、`sandbox_desired_state TEXT`、`last_activity_at REAL`;`touch_activity(sid)` |
| `server/manager.py`(改) | create/delete 写状态机;`touch_activity` 挂到消息路由;失联 VM 的 session 重建入口 |
| `server/app.py`(改) | 工厂函数 `_build_smolvm_pool()`;lifespan 挂 supervisor(startup_reclaim → reaper);shutdown 顺序:supervisor → pool |
| `config.py`(改) | `preflight_sandbox_kind()`:按 D5 降级链探测(kvm 可读写 + firecracker 二进制 + sudoers 检查 + smolvm 可导入) |
| `cli.py`(改) | `--sandbox smolvm`;`hagent sandbox {ls,stop,logs}` 识别 smolvm(ls 走 SDK `list_vms` 过滤 `hagent-` 前缀,logs 读 `data_dir/{vm_id}.log`) |

### 4.3 会话状态机(sessions 表)

```text
 creating ──► running ──► paused ──► running(resume)
    │            │           │    └──► snapshotted ──► running(从快照恢复,Phase C)
    ▼            ▼           ▼
  error       orphaned    evicted ──► closed
 (重试耗尽)   (VM 失联,待重建)
```

| 转移 | 触发 | 动作 |
| --- | --- | --- |
| → creating | `POST /sessions` | ledger 占位 → pool.acquire(池空则 lifecycle.start) |
| creating → running | readiness 过 | 写 manifest 元数据 + `sandbox_state=running` |
| creating → error | 重试 2 次耗尽 | ledger 释放;session 删除;API 5xx |
| running → paused | pool GC:idle ≥ `idle_pause_seconds` | `vm.pause()`(内存驻留,账本不释放) |
| paused → running | 新消息到达 | `vm.resume()` + touch |
| paused → snapshotted | pool GC:idle ≥ `idle_evict_seconds`(Phase C,持久化可用时优先于驱逐) | DISK 快照 → `stop+delete+close`;ledger 释放;快照 id 落 sessions 表;SSE `sandbox.snapshotted` |
| snapshotted → running | 新消息到达 | `from_snapshot(resume_vm=True)` 回原 vm_id + readiness;恢复失败回退 orphaned 全新重建;SSE `sandbox.restored` |
| paused → evicted | pool GC:idle ≥ `idle_evict_seconds`(持久化关闭/失败) 或 max_lifetime 到 | `stop+delete+close`;ledger 释放;SSE `sandbox.evicted` |
| running → orphaned | reaper/health:VM 进程消失或连续 3 次探活失败 | 残留资源清理;session 保留,首次新消息触发重建(新 VM + 重灌 files) |
| any → closed | `DELETE /sessions` | 全链清理 |

### 4.4 启动对账矩阵(startup_reclaim)

对账键:vm_id 前缀 `hagent-<sid8>-<rand6>`。枚举 SmolVM DB 全部 `hagent-` VM × hagent sessions:

| SmolVM DB 状态 | hagent session 状态 | 动作 |
| --- | --- | --- |
| RUNNING(pid 活) | active session 匹配 | **收养**:`from_id` 重建句柄 + readiness 探针;探针败则清场+标 orphaned |
| RUNNING(pid 活) | 无匹配 / session 已删 | **清场**:`stop+delete` |
| RUNNING/PAUSED(pid 死) | 任意 | `reconcile()` 降 ERROR → `delete()`;session 标 orphaned |
| CREATED / STOPPED / ERROR | 任意 | `delete()` 清残留 |
| (无 VM) | session 标 running | session 标 orphaned(数据仍在,等用户回来重建) |

周期 reaper(60s)跑同一矩阵的增量版 + `reap_errors()`;单次清理失败记数,连续 3 次同对象失败升 ERROR 日志(不静默重试)。

**无主 VM 两轮复核(实现期补,生产事故教训)**:`pool.acquire` 的 VM 启动窗口(1–2s)里已在 SmolVM DB、却未进池保护集、session 元数据未写——周期轮扫到会误判「无主活 VM」清场(实测:池发出死句柄 → 上传 500)。故周期轮对无主活 VM 与 CREATED/STOPPED/ERROR 残留**首见缓刑、连续两轮无主才清**;pid 死是确证故障不缓刑;启动对账首轮维持立即清场(彼时本进程无创建中 VM)。副作用:与 dev server 并行跑门控测试时,短命测试 VM(<60s)不再被 server reaper 误杀。

**保护集(实现期补,e2e 教训)**:池在册(warm idle + leased)VM 经 `pool.live_vm_ids()` 注入 reconciler,一律不参与对账——暖池 VM 天然无 session 不是无主(reaper 清场会让池发出死句柄 → upload 500);已租借 VM 已被本进程管理,重复收养会造成双句柄。启动对账时池为空、保护集为空,矩阵行为不变。

### 4.5 审计与事件 schema(Phase B)

- 命令审计 JSONL(`.logs/sandbox/audit-<sid>.jsonl`,append-only):`{ts, session_id, vm_id, action: exec|upload|download, command|path, exit_code, duration_ms, bytes_out}`。
- 生命周期事件表(hagent SQLite `sandbox_events`):`{ts, session_id, vm_id, event, detail_json}`;event ∈ created/adopted/paused/resumed/evicted/orphaned/health_fail/reaped/create_failed。
- 指标:supervisor 内 5–10s 读 `/proc/<pid>/stat|statm` 记 CPU/RSS 到事件表(`event=metrics`,可降采样)。

## 5. 配置面(env)

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `HAGENT_SANDBOX_KIND` | **`smolvm`**(server;CLI demo 仍 `none`) | D5 降级链:smolvm → docker → none |
| `HAGENT_SANDBOX_REQUIRE` | 空 | 设 `smolvm` 时预检失败直接启动失败 |
| `HAGENT_SMOLVM_VCPUS` / `_MEMORY_MIB` / `_DISK_MIB` | 2 / 2048 / 4096 | 每 VM 配额(VMConfig) |
| `HAGENT_SMOLVM_MEM_RESERVE_PCT` | 25 | ledger 宿主内存预留 |
| `HAGENT_SMOLVM_CPU_OVERCOMMIT` | 2 | ledger CPU 超卖比 |
| `HAGENT_SMOLVM_ALLOWED_DOMAINS` | 空(不启用) | 逗号分隔;设置即 fail-closed 白名单 |
| `HAGENT_SMOLVM_MAX_LIFETIME_SECONDS` | 86400 | 沙箱绝对寿命上限 |
| `HAGENT_SANDBOX_POOL_MIN/MAX`、`HAGENT_SANDBOX_PREWARM`、`HAGENT_SANDBOX_REUSE` | 沿用 | 语义不变;REUSE 对 smolvm 同样是清 `/workspace` 后回池 |
| `HAGENT_SANDBOX_RECYCLE_SECONDS` | 3600 | Phase C:warm idle 超龄回收(防漂移;只针对池内闲置实例) |
| `HAGENT_SMOLVM_SNAPSHOT_PERSIST` | 开(`0` 关) | Phase C:idle_evict 阈值优先 DISK 快照休眠,替代破坏性驱逐 |
| `SMOLVM_DATA_DIR` / `SMOLVM_DATABASE_URL` | SDK 默认 | 透传;Postgres 切换属部署项(Phase C 文档化) |

idle 双档沿用 pool 现有 `idle_pause_seconds=300` / `idle_evict_seconds=1800`。**活跃度以 session API 交互计**(消息/工具调用 touch),SSE 长连接本身不算(防机械心跳误刷,Daytona #4805 教训【业界】)。

## 6. 错误处理分层

| 层 | 故障 | 行为 |
| --- | --- | --- |
| 预检 | kvm 不可读写 / firecracker 缺失 / sudoers 未配 / smolvm 未装 | 按 D5 降级 + WARNING(逐项打印缺什么、给修复命令);`HAGENT_SANDBOX_REQUIRE=smolvm` 时 RuntimeError |
| 镜像 | Docker 不可用 / 构建失败 | 启动期失败(与 docker provider `ensure_image` 语义一致,不静默降级) |
| 创建 | `start`/`wait_for_ready` 失败或超时 | `delete()` 全清理后重试,≤2 次;耗尽 → ledger 释放 + session 删除 + 5xx;事件表记 create_failed |
| 准入 | `CapacityExceeded` / `PoolExhausted` | API 503 + `Retry-After`(与现有 pool 超时语义合并) |
| 单次 exec | `OperationTimeoutError` | `ExecuteResponse(output="command timed out after {n}s", exit_code=124)`;不污染会话 |
| 单次 exec | 通道断连 / SmolVMError | `ExecuteResponse(output="sandbox exec failed: {exc}", exit_code=137)`(对齐 docker provider 现有约定) |
| 文件 | 上传/下载失败 | `FileUploadResponse/FileDownloadResponse(error=...)` 部分成功语义,对齐 docker provider |
| 健康 | 连续 3 次探活失败 / 进程死(**paused 态豁免探针**,见 F16) | 杀重建:清残留 → session 标 orphaned → 首条新消息触发新 VM + 重灌 files;artifacts 尽力 `download_files` 抢救(Phase B) |
| server 崩溃 | — | VM 照跑(F1);重启走 §4.4 对账矩阵 |

## 7. LLM 视角语义不变(硬性)

与 M6 spec §5.5 同一契约:Bash / Read / Write / Edit / Grep / Glob 在 smolvm 模式下的 schema、输出格式、错误信息与 host / docker 模式 byte-equal(除路径前缀);`tests/sandbox/test_tool_parity.py` 扩展为三方对照(host / docker / smolvm)。workspace 仍为 `/workspace`(镜像内建目录,Firecracker 无 bind-mount,文件进出全走 upload/download——与 D8「仅上传下载」决策天然一致)。base prompt 的 sandbox 段无需改动(`_SANDBOX_BACKEND_NAMES` 加 `HagentSmolVMSandbox` 即可)。

## 8. Testing

分层沿用 M6 模式:

| 层 | 标记 | 内容 |
| --- | --- | --- |
| L1 单元 | 默认跑 | image(Dockerfile 内容断言 + builder mock)、lifecycle(SDK mock:重试/异常映射/adopt)、sandbox(锁并发、tempfile 桥、超时映射、输出格式)、ledger(占位/提交/释放/耗尽)、pool 改造(占位补货熔断)、reconciler(对账矩阵全 8 分支表驱动)、supervisor(reclaim/reaper 循环,mock reconciler) |
| L2 契约 | 默认跑 | fake SmolVM SDK 过 `BaseSandbox` 全套 + protocol 契约(现有 test_protocol_types 扩展) |
| L3 集成 | `@pytest.mark.smolvm` + `HAGENT_TEST_SMOLVM=1` | 真 Firecracker:start/exec/upload/download/timeout/pause/resume/close;tool_parity 真跑;**孤儿治理端到端**(kill -9 server 进程模拟崩溃 → 重启 → 断言收养/清场);server 路由集成 |
| L5 e2e | `ANTHROPIC_API_KEY` + `HAGENT_TEST_SMOLVM=1` | `python -m hagent --sandbox smolvm demo` 真实模型跑通写文件任务 |

**验收标准**(全部满足才可切默认):

1. `pytest -v`(默认套件)全绿,含新增 L1/L2。
2. `HAGENT_TEST_SMOLVM=1 pytest -m smolvm -v` 全绿(本机 WSL2 已具备条件)。
3. `HAGENT_TEST_DOCKER=1 pytest -m docker -v` 全绿(docker provider 无回归)。
4. tool_parity 三方对照(host/docker/smolvm)全绿。
5. 孤儿治理 L3:模拟崩溃重启后,活跃会话 VM 被收养且对话可继续;残留 VM 被清场;`smolvm sandbox list` 无 `hagent-` 前缀泄漏。
6. 预检降级链验证:无 kvm 环境(mock)下 server 起为 docker,并有 WARNING。
7. `./scripts/curl_smoke.sh` 通过;前端建 session → 上传 → 对话链路人工验证。
8. spec/plan 入仓,`CLAUDE.md`/`AGENTS.md` 同步(见 §11)。

**性能 SLO**(非验收门槛):冷启动(create→ready)WSL2 < 1.5s;exec RTT(vsock)< 20ms;收养单 VM < 200ms;reaper 单轮 < 5s(50 VM 规模)。

## 9. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| smolvm 0.0.x API 破坏性变更(guest agent 正 Python→Rust 重写) | provider 升级即碎 | 锁版本;L3 门控测试是升级门;lifecycle 层收敛全部 SDK 调用点 |
| 无 cgroup/jailer(F9) | 单 VM 可吃满宿主 CPU;sudoers 面宽 | vcpus 配额 + ledger 控总量;记录部署要求「宿主不混跑敏感负载」;jailer/cgroup 补全列 Phase C 后续 |
| WSL2 `/dev/kvm` 权限随重启重置 | 本地开发预检失败 | 预检给出修复命令;部署文档写 wsl.conf boot 固化;降级链保底 |
| ext4 上派生退化为稀疏拷贝(F5) | 创建延迟随镜像增大 | base 镜像控制体积;生产宿主建议 btrfs/XFS 数据盘(文档) |
| Celesto AI 存续风险 | 上游停维 | protocol 抽象层保证可退回 docker;镜像 Dockerfile 与审计/账本/supervisor 均 provider 无关可迁移 |
| pause 不释放内存(D13) | paused 沙箱占满账本 | `idle_evict_seconds` 兜底驱逐;DISK 快照持久化(Phase C)释放配额 |

## 10. Out of scope(本 spec 不做)

多机调度(NodeClient 接缝仅预留)、Postgres 状态库切换(仅文档)、golden snapshot 内存态恢复、CAP_NET_ADMIN 快路径部署、jailer/cgroup 加固、GPU、多租户配额计费、CubeSandbox provider、Web 前端 sandbox 管理 UI。

## 11. 文档同步清单

- `CLAUDE.md`:架构表 `sandbox/` 行补 smolvm;门控测试补 `HAGENT_TEST_SMOLVM=1 pytest -m smolvm -v`;「Host / Sandbox 双模式」段落更新默认 provider 说明。
- `AGENTS.md`:sandbox 相关 PR 验证命令补 smolvm 门控行。
- `docs/deploy/smolvm.md`(新):宿主要求(KVM、kvm 组、sudoers、Docker)、WSL2 固化、btrfs/XFS 建议、`smolvm setup` 步骤。
- `prompts/hagent_base.zh.md`:无需改动(sandbox 段按 `_SANDBOX_BACKEND_NAMES` 动态注入,语义不变)。
