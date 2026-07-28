from __future__ import annotations

import sqlite3

from hagent.server.leases import LeaseStore, SandboxState


def test_project_lease_schema_and_state_round_trip(tmp_path):
    db = tmp_path / "hagent.db"
    store = LeaseStore(db)
    lease = store.ensure("project-alpha", sandbox_kind="smolvm", node="local")
    store.update_state(
        lease.project_id,
        state=SandboxState.RUNNING.value,
        desired_state=SandboxState.RUNNING.value,
    )
    store.update_metadata(
        lease.project_id,
        sandbox_id="hagent-projecta-a1b2c3",
        materialized_revision="abc123",
    )

    saved = store.get("project-alpha")
    assert saved is not None
    assert saved.sandbox_state == "running"
    assert saved.sandbox_id == "hagent-projecta-a1b2c3"
    assert saved.materialized_revision == "abc123"

    with sqlite3.connect(db) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sandbox_leases)")}
    assert columns == {
        "project_id",
        "sandbox_id",
        "sandbox_kind",
        "sandbox_state",
        "sandbox_desired_state",
        "snapshot_id",
        "materialized_revision",
        "node",
        "last_activity_at",
        "metadata_json",
    }
