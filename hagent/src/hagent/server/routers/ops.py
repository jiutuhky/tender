"""只读运维 API(`/ops/*`)—— SmolVM Ops Console 的数据源。

**只读**:不提供任何破坏性操作(stop/evict/kill),避免误触打死线上 VM;
运维要动手走 `hagent sandbox` CLI。数据全部来自现有运行时(pool / ledger /
supervisor / SmolVM DB / sandbox_events),不改任何状态。

上下文经 ``set_ops_context`` 在 app 装配期注入;未注入(如 none provider 或
测试早期)时端点返回 kind + 空机群,前端据此提示无 smolvm 数据。
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from fastapi import APIRouter, Depends, Query

from hagent.server.auth import require_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops", dependencies=[Depends(require_api_key)])

VM_ID_PREFIX = "hagent-"
_METRICS_SCAN_LIMIT = 400  # 扫最近这么多条 metrics 事件取每 VM 最新一条


@dataclass
class OpsContext:
    kind: str
    pool: Any | None = None
    ledger: Any | None = None
    supervisor: Any | None = None
    event_store: Any | None = None
    store_getter: Callable[[], Any] | None = None
    manager_factory: Callable[[], Any] | None = None
    quota_mem_mib: int = 0
    quota_vcpus: int = 0


_CTX: OpsContext | None = None


def set_ops_context(ctx: OpsContext | None) -> None:
    global _CTX
    _CTX = ctx


def _pid_alive(pid: int | None) -> bool:
    return pid is not None and os.path.exists(f"/proc/{pid}")


def _latest_metrics_by_vm(event_store: Any) -> dict[str, dict]:
    """最近 metrics 事件里每 VM 的最新 CPU/RSS。倒序扫,首见即最新。"""
    latest: dict[str, dict] = {}
    try:
        rows = event_store.list(event="metrics", limit=_METRICS_SCAN_LIMIT)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ops: 读 metrics 事件失败: %s", exc)
        return latest
    for row in rows:  # limit 模式为倒序(最新在前)
        vm_id = row.vm_id
        detail = row.detail or {}
        if not vm_id or vm_id in latest:
            continue
        rss_bytes = detail.get("rss_bytes")
        latest[vm_id] = {
            "ts": row.ts,
            "cpu_seconds": detail.get("cpu_seconds"),
            "rss_mib": round(rss_bytes / (1024 * 1024), 1) if rss_bytes else None,
        }
    return latest


def _sdk_vms_by_id(manager_factory: Callable[[], Any] | None) -> dict[str, dict]:
    """SmolVM DB 里 hagent- 前缀 VM 的 status/pid。SDK 不可用时空。"""
    if manager_factory is None:
        return {}
    out: dict[str, dict] = {}
    try:
        manager = manager_factory()
        with manager as mgr:
            vms = mgr.list_vms()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ops: SmolVM list_vms 失败: %s", exc)
        return out
    for vm in vms:
        if not vm.vm_id.startswith(VM_ID_PREFIX):
            continue
        out[vm.vm_id] = {
            "sdk_status": getattr(getattr(vm, "status", None), "value", None),
            "pid": getattr(vm, "pid", None),
        }
    return out


def _build_sandbox_rows(ctx: OpsContext, now: float) -> tuple[list[dict], dict[str, int]]:
    rows: list[dict] = []
    state_counts: dict[str, int] = {}
    if ctx.store_getter is None:
        return rows, state_counts
    try:
        leases = ctx.store_getter().list()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ops: 读 sandbox_leases 失败: %s", exc)
        return rows, state_counts

    metrics = _latest_metrics_by_vm(ctx.event_store) if ctx.event_store is not None else {}
    sdk_vms = _sdk_vms_by_id(ctx.manager_factory)
    seen_vm_ids: set[str] = set()

    for lease in leases:
        if lease.sandbox_kind != "smolvm" or lease.sandbox_state == "closed":
            continue
        state = lease.sandbox_state or "unknown"
        state_counts[state] = state_counts.get(state, 0) + 1
        vm_id = lease.sandbox_id
        if vm_id:
            seen_vm_ids.add(vm_id)
        sdk = sdk_vms.get(vm_id or "", {})
        m = metrics.get(vm_id or "", {})
        pid = sdk.get("pid")
        last_activity = lease.last_activity_at
        if isinstance(last_activity, str):
            try:
                last_activity = datetime.fromisoformat(last_activity).timestamp()
            except ValueError:
                last_activity = None
        rows.append(
            {
                "project_id": lease.project_id,
                "vm_id": vm_id,
                "state": state,
                "node": lease.node,
                "pid": pid,
                "pid_alive": _pid_alive(pid) if pid is not None else None,
                "sdk_status": sdk.get("sdk_status"),
                "cpu_seconds": m.get("cpu_seconds"),
                "rss_mib": m.get("rss_mib"),
                "last_activity_at": last_activity,
                "idle_seconds": (
                    round(now - last_activity, 1) if isinstance(last_activity, (int, float)) else None
                ),
                "snapshot_id": lease.snapshot_id,
            }
        )

    # SmolVM DB 里有、但 session 未匹配的 hagent- VM(潜在无主/暖池)—— 单列出来
    for vm_id, sdk in sdk_vms.items():
        if vm_id in seen_vm_ids:
            continue
        rows.append(
            {
                "project_id": None,
                "vm_id": vm_id,
                "state": "unmatched-vm",
                "node": None,
                "pid": sdk.get("pid"),
                "pid_alive": _pid_alive(sdk.get("pid")) if sdk.get("pid") is not None else None,
                "sdk_status": sdk.get("sdk_status"),
                "cpu_seconds": metrics.get(vm_id, {}).get("cpu_seconds"),
                "rss_mib": metrics.get(vm_id, {}).get("rss_mib"),
                "last_activity_at": None,
                "idle_seconds": None,
                "snapshot_id": None,
            }
        )
        state_counts["unmatched-vm"] = state_counts.get("unmatched-vm", 0) + 1
    return rows, state_counts


@router.get("/state")
def ops_state() -> dict:
    """聚合快照:provider / 池 / 账本 / supervisor / 机群 / 状态分布。一次往返。"""
    now = time.time()
    ctx = _CTX
    if ctx is None:
        return {
            "kind": "none",
            "generated_at": now,
            "pool": None,
            "ledger": None,
            "supervisor": None,
            "quota": None,
            "sandboxes": [],
            "state_counts": {},
        }

    pool_stats = None
    if ctx.pool is not None:
        try:
            pool_stats = ctx.pool.stats()
        except Exception as exc:  # noqa: BLE001
            logger.warning("ops: pool.stats 失败: %s", exc)

    ledger = None
    if ctx.ledger is not None:
        ledger = {
            "mem_capacity_mib": ctx.ledger.mem_capacity_mib,
            "mem_in_use_mib": ctx.ledger.mem_in_use_mib,
            "cpu_capacity": ctx.ledger.cpu_capacity,
            "cpu_in_use": ctx.ledger.cpu_in_use,
        }

    supervisor = None
    if ctx.supervisor is not None:
        try:
            supervisor = ctx.supervisor.loop_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("ops: supervisor.loop_status 失败: %s", exc)

    sandboxes, state_counts = _build_sandbox_rows(ctx, now)
    return {
        "kind": ctx.kind,
        "generated_at": now,
        "pool": pool_stats,
        "ledger": ledger,
        "supervisor": supervisor,
        "quota": {"mem_mib": ctx.quota_mem_mib, "vcpus": ctx.quota_vcpus},
        "sandboxes": sandboxes,
        "state_counts": state_counts,
    }


@router.get("/events")
def ops_events(
    limit: int = Query(default=100, ge=1, le=500),
    project_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    event: str | None = Query(default=None),
) -> dict:
    """事件尾:最近 N 条 sandbox_events(倒序),可按 session / kind 筛。"""
    ctx = _CTX
    if ctx is None or ctx.event_store is None:
        return {"events": [], "count": 0}
    try:
        rows = ctx.event_store.list(
            project_id=project_id,
            session_id=session_id,
            event=event,
            limit=limit,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("ops: 读事件失败: %s", exc)
        return {"events": [], "count": 0}
    events = [
        {
            "ts": r.ts,
            "project_id": r.project_id,
            "session_id": r.session_id,
            "vm_id": r.vm_id,
            "event": r.event,
            "detail": r.detail,
        }
        for r in rows
    ]
    return {"events": events, "count": len(events)}
