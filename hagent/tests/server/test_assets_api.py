"""REST adapter（票 07）：前端读端点与人工动作，全部经 service 层。

读输出与 MCP 工具同源（assets/schemas.py 共用模型）；人工动作审计
actor_kind=user，与 agent 写并发时乐观锁 409 + 当前 version。
"""

import pytest
from fastapi.testclient import TestClient

from hagent.assets.model import Actor
from hagent.assets.schemas import document_page_model, query_items_model
from hagent.assets.service import get_asset_service
from hagent.server.app import create_app

AGENT = Actor(kind="agent", ref="run-rest")


def make_item(i: int, *, category: str = "function", mandatory: bool = False) -> dict:
    return {
        "id": f"TECH-{i:03d}",
        "category": category,
        "title": f"需求条目 {i}",
        "requirement_text": f"第 {i} 条要求原文",
        "mandatory": mandatory,
        "source_refs": [{"document_id": "doc-00000000", "line_span": [i, i + 1]}],
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    return TestClient(create_app())


@pytest.fixture
def project(client):
    return client.post("/projects", json={"name": "REST 测试项目"}).json()["id"]


@pytest.fixture
def seeded(client, project):
    """agent 侧种子数据：technical 草稿 + 3 条 items（1 条 mandatory）+ 1 条时间线行。"""
    svc = get_asset_service()
    svc.start_draft(project, "technical", actor=AGENT)
    svc.submit_records(
        project,
        "technical",
        section="items",
        records=[make_item(1), make_item(2, category="performance", mandatory=True), make_item(3)],
        actor=AGENT,
    )
    svc.submit_records(
        project,
        "technical",
        section="deliverables",
        records=[{"name": "交付物清单", "requirement": "验收前提交"}],
        actor=AGENT,
    )
    return project


# —— 读端点 ——


def test_matrix_overview_returns_envelope_and_stats(client, seeded):
    r = client.get(f"/projects/{seeded}/matrices/technical")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["matrix_type"] == "technical"
    assert body["state"] == "drafting"
    stats = body["stats"]
    assert stats["stage"] == "draft"
    assert stats["total"] == 4
    assert stats["by_section"] == {"items": 3, "deliverables": 1}
    assert stats["mandatory_count"] == 1
    assert stats["by_response_status"] == {"unset": 3}
    assert stats["by_category"] == {"function": 2, "performance": 1}


def test_matrix_overview_empty_matrix(client, project):
    r = client.get(f"/projects/{project}/matrices/business")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "empty"
    assert body["stats"]["total"] == 0


def test_items_query_filters_match_mcp_semantics(client, seeded):
    """同一过滤/分页语义：REST 输出 == 共用模型对 service.query_items 的投影
    （MCP prose_query_matrix_items 经同一条路径构造，同参数必同结果）。"""
    params = {"category": "function", "limit": 1, "offset": 0}
    r = client.get(f"/projects/{seeded}/matrices/technical/items", params=params)
    assert r.status_code == 200, r.text

    svc = get_asset_service()
    items, total = svc.query_items(seeded, "technical", category="function", limit=1, offset=0)
    expected = query_items_model(items, total, limit=1, offset=0).model_dump(mode="json")
    assert r.json() == expected
    assert r.json()["total_count"] == 2
    assert r.json()["has_more"] is True
    assert r.json()["next_offset"] == 1


def test_items_query_deviation_projection(client, seeded):
    """偏离表投影同源：response_status 过滤即偏离表数据口径。"""
    svc = get_asset_service()
    svc.set_item_response_status(
        seeded, "technical", "TECH-002", status="negative_deviation", actor=AGENT
    )
    r = client.get(
        f"/projects/{seeded}/matrices/technical/items",
        params={"response_status": "negative_deviation"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total_count"] == 1
    assert body["items"][0]["item_id"] == "TECH-002"


def test_items_query_pagination_bounds(client, seeded):
    assert (
        client.get(f"/projects/{seeded}/matrices/technical/items", params={"limit": 0}).status_code
        == 422
    )
    assert (
        client.get(
            f"/projects/{seeded}/matrices/technical/items", params={"limit": 101}
        ).status_code
        == 422
    )
    assert (
        client.get(
            f"/projects/{seeded}/matrices/technical/items",
            params={"response_status": "不存在的状态"},
        ).status_code
        == 422
    )


def test_matrix_status_summary(client, seeded):
    r = client.get(f"/projects/{seeded}/matrices")
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == seeded
    by_type = {m["matrix_type"]: m for m in body["matrices"]}
    assert set(by_type) == {"basic_info", "business", "technical", "scoring"}
    assert by_type["technical"]["state"] == "drafting"
    assert by_type["technical"]["draft_count"] == 4
    assert by_type["technical"]["current_count"] == 0
    assert by_type["business"]["state"] == "empty"


def test_unknown_matrix_type_and_project_404(client, seeded):
    assert client.get(f"/projects/{seeded}/matrices/unknown").status_code == 422
    assert client.get("/projects/nope/matrices").status_code == 404
    assert client.get("/projects/nope/matrices/technical").status_code == 404


# —— documents 读端点（文档注册表，溯源预览取数用） ——


@pytest.fixture
def documented(client, project):
    """种子注册表：3 份文档（sha256 互异，其一 doc_type=None）。"""
    svc = get_asset_service()
    svc.register_document(
        project, path="sources/tender.md", sha256="a" * 64, doc_type="tender", actor=AGENT
    )
    svc.register_document(
        project, path="sources/amendment.md", sha256="b" * 64, doc_type="amendment", actor=AGENT
    )
    svc.register_document(
        project, path="sources/other.md", sha256="c" * 64, doc_type=None, actor=AGENT
    )
    return project


def test_documents_list_returns_registry_records(client, documented):
    """输出与共用模型对 service.list_documents 的投影一致（同源于 MCP prose_list_documents）。"""
    r = client.get(f"/projects/{documented}/documents")
    assert r.status_code == 200, r.text

    svc = get_asset_service()
    documents, total = svc.list_documents(documented, limit=20, offset=0)
    expected = document_page_model(documents, total, limit=20, offset=0).model_dump(mode="json")
    assert r.json() == expected

    body = r.json()
    assert body["total_count"] == 3
    first = body["documents"][0]
    assert first["id"].startswith("doc-")
    assert first["path"] == "sources/tender.md"
    assert first["sha256"] == "a" * 64
    assert first["doc_type"] == "tender"


def test_documents_pagination_matches_items_semantics(client, documented):
    r = client.get(f"/projects/{documented}/documents", params={"limit": 1, "offset": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_count"] == 3
    assert body["limit"] == 1
    assert body["offset"] == 1
    assert body["has_more"] is True
    assert body["next_offset"] == 2
    assert len(body["documents"]) == 1
    assert body["documents"][0]["path"] == "sources/amendment.md"

    tail = client.get(f"/projects/{documented}/documents", params={"limit": 1, "offset": 2}).json()
    assert tail["has_more"] is False
    assert tail["next_offset"] is None


def test_documents_pagination_bounds(client, documented):
    assert client.get(f"/projects/{documented}/documents", params={"limit": 0}).status_code == 422
    assert client.get(f"/projects/{documented}/documents", params={"limit": 101}).status_code == 422
    assert client.get(f"/projects/{documented}/documents", params={"offset": -1}).status_code == 422


def test_documents_empty_registry_and_missing_project(client, project):
    r = client.get(f"/projects/{project}/documents")
    assert r.status_code == 200
    body = r.json()
    assert body["documents"] == []
    assert body["total_count"] == 0
    assert body["has_more"] is False
    assert body["next_offset"] is None

    assert client.get("/projects/nope/documents").status_code == 404


# —— 人工动作（写端点，audit actor_kind=user） ——


def test_confirm_item_records_user_audit(client, seeded):
    r = client.post(f"/projects/{seeded}/matrices/technical/items/TECH-001/confirm")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["confirmed"] is True
    assert body["version"] == 2

    svc = get_asset_service()
    confirm_events = svc.list_events(seeded, action="confirm_matrix_item")
    assert len(confirm_events) == 1
    assert confirm_events[0].actor_kind == "user"
    # 种子写入的 agent 事件与人工动作可区分
    submit_events = svc.list_events(seeded, action="submit_matrix_records")
    assert all(e.actor_kind == "agent" for e in submit_events)


def test_set_response_status_via_rest(client, seeded):
    r = client.put(
        f"/projects/{seeded}/matrices/technical/items/TECH-001/response-status",
        json={"status": "negative_deviation", "note": "仅支持每秒五百次并发", "reason": "用户标注"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["response_status"] == "negative_deviation"
    assert body["response_note"] == "仅支持每秒五百次并发"

    svc = get_asset_service()
    events = svc.list_events(seeded, action="set_item_response_status")
    assert events[-1].actor_kind == "user"
    assert events[-1].reason == "用户标注"


def test_set_response_status_rejects_invalid_input(client, seeded, project):
    # 未知状态值：请求模型 Literal 拦截
    assert (
        client.put(
            f"/projects/{seeded}/matrices/technical/items/TECH-001/response-status",
            json={"status": "不存在"},
        ).status_code
        == 422
    )
    # basic_info 不支持应答状态：service 裁决 → 400 + 结构化错误
    svc = get_asset_service()
    svc.start_draft(project, "basic_info", actor=AGENT)
    svc.submit_records(
        project, "basic_info", section="timeline",
        records=[{"event": "开标", "time": "2026-08-01"}], actor=AGENT,
    )
    r = client.put(
        f"/projects/{project}/matrices/basic_info/items/whatever/response-status",
        json={"status": "compliant"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_argument"


def test_item_not_found_maps_to_404(client, seeded):
    r = client.post(f"/projects/{seeded}/matrices/technical/items/TECH-999/confirm")
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert detail["code"] == "item_not_found"
    assert detail["hint"]


def test_concurrent_agent_write_conflicts_with_409(client, seeded):
    """人工动作与 agent 写并发：用户基于陈旧 version 提交 → 409 + 当前 version。"""
    svc = get_asset_service()
    # 用户在前端看到 version=1；此时 agent 把条目推进到 version=2
    svc.update_item(
        seeded, "technical", "TECH-001", set={"mandatory": True}, actor=AGENT
    )
    r = client.post(
        f"/projects/{seeded}/matrices/technical/items/TECH-001/confirm",
        json={"expected_version": 1},
    )
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["code"] == "version_conflict"
    assert detail["current_version"] == 2

    r2 = client.put(
        f"/projects/{seeded}/matrices/technical/items/TECH-001/response-status",
        json={"status": "compliant", "expected_version": 1},
    )
    assert r2.status_code == 409
    assert r2.json()["detail"]["current_version"] == 2

    # 以最新 version 重试成功
    r3 = client.post(
        f"/projects/{seeded}/matrices/technical/items/TECH-001/confirm",
        json={"expected_version": detail["current_version"]},
    )
    assert r3.status_code == 200
    assert r3.json()["confirmed"] is True


def test_asset_endpoints_require_api_key_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.setenv("HAGENT_API_KEY", "sk-test")
    client = TestClient(create_app())
    assert client.get("/projects/p/matrices").status_code == 401
    assert client.get("/projects/p/documents").status_code == 401
    assert (
        client.get(
            "/projects/p/matrices", headers={"Authorization": "Bearer sk-test"}
        ).status_code
        == 404
    )
    assert (
        client.get(
            "/projects/p/documents", headers={"Authorization": "Bearer sk-test"}
        ).status_code
        == 404
    )
