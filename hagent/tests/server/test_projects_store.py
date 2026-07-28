import time

import pytest

from hagent.server.projects import (
    PROJECT_STATUS_ACTIVE,
    PROJECT_STATUS_DELETED,
    ProjectState,
    ProjectStore,
)
from hagent.server.sessions import SessionStore


@pytest.fixture
def store(tmp_path):
    return ProjectStore(db_path=tmp_path / "sessions.db")


def test_create_returns_new_project(store):
    p = store.create("测试招标项目")
    assert isinstance(p, ProjectState)
    assert p.id
    assert p.name == "测试招标项目"
    assert p.status == PROJECT_STATUS_ACTIVE
    assert p.created_at > 0
    assert p.updated_at == p.created_at
    assert p.metadata_json is None


def test_get_round_trips(store):
    p = store.create("项目A", metadata_json='{"doc_name": "招标文件.md"}')
    p2 = store.get(p.id)
    assert p2 is not None
    assert p2.name == "项目A"
    assert p2.metadata_json == '{"doc_name": "招标文件.md"}'


def test_get_missing_returns_none(store):
    assert store.get("nope") is None


def test_list_orders_by_updated_at_desc(store):
    a = store.create("项目A")
    time.sleep(0.01)
    b = store.create("项目B")
    assert [p.id for p in store.list()] == [b.id, a.id]
    time.sleep(0.01)
    store.touch(a.id)
    assert [p.id for p in store.list()] == [a.id, b.id]


def test_update_fields_and_bumps_updated_at(store):
    p = store.create("旧名")
    time.sleep(0.01)
    updated = store.update(p.id, name="新名", status="parsed", metadata_json='{"k": 1}')
    assert updated.name == "新名"
    assert updated.status == "parsed"
    assert updated.metadata_json == '{"k": 1}'
    assert updated.updated_at > p.updated_at


def test_update_partial_keeps_other_fields(store):
    p = store.create("项目A", metadata_json='{"k": 1}')
    updated = store.update(p.id, status="parsed")
    assert updated.name == "项目A"
    assert updated.metadata_json == '{"k": 1}'


def test_update_missing_raises_keyerror(store):
    with pytest.raises(KeyError):
        store.update("nope", name="x")


def test_delete_soft_deletes(store):
    p = store.create("项目A")
    store.delete(p.id)
    assert all(x.id != p.id for x in store.list())
    listed = store.list(include_deleted=True)
    assert any(x.id == p.id and x.status == PROJECT_STATUS_DELETED for x in listed)
    # get 仍可查(镜像 sessions 的 ended 语义)
    assert store.get(p.id).status == PROJECT_STATUS_DELETED


def test_metadata_json_round_trips_chinese(store):
    p = store.create("项目A", metadata_json='{"doc_name": "仿真软件招标文件.md"}')
    assert store.get(p.id).metadata_json == '{"doc_name": "仿真软件招标文件.md"}'


def test_coexists_with_session_store_in_same_db(store, tmp_path):
    # projects 与 sessions 共用同一个 sqlite 文件(app.py 同一 db_path),两表互不干扰。
    sessions = SessionStore(db_path=tmp_path / "sessions.db")
    p = store.create("项目A")
    s = sessions.create(project_id=p.id)
    assert store.get(p.id).name == "项目A"
    assert sessions.get(s.id).project_id == p.id
