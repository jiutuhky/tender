from tests.server.helpers import create_project_session
import json
import sqlite3
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from hagent.server.app import create_app
from hagent.server.routers.messages import _expand_skill_message, _stream_agent_events
from hagent.server.workspace_checkpoint import CheckpointFailure, CheckpointResult
from hagent.task_tools.models import Task, TaskListItem


class FakeAgent:
    stream_kwargs = None

    def stream(self, *_args, **_kwargs):
        type(self).stream_kwargs = _kwargs
        # 模拟 messages 模式输出一个简单字符片段，再触发 done
        class FakeAIChunk:
            type = "AIMessageChunk"
            content = "ok"
            tool_call_chunks = []

        # subgraphs=True 格式：(namespace_tuple, mode, payload)
        yield ((), "messages", (FakeAIChunk(), {}))


def test_post_message_returns_sse(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: FakeAgent(),
    )
    app = create_app()
    client = TestClient(app)

    r = create_project_session(client)
    sid = r.json()["session_id"]

    with client.stream("POST", f"/sessions/{sid}/messages", json={"content": "hi"}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = b"".join(r.iter_bytes())
        assert b"event: message.delta" in body
        assert b'"content_chunk": "ok"' in body
    assert b"event: done" in body
    assert FakeAgent.stream_kwargs is not None
    config = FakeAgent.stream_kwargs["config"]
    assert config == {"configurable": {"thread_id": sid}}


def test_post_message_checkpoints_workspace_before_done(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    db = tmp_path / "h.sqlite"
    monkeypatch.setenv("HAGENT_DB_PATH", str(db))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    class WritingAgent:
        def __init__(self, workspace_dir):
            self.workspace_dir = workspace_dir

        def stream(self, *_args, **_kwargs):
            from pathlib import Path

            target = Path(self.workspace_dir) / "deliverables" / "技术方案.md"
            target.write_text("第一轮成果", encoding="utf-8")
            yield from ()

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: WritingAgent(wd),
    )
    app = create_app()
    client = TestClient(app)
    session = create_project_session(client).json()

    with client.stream(
        "POST",
        f"/sessions/{session['session_id']}/messages",
        json={"content": "生成技术方案"},
    ) as response:
        body = b"".join(response.iter_bytes()).decode("utf-8")

    assert body.index("event: run.started") < body.index(
        "event: workspace.checkpointed"
    ) < body.index("event: done")
    from hagent.server.project_workspace import ProjectWorkspace
    from hagent.server.runs import RunStatus, RunStore

    runs = RunStore(db).active_for_project(session["project_id"])
    assert runs == []
    history = ProjectWorkspace(tmp_path / "workspaces").history(session["project_id"])
    assert history[0].kind == "chat_turn"
    assert history[0].session_id == session["session_id"]
    assert history[0].run_id in body
    saved = RunStore(db).get(history[0].run_id)
    assert saved is not None
    assert saved.status is RunStatus.COMMITTED
    assert saved.base_revision is not None
    assert saved.commit_sha == history[0].sha


def test_post_message_without_file_changes_finishes_as_noop_run(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    db = tmp_path / "h.sqlite"
    monkeypatch.setenv("HAGENT_DB_PATH", str(db))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: FakeAgent(),
    )
    client = TestClient(create_app())
    session = create_project_session(client).json()

    with client.stream(
        "POST",
        f"/sessions/{session['session_id']}/messages",
        json={"content": "只回答问题"},
    ) as response:
        body = b"".join(response.iter_bytes()).decode("utf-8")

    assert "event: run.started" in body
    assert "event: workspace.checkpointed" not in body
    assert "event: done" in body
    from hagent.server.runs import RunStatus, RunStore

    with sqlite3.connect(db) as conn:
        run_id = conn.execute("SELECT id FROM runs").fetchone()[0]
    saved = RunStore(db).get(run_id)
    assert saved is not None
    assert saved.status is RunStatus.COMMITTED
    assert saved.commit_sha is None


def test_agent_error_best_effort_checkpoints_partial_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    db = tmp_path / "h.sqlite"
    monkeypatch.setenv("HAGENT_DB_PATH", str(db))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    class FailingAgent:
        def __init__(self, workspace_dir):
            self.workspace_dir = workspace_dir

        def stream(self, *_args, **_kwargs):
            from pathlib import Path

            target = Path(self.workspace_dir) / "deliverables" / "未完稿.md"
            target.write_text("已生成的部分", encoding="utf-8")
            raise RuntimeError("模型连接中断")
            yield  # pragma: no cover

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: FailingAgent(wd),
    )
    client = TestClient(create_app())
    session = create_project_session(client).json()

    with client.stream(
        "POST",
        f"/sessions/{session['session_id']}/messages",
        json={"content": "生成未完稿"},
    ) as response:
        body = b"".join(response.iter_bytes()).decode("utf-8")

    assert body.index("event: workspace.checkpointed") < body.index("event: error")
    assert "event: done" not in body
    from hagent.server.project_workspace import ProjectWorkspace
    from hagent.server.runs import RunStatus, RunStore

    history = ProjectWorkspace(tmp_path / "workspaces").history(session["project_id"])
    saved = RunStore(db).get(history[0].run_id)
    assert saved is not None
    assert saved.status is RunStatus.INTERRUPTED
    assert saved.commit_sha == history[0].sha
    assert saved.error == "模型连接中断"
    assert history[0].interrupted is True


def test_closing_message_stream_marks_checkpoint_interrupted():
    checkpoints: list[dict] = []

    class StreamingAgent:
        def stream(self, *_args, **_kwargs):
            while True:
                class FakeAIChunk:
                    type = "AIMessageChunk"
                    content = "片段"
                    tool_call_chunks = []

                yield ((), "messages", (FakeAIChunk(), {}))

    def checkpoint(**kwargs):
        checkpoints.append(kwargs)
        return CheckpointResult("run-one", None, ())

    stream = _stream_agent_events(
        StreamingAgent(),
        "继续生成",
        "session-one",
        run_id="run-one",
        checkpoint=checkpoint,
    )
    next(stream)
    next(stream)

    stream.close()

    assert checkpoints == [
        {"interrupted": True, "error": "客户端断连或用户打断"}
    ]


def test_checkpoint_error_keeps_persisted_file_list_and_uses_distinct_code():
    def checkpoint(**_kwargs):
        raise CheckpointFailure(
            "guest 基线推进失败",
            result=CheckpointResult(
                "run-one",
                "commit-sha",
                ("deliverables/技术方案.md",),
            ),
        )

    body = b"".join(
        _stream_agent_events(
            FakeAgent(),
            "生成方案",
            "session-one",
            run_id="run-one",
            checkpoint=checkpoint,
        )
    ).decode("utf-8")

    assert "event: workspace.checkpointed" in body
    assert '"files_changed": ["deliverables/技术方案.md"]' in body
    assert '"code": "workspace_checkpoint_error"' in body
    assert "event: done" not in body


def test_sandbox_initialization_error_interrupts_run_instead_of_rejecting(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    db = tmp_path / "h.sqlite"
    monkeypatch.setenv("HAGENT_DB_PATH", str(db))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    client = TestClient(create_app(), raise_server_exceptions=False)
    session = create_project_session(client).json()
    monkeypatch.setattr(
        "hagent.server.routers.messages._session_sandbox",
        lambda sid, *, rebuild=False: (_ for _ in ()).throw(RuntimeError("启动失败")),
    )

    response = client.post(
        f"/sessions/{session['session_id']}/messages",
        json={"content": "开始生成"},
    )

    assert response.status_code == 500
    from hagent.server.runs import RunStatus, RunStore

    with sqlite3.connect(db) as conn:
        run_id = conn.execute("SELECT id FROM runs").fetchone()[0]
    saved = RunStore(db).get(run_id)
    assert saved.status is RunStatus.INTERRUPTED
    assert saved.error == "启动失败"


def test_post_message_404_on_missing_session(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)
    r = client.post("/sessions/nope/messages", json={"content": "hi"})
    assert r.status_code == 404


def test_expand_skill_message_converts_skill_prefix() -> None:
    assert (
        _expand_skill_message("/skill:review src tests")
        == 'Use the `Skill` tool with skill: "review" and args: "src tests".'
    )


def test_expand_skill_message_leaves_normal_message_alone() -> None:
    assert _expand_skill_message("review this code") == "review this code"


def test_get_messages_preserves_content_blocks(tmp_path, monkeypatch):
    """历史回放保留 list-of-content-blocks 原结构，不 str() 成 repr 串。"""
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    blocks = [
        {"type": "thinking", "thinking": "推理中"},
        {"type": "text", "text": "答案"},
    ]

    class FakeAIMessage:
        type = "ai"
        content = blocks

    class FakeState:
        values = {"messages": [FakeAIMessage()]}

    class HistoryFakeAgent:
        def stream(self, *_a, **_kw):
            yield from ()

        def get_state(self, _cfg):
            return FakeState()

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: HistoryFakeAgent(),
    )
    app = create_app()
    client = TestClient(app)
    r = create_project_session(client)
    sid = r.json()["session_id"]
    r = client.get(f"/sessions/{sid}/messages")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["role"] == "ai"
    assert body[0]["content"] == blocks  # list 原样保留


def test_get_messages_returns_history_after_post(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    class FakeState:
        values = {"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "ok"}]}

    class FakeAgent:
        def stream(self, *_a, **_kw):
            yield from ()

        def get_state(self, _cfg):
            return FakeState()

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: FakeAgent(),
    )
    app = create_app()
    client = TestClient(app)
    r = create_project_session(client)
    sid = r.json()["session_id"]
    r = client.get(f"/sessions/{sid}/messages")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_todos_returns_list(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    class FakeState:
        values = {"todos": [{"content": "do x", "status": "pending"}]}

    class FakeAgent:
        def stream(self, *_a, **_kw):
            yield from ()

        def get_state(self, _cfg):
            return FakeState()

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: FakeAgent(),
    )
    app = create_app()
    client = TestClient(app)
    r = create_project_session(client)
    sid = r.json()["session_id"]
    r = client.get(f"/sessions/{sid}/todos")
    assert r.status_code == 200
    assert r.json() == [{"content": "do x", "status": "pending"}]


def test_get_todos_prefers_task_store_over_legacy_state(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    class FakeState:
        values = {"todos": [{"content": "legacy todo", "status": "pending"}]}

    class FakeTaskStore:
        def list_tasks(self):
            return [
                Task(
                    id="1",
                    subject="Task store todo",
                    description="Use task store state.",
                    status="in_progress",
                    blocks=[],
                    blockedBy=[],
                )
            ]

    class FakeAgent:
        _hagent_task_store = FakeTaskStore()

        def stream(self, *_a, **_kw):
            yield from ()

        def get_state(self, _cfg):
            return FakeState()

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: FakeAgent(),
    )
    app = create_app()
    client = TestClient(app)
    sid = create_project_session(client).json()["session_id"]

    r = client.get(f"/sessions/{sid}/todos")

    assert r.status_code == 200
    assert r.json() == [
        {
            "content": "Task store todo",
            "status": "in_progress",
            "id": "1",
            "description": "Use task store state.",
            "blockedBy": [],
        }
    ]


def test_get_todos_filters_completed_blockers_in_task_store_projection(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    class FakeState:
        values = {"todos": [{"content": "legacy todo", "status": "pending"}]}

    class FakeTaskStore:
        def list_tasks(self):
            return [
                Task(
                    id="1",
                    subject="Completed blocker",
                    description="Already done.",
                    status="completed",
                    blocks=[],
                    blockedBy=[],
                ),
                Task(
                    id="2",
                    subject="Blocked task",
                    description="Should no longer show completed blockers.",
                    status="pending",
                    blocks=[],
                    blockedBy=["1"],
                    owner="coder",
                ),
            ]

        def list_task_items(self):
            return [
                TaskListItem(
                    id="1",
                    subject="Completed blocker",
                    status="completed",
                    blockedBy=[],
                ),
                TaskListItem(
                    id="2",
                    subject="Blocked task",
                    status="pending",
                    owner="coder",
                    blockedBy=[],
                ),
            ]

    class FakeAgent:
        _hagent_task_store = FakeTaskStore()

        def stream(self, *_a, **_kw):
            yield from ()

        def get_state(self, _cfg):
            return FakeState()

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: FakeAgent(),
    )
    app = create_app()
    client = TestClient(app)
    sid = create_project_session(client).json()["session_id"]

    r = client.get(f"/sessions/{sid}/todos")

    assert r.status_code == 200
    assert r.json()[1] == {
        "content": "Blocked task",
        "status": "pending",
        "id": "2",
        "description": "Should no longer show completed blockers.",
        "blockedBy": [],
        "owner": "coder",
    }


def test_get_todos_falls_back_to_legacy_state_when_task_store_breaks(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    class FakeState:
        values = {"todos": [{"content": "legacy todo", "status": "pending"}]}

    class BrokenTaskStore:
        def list_tasks(self):
            raise RuntimeError("task store unavailable")

    class FakeAgent:
        _hagent_task_store = BrokenTaskStore()

        def stream(self, *_a, **_kw):
            yield from ()

        def get_state(self, _cfg):
            return FakeState()

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: FakeAgent(),
    )
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    sid = create_project_session(client).json()["session_id"]

    r = client.get(f"/sessions/{sid}/todos")

    assert r.status_code == 200
    assert r.json() == [{"content": "legacy todo", "status": "pending"}]


def test_post_message_streams_todo_updated_after_task_tool_completion(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    class FakeToolMessage:
        type = "tool"
        content = "Updated task 1"
        tool_call_id = "abc"
        name = "TaskUpdate"

    class FakeTaskStore:
        def list_tasks(self):
            return [
                Task(
                    id="1",
                    subject="Run tests",
                    description="Run the focused server tests.",
                    status="completed",
                    blocks=[],
                    blockedBy=[],
                )
            ]

    class FakeAgent:
        _hagent_task_store = FakeTaskStore()

        def stream(self, *_a, **_kw):
            yield ((), "messages", (FakeToolMessage(), {}))

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: FakeAgent(),
    )
    app = create_app()
    client = TestClient(app)
    sid = create_project_session(client).json()["session_id"]

    with client.stream("POST", f"/sessions/{sid}/messages", json={"content": "hi"}) as r:
        assert r.status_code == 200
        body = b"".join(r.iter_bytes()).decode("utf-8")

    assert "event: tool_call.completed" in body
    assert "event: todo.refresh_requested" not in body
    assert "event: todo.updated" in body
    assert json.dumps(
        {
            "todos": [
                {
                    "content": "Run tests",
                    "status": "completed",
                    "id": "1",
                    "description": "Run the focused server tests.",
                    "blockedBy": [],
                }
            ]
        }
    ) in body


def test_post_message_stream_filters_completed_blockers_in_todo_updated(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    class FakeToolMessage:
        type = "tool"
        content = "Updated task 2"
        tool_call_id = "abc"
        name = "TaskUpdate"

    class FakeTaskStore:
        def list_tasks(self):
            return [
                Task(
                    id="1",
                    subject="Completed blocker",
                    description="Already done.",
                    status="completed",
                    blocks=[],
                    blockedBy=[],
                ),
                Task(
                    id="2",
                    subject="Blocked task",
                    description="Should no longer show completed blockers.",
                    status="pending",
                    blocks=[],
                    blockedBy=["1"],
                ),
            ]

        def list_task_items(self):
            return [
                TaskListItem(
                    id="1",
                    subject="Completed blocker",
                    status="completed",
                    blockedBy=[],
                ),
                TaskListItem(
                    id="2",
                    subject="Blocked task",
                    status="pending",
                    blockedBy=[],
                ),
            ]

    class FakeAgent:
        _hagent_task_store = FakeTaskStore()

        def stream(self, *_a, **_kw):
            yield ((), "messages", (FakeToolMessage(), {}))

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: FakeAgent(),
    )
    app = create_app()
    client = TestClient(app)
    sid = create_project_session(client).json()["session_id"]

    with client.stream("POST", f"/sessions/{sid}/messages", json={"content": "hi"}) as r:
        assert r.status_code == 200
        body = b"".join(r.iter_bytes()).decode("utf-8")

    assert json.dumps(
        {
            "todos": [
                {
                    "content": "Completed blocker",
                    "status": "completed",
                    "id": "1",
                    "description": "Already done.",
                    "blockedBy": [],
                },
                {
                    "content": "Blocked task",
                    "status": "pending",
                    "id": "2",
                    "description": "Should no longer show completed blockers.",
                    "blockedBy": [],
                },
            ]
        }
    ) in body


def test_post_message_suppresses_refresh_when_task_store_breaks(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    class FakeToolMessage:
        type = "tool"
        content = "Updated task 1"
        tool_call_id = "abc"
        name = "TaskUpdate"

    class BrokenTaskStore:
        def list_tasks(self):
            raise RuntimeError("task store unavailable")

    class FakeAgent:
        _hagent_task_store = BrokenTaskStore()

        def stream(self, *_a, **_kw):
            yield ((), "messages", (FakeToolMessage(), {}))

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: FakeAgent(),
    )
    app = create_app()
    client = TestClient(app)
    sid = create_project_session(client).json()["session_id"]

    with client.stream("POST", f"/sessions/{sid}/messages", json={"content": "hi"}) as r:
        assert r.status_code == 200
        body = b"".join(r.iter_bytes()).decode("utf-8")

    assert "event: tool_call.completed" in body
    assert "event: todo.updated" not in body
    assert "event: error" not in body
    assert "event: done" in body


def test_post_message_passes_manager_sandbox_to_get_or_build_agent(tmp_path, monkeypatch):
    """Regression: when SessionManager holds a sandbox lease for the session,
    messages router must thread that sandbox into get_or_build_agent so
    create_hagent() does NOT auto-start a second container behind its back."""
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    captured = {}
    fake_sandbox_marker = MagicMock()
    fake_sandbox_marker.id = "sandbox-test-marker"
    fake_sandbox_marker.workspace_dir = "/workspace"
    fake_sandbox_marker.execute.return_value = MagicMock(exit_code=0, output="")
    fake_sandbox_marker.upload_files.return_value = [MagicMock(error=None)]

    def recorder(sid, wd, *, project_id=None, sandbox=None):
        captured["sid"] = sid
        captured["sandbox"] = sandbox

        class _Agent:
            def stream(self, *_a, **_kw):
                class _Chunk:
                    type = "AIMessageChunk"
                    content = "ok"
                    tool_call_chunks = []
                yield ((), "messages", (_Chunk(), {}))

            def get_state(self, _cfg):
                class _S:
                    values = {}
                return _S()

        return _Agent()

    monkeypatch.setattr("hagent.server.routers.messages.get_or_build_agent", recorder)
    app = create_app()
    client = TestClient(app)
    sid = create_project_session(client).json()["session_id"]

    # 向 manager 的项目租约映射注入沙箱。
    from hagent.server.routers.sessions import get_session_manager
    from hagent.sandbox.pool import SandboxLease
    mgr = get_session_manager()
    project_id = mgr.store.get(sid).project_id
    mgr._leases[project_id] = SandboxLease(
        sandbox=fake_sandbox_marker, project_id=project_id
    )

    with client.stream("POST", f"/sessions/{sid}/messages", json={"content": "hi"}) as r:
        assert r.status_code == 200
        b"".join(r.iter_bytes())

    assert captured["sandbox"] is fake_sandbox_marker


def test_get_todos_passes_manager_sandbox_to_get_or_build_agent(tmp_path, monkeypatch):
    """GET /todos is what the frontend hits first (useEffect tick) — must also
    forward the manager-held sandbox so we don't double-spin on first poll."""
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    captured = {}
    fake_sandbox_marker = object()

    def recorder(sid, wd, *, project_id=None, sandbox=None):
        captured["sandbox"] = sandbox

        class _Agent:
            def get_state(self, _cfg):
                class _S:
                    values = {"todos": []}
                return _S()

        return _Agent()

    monkeypatch.setattr("hagent.server.routers.messages.get_or_build_agent", recorder)
    app = create_app()
    client = TestClient(app)
    sid = create_project_session(client).json()["session_id"]

    from hagent.server.routers.sessions import get_session_manager
    from hagent.sandbox.pool import SandboxLease
    mgr = get_session_manager()
    project_id = mgr.store.get(sid).project_id
    mgr._leases[project_id] = SandboxLease(
        sandbox=fake_sandbox_marker, project_id=project_id
    )

    r = client.get(f"/sessions/{sid}/todos")
    assert r.status_code == 200
    assert captured["sandbox"] is fake_sandbox_marker


def test_post_message_passes_session_project_to_get_or_build_agent(tmp_path, monkeypatch):
    """项目绑定必须由 server 打给 agent 的 MCP 连接：sandbox 里的 agent 只看得见
    /workspace，无从得知自己的 hagent project_id——不绑定它就只能猜（2026-07-13 事故：
    猜成了招标文件正文里的项目编号，写脏幽灵命名空间并 flail 到沙箱被杀）。"""
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)

    captured = {}

    def recorder(sid, wd, *, project_id=None, sandbox=None):
        captured["project_id"] = project_id
        return FakeAgent()

    monkeypatch.setattr("hagent.server.routers.messages.get_or_build_agent", recorder)
    app = create_app()
    client = TestClient(app)
    session = create_project_session(client).json()
    sid = session["session_id"]

    with client.stream("POST", f"/sessions/{sid}/messages", json={"content": "hi"}) as r:
        assert r.status_code == 200
        r.read()

    from hagent.server.routers.sessions import get_session_manager

    assert captured["project_id"] == get_session_manager().store.get(sid).project_id
    assert captured["project_id"]  # 非空：会话必归属项目（spec §4.4）


def test_interrupt_endpoint_accepts_decision(tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)
    sid = create_project_session(client).json()["session_id"]
    r = client.post(
        f"/sessions/{sid}/interrupt",
        json={"interrupt_id": "abc", "decision": "approve"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ---------------------------------------------------------------------------
# 轮末 checkpoint 三路归一进 finally + 取消路径 + run 中沙箱事件即时冲刷
# ---------------------------------------------------------------------------


class _AIChunk:
    type = "AIMessageChunk"
    content = "片段"
    tool_call_chunks = []


def _collect_checkpoints():
    calls: list[dict] = []

    def checkpoint(**kwargs):
        calls.append(kwargs)
        return CheckpointResult("run-one", None, ())

    return calls, checkpoint


def test_stream_checkpoints_exactly_once_on_success():
    calls, checkpoint = _collect_checkpoints()
    body = b"".join(
        _stream_agent_events(FakeAgent(), "x", "s", run_id="run-one", checkpoint=checkpoint)
    ).decode("utf-8")
    assert calls == [{"interrupted": False, "error": None}]
    assert body.rstrip().endswith('{"thread_id": "s"}') or "event: done" in body


def test_stream_checkpoints_exactly_once_on_agent_error():
    class ExplodingAgent:
        def stream(self, *_a, **_k):
            yield ((), "messages", (_AIChunk(), {}))
            raise RuntimeError("model down")

    calls, checkpoint = _collect_checkpoints()
    body = b"".join(
        _stream_agent_events(ExplodingAgent(), "x", "s", run_id="run-one", checkpoint=checkpoint)
    ).decode("utf-8")
    assert calls == [{"interrupted": True, "error": "model down"}]
    assert '"code": "agent_error"' in body
    assert "event: done" not in body


def test_stream_checkpoints_exactly_once_on_generator_exit():
    class Endless:
        def stream(self, *_a, **_k):
            while True:
                yield ((), "messages", (_AIChunk(), {}))

    calls, checkpoint = _collect_checkpoints()
    stream = _stream_agent_events(Endless(), "x", "s", run_id="run-one", checkpoint=checkpoint)
    next(stream)
    next(stream)
    stream.close()
    assert calls == [{"interrupted": True, "error": "客户端断连或用户打断"}]


def test_stream_terminates_with_sandbox_unavailable_when_run_cancelled():
    """健康杀重建把 Run 取消后,消息流必须终止本轮而不是让模型继续跑在死 VM 上。"""

    class Endless:
        def stream(self, *_a, **_k):
            while True:
                yield ((), "messages", (_AIChunk(), {}))

    calls, checkpoint = _collect_checkpoints()
    seen = {"n": 0}

    def cancel_check():
        seen["n"] += 1
        return "沙箱健康巡检杀重建,本轮已中断" if seen["n"] >= 3 else None

    body = b"".join(
        _stream_agent_events(
            Endless(),
            "x",
            "s",
            run_id="run-one",
            checkpoint=checkpoint,
            cancel_check=cancel_check,
        )
    ).decode("utf-8")
    assert calls == [{"interrupted": True, "error": "沙箱健康巡检杀重建,本轮已中断"}]
    assert '"code": "sandbox_unavailable"' in body
    assert "event: done" not in body


def test_stream_flushes_sandbox_events_mid_run():
    from hagent.server import sse as sse_mod

    class TwoChunkAgent:
        def stream(self, *_a, **_k):
            yield ((), "messages", (_AIChunk(), {}))
            # 后台线程在 run 中途推入的生命周期事件
            sse_mod.push_sandbox_event(
                sse_mod.SandboxEvent(kind="paused", session_id="s-mid", sandbox_id="smolvm-x")
            )
            yield ((), "messages", (_AIChunk(), {}))

    frames = list(_stream_agent_events(TwoChunkAgent(), "x", "s-mid", run_id="run-one"))
    body = b"".join(frames).decode("utf-8")
    assert "event: sandbox.paused" in body
    # 出现在 done 之前(run 中即时可见),而不是只在下一轮流首冲刷
    assert body.index("event: sandbox.paused") < body.index("event: done")
