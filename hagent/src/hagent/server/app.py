from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hagent.assets.mcp import build_mcp_server
from hagent.assets.mcp_actor import AgentContextASGI
from hagent.assets.mcp_guard import LoopbackOnlyASGI
from hagent.assets.service import AssetService, set_asset_service
from hagent.assets.store import AssetStore
from hagent.config import load_env_file, preflight_sandbox_kind, resolve_sessions_db_path
from hagent.sandbox import SandboxKind
from hagent.sandbox.docker.sandbox import HagentDockerSandbox
from hagent.sandbox.pool import SandboxPool
from hagent.sandbox.supervisor import SandboxSupervisor
from hagent.server.leases import LeaseStore
from hagent.server.manager import SessionManager
from hagent.server.project_workspace import ProjectWorkspace, set_project_workspace
from hagent.server.projects import ProjectStore, set_project_store
from hagent.server.routers import files as files_router
from hagent.server.routers import messages as messages_router
from hagent.server.routers import project_files as project_files_router
from hagent.server.routers import projects as projects_router
from hagent.server.routers import sessions as sessions_router
from hagent.server.routers.sessions import (
    begin_drain,
    set_default_sandbox_kind,
    set_draining,
    set_session_manager,
)
from hagent.server.runs import RunStore
from hagent.server.sessions import SessionStore
from hagent.server.workspace_materialization import WorkspaceMaterializer
from hagent.server.workspace_checkpoint import WorkspaceCheckpointer


def _cors_origins() -> list[str]:
    """从 env 读 CORS 允许列表，默认放行本地 Next.js dev server (3000)。

    MVP 单租户场景：开发用 ["http://localhost:3000"]，生产部署同源时清空即可。
    """
    raw = os.environ.get("HAGENT_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


def _build_docker_pool() -> SandboxPool:
    """Build a SandboxPool backed by HagentDockerSandbox.start().

    The pool does NOT prewarm by default — containers are only started on
    demand (acquire()).  Call pool.prewarm() and pool.start_gc_loop() in
    production when HAGENT_SANDBOX_PREWARM=true.
    """
    return SandboxPool(
        sandbox_factory=lambda: HagentDockerSandbox.start(),
        min_size=int(os.environ.get("HAGENT_SANDBOX_POOL_MIN", "1")),
        max_size=int(os.environ.get("HAGENT_SANDBOX_POOL_MAX", "4")),
        **_idle_thresholds_from_env(),
    )


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    return float(raw) if raw else default


def _idle_thresholds_from_env() -> dict[str, float]:
    """idle 两级降档阈值(spec §5):pause 300s / evict 1800s,env 可覆盖。"""
    return {
        "idle_pause_seconds": _float_env("HAGENT_SANDBOX_IDLE_PAUSE_SECONDS", 300.0),
        "idle_evict_seconds": _float_env("HAGENT_SANDBOX_IDLE_EVICT_SECONDS", 1800.0),
    }


def _build_smolvm_auditor(db_path: str):
    """审计三流之二(spec §4.5):命令 JSONL + 事件表(与 sessions 同库分表)。"""
    from hagent.sandbox.smolvm.audit import CommandAuditLog, SandboxAuditor, SandboxEventStore

    return SandboxAuditor(
        command_log=CommandAuditLog(), event_store=SandboxEventStore(db_path)
    )


def _build_smolvm_pool(auditor=None) -> SandboxPool:
    """SandboxPool backed by HagentSmolVMSandbox + AdmissionLedger 准入。"""
    from hagent.sandbox.ledger import AdmissionLedger
    from hagent.sandbox.smolvm.sandbox import HagentSmolVMSandbox

    return SandboxPool(
        sandbox_factory=lambda: HagentSmolVMSandbox.start(auditor=auditor),
        project_sandbox_factory=lambda project_id: HagentSmolVMSandbox.start(
            project_id=project_id, auditor=auditor
        ),
        # VM id 必须含 project 前缀，不能使用无归属的 warm VM。
        min_size=0,
        max_size=int(os.environ.get("HAGENT_SANDBOX_POOL_MAX", "4")),
        max_lifetime_seconds=int(os.environ.get("HAGENT_SMOLVM_MAX_LIFETIME_SECONDS", "86400")),
        recycle_after_seconds=int(os.environ.get("HAGENT_SANDBOX_RECYCLE_SECONDS", "3600")),
        restore_factory=lambda snapshot_id, project_id: HagentSmolVMSandbox.restore(
            snapshot_id, project_id=project_id, auditor=auditor
        ),
        ledger=AdmissionLedger(),
        quota_mem_mib=int(os.environ.get("HAGENT_SMOLVM_MEMORY_MIB", "2048")),
        quota_vcpus=int(os.environ.get("HAGENT_SMOLVM_VCPUS", "2")),
        **_idle_thresholds_from_env(),
    )


def _ensure_smolvm_image() -> None:
    """golden base 启动期烘焙(Task C1):首会话不再付 docker build 成本。

    指纹缓存命中时近零开销;构建失败即启动失败(spec §6 镜像语义,
    与 docker provider ensure_image 一致,不静默降级)。
    """
    from hagent.sandbox.smolvm.image import ensure_boot_image

    ensure_boot_image()


def _build_smolvm_supervisor(
    mgr: SessionManager, pool: SandboxPool, auditor=None
) -> SandboxSupervisor:
    """孤儿治理 + 健康巡检:对账收养挂回 manager;连败杀重建标 orphaned。"""
    from smolvm import SmolVMManager

    from hagent.sandbox.smolvm.health import SmolVMHealthChecker
    from hagent.sandbox.smolvm.metrics import SmolVMMetricsSampler
    from hagent.sandbox.smolvm.reconciler import SmolVMReconciler
    from hagent.sandbox.smolvm.sandbox import HagentSmolVMSandbox

    reconciler = SmolVMReconciler(
        manager=SmolVMManager(),
        leases=mgr.lease_store,
        adopt_fn=HagentSmolVMSandbox.adopt,
        on_adopted=mgr.adopt_sandbox,
        protected_vm_ids=pool.live_vm_ids,
        on_orphaned=lambda project_id, reason: mgr.emit_project_event(
            "orphaned", project_id, reason=reason
        ),
    )
    health_checker = SmolVMHealthChecker(
        targets_fn=mgr.live_sandboxes,
        drop_fn=mgr.drop_sandbox,
        leases=mgr.lease_store,
        workspace_root=mgr.workspace_root,
        auditor=auditor,
        event_fn=mgr.emit_project_event,
        project_workspace=mgr.project_workspace,
        run_store=mgr.run_store,
    )
    metrics_sampler = (
        SmolVMMetricsSampler(targets_fn=mgr.live_sandboxes, auditor=auditor)
        if auditor is not None
        else None
    )
    return SandboxSupervisor(
        reconciler=reconciler,
        health_checker=health_checker,
        metrics_sampler=metrics_sampler,
    )


def _wire_ops_console(
    *, effective_kind, pool, supervisor, store, db_path: str
) -> None:
    """SmolVM Ops Console 只读数据源接线(design: docs/ops-console-design.md)。

    smolvm 生效时接账本 + 事件表 + SDK 枚举;docker/none 只给 provider + 池视图。
    """
    from hagent.sandbox.smolvm.audit import SandboxEventStore
    from hagent.server.routers.ops import OpsContext, set_ops_context

    if effective_kind is SandboxKind.SMOLVM:
        from smolvm import SmolVMManager

        set_ops_context(
            OpsContext(
                kind=effective_kind.value,
                pool=pool,
                ledger=getattr(pool, "_ledger", None),
                supervisor=supervisor,
                event_store=SandboxEventStore(db_path),
                store_getter=lambda: store,
                manager_factory=SmolVMManager,
                quota_mem_mib=int(os.environ.get("HAGENT_SMOLVM_MEMORY_MIB", "2048")),
                quota_vcpus=int(os.environ.get("HAGENT_SMOLVM_VCPUS", "2")),
            )
        )
    else:
        set_ops_context(
            OpsContext(kind=effective_kind.value, pool=pool, store_getter=lambda: store)
        )


def create_app() -> FastAPI:
    load_env_file()

    # Support both env var names: HAGENT_SESSIONS_DB (new) and HAGENT_DB_PATH (legacy)
    db_path = resolve_sessions_db_path()
    workspace_root = Path(os.environ.get("HAGENT_WORKSPACE_ROOT", "/tmp/hagent/workspaces"))
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    workspace_root.mkdir(parents=True, exist_ok=True)

    store = SessionStore(db_path)
    lease_store = LeaseStore(db_path)
    run_store = RunStore(db_path)
    # projects 与 sessions 共用同一个 sqlite 文件(独立表)
    project_store = ProjectStore(db_path)
    set_project_store(project_store)
    project_workspace = ProjectWorkspace(workspace_root)
    set_project_workspace(project_workspace)

    # 结构化资产：对象库与 sessions 同一 SQLite 文件（独立五表）；
    # MCP adapter 挂 /mcp（loopback Streamable HTTP，stateless JSON）
    asset_service = AssetService(AssetStore(db_path))
    set_asset_service(asset_service)
    # project 存在性判定与 REST adapter 的 `_require_project` 同源（ProjectStore），
    # 让 agent 传错 project_id 时第一次调用就 fail loud，而不是静默建幽灵命名空间。
    mcp_server = build_mcp_server(
        asset_service,
        workspace_for=project_workspace.path_for,
        project_exists=lambda project_id: project_store.get(project_id) is not None,
    )

    # 预检降级链(spec D5)决定本进程的 sandbox provider 与 session 默认 kind
    effective_kind = preflight_sandbox_kind()
    set_default_sandbox_kind(effective_kind.value)

    # smolvm 生效时装 smolvm pool;否则维持 docker pool(none 默认下仍支持
    # per-request sandbox_kind=docker)。Prewarm 由 HAGENT_SANDBOX_PREWARM 门控。
    auditor = _build_smolvm_auditor(db_path) if effective_kind is SandboxKind.SMOLVM else None
    prewarm_enabled = os.environ.get("HAGENT_SANDBOX_PREWARM", "false").lower() in ("1", "true", "yes")
    if effective_kind is SandboxKind.SMOLVM:
        pool = _build_smolvm_pool(auditor)
        # Task C1:镜像先于预热(prewarm 首 VM 不再触发构建);GC 循环常开——
        # idle 治理 / max_lifetime / warm recycle 均挂其上,不依赖 PREWARM。
        _ensure_smolvm_image()
        if prewarm_enabled:
            pool.prewarm()
        pool.start_gc_loop()
    else:
        pool = _build_docker_pool()
        if prewarm_enabled:
            pool.prewarm()
            pool.start_gc_loop()

    mgr = SessionManager(
        store=store,
        lease_store=lease_store,
        sandbox_pool=pool,
        workspace_root=workspace_root,
        workspace_materializer=WorkspaceMaterializer(project_workspace),
        project_workspace=project_workspace,
        run_store=run_store,
        workspace_checkpointer=WorkspaceCheckpointer(
            workspace=project_workspace,
            runs=run_store,
            leases=lease_store,
        ),
        # run-hold 上限:活跃 Run 超时仍未终结时不再阻止 GC 降档(防卡死 Run 霸占 VM)
        run_hold_max_seconds=_float_env("HAGENT_RUN_HOLD_MAX_SECONDS", 7200.0),
    )
    set_session_manager(mgr)
    set_draining(False)  # 新装配复位(测试多 app 实例共享模块旗标)

    # Task C2:paused 超阈值 → DISK 快照持久化替代破坏性驱逐(默认开,
    # HAGENT_SMOLVM_SNAPSHOT_PERSIST=0 退回纯驱逐);manager 持 session 记账
    if effective_kind is SandboxKind.SMOLVM and os.environ.get(
        "HAGENT_SMOLVM_SNAPSHOT_PERSIST", "1"
    ).lower() not in ("0", "false", "no"):
        pool.set_persist_fn(mgr.persist_sandbox)

    supervisor = (
        _build_smolvm_supervisor(mgr, pool, auditor)
        if effective_kind is SandboxKind.SMOLVM
        else None
    )
    if supervisor is None:
        mgr.interrupt_unrecovered_runs()

    _wire_ops_console(
        effective_kind=effective_kind,
        pool=pool,
        supervisor=supervisor,
        store=lease_store,
        db_path=db_path,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # MCP session manager 由父 app lifespan 承载（FastAPI 不跑子 app lifespan）
        async with mcp_server.session_manager.run():
            # startup:先同步对账(收养/清场),再起周期 reaper 与健康巡检
            if supervisor is not None:
                supervisor.startup_reclaim()
                mgr.interrupt_unrecovered_runs()
                supervisor.start_reaper()
                supervisor.start_health_loop()
                supervisor.start_metrics_loop()
            yield
            # graceful drain(Task B5):拒新建 → supervisor 先停(防巡检把
            # paused 误判病 VM、对账与关闭竞态)→ 存量 pause 保留(重启收养)。
            # docker/none 无收养机制,维持全拆语义。
            begin_drain()
            if supervisor is not None:
                supervisor.shutdown()
                mgr.drain()
            else:
                mgr.shutdown()

    app = FastAPI(title="Hagent Agent Server", version="0.0.1", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    app.include_router(sessions_router.router)
    app.include_router(messages_router.router)
    app.include_router(files_router.router)
    app.include_router(projects_router.router)
    app.include_router(project_files_router.router)

    # 结构化资产 REST adapter（票 07）：前端读端点 + 人工动作，
    # 与 MCP adapter 同委托 asset_service（唯一写入口）
    from hagent.assets.router import router as assets_router

    app.include_router(assets_router)

    from hagent.server.routers import ops as ops_router

    app.include_router(ops_router.router)

    # SmolVM Ops Console(只读运维仪表盘,同源免 CORS;静态壳无鉴权,数据端点鉴权)
    _ops_console_html = Path(__file__).resolve().parent / "ops_console" / "index.html"

    @app.get("/ops-console", include_in_schema=False)
    def ops_console():
        from fastapi.responses import FileResponse, JSONResponse

        if not _ops_console_html.is_file():
            return JSONResponse({"error": "ops console asset missing"}, status_code=404)
        return FileResponse(_ops_console_html, media_type="text/html")

    # MCP 面（spec §6）：子 app 自带 /mcp 路径、挂根做兜底（Mount("/mcp") 会对
    # POST /mcp 发 307）。必须在全部路由之后 mount。loopback 之外 403，
    # 对外开放待 auth（OAuth 2.1），不在本 feature。guard 在外先裁准入，
    # AgentContextASGI 在内收 run 归属与项目绑定 header（票 04）。
    app.mount("/", LoopbackOnlyASGI(AgentContextASGI(mcp_server.streamable_http_app())))

    return app
