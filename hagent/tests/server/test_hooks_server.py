"""server 层 hook 接线 e2e：SessionStart / SessionEnd / UserPromptSubmit。"""

from __future__ import annotations

from tests.server.helpers import create_project_session

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hagent.server import hooks_registry
from hagent.server.app import create_app


@pytest.fixture(autouse=True)
def _reset_hooks_registry():
    hooks_registry._runners.clear()
    hooks_registry._pending_session_context.clear()
    yield
    hooks_registry._runners.clear()
    hooks_registry._pending_session_context.clear()


class CaptureAgent:
    """记录 stream 入参的假 agent。"""

    last_input: dict | None = None

    def stream(self, *args, **kwargs):
        type(self).last_input = args[0] if args else None

        class _Chunk:
            type = "AIMessageChunk"
            content = "ok"
            tool_call_chunks = []

        yield ((), "messages", (_Chunk(), {}))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    CaptureAgent.last_input = None
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path / "sessions"))
    monkeypatch.setenv("HAGENT_DB_PATH", str(tmp_path / "h.sqlite"))
    monkeypatch.delenv("HAGENT_API_KEY", raising=False)
    monkeypatch.setattr(
        "hagent.server.routers.messages.get_or_build_agent",
        lambda sid, wd, *, project_id=None, sandbox=None: CaptureAgent(),
    )
    return TestClient(create_app())


def _write_hooks(tmp_path: Path, monkeypatch, hooks: dict) -> None:
    settings = tmp_path / "hook-settings.json"
    settings.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
    monkeypatch.setenv("HAGENT_HOOKS_SETTINGS_PATHS", str(settings))


def test_session_start_context_injected_into_first_message(
    tmp_path: Path, monkeypatch, client: TestClient
):
    marker = tmp_path / "started"
    payload = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "项目约定：所有文案用中文",
            }
        }
    )
    _write_hooks(
        tmp_path,
        monkeypatch,
        {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": f"touch {marker}; echo '{payload}'"}]}
            ]
        },
    )
    r = create_project_session(client)
    assert r.status_code == 200
    sid = r.json()["session_id"]
    assert marker.exists()

    with client.stream(
        "POST", f"/sessions/{sid}/messages", json={"content": "第一条"}
    ) as resp:
        b"".join(resp.iter_bytes())
    content = CaptureAgent.last_input["messages"][0]["content"]
    assert content.startswith("<session-start-hook>")
    assert "项目约定：所有文案用中文" in content
    assert "第一条" in content

    # 第二条消息不再注入（pending 已消费）
    with client.stream(
        "POST", f"/sessions/{sid}/messages", json={"content": "第二条"}
    ) as resp:
        b"".join(resp.iter_bytes())
    content2 = CaptureAgent.last_input["messages"][0]["content"]
    assert "<session-start-hook>" not in content2


def test_session_start_initial_user_message_in_response(
    tmp_path: Path, monkeypatch, client: TestClient
):
    payload = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "initialUserMessage": "请先自检环境",
            }
        }
    )
    _write_hooks(
        tmp_path,
        monkeypatch,
        {"SessionStart": [{"hooks": [{"type": "command", "command": f"echo '{payload}'"}]}]},
    )
    r = create_project_session(client)
    assert r.json()["initial_user_message"] == "请先自检环境"


def test_session_start_blocking_is_ignored(
    tmp_path: Path, monkeypatch, client: TestClient
):
    _write_hooks(
        tmp_path,
        monkeypatch,
        {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": "echo no >&2; exit 2"}]}
            ]
        },
    )
    r = create_project_session(client)
    assert r.status_code == 200  # blocking 忽略，session 照常创建


def test_user_prompt_submit_block_erases_prompt(
    tmp_path: Path, monkeypatch, client: TestClient
):
    _write_hooks(
        tmp_path,
        monkeypatch,
        {
            "UserPromptSubmit": [
                {"hooks": [{"type": "command", "command": "echo 包含敏感词 >&2; exit 2"}]}
            ]
        },
    )
    sid = create_project_session(client).json()["session_id"]
    with client.stream(
        "POST", f"/sessions/{sid}/messages", json={"content": "违规内容"}
    ) as resp:
        assert resp.status_code == 200
        body = b"".join(resp.iter_bytes())
    assert b"event: hook.blocked" in body
    assert "包含敏感词".encode() in body
    assert b"event: done" in body
    assert CaptureAgent.last_input is None  # prompt 未进图（擦除语义）


def test_user_prompt_submit_context_appended(
    tmp_path: Path, monkeypatch, client: TestClient
):
    _write_hooks(
        tmp_path,
        monkeypatch,
        {
            "UserPromptSubmit": [
                {"hooks": [{"type": "command", "command": "echo 当前分支是 main"}]}
            ]
        },
    )
    sid = create_project_session(client).json()["session_id"]
    with client.stream(
        "POST", f"/sessions/{sid}/messages", json={"content": "帮我提交"}
    ) as resp:
        b"".join(resp.iter_bytes())
    content = CaptureAgent.last_input["messages"][0]["content"]
    assert content.startswith("帮我提交")
    assert "当前分支是 main" in content


def test_session_end_hook_fires_with_timeout(
    tmp_path: Path, monkeypatch, client: TestClient
):
    capture = tmp_path / "end-payload.json"
    slow_marker = tmp_path / "slow-done"
    _write_hooks(
        tmp_path,
        monkeypatch,
        {
            "SessionEnd": [
                {
                    "hooks": [
                        {"type": "command", "command": f"cat > {capture}"},
                        # 超过 1.5s 默认超时的慢 hook 不能拖死删除
                        {"type": "command", "command": f"sleep 10 && touch {slow_marker}"},
                    ]
                }
            ]
        },
    )
    sid = create_project_session(client).json()["session_id"]
    start = time.monotonic()
    r = client.delete(f"/sessions/{sid}")
    elapsed = time.monotonic() - start
    assert r.json() == {"ok": True}
    assert elapsed < 5  # 1.5s 超时兜底，不被 sleep 10 拖死
    payload = json.loads(capture.read_text())
    assert payload["hook_event_name"] == "SessionEnd"
    assert payload["reason"] == "other"
    assert payload["session_id"] == sid
    assert not slow_marker.exists()
    # registry 已清理
    assert hooks_registry.get_hook_runner(sid) is None


def test_no_hooks_configured_no_behavior_change(
    tmp_path: Path, monkeypatch, client: TestClient
):
    monkeypatch.setenv(
        "HAGENT_HOOKS_SETTINGS_PATHS", str(tmp_path / "missing.json")
    )
    sid = create_project_session(client).json()["session_id"]
    with client.stream(
        "POST", f"/sessions/{sid}/messages", json={"content": "hi"}
    ) as resp:
        body = b"".join(resp.iter_bytes())
    assert b"event: done" in body
    assert b"hook.blocked" not in body
    assert CaptureAgent.last_input["messages"][0]["content"] == "hi"
    assert client.delete(f"/sessions/{sid}").json() == {"ok": True}