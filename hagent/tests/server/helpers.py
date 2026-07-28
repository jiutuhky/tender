from __future__ import annotations

import uuid


def create_project_session(client, payload: dict | None = None):
    project = client.post(
        "/projects", json={"name": f"测试项目-{uuid.uuid4().hex[:8]}"}
    )
    assert project.status_code == 200, project.text
    body = dict(payload or {})
    body["project_id"] = project.json()["id"]
    return client.post("/sessions", json=body)
