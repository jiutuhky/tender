from pathlib import Path
import subprocess
import time

import pytest

from hagent.bash_tool.tasks import TaskRegistry


def test_task_registry_tracks_lifecycle_fields(tmp_path: Path) -> None:
    registry = TaskRegistry()
    output_path = tmp_path / "task.log"

    record = registry.start(
        task_id="task-1",
        command="printf ok",
        description="Print ok",
        pid=123,
        process_group_id=123,
        output_path=output_path,
    )
    registry.mark_completed("task-1", exit_code=0, interrupted=False)

    saved = registry.get("task-1")
    assert saved is not None
    assert record.started_at <= saved.completed_at
    assert saved.command == "printf ok"
    assert saved.description == "Print ok"
    assert saved.pid == 123
    assert saved.process_group_id == 123
    assert saved.output_path == output_path
    assert saved.status == "completed"
    assert saved.exit_code == 0
    assert saved.interrupted is False


def test_task_registry_cleanup_kills_running_process_group(tmp_path: Path) -> None:
    proc = subprocess.Popen(
        ["bash", "-c", "sleep 5"],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    registry = TaskRegistry()
    registry.start(
        task_id="sleep-task",
        command="sleep 5",
        description=None,
        pid=proc.pid,
        process_group_id=proc.pid,
        output_path=tmp_path / "sleep.log",
    )

    registry.cleanup()

    for _ in range(50):
        if proc.poll() is not None:
            break
        time.sleep(0.02)

    saved = registry.get("sleep-task")
    assert proc.poll() is not None
    assert saved is not None
    assert saved.status == "killed"
    assert saved.interrupted is True


def test_task_registry_kill_process_lookup_error_leaves_status_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry = TaskRegistry()
    registry.start(
        task_id="race-task",
        command="sleep 0",
        description=None,
        pid=999999,
        process_group_id=999999,
        output_path=tmp_path / "race.log",
        status="backgrounded",
    )

    def raise_process_lookup_error(_pgid: int, _sig: int) -> None:
        raise ProcessLookupError

    monkeypatch.setattr("hagent.bash_tool.tasks.os.killpg", raise_process_lookup_error)

    assert registry.kill("race-task") is False
    saved = registry.get("race-task")
    assert saved is not None
    assert saved.status == "backgrounded"
    assert saved.completed_at is None
    assert saved.interrupted is False
