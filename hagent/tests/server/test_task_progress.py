import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from hagent.server.app import create_app
from hagent.server.routers.messages import _task_store_todos
from hagent.task_tools.store import TaskStore
from tests.server.helpers import create_project_session


@pytest.fixture
def planned_tasks(tmp_path):
    store = TaskStore(tmp_path)
    review = store.create_task(subject="复核", description="复核抽取结果")
    extract = store.create_task(subject="抽取", description="抽取四张矩阵")
    publish = store.create_task(subject="发布", description="校验并发布矩阵")
    store.block_task(extract.id, review.id)
    store.block_task(review.id, publish.id)
    return store


@pytest.mark.parametrize(
    "statuses,expected_blockers",
    [
        (("pending", "in_progress", "pending"), [[], ["2"], ["1"]]),
        (("in_progress", "completed", "pending"), [[], [], ["1"]]),
        (("completed", "completed", "in_progress"), [[], [], []]),
        (("completed", "completed", "completed"), [[], [], []]),
    ],
)
def test_progress_keeps_step_order_as_tasks_complete(planned_tasks, statuses, expected_blockers):
    for task_id, status in zip(("1", "2", "3"), statuses):
        planned_tasks.update_task(task_id, status=status)

    todos = _task_store_todos(SimpleNamespace(_hagent_task_store=planned_tasks))

    assert [todo["id"] for todo in todos] == ["2", "1", "3"]
    assert [todo["blockedBy"] for todo in todos] == expected_blockers
    # 展示排序不改写任务编号、存储顺序或完整依赖。
    assert [task.id for task in planned_tasks.list_tasks()] == ["1", "2", "3"]
    assert planned_tasks.get_task("1").blockedBy == ["2"]


def test_parallel_steps_keep_creation_order(tmp_path):
    store = TaskStore(tmp_path)
    for subject in ("复核", "商务抽取", "技术抽取", "发布"):
        store.create_task(subject=subject, description=subject)
    store.block_task("2", "1")
    store.block_task("3", "1")
    store.block_task("1", "4")

    todos = _task_store_todos(SimpleNamespace(_hagent_task_store=store))

    assert [todo["id"] for todo in todos] == ["2", "3", "1", "4"]


def test_tasks_without_dependencies_keep_numeric_creation_order(tmp_path):
    store = TaskStore(tmp_path)
    for index in range(12):
        store.create_task(subject=f"步骤 {index + 1}", description="独立任务")
    store.update_task("10", status="in_progress")

    todos = _task_store_todos(SimpleNamespace(_hagent_task_store=store))

    assert [todo["id"] for todo in todos] == [str(index + 1) for index in range(12)]


def test_cycles_and_unavailable_dependencies_keep_visible_tasks(tmp_path):
    store = TaskStore(tmp_path)
    for subject in ("循环甲", "循环乙", "可执行步骤", "循环后续"):
        store.create_task(subject=subject, description=subject)
    hidden = store.create_task(subject="内部步骤", description="内部任务", metadata={"_internal": True})
    store.block_task("1", "2")
    store.block_task("2", "1")
    store.block_task("2", "4")
    store.block_task(hidden.id, "3")
    # 模拟遗留数据中引用了不存在的前置任务。
    path = store.tasks_dir / "3.json"
    data = json.loads(path.read_text())
    data["blockedBy"].append("missing")
    path.write_text(json.dumps(data))

    todos = _task_store_todos(SimpleNamespace(_hagent_task_store=store))

    assert [todo["id"] for todo in todos] == ["3", "1", "2", "4"]
    assert todos[0]["blockedBy"] == [hidden.id, "missing"]


def test_empty_progress(tmp_path):
    assert _task_store_todos(SimpleNamespace(_hagent_task_store=TaskStore(tmp_path))) == []


def test_rest_and_sse_share_dependency_order(planned_tasks, tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    planned_tasks.update_task("2", status="completed")
    planned_tasks.update_task("1", status="in_progress")

    class Agent:
        _hagent_task_store = planned_tasks

        def stream(self, *_args, **_kwargs):
            yield ((), "messages", (SimpleNamespace(
                type="tool", content="任务已更新", tool_call_id="progress", name="TaskUpdate",
            ), {}))

    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda *_args, **_kwargs: Agent(),
    )
    client = TestClient(create_app())
    sid = create_project_session(client).json()["session_id"]
    response = client.get(f"/sessions/{sid}/todos")
    assert response.status_code == 200
    todos = response.json()
    assert [todo["id"] for todo in todos] == ["2", "1", "3"]
    assert todos[1]["blockedBy"] == []

    response = client.post(f"/sessions/{sid}/messages", json={"content": "继续"})
    assert response.status_code == 200
    frames = response.text.split("\n\n")
    frame = next(frame for frame in frames if "event: todo.updated\n" in frame)
    data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
    assert json.loads(data_line.removeprefix("data: "))["todos"] == todos
