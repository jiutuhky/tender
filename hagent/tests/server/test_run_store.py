from __future__ import annotations

import sqlite3

from hagent.server.runs import RunStatus, RunStore


def test_runs_schema_matches_project_execution_contract(tmp_path):
    db = tmp_path / "hagent.db"
    RunStore(db)

    with sqlite3.connect(db) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
        indexes = {row[1] for row in conn.execute("PRAGMA index_list(runs)")}

    assert columns == {
        "id",
        "project_id",
        "kind",
        "session_id",
        "node_id",
        "status",
        "base_revision",
        "commit_sha",
        "owned_paths",
        "error",
        "created_at",
        "finished_at",
        "metadata_json",
    }
    assert {"idx_runs_project", "idx_runs_active"} <= indexes


def test_chat_turn_run_records_revision_and_terminal_checkpoint(tmp_path):
    store = RunStore(tmp_path / "hagent.db")

    run = store.create_chat_turn(
        project_id="project-alpha",
        session_id="session-one",
        base_revision="base-sha",
        summary="chat_turn: 生成技术方案",
    )
    store.mark_running(run.id)
    finished = store.finish(
        run.id,
        status=RunStatus.COMMITTED,
        commit_sha="commit-sha",
    )

    assert finished.project_id == "project-alpha"
    assert finished.session_id == "session-one"
    assert finished.kind == "chat_turn"
    assert finished.base_revision == "base-sha"
    assert finished.commit_sha == "commit-sha"
    assert finished.status is RunStatus.COMMITTED
    assert finished.finished_at is not None
    assert store.active_for_project("project-alpha") == []


def test_active_runs_survive_new_store_instance_for_lifecycle_recovery(tmp_path):
    db = tmp_path / "hagent.db"
    first = RunStore(db)
    run = first.create_chat_turn(
        project_id="project-alpha",
        session_id="session-one",
        base_revision="base-sha",
        summary="chat_turn: 编写商务条款",
    )
    first.mark_running(run.id)

    active = RunStore(db).active_for_project("project-alpha")

    assert [item.id for item in active] == [run.id]
    assert active[0].summary == "chat_turn: 编写商务条款"


def test_startup_recovery_marks_nonterminal_runs_interrupted(tmp_path):
    store = RunStore(tmp_path / "hagent.db")
    run = store.create_chat_turn(
        project_id="project-alpha",
        session_id="session-one",
        base_revision="base-sha",
        summary="chat_turn: 生成过程中重启",
    )
    store.mark_running(run.id)

    recovered = store.interrupt_active(error="server 重启中断未完成 Run")

    assert [item.id for item in recovered] == [run.id]
    assert recovered[0].status is RunStatus.INTERRUPTED
    assert recovered[0].error == "server 重启中断未完成 Run"
