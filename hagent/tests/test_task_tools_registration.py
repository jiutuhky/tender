from deepagents.backends import FilesystemBackend

from hagent.config import HagentConfig
from hagent.core import create_hagent
from hagent.server import agents


def test_create_hagent_registers_task_tools_before_extra_tools(monkeypatch, tmp_path):
    from langchain_core.tools import tool

    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return type("FakeAgent", (), {})()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    backend = FilesystemBackend(root_dir=tmp_path, virtual_mode=False)

    @tool("ExtraTool")
    def extra_tool(value: str) -> str:
        """Extra tool used to verify registration ordering."""
        return value

    create_hagent(
        config=HagentConfig(
            model="anthropic:claude-sonnet-4-6",
            langsmith_tracing=False,
            skills_paths=str(tmp_path / "no-skills"),
        ),
        backend=backend,
        extra_tools=[extra_tool],
    )

    tool_names = [tool.name for tool in captured["tools"]]
    assert tool_names == [
        "Bash",
        "Read",
        "Write",
        "Edit",
        "Grep",
        "Glob",
        "TaskCreate",
        "TaskGet",
        "TaskUpdate",
        "TaskList",
        "ExtraTool",
        "Agent",
    ]


def test_create_hagent_attaches_task_store_with_explicit_task_list_id(monkeypatch, tmp_path):
    def fake_create_deep_agent(**_kwargs):
        return type("FakeAgent", (), {})()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    backend = FilesystemBackend(root_dir=tmp_path, virtual_mode=False)
    agent = create_hagent(
        config=HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False),
        backend=backend,
        task_list_id="session-123",
    )

    assert agent._hagent_task_store.workspace_root == tmp_path
    assert agent._hagent_task_store.task_list_id == "session-123"
    assert agent._hagent_task_store.tasks_dir == tmp_path / ".hagent" / "tasks" / "session-123"


def test_create_hagent_task_tools_share_attached_store(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return type("FakeAgent", (), {})()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    backend = FilesystemBackend(root_dir=tmp_path, virtual_mode=False)
    agent = create_hagent(
        config=HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False),
        backend=backend,
        task_list_id="shared",
    )

    task_tools = {
        tool.name: tool
        for tool in captured["tools"]
        if tool.name in {"TaskCreate", "TaskGet", "TaskUpdate", "TaskList"}
    }

    created = task_tools["TaskCreate"].invoke(
        {"subject": "Write tests", "description": "Cover registration."}
    )
    listed = task_tools["TaskList"].invoke({})
    fetched = task_tools["TaskGet"].invoke({"taskId": "1"})

    assert created == "Task #1 created successfully: Write tests"
    assert listed == "#1 [pending] Write tests"
    assert fetched == "\n".join(
        [
            "Task #1: Write tests",
            "Status: pending",
            "Description: Cover registration.",
        ]
    )
    assert agent._hagent_task_store.get_task("1").subject == "Write tests"


def test_registered_task_update_can_start_blocked_task_without_claimant(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return type("FakeAgent", (), {})()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    backend = FilesystemBackend(root_dir=tmp_path, virtual_mode=False)
    agent = create_hagent(
        config=HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False),
        backend=backend,
        task_list_id="blocked",
    )
    task_tools = {
        tool.name: tool
        for tool in captured["tools"]
        if tool.name in {"TaskCreate", "TaskUpdate"}
    }

    assert (
        task_tools["TaskCreate"].invoke(
            {"subject": "Blocker", "description": "Must finish first."}
        )
        == "Task #1 created successfully: Blocker"
    )
    assert (
        task_tools["TaskCreate"].invoke(
            {"subject": "Blocked", "description": "Waits for blocker."}
        )
        == "Task #2 created successfully: Blocked"
    )
    agent._hagent_task_store.block_task("1", "2")

    result = task_tools["TaskUpdate"].invoke({"taskId": "2", "status": "in_progress"})

    blocked = agent._hagent_task_store.get_task("2")
    assert result == "Updated task #2 status"
    assert blocked.status == "in_progress"
    assert blocked.owner is None


def test_registered_task_update_in_progress_respects_explicit_owner(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return type("FakeAgent", (), {})()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)

    backend = FilesystemBackend(root_dir=tmp_path, virtual_mode=False)
    agent = create_hagent(
        config=HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False),
        backend=backend,
        task_list_id="claimant",
    )
    task_tools = {
        tool.name: tool
        for tool in captured["tools"]
        if tool.name in {"TaskCreate", "TaskUpdate"}
    }

    assert (
        task_tools["TaskCreate"].invoke(
            {"subject": "Claim me", "description": "Registered update claims this."}
        )
        == "Task #1 created successfully: Claim me"
    )

    result = task_tools["TaskUpdate"].invoke(
        {"taskId": "1", "status": "in_progress", "owner": "other"}
    )

    updated = agent._hagent_task_store.get_task("1")
    assert result == "Updated task #1 status, owner"
    assert updated.status == "in_progress"
    assert updated.owner == "other"


def test_create_hagent_uses_env_task_list_id_when_not_explicit(monkeypatch, tmp_path):
    def fake_create_deep_agent(**_kwargs):
        return type("FakeAgent", (), {})()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    monkeypatch.setenv("HAGENT_TASK_LIST_ID", "env-session")

    backend = FilesystemBackend(root_dir=tmp_path, virtual_mode=False)
    agent = create_hagent(
        config=HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False),
        backend=backend,
    )

    assert agent._hagent_task_store.task_list_id == "env-session"


def test_get_or_build_agent_passes_session_id_as_task_list_id(tmp_path, monkeypatch):
    captured = {}

    def fake_create_hagent(
        *, backend, checkpointer, task_list_id, hook_runner=None, mcp_connection=None
    ):
        captured["backend"] = backend
        captured["checkpointer"] = checkpointer
        captured["task_list_id"] = task_list_id
        return object()

    monkeypatch.setattr(agents, "_agents", {})
    monkeypatch.setattr(agents, "get_checkpointer", lambda: object())
    monkeypatch.setattr(agents, "create_hagent", fake_create_hagent)

    agent = agents.get_or_build_agent("sid", str(tmp_path))

    assert agent is not None
    assert type(captured["backend"]).__name__ == "FilesystemBackend"
    assert captured["task_list_id"] == "sid"
