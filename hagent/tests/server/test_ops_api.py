"""只读运维 API(/ops/*)—— 聚合快照 + 事件尾;全 fake,不碰真 SDK。"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hagent.server.routers import ops as ops_mod
from hagent.server.routers.ops import OpsContext, set_ops_context


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(ops_mod.router)
    yield TestClient(app)
    set_ops_context(None)  # 逐测试复位模块级上下文


# ---------------------------------------------------------------------------
# 无上下文(none provider / 装配早期):降级返回 kind + 空机群,不炸
# ---------------------------------------------------------------------------


def test_state_without_context_returns_empty(client):
    set_ops_context(None)
    body = client.get("/ops/state").json()
    assert body["kind"] == "none"
    assert body["sandboxes"] == []
    assert body["pool"] is None and body["ledger"] is None


def test_events_without_context_returns_empty(client):
    set_ops_context(None)
    body = client.get("/ops/events").json()
    assert body == {"events": [], "count": 0}


# ---------------------------------------------------------------------------
# 全量聚合:pool / ledger / supervisor / 机群 join / 状态分布
# ---------------------------------------------------------------------------


@dataclass
class _Lease:
    project_id: str
    sandbox_kind: str
    sandbox_state: str
    sandbox_id: str | None
    node: str | None = "local"
    last_activity_at: float | None = 1000.0
    snapshot_id: str | None = None


@dataclass
class _Row:
    ts: float
    project_id: str | None
    session_id: str | None
    vm_id: str | None
    event: str
    detail: dict | None


class _Pool:
    def stats(self):
        return {
            "size": 2, "idle": 1, "leased": 1, "min_size": 1, "max_size": 4,
            "replenish_breaker_open": False, "replenish_failures": 0,
        }


class _Ledger:
    mem_capacity_mib = 6000
    mem_in_use_mib = 2048
    cpu_capacity = 8
    cpu_in_use = 2


class _Supervisor:
    def loop_status(self):
        return {"reaper": True, "health": True, "metrics": True}


class _Store:
    def __init__(self, leases):
        self._leases = leases

    def list(self):
        return self._leases


class _Events:
    def __init__(self, rows):
        self._rows = rows

    def list(self, *, project_id=None, session_id=None, event=None, limit=None):
        rows = self._rows
        if event is not None:
            rows = [r for r in rows if r.event == event]
        if project_id is not None:
            rows = [r for r in rows if r.project_id == project_id]
        if session_id is not None:
            rows = [r for r in rows if r.session_id == session_id]
        rows = list(reversed(rows)) if limit else rows
        return rows[:limit] if limit else rows


def _wire(leases, rows, manager_factory=None):
    set_ops_context(
        OpsContext(
            kind="smolvm",
            pool=_Pool(),
            ledger=_Ledger(),
            supervisor=_Supervisor(),
            event_store=_Events(rows),
            store_getter=lambda: _Store(leases),
            manager_factory=manager_factory,
            quota_mem_mib=2048,
            quota_vcpus=2,
        )
    )


def test_state_aggregates_pool_ledger_supervisor(client):
    _wire(leases=[], rows=[])
    body = client.get("/ops/state").json()
    assert body["kind"] == "smolvm"
    assert body["pool"]["leased"] == 1 and body["pool"]["max_size"] == 4
    assert body["ledger"]["mem_in_use_mib"] == 2048
    assert body["supervisor"] == {"reaper": True, "health": True, "metrics": True}
    assert body["quota"] == {"mem_mib": 2048, "vcpus": 2}


def test_state_builds_sandbox_rows_and_state_counts(client):
    leases = [
        _Lease(project_id="project-running", sandbox_kind="smolvm", sandbox_state="running", sandbox_id="hagent-a-1"),
        _Lease(project_id="project-snapshot", sandbox_kind="smolvm", sandbox_state="snapshotted",
               sandbox_id="hagent-b-2", snapshot_id="snap-hagent-b-2-1"),
        _Lease(project_id="project-docker", sandbox_kind="docker", sandbox_state="running", sandbox_id="cid"),
    ]
    metrics_rows = [
        _Row(ts=900.0, project_id="project-running", session_id=None, vm_id="hagent-a-1", event="metrics",
             detail={"pid": 111, "cpu_seconds": 1.5, "rss_bytes": 200 * 1024 * 1024}),
        _Row(ts=950.0, project_id="project-running", session_id=None, vm_id="hagent-a-1", event="metrics",
             detail={"pid": 111, "cpu_seconds": 2.5, "rss_bytes": 210 * 1024 * 1024}),
    ]
    _wire(leases=leases, rows=metrics_rows)
    body = client.get("/ops/state").json()
    # 只算 smolvm active,docker session 不进机群
    assert body["state_counts"] == {"running": 1, "snapshotted": 1}
    ids = {r["project_id"] for r in body["sandboxes"]}
    assert ids == {"project-running", "project-snapshot"}
    running = next(r for r in body["sandboxes"] if r["project_id"] == "project-running")
    # 取最新一条 metrics(950 > 900):rss 210 MiB
    assert running["rss_mib"] == 210.0
    assert running["cpu_seconds"] == 2.5
    snap = next(r for r in body["sandboxes"] if r["project_id"] == "project-snapshot")
    assert snap["snapshot_id"] == "snap-hagent-b-2-1"


def test_events_returns_rows_with_detail(client):
    rows = [
        _Row(ts=1.0, project_id="p1", session_id=None, vm_id="hagent-a-1", event="created", detail=None),
        _Row(ts=2.0, project_id="p1", session_id=None, vm_id="hagent-a-1", event="health_fail",
             detail={"reason": "连续探活失败,杀重建"}),
    ]
    _wire(leases=[], rows=rows)
    body = client.get("/ops/events?limit=10").json()
    assert body["count"] == 2
    # limit 模式倒序:最新 health_fail 在前
    assert body["events"][0]["event"] == "health_fail"
    assert body["events"][0]["detail"]["reason"].startswith("连续探活")


def test_state_survives_sdk_list_vms_failure(client):
    def boom():
        raise RuntimeError("smolvm DB locked")

    _wire(
        leases=[_Lease(project_id="p1", sandbox_kind="smolvm", sandbox_state="running", sandbox_id="hagent-a-1")],
        rows=[],
        manager_factory=boom,
    )
    body = client.get("/ops/state").json()
    # SDK 挂了也要出机群(pid/status 缺失但行在)
    assert len(body["sandboxes"]) == 1
    assert body["sandboxes"][0]["pid"] is None
