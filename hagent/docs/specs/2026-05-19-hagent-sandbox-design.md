# Hagent Sandbox 设计稿（2026-05-19）

## 0. 元信息

- **状态**：草稿（待 Plan 拆分）
- **作者**：Claude Code（brainstorming 会话产物，与项目作者协作）
- **依赖 deepagents 版本**：`0.6.x`（实际安装在 `.venv/lib/python3.12/site-packages/deepagents/`）
- **相关历史文档**：
  - 取代 `docs/plans/2026-05-12-plan-5-docker-backend-and-swap.md` 里基于 deepagents 0.5.x + shim JSON-RPC 的早期 DockerBackend 草稿（本设计弃用 shim，改走 deepagents `BaseSandbox` + `docker exec/cp`）。
  - 与 `docs/specs/2026-05-12-hagent-backend-design.md` 的"Track B / Layer 2 容器化"承接，但接口契约以本稿为准。
- **设计目的**：为 Hagent M6 引入"可生产"的代码执行 sandbox 能力，本地走 gVisor + Docker，预留托管供应商（首发 Daytona）适配槽位。

## 1. 背景与目标

Hagent 当前默认通过 `HagentLocalShellBackend`（继承 deepagents `LocalShellBackend`）把 LLM 给出的 bash / Python / 文件写入直接落在 host 用户空间。这对单人本地开发尚可，但：

1. LLM 误操作或 prompt injection 可导致 host 文件被覆盖、`.env`/`~/.ssh` 被读、`rm -rf` 误执行。
2. Agent Server（FastAPI / SSE）多用户共享同一进程，所有 session 共用 host fs，无法做到会话级文件隔离。
3. 长任务 / 大输出 / 后台进程在 host 里跑会污染主机环境。
4. Web 前端 `web/` 想给最终用户提供"AI 在云端干活"的体验，缺少可计费、可销毁的执行容器。

**目标（本设计稿覆盖）**：

- 引入统一 `HagentSandboxBackend` 抽象，对接 deepagents `SandboxBackendProtocol`。
- 本版实现：`HagentDockerSandbox`（本地 Docker，优先用 gVisor `runsc` runtime 增强隔离）。
- 本版预留：`HagentDaytonaSandbox`（基于 `langchain-daytona`，仅 stub + 抽象层兼容测试）。
- 把 Hagent 自研 Bash / Read / Write / Edit 工具桥接到 sandbox，**LLM 视角的工具 schema、输出格式与现状完全一致**。
- 在 Agent Server 侧增加 sandbox-aware 的 `SessionManager`，含 warm pool、idle GC、TTL 驱逐。
- 默认网络出口开放，secrets 留 host（不注入 sandbox）。
- 默认 sandbox 内 permission 放开（容器 + gVisor 即为信任边界），保留 opt-in 自定义 deny。

**非目标**：

- GPU、--gpus、CUDA 镜像支持。
- 复杂 egress 凭证注入代理（host-side proxy）。
- 自托管 Daytona 集群运维。
- 多供应商（E2B / Modal / AgentCore / Cloudflare Sandbox）的实际实现——本版只确认抽象层不绑死 Docker。
- Snapshot resume / 容器跨会话内容持久化（assistant-scoped sandbox）。
- Web 前端 sandbox 管理 UI（仅暴露后端 SSE 事件，UI 改造在另一个 plan）。

## 2. 关键决策（决策记录）

| # | 决策 | 选项 | 选择 | 理由 |
| --- | --- | --- | --- | --- |
| D1 | 目标使用场景 | 本地 / 自托管 / SaaS / 双路线 | 本地 + 托管双路线 | 笔记本 + WSL 跑 Docker 是当前主要工作环境；同时为 Agent Server 上线托管沙箱预留路径 |
| D2 | 托管供应商首选 | Daytona / E2B / Modal / 抽象 | Daytona（接口预留，本版不重点实现） | `langchain-daytona` 官方包成熟、最低价、snapshot/labels/TTL 完备 |
| D3 | 本地隔离路线 | Docker+BaseSandbox / microsandbox / bubblewrap / 多选 | Docker + BaseSandbox（gVisor 优先） | 跨 OS 一致（WSL / macOS / Linux）；与 deepagents `BaseSandbox` 自动获得 ls/read/grep/glob/edit 实现；安装成本低 |
| D4 | session ↔ sandbox 生命周期 | thread-scoped / assistant-scoped / 两支持 / 最简 | Thread-scoped + warm pool + idle GC | 与 deepagents 默认一致；适合 dev → 小规模多用户 |
| D5 | LLM 工具如何路由到 sandbox | Provider 抽象 / 切 deepagents 内置 / 双轨 / 仅 Bash | Provider 抽象 + sandbox-aware | 保留已对齐 Claude Code 的 schema 资产；改动集中在 provider 层 |
| D6 | 网络出口 + secrets | 开放+host / 开放+注入 / 断网+proxy / 可配置 | 默认出口 + secrets 留 host | 平衡可用性与安全；agent loop 跑 host，sandbox 只跑 LLM 给出的指令 |
| D7 | sandbox 内 permission 策略 | 默认 deny / 默认 allow / opt-in deny | 默认放开 + opt-in deny | 容器 + gVisor 即信任边界，host permission 在 sandbox 内多此一举 |
| D8 | host workspace 是否 bind-mount | 直接 mount / 仅上传下载 | 仅上传下载 | 贴近 BaseSandbox 模型；避免 host 文件被 LLM 误删；规避 gVisor 文件 IO 性能坑 |
| D9 | release 策略 | stop+rm / 复用 / 可配置 | 默认 stop+rm，opt-in 复用 | 默认行为隔离最强；性能优化由 env 显式开启 |
| D10 | gVisor 缺失行为 | 强制失败 / warn 回退 / 可配置 | 默认 warn 回退到 runc，`HAGENT_SANDBOX_REQUIRE_RUNSC=1` 时强制失败 | 让本地 dev 在没装 gVisor 时仍能跑通；生产环境通过 env 强约束 |

## 3. 架构层级与模块分解

### 3.1 总体三层结构

```
┌──────────────────────────────────────────────────────────────┐
│ LLM Tools  (Bash / Read / Write / Edit / Skill / Agent / …)  │  ← schema 不变
└────────────────┬─────────────────────────┬───────────────────┘
                 │                         │
                 ▼                         ▼
        ShellProvider              FileTransport            ← Hagent 自研工具的"执行层契约"
       (host | sandbox)           (host | sandbox)
                 │                         │
                 └────────────┬────────────┘
                              ▼
            HagentSandboxBackend  (SandboxBackendProtocol)   ← deepagents 视角
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                           │
        ▼                                           ▼
  HagentDockerSandbox  ← 本版重点 (gVisor)    HagentDaytonaSandbox  ← 接口 stub
        │
   docker SDK / runsc runtime
```

### 3.2 `src/hagent/sandbox/` 新增包结构

| 文件 | 职责 |
| --- | --- |
| `sandbox/__init__.py` | 导出 `SandboxKind`、`SandboxFactory`、工厂函数 `create_sandbox_for_session()` |
| `sandbox/protocol.py` | `HagentSandboxProtocol`：在 deepagents `SandboxBackendProtocol` 之上加 Hagent 视角的 `workspace_dir`、`shell_provider()`、`file_transport()`、`close()`、`metadata` |
| `sandbox/docker/runtime.py` | gVisor runtime 检测：探测 `runsc`、读 `/etc/docker/daemon.json`、WSL2 ptrace 模式回退；`select_runtime(prefer="runsc") -> str` |
| `sandbox/docker/lifecycle.py` | `DockerContainerLifecycle`：`start(image, mounts, env)`、`stop()`、`pause()`、`resume()`；只管单个容器 |
| `sandbox/docker/sandbox.py` | `HagentDockerSandbox`：继承 `deepagents.backends.sandbox.BaseSandbox`，实现 `execute()`（`docker exec`）、`upload_files()` / `download_files()`（`docker cp` + tar）、`id` |
| `sandbox/docker/image.py` | 镜像构建/拉取：`build_default_image()` + `ensure_image(tag)`；本仓 `sandbox/docker/images/hagent-base/Dockerfile` 提供 `python:3.12-slim` + uv + git + ripgrep + bash |
| `sandbox/daytona/sandbox.py` | `HagentDaytonaSandbox`：组合 `langchain_daytona.DaytonaSandbox`；本版仅占位（`NotImplementedError` + 测试 stub） |
| `sandbox/providers/shell.py` | `SandboxShellProvider`：实现 `bash_tool.shell_provider.ShellProvider` 接口，构造命令时把环境/快照变量映射成 `docker exec env=… cmd` |
| `sandbox/providers/file.py` | `SandboxFileTransport`：被 `file_tools.io` 用来读写文件——Read 转 `download_files()`，Write/Edit 转 `upload_files()` + 服务端脚本（继承 `BaseSandbox._edit_inline`） |
| `sandbox/pool.py` | `SandboxPool`：warm pool（预启动 N 个空容器）、`acquire(session_id)`、`release()`（pause+回池或 stop+rm）、`idle_gc(ttl)` 后台 task |
| `sandbox/manifest.py` | session ↔ sandbox 元数据（`container_id`、`image_tag`、`runtime`、`created_at`、`last_used_at`）；写入扩展后的 `SessionStore` |

仓库根的 `sandbox/`（Dockerfile 等容器内资产）目录新增：

| 路径 | 用途 |
| --- | --- |
| `sandbox/docker/images/hagent-base/Dockerfile` | 默认 sandbox 镜像（`python:3.12-slim` + uv + git + ripgrep + bash） |
| `sandbox/docker/images/hagent-base/entrypoint.sh` | 容器入口（`tail -f /dev/null`，等 `docker exec` 调） |
| `scripts/build_sandbox_image.sh` | 本地构建脚本（`docker build -t hagent/sandbox:dev ...`） |

### 3.3 与现有模块的接线

- `bash_tool/shell_provider.py`：保留现有 `ShellProvider` 基类（host 实现），新增 `SandboxShellProvider`；`bash_tool.runtime.BashRuntime` 接受 `ShellProvider` 抽象不变。
- `file_tools/io.py`、`file_tools/tools.py`：抽出 `FileTransport` 接口（`read_bytes`、`write_bytes`、`edit_inline`），host 默认走 `Path.read_bytes()` / `os.open()`，sandbox 走 `SandboxFileTransport`。
- `core.py::create_hagent(...)`：在 sandbox 启用时——
  1. 用 sandbox 实例当 `backend=` 传给 `_create_deep_agent`（`BackendProtocol` 来源即 sandbox，permissions 不再适用，与 deepagents 文档一致）。
  2. 同时把同一个 sandbox 实例传给 `create_bash_tool(shell_provider=SandboxShellProvider(sandbox))`、`create_claude_file_tools(transport=SandboxFileTransport(sandbox))`。
  3. **不再走** `_filesystem_backend_for_workspace`——sandbox 模式下文件操作落在容器。
  4. `permissions=` 参数自动不向 deepagents 传入；用户传入的 `FilesystemPermission` 列表被忽略并记 `INFO` 日志。
- `server/sessions.py`：`SessionRow` 加 `sandbox_kind`、`container_id`、`image_tag`、`runtime`、`sandbox_metadata_json` 字段（migration 由 `SessionStore.__init__` 用 `PRAGMA table_info` + `ALTER TABLE` 增量执行）。
- `server/manager.py`（新增）：`SessionManager` 持有 `SandboxPool`；`create_session()` → `pool.acquire()`；`delete_session()` → `pool.release()`；SSE 关闭 / 长时间 idle → GC。
- `cli.py`：`python -m hagent demo --sandbox docker|none` flag；默认 `none`（host 模式）。同时新增 `python -m hagent sandbox {ls|stop|logs}` 子命令。

### 3.4 与 deepagents 0.6.x 的兼容性确认

- `HagentDockerSandbox` 继承 `deepagents.backends.sandbox.BaseSandbox`，自动获得 ls/read/grep/glob/edit 的"服务端脚本 via execute" 默认实现。
- `core.py` 仍禁用 deepagents 内置 `execute / read_file / write_file / edit_file / write_todos`——LLM 看到的工具仍是 Hagent 自研的（schema 对齐 Claude Code）。
- `BaseSandbox.read/write/edit` 在 deepagents 内部仅作为 BackendProtocol fallback；当 Hagent ShellProvider / FileTransport 直接调 sandbox 的 `execute` / `upload_files` / `download_files`，行为可控。
- `SummarizationMiddleware` 仍禁用、`SanitizeAnthropicThinkingBlocksMiddleware` 仍启用、`HagentSkillsMiddleware` 仍启用：sandbox 与 middleware 解耦。

## 4. 数据流与会话生命周期

### 4.1 一次 LLM tool call 的端到端数据流

以 LLM 调用 `Bash {"command": "ls -la"}` 为例（sandbox 启用时）：

```
LLM  →  Bash 工具 (Hagent schema, parser/permissions/output 不变)
        │
        ├─ runtime.BashRuntime.execute(command, *, cwd, env, timeout)
        │     │
        │     ▼
        │  ShellProvider.build_command(...) → 已有逻辑生成 shell snapshot
        │     │
        │     ▼
        │  SandboxShellProvider.run(shell_script, cwd, env, timeout)
        │     │
        │     ▼
        │  HagentDockerSandbox.execute(shell_script, timeout=...)
        │     │     (docker exec -i -w {cwd} -e PATH=… <cid> /bin/bash -lc "<script>")
        │     ▼
        │  ExecuteResponse(output, exit_code, truncated)
        ▼
   Hagent BashRuntime 把 output 截断 / 跑 progress / 写大文件到 .logs，
   返回 Claude-Code-compatible Bash 工具结果给 LLM
```

`Read` 工具类似：

```
Read {"file_path":"/workspace/foo.py","offset":0,"limit":2000}
  → file_tools.tools.create_read_tool 调 FileTransport.read_lines(...)
  → SandboxFileTransport.read_lines: 调 HagentDockerSandbox.read(...)（BaseSandbox 内置脚本）
  → 拿 FileData(content=…, encoding=utf-8) → format_with_line_numbers → 返回 cat -n
```

**关键点**：

- LLM 看到的工具签名 / 输出格式 / 错误信息完全等同 host 模式（schema 对齐 Claude Code 不动）。
- "文件路径" 在 LLM 视角是 sandbox 内的绝对路径，例如 `/workspace/foo.py`。Hagent UI 显示路径时按 sandbox 路径展示（与 Daytona 路径一致，未来切供应商 prompt 无需改）。
- "host 看到的"那个目录是后台逻辑：Web 前端的 file upload/download 端点（`server/routers/files.py`）转 `HagentSandbox.upload_files()` / `download_files()` 调 docker cp。

### 4.2 Session lifecycle 状态机

```
                  ┌──────────────────────────────┐
                  ▼                              │
   creating ──► running ──► idle ──► paused ─────┤
                  │           │        │         │
                  │           │        ▼         │
                  │           │     stopping ────┘
                  │           ▼
                  │       evicting (LRU/TTL)
                  ▼           │
              error ──► stopped/cleanup
```

| 状态 | 触发 | 操作 |
| --- | --- | --- |
| `creating` | `POST /sessions` → `SessionManager.create()` | `SandboxPool.acquire()` 从 warm pool 拿一个或新建；写 sandbox metadata 进 `SessionStore` |
| `running` | 容器 ready、`docker exec true` healthcheck 通过 | normal serving |
| `idle` | 距上次 tool call > `IDLE_TO_PAUSE_SECONDS`（默认 300） | 不动容器；只设状态 |
| `paused` | 距上次 > `IDLE_TO_STOP_SECONDS`（默认 1800） | `docker pause <cid>`；恢复时 `docker unpause` |
| `evicting` | warm pool 满、`TOTAL_SESSION_TTL`（默认 86400）到 | 异步 stop + rm；通知 SSE |
| `stopped` | 用户 `DELETE /sessions/{id}` 或 evict 完成 | 删 metadata；临时目录清理 |
| `error` | docker daemon 不可达、runsc 不存在（且 require=1）、image pull 失败 | 落 `session.status=error`；返回 503 给 API；不阻塞其他 session |

### 4.3 Warm pool 策略

- **Pool size**：`HAGENT_SANDBOX_POOL_MIN=1`、`HAGENT_SANDBOX_POOL_MAX=4`（dev 默认；生产侧由 env 调）。
- **预热内容**：容器跑 `tail -f /dev/null`，容器内创建空目录 `/workspace`（**不** bind-mount host 路径，与 D8 一致）；启动后 `docker exec` 一次 `python -c "import sys; print(sys.version)"` 当 readiness probe。
- **acquire 优先级**：pool 空闲 > pool 满则新建（直到 max）> 满则等（默认 5s 超时返回 503）。
- **release**：默认 `docker rm -f`（不复用，避免上一个 session 的文件污染下一个）；若 `HAGENT_SANDBOX_REUSE=true` 则 `docker exec rm -rf /workspace/* && pool.return()`。
- **idle GC**：后台 `asyncio.create_task` 跑 60s 巡检；状态机驱动 pause/evict。

### 4.4 文件 IO 路径

LLM 视角的所有路径都在容器内，默认根 `/workspace`。**不做 host workspace bind-mount**（决策 D8）。

| 操作 | 实现 |
| --- | --- |
| LLM `Write /workspace/foo.py` | `SandboxFileTransport.write()` → `docker cp - <cid>:/workspace/foo.py`（tar stream） |
| LLM `Read /workspace/foo.py` | `BaseSandbox.read()` 服务端脚本（已有），返回分页 + 行号 |
| LLM `Edit /workspace/foo.py` | `BaseSandbox.edit()` 服务端 inline 脚本，old+new < 50KB 一次 RPC 完成 |
| Server `POST /sessions/{id}/files` 用户上传 | `HagentSandbox.upload_files([...])` |
| Server `GET /sessions/{id}/files?path=...` 用户下载 | `HagentSandbox.download_files([...])` |
| `python -m hagent demo` CLI 想看产物 | demo 跑完后调 `download_files(["/workspace"])` 拷一份到 `./artifacts/<sid>/` |

### 4.5 SessionStore 扩展

`server/sessions.py` 的 `SessionRow` 增加以下列（启动期 migration 由 `SessionStore.__init__` 自动执行）：

```sql
ALTER TABLE sessions ADD COLUMN sandbox_kind TEXT NOT NULL DEFAULT 'none';      -- none|docker|daytona
ALTER TABLE sessions ADD COLUMN sandbox_id TEXT;                                 -- hagent 自己生成的逻辑 id
ALTER TABLE sessions ADD COLUMN container_id TEXT;                               -- docker 容器 id (kind=docker)
ALTER TABLE sessions ADD COLUMN image_tag TEXT;                                  -- 镜像 tag
ALTER TABLE sessions ADD COLUMN runtime TEXT;                                    -- runc | runsc
ALTER TABLE sessions ADD COLUMN sandbox_metadata_json TEXT;                      -- 额外元数据
```

`SessionStore.create_session(...)` 新增 `sandbox_kind`、`container_id` 等参数；旧调用 `sandbox_kind="none"` 默认。

## 5. 错误处理、HITL、Permissions

### 5.1 错误分层与降级

| 层级 | 故障类型 | Hagent 行为 |
| --- | --- | --- |
| **runtime detect** | host 未装 `docker` / daemon 不可达 | `create_hagent(sandbox="docker")` 启动期 `RuntimeError("docker not available — install docker or pass --sandbox none")`；不静默回退 |
| **runtime detect** | host 装了 docker 但没装 `runsc` | 默认 `WARN: gVisor (runsc) not found; falling back to default docker runtime (runc). 隔离强度下降。`；`HAGENT_SANDBOX_REQUIRE_RUNSC=1` 时强制启动失败（D10） |
| **image** | 镜像不存在 / pull 超时 | `creating → error`；session 状态写 error，SSE 推送 `{event:"sandbox.error", reason:"image_pull_failed", retry:false}` |
| **container start** | `docker run` exit code != 0、OCI runtime fail | 自动重试 1 次（换 runc）；仍败则 error |
| **exec/io 单调用** | `docker exec` 超时 / 流中断 | 单 tool call 失败：返回 `ExecuteResponse(output="container exec failed: <reason>", exit_code=137, truncated=False)`；不污染 session |
| **exec/io 健康检查** | 连续 N=3 次 `docker exec` 失败、`docker inspect` 显示 exited | session 状态 `running → error`；前端给"重启容器"按钮（手动） |
| **upload/download** | tar stream 中断 / 文件超过 limit | 返回 `FileUploadResponse(path=..., error="upload_failed: <reason>")`；其他文件按 batch partial success 处理 |
| **HITL / permission deny** | LLM 工具调用被 permission 拒绝 | 不到达 sandbox；与现有行为一致 |
| **pool 满 + acquire 超时** | warm pool 已满、新建超时 | API 返回 503 `Service overloaded, try later`；写 `sandbox.pool_exhausted` 日志 |

### 5.2 安全策略

按 D6 / D7 / D8 确认：

| 资源 | sandbox 内可见 | 实现 |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` 等 LLM 凭证 | ❌ 不注入 | docker run 时不传 `-e`；agent loop（含 sub-agent / sub-graph）跑在 host，sandbox 只执行 LLM 给出的 bash/python |
| `PATH`、`HOME`、`LANG` 等基础 env | ✅ 注入受控集合 | `HagentDockerSandbox` 维护 `safe_env = {"PATH":"/usr/local/bin:/usr/bin:/bin", "HOME":"/workspace", "LANG":"C.UTF-8", "TERM":"dumb"}`；通过 `docker exec -e` 传 |
| 用户工作目录文件 | ✅ 通过 `upload_files` / Write 工具 | 不 bind-mount，避免 host 文件被 LLM 误删 |
| 网络出口 | ✅ 默认开放 | `docker run --network bridge`；不加 `--network none` |
| `~/.ssh`、`~/.aws`、`~/.config` 等 host 凭证 | ❌ 不挂载 | container 起新的 `/root` HOME，不 mount user home |
| GPU、host docker socket | ❌ 不暴露 | 不传 `-v /var/run/docker.sock:/var/run/docker.sock`；不传 `--gpus`；本版不考虑 |

### 5.3 Permissions 在 sandbox 模式下的语义（D7）

- **deepagents `FilesystemPermission`**：sandbox 启用时**自动忽略**（`create_hagent` 在 sandbox 模式下不向 deepagents 传 `permissions=`，并发 `INFO` 日志告知）。
- **Hagent 自研 Bash permissions**（`bash_tool/permissions.py`）：sandbox 模式下默认放开（容器 + gVisor 即信任边界）；用户仍可通过 `permissions_overrides=` 注入自定义 deny 规则（opt-in）。
- **HITL middleware**：不变；用户可以继续 `interrupt_on=["bash"]` 让所有 bash 调用走人工审批，配合 sandbox 进一步收紧。
- **文件写入的"边界保护"**：Hagent 自研 `file_tools` 内的路径检查（不允许写 `/etc/`、`/sbin/` 等）在 sandbox 模式下默认**关闭**——因为这些路径仅是容器内的、无外溢风险。

### 5.4 可观测性

- `server/sse.py` 增加事件类型：`sandbox.created`、`sandbox.paused`、`sandbox.resumed`、`sandbox.evicted`、`sandbox.error`，前端 Timeline 能可视化容器生命周期。
- 每个 sandbox 写一个 per-session 日志文件到 `.logs/sandbox/<sid>.log`（`docker logs` 输出 + Hagent 状态机变迁）。
- `HagentDockerSandbox.id` 用 `docker-<container_short_id>`，方便对照 `docker ps`。
- 新增 `python -m hagent sandbox {ls|stop|logs} [<sid>]` CLI 子命令。

### 5.5 LLM 视角"语义不变"清单（硬性）

以下行为在 host 与 sandbox 模式下必须 byte-equal（除路径前缀差异）：

- Bash 工具 schema、cwd 跟踪、background task、`shell_provider` snapshot 行为
- Read 工具 `cat -n` 格式、行号 base 1、empty file 提示、binary base64 编码、`offset/limit` 分页
- Edit 工具 unique-old-string、`replace_all`、CRLF/LF 处理
- Skill 工具（`Skill` 工具 + skills middleware）：仍读 host 上的 `~/.claude/skills/`、`HAGENT_SKILLS_PATHS`；skill body 通过 `upload_files` 推到容器 `/tmp/hagent-skills/`，sandbox 内的 bash 工具能 source

## 6. 测试策略与验收标准

### 6.1 测试分层

| 层 | 标记 | 跑法 | CI 是否门控 |
| --- | --- | --- | --- |
| **L1 单元**：纯 Python，mock docker SDK | 无 | `pytest tests/sandbox/test_*_unit.py` | ✅ 默认跑 |
| **L2 协议契约**：把 `HagentDockerSandbox` 替换成 in-memory fake，验证 `SandboxBackendProtocol` 完整实现 | 无 | `pytest tests/sandbox/test_protocol_*.py` | ✅ 默认跑 |
| **L3 Docker 集成**：需要 docker daemon | `@pytest.mark.docker` + env `HAGENT_TEST_DOCKER=1` skip 条件 | `HAGENT_TEST_DOCKER=1 pytest -m docker -v` | ⚠️ 本地 / CI Docker runner，非默认 |
| **L4 gVisor 集成**：需要 docker + `runsc` 已装 | `@pytest.mark.gvisor` + env `HAGENT_TEST_GVISOR=1` | `HAGENT_TEST_GVISOR=1 pytest -m gvisor -v` | ⚠️ 仅 self-host runner |
| **L5 端到端**：CLI + Agent Server + 真实 LLM | `@pytest.mark.e2e` + `ANTHROPIC_API_KEY` 必备 | `set -a && source .env && set +a && pytest tests/test_demo_e2e_sandbox.py -s` | ❌ 手动 |

### 6.2 关键测试用例

**`tests/sandbox/test_docker_sandbox_unit.py`**（L1，mock subprocess/docker SDK）：

- `select_runtime` 在 daemon.json 有 runsc 时返回 `runsc`；没有时返回 `runc` 并 warn
- `WSL2 detection` 走 ptrace 路径而非 KVM
- `safe_env` 不包含 `ANTHROPIC_API_KEY`、`OPENAI_API_KEY`、`AWS_*`、`SSH_*`
- `HagentDockerSandbox.execute()` 把 cwd / env / timeout 正确翻译成 `docker exec` 参数

**`tests/sandbox/test_pool.py`**（L1）：

- `SandboxPool` warm pool 预热到 min 大小
- `acquire` 池空走新建；池有走 reuse-or-create
- `idle_gc` 状态机：running → idle → paused → evicted
- `release` 默认 stop+rm，`HAGENT_SANDBOX_REUSE=1` 时清理 workspace 后回池

**`tests/sandbox/test_protocol_contract.py`**（L2，使用 fake sandbox 实现 BaseSandbox）：

- 跑一遍 deepagents `BaseSandbox` ls/read/grep/glob/edit/write 全套，断言返回类型 / error 路径
- 跑 Hagent `SandboxShellProvider` 把同样 bash 命令对比 host vs fake，输出 byte-equal（除路径前缀）

**`tests/sandbox/test_docker_sandbox_integration.py`**（L3）：

- `start → execute("python --version") → assert exit_code==0`
- `upload_files([("/workspace/a.txt", b"x")]) → execute("cat /workspace/a.txt") → assert "x"`
- `download_files(["/workspace/a.txt"]) → assert content == b"x"`
- `execute(timeout=2, command="sleep 5") → exit_code==124`
- `large output` 截断走 BaseSandbox truncation 提示
- `stop` 之后 `execute` 返回 sandbox-not-running 错误而非 hang

**`tests/sandbox/test_gvisor.py`**（L4）：

- 用 `--runtime=runsc` 启动；`execute("uname -r")` 输出和 host 不同（gVisor kernel 串）
- `execute("dmesg")` 在 gVisor 下被拦截 / 空输出（验证 syscall 拦截）

**`tests/server/test_sessions_sandbox.py`**（L3）：

- `POST /sessions` 带 `sandbox_kind=docker` → `SessionRow` 包含 `container_id`；`docker ps` 能看到
- `DELETE /sessions/{sid}` → 容器消失，SSE 推送 `sandbox.evicted`
- `POST /sessions/{sid}/messages` 触发 LLM → Bash → 容器内执行 → SSE 含 `tool_result`

**`tests/test_demo_e2e_sandbox.py`**（L5）：

- 跑 `python -m hagent demo --sandbox docker "用 python 算 1+1 并写到 /workspace/result.txt"` → demo 结束后 `download_files(["/workspace/result.txt"])` 读到 `"2"`

### 6.3 行为对齐回归测试

新增 `tests/sandbox/test_tool_parity.py`：同一份输入分别在 host (`LocalShellBackend`) 和 sandbox (`HagentDockerSandbox`) 跑，断言：

- Bash 工具输出（含 truncation marker、exit code、stderr 前缀）byte-equal
- Read 工具返回的 cat -n 文本完全一致（行号、行尾、empty 提示）
- Edit 工具 `string_not_found` / `multiple_occurrences` / CRLF preserve 错误信息一致

这套测试是"sandbox 不改变 LLM 视角行为"的可执行契约。

### 6.4 既有测试套件影响

- **不要破坏的**：`tests/test_core.py`、`tests/test_bash_tool_*.py`、`tests/test_claude_*_tool.py` 在 `sandbox=none` 默认下行为不变。
- **需要扩展的**：`tests/test_core.py` 加 `test_create_hagent_with_docker_sandbox`（mock `_create_deep_agent` + mock `HagentDockerSandbox`），断言 `backend` 是 sandbox 实例、`permissions=` 未传入、Hagent 自研工具仍替换 deepagents 同名工具。
- **新增 mock fixture**：`tests/conftest.py` 加 `fake_sandbox` fixture，返回内存 `BaseSandbox` 子类（用 tmpdir 模拟容器内 fs），让 L2 测试不依赖 docker。

### 6.5 验收标准

本 spec 对应的实现 plan 完成时，需以下全部满足：

1. `pytest -v`（默认套件，无 docker / gvisor）全绿，包含新增的 L1/L2 测试。
2. `HAGENT_TEST_DOCKER=1 pytest -m docker -v` 全绿（装有 docker 的 WSL2 / Linux 主机）。
3. `HAGENT_TEST_GVISOR=1 pytest -m gvisor -v` 全绿（self-host runner，能装 runsc）。
4. `python -m hagent demo --sandbox docker "..."` 在装了 docker 的 WSL2 上跑通 CSV 画图任务（对齐 Plan 5 原目标）。
5. Web 前端（`web/`）能新建一个 `sandbox_kind=docker` 的 session、LLM 在容器内跑 bash、文件能通过 file API 上传/下载、SSE 显示 `sandbox.created/evicted` 事件。
6. `scripts/check_base_prompt.sh` 仍过（base prompt 未被 sandbox 改动污染）。
7. `pre-commit` / `ruff` / `mypy` 不引入 regression。
8. spec（本文件）与对应 plan `docs/plans/2026-05-19-hagent-sandbox-impl.md` 入仓。
9. `HagentDaytonaSandbox` 类存在、有一个 `pytest.skip` 的 stub 测试证明抽象层不绑死 docker。

### 6.6 性能 / 资源预算（SLO）

非验收门槛，仅 spec 内 SLO：

- 冷启容器（docker run + readiness probe）：本机 WSL2 < 1.5s（runc）/ < 2.0s（runsc）
- warm pool acquire：< 100ms
- `docker exec` 单次 round-trip：本机 < 80ms
- 1 个 warm 容器内存预算：< 80MB（python 进程未启动时）
- 24h idle session 自动 evict，容器不留尸

## 7. Out of scope

- GPU / CUDA 镜像（未来加 `--sandbox docker-gpu`）。
- 自托管 Daytona / E2B / Modal / AgentCore / Cloudflare 集群运维。
- Snapshot resume、assistant-scoped sandbox（跨会话状态持久化）。
- Egress proxy 注入凭证（与 Cloudflare Sandbox SDK 同款）。
- Web 前端的 sandbox 管理 UI（仅后端 SSE 暴露事件；UI 改造另起 plan）。
- 容器内的 IDE / TTY / 远程调试（Daytona / Runloop 提供，但 Hagent 本版不暴露）。
- 多用户 / 多租户配额、计费、限速。

## 8. 未来工作

- **F1**：实现 `HagentDaytonaSandbox`，把 `langchain-daytona.DaytonaSandbox` 接入 Hagent SessionManager，对齐 warm pool / GC 抽象。
- **F2**：加入 `HagentE2BSandbox`（等 deepagents PR #1739 GA）/ `HagentModalSandbox`，作为可选 backend。
- **F3**：Snapshot 与 assistant-scoped sandbox 支持（容器 commit + image cache）。
- **F4**：Web 前端 sandbox 控制台（实时 docker logs、文件树、停启重启按钮）。
- **F5**：egress proxy 路径，secrets 可受控注入而 agent 看不到。

## 9. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| WSL2 上 gVisor 不可用 / 性能差 | 本地隔离强度下降 | 默认 warn 回退 runc；提供 `HAGENT_SANDBOX_REQUIRE_RUNSC=1` 给生产；提供 wiki 文档教如何在 WSL2 配 runsc-ptrace |
| `docker exec` 单次 ~50-80ms 延迟拖慢 agent loop | UX 体感变差 | warm pool 减冷启；批量 tool 调用走同一容器；future: persistent exec 通道（`docker exec -i` keep-alive） |
| BaseSandbox 服务端脚本 (Python heredoc) 体积大，每次 exec 发完整脚本 | 网络 IO 浪费 | 镜像里预置脚本到 `/opt/hagent/*.py`，`execute` 只调 `python3 /opt/hagent/read.py …`；列入 Plan 但本版可后置 |
| 容器 fs 与 LLM 路径假设不一致（agent 习惯了 host 路径） | tool 调用失败 | base prompt 改动 sandbox 段落，明示 LLM "你看到的路径都在 /workspace 内"；同步更新 `prompts/decisions.md` |
| Daytona stub 没人维护、未来上线时已腐烂 | 切换托管路线时返工 | L2 contract 测试持续覆盖 stub，保证抽象层不被 docker 实现绑死 |
| Plan 5 旧 spec 与本 spec 冲突 | 工程师混淆 | 本 spec 第 0 节明示取代关系；同步在 Plan 5 文件顶部加 superseded note |

## 10. 文档同步清单（spec 落地时执行）

- `CLAUDE.md`：新增 "Sandbox 模式" 段落（替换 `HagentLocalShellBackend` 描述里的 "正式部署走 Plan 5 DockerBackend" 字样）。
- `docs/plans/2026-05-12-plan-5-docker-backend-and-swap.md`：顶部加 superseded 注，指向本 spec 与对应实现 plan。
- `prompts/hagent_base.zh.md` + `prompts/decisions.md`：sandbox 模式下"工作目录默认 `/workspace`、网络可用、不要尝试访问 host 路径"的提示段落（KEEP/MODIFY/DELETE 记录同步）。
- `web/CLAUDE.md`：Web 前端在 sandbox 模式下文件 API 走 `/sessions/{sid}/files`、SSE 含 `sandbox.*` 事件。
- `AGENTS.md`：PR 验证命令补 `HAGENT_TEST_DOCKER=1 pytest -m docker -v`。
