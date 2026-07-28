from __future__ import annotations

import time

import pytest

from hagent.server.sessions import SessionState, SessionStatus, SessionStore


@pytest.fixture
def store(tmp_path):
    return SessionStore(db_path=tmp_path / "hagent.sqlite")


def test_create_returns_project_conversation(store):
    session = store.create(project_id="project-1")
    assert isinstance(session, SessionState)
    assert session.project_id == "project-1"
    assert session.status == SessionStatus.ACTIVE


def test_create_requires_project(store):
    with pytest.raises((TypeError, ValueError)):
        store.create(project_id="")


def test_get_list_delete_and_touch(store):
    session = store.create(project_id="project-1")
    before = session.last_active
    time.sleep(0.01)
    store.touch(session.id)
    assert store.get(session.id).last_active > before
    assert [item.id for item in store.list(project_id="project-1")] == [session.id]
    store.delete(session.id)
    assert store.get(session.id).status == SessionStatus.ENDED


def test_list_filters_projects_and_latest_per_project(store):
    old = store.create(project_id="project-1")
    time.sleep(0.01)
    new = store.create(project_id="project-1")
    other = store.create(project_id="project-2")

    assert [session.id for session in store.list(project_id="project-1")] == [new.id, old.id]
    latest = store.latest_per_project()
    assert latest["project-1"].id == new.id
    assert latest["project-2"].id == other.id
