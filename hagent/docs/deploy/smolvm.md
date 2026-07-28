# SmolVM Sandbox 部署手册(Firecracker microVM)

hagent server 默认 sandbox provider(`HAGENT_SANDBOX_KIND=smolvm`)。本文覆盖宿主要求、WSL2 固化、文件系统与状态库选型、systemd 样例、配置面与运维排障。设计契约见 `docs/specs/2026-07-06-smolvm-sandbox-design.md`。

## 1. 宿主要求

| 项 | 要求 | 预检失败时的修复 |
| --- | --- | --- |
| KVM | `/dev/kvm` 存在且服务用户可读写 | `sudo usermod -aG kvm <user>` 后**重新登录**;WSL2 见 §2 |
| kvm 组生效 | **库调用路径不带 CLI 的 `sg kvm` 自动 re-exec(spec F11)** | 旧登录会话拿不到新补充组:重登录,或临时 `sg kvm -c "…"` 包住启动命令 |
| firecracker | 二进制在 PATH | `smolvm setup` |
| sudoers | `/etc/sudoers.d/smolvm-runtime-<user>`(TAP/nftables 需要) | `smolvm setup` |
| smolvm SDK | `smolvm==0.0.25`(**锁版本**,升级走显式任务并重跑门控测试) | `pip install smolvm==0.0.25` |
| Docker | 镜像烘焙(DockerRootfsBuilder:Dockerfile→ext4)依赖宿主 Docker | 安装 docker 并保证 daemon 可达 |

启动预检(`preflight_sandbox_kind()`)逐项探测,失败按 `smolvm → docker → none` 降级并打 WARNING;生产环境设 `HAGENT_SANDBOX_REQUIRE=smolvm` 让预检失败直接拒绝启动,不静默降级。

镜像(golden base)在 **server 启动期**烘焙(指纹缓存,Dockerfile/物料不变时秒过;首次分钟级);构建失败即启动失败——这是刻意的,与 docker provider `ensure_image` 语义一致。

## 2. WSL2 固化

两个坑(本机踩过,均已验证):

1. **`/dev/kvm` 权限随 WSL 重启重置**(root:kvm 660 → 重启后回 root:root 600)。固化进 `/etc/wsl.conf`:

   ```ini
   [boot]
   command = chgrp kvm /dev/kvm && chmod 660 /dev/kvm
   ```

2. **kvm 组不在当前登录会话生效**:`/etc/group` 已有但旧 shell 拿不到。重开终端(重登录),或用 `sg kvm -c "…"` 包住 server/测试命令:

   ```bash
   sg kvm -c "bash -lc 'set -a && source .env && set +a && HAGENT_SANDBOX_KIND=smolvm exec .venv/bin/python -m uvicorn hagent.server.app:create_app --factory --host 0.0.0.0 --port 8000'"
   ```

另注意:仓库根 `.env` 若显式 `export HAGENT_SANDBOX_KIND=docker`,会盖过 server 的 smolvm 默认(预检尊重显式请求、不告警)——本机启动时用命令行 env 显式压回 `smolvm`,或改 `.env`。

## 3. 文件系统与磁盘

- 所有 VM 以 `disk_mode="isolated"` 从共享 base rootfs CoW 派生(spec F5)。**btrfs / XFS 数据盘强烈建议**:reflink 派生瞬时完成;ext4 退化为稀疏拷贝,创建延迟随镜像体积线性增长(Alpine base 实占 ~84MB 可忍,base 越大越痛)。
- SDK 数据目录默认 `~/.local/state/smolvm/`(`SMOLVM_DATA_DIR` 可移):VM 磁盘、快照、`{vm_id}.log` 运行日志都在这里,放到大盘。
- DISK 快照持久化(Task C2)会在 idle 沙箱身上产生快照文件:恢复即清、session 删除即清、被新快照取代即清,常态无泄漏;`smolvm sandbox snapshot list` 可人工核对(`snapshot` 是 `sandbox` 的子命令)。

## 4. 状态库:SQLite → Postgres(`SMOLVM_DATABASE_URL`)

SDK 状态库默认 SQLite(`~/.local/state/smolvm/smolvm.db`,未开 WAL、EXCLUSIVE 事务,spec F2)。单机小并发够用;并发起停 VM 频繁时(大池 + 高 churn)锁竞争会放大,设:

```bash
export SMOLVM_DATABASE_URL="postgresql://smolvm:…@127.0.0.1:5432/smolvm"
```

切 Postgres(hagent 透传不加工)。注意:**hagent 自己的 sessions/sandbox_events 库仍是 hagent SQLite**(`HAGENT_SESSIONS_DB`),两者独立;此处只切 SmolVM 的 VM 层事实源。

多进程共享同一 SmolVM DB 时(如 dev server + 并行门控测试),server 的 reaper 会把别进程的 `hagent-` VM 当「无主活 VM」对账——两轮复核缓解了短命 VM 误杀,但稳妥做法仍是**停 server 再跑门控测试**。

## 5. systemd unit 样例

```ini
[Unit]
Description=Hagent Agent Server (smolvm sandbox)
After=network-online.target docker.service
Wants=network-online.target

[Service]
User=hagent
WorkingDirectory=/opt/hagent
Environment=HAGENT_SANDBOX_KIND=smolvm
Environment=HAGENT_SANDBOX_REQUIRE=smolvm
# kvm 补充组:库调用路径没有 sg kvm 自动 re-exec(spec F11)
SupplementaryGroups=kvm
# 快路径(可选):给进程 CAP_NET_ADMIN 后,TAP/nftables 装配可不经 sudo,
# 减少 sudoers 面;保守部署可去掉此行,走 smolvm setup 的 sudoers 方案
AmbientCapabilities=CAP_NET_ADMIN
ExecStart=/opt/hagent/.venv/bin/python -m uvicorn hagent.server.app:create_app --factory --host 0.0.0.0 --port 8000
# graceful drain:拒新建 → 存量 pause 保留(重启后对账收养,会话不丢)
KillSignal=SIGTERM
TimeoutStopSec=60
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

宿主纪律(spec F9 已知缺口):SDK 无 cgroup 限额、无 jailer,单 VM 可吃满宿主 CPU——**沙箱宿主不混跑敏感负载**,总量靠 `AdmissionLedger`(内存不超卖、CPU 2x 超卖)控制。

## 6. 配置面(env)

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `HAGENT_SANDBOX_KIND` | `smolvm`(server) | 降级链 smolvm → docker → none |
| `HAGENT_SANDBOX_REQUIRE` | 空 | `smolvm` 时预检失败拒绝启动 |
| `HAGENT_SMOLVM_VCPUS` / `_MEMORY_MIB` / `_DISK_MIB` | 2 / 2048 / 4096 | 每 VM 配额 |
| `HAGENT_SMOLVM_MEM_RESERVE_PCT` | 25 | 账本的宿主内存预留 |
| `HAGENT_SMOLVM_CPU_OVERCOMMIT` | 2 | 账本 CPU 超卖比 |
| `HAGENT_SMOLVM_MAX_LIFETIME_SECONDS` | 86400 | 沙箱绝对寿命(到期驱逐,活跃也拆) |
| `HAGENT_SANDBOX_POOL_MIN` / `_MAX` | 1 / 4 | 池深度 |
| `HAGENT_SANDBOX_PREWARM` | 关 | 启动即预热 min 只 warm VM |
| `HAGENT_SANDBOX_RECYCLE_SECONDS` | 3600 | warm idle 超龄回收(防漂移,Task C1) |
| `HAGENT_SMOLVM_SNAPSHOT_PERSIST` | 开 | idle 驱逐前先 DISK 快照休眠(Task C2);`0` 退回纯驱逐 |
| `HAGENT_SMOLVM_ALLOWED_DOMAINS` | 空=不启用 | 出口白名单,见 §7 |
| `HAGENT_SANDBOX_AUDIT_DIR` | `.logs/sandbox` | 命令审计 JSONL 目录 |
| `SMOLVM_DATA_DIR` / `SMOLVM_DATABASE_URL` | SDK 默认 | 透传,见 §3/§4 |

idle 两级降档沿用池默认:300s 无 API 交互 → pause(内存驻留,健康巡检豁免冻结 VM);1800s → DISK 快照休眠(或驱逐)。paused 会话收到新消息时消息路径自动 resume。活跃度只认消息/工具级 API 交互,SSE 长连不续期。

## 7. 出口白名单(`HAGENT_SMOLVM_ALLOWED_DOMAINS`)

```bash
export HAGENT_SMOLVM_ALLOWED_DOMAINS="pypi.org,files.pythonhosted.org,github.com"
```

逗号分隔**裸主机名**(带路径/凭据的 URL 会被 SDK 校验拒绝)。设置即 fail-closed:白名单外全拒。不设置(默认)为全放行,与 docker provider 一致。

**IP 固化局限(spec F6,接受后再启用)**:域名在 **VM 创建时**由宿主解析一次,IP 钉进 per-TAP nftables;CDN 轮换 IP、DNS 变更后,已存在的 VM 会开始误伤(白名单内域名连不通)。长寿沙箱 + CDN 域名的组合慎用;`HAGENT_SMOLVM_MAX_LIFETIME_SECONDS` 的寿命上限天然缓解。仅 Firecracker(TAP)路径生效。

## 8. 运维与排障

```bash
python -m hagent sandbox ls            # 容器 + smolvm VM(hagent- 前缀即本项目)
python -m hagent sandbox stop <vm_id>  # 全拆(stop+delete+close)
python -m hagent sandbox logs <vm_id>  # 读 SMOLVM_DATA_DIR/{vm_id}.log
```

- **审计三流**:命令 JSONL(`.logs/sandbox/audit-<sid>.jsonl`)、VM 运行日志(SDK data_dir)、生命周期事件表(hagent SQLite `sandbox_events`,含 metrics 采样)。
- **孤儿治理**:server 崩溃 VM 照跑;重启时启动对账收养活跃会话 VM、清场无主残留;60s reaper 周期兜底(无主 VM 两轮复核防创建窗口误杀)。`smolvm sandbox list` 里不应有无主 `hagent-` 前缀 VM 长存。
- **健康巡检**:15s 探活,连续 3 败杀重建(session 标 orphaned,首条新消息重建 + files 重灌)。
- **快照休眠**:idle 会话的 VM 被替换为 DISK 快照(`sandbox_events` 里 `snapshotted`/`restored`);下一条消息自动恢复,恢复失败自动回退全新重建。
- 典型故障:`Permission denied /dev/kvm` → §1/§2;`vsock CONNECT handshake failed` 偶发 → 连接期已有界重试(spec F15),持续出现查宿主负载;上传 500 + 池发死句柄 → 检查是否有别进程共享 SmolVM DB(§4)。
