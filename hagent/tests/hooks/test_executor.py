"""command 执行器测试 —— 真子进程 fake hook。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from hagent.hooks.context import HookContext
from hagent.hooks.events import HookEvent
from hagent.hooks.executor import execute_command_hook
from hagent.hooks.schema import CommandHookConfig


def _ctx(tmp_path: Path) -> HookContext:
    cwd = tmp_path / "ws"
    cwd.mkdir(exist_ok=True)
    return HookContext(
        session_id="s1",
        cwd=cwd,
        project_root=tmp_path,
        transcript_path=tmp_path / "t.jsonl",
    )


_PAYLOAD = {"hook_event_name": "PreToolUse", "tool_name": "Bash"}


async def test_exit0_plain_text(tmp_path: Path):
    res = await execute_command_hook(
        CommandHookConfig(command="echo hello"), _PAYLOAD, _ctx(tmp_path),
        HookEvent.PRE_TOOL_USE,
    )
    assert res.outcome == "success"
    assert res.exit_code == 0
    assert res.plain_text == "hello"


async def test_exit2_blocking_with_stderr(tmp_path: Path):
    res = await execute_command_hook(
        CommandHookConfig(command="echo nope >&2; exit 2"),
        _PAYLOAD,
        _ctx(tmp_path),
        HookEvent.PRE_TOOL_USE,
    )
    assert res.outcome == "blocking"
    assert res.exit_code == 2
    assert res.blocking_error is not None
    assert "nope" in res.blocking_error
    assert res.blocking_error.startswith("[echo nope >&2; exit 2]:")


async def test_exit1_non_blocking(tmp_path: Path):
    res = await execute_command_hook(
        CommandHookConfig(command="echo warn >&2; exit 1"),
        _PAYLOAD,
        _ctx(tmp_path),
        HookEvent.PRE_TOOL_USE,
    )
    assert res.outcome == "non_blocking_error"
    assert res.error_message is not None
    assert "Failed with non-blocking status code" in res.error_message


async def test_stdin_receives_payload_json_with_trailing_newline(tmp_path: Path):
    out = tmp_path / "captured.bin"
    res = await execute_command_hook(
        CommandHookConfig(command=f"cat > {out}"),
        {"hook_event_name": "UserPromptSubmit", "prompt": "你好"},
        _ctx(tmp_path),
        HookEvent.USER_PROMPT_SUBMIT,
    )
    assert res.outcome == "success"
    raw = out.read_bytes()
    assert raw.endswith(b"\n")  # CC 刻意的尾随换行
    payload = json.loads(raw.decode("utf-8"))
    assert payload["prompt"] == "你好"  # ensure_ascii=False，中文原样
    assert "\\u" not in raw.decode("utf-8")


async def test_env_has_claude_project_dir_and_cwd(tmp_path: Path):
    ctx = _ctx(tmp_path)
    res = await execute_command_hook(
        CommandHookConfig(command='echo "$CLAUDE_PROJECT_DIR|$(pwd)"'),
        _PAYLOAD,
        ctx,
        HookEvent.PRE_TOOL_USE,
    )
    project_dir, cwd = (res.plain_text or "").split("|")
    assert project_dir == str(ctx.project_root)
    assert Path(cwd).resolve() == ctx.cwd.resolve()


async def test_json_output_overrides_exit_code(tmp_path: Path):
    # stdout 是合法 JSON 时 JSON 语义优先（即使 exit 2）
    res = await execute_command_hook(
        CommandHookConfig(command="echo '{\"decision\": \"approve\"}'; exit 2"),
        _PAYLOAD,
        _ctx(tmp_path),
        HookEvent.PRE_TOOL_USE,
    )
    assert res.outcome == "success"
    assert res.permission_behavior == "allow"
    assert res.blocking_error is None


async def test_json_decision_block(tmp_path: Path):
    cmd = "echo '{\"decision\": \"block\", \"reason\": \"危险操作\"}'"
    res = await execute_command_hook(
        CommandHookConfig(command=cmd), _PAYLOAD, _ctx(tmp_path),
        HookEvent.PRE_TOOL_USE,
    )
    assert res.outcome == "success"  # JSON 路径 outcome 恒 success
    assert res.permission_behavior == "deny"
    assert res.blocking_error == "危险操作"


async def test_invalid_json_is_non_blocking(tmp_path: Path):
    res = await execute_command_hook(
        CommandHookConfig(command="echo '{broken'"), _PAYLOAD, _ctx(tmp_path),
        HookEvent.PRE_TOOL_USE,
    )
    assert res.outcome == "non_blocking_error"
    assert res.exit_code == 1
    assert "JSON validation failed" in (res.error_message or "")


async def test_hook_event_name_mismatch_rejected(tmp_path: Path):
    cmd = (
        "echo '{\"hookSpecificOutput\": {\"hookEventName\": \"PostToolUse\"}}'"
    )
    res = await execute_command_hook(
        CommandHookConfig(command=cmd), _PAYLOAD, _ctx(tmp_path),
        HookEvent.PRE_TOOL_USE,
    )
    assert res.outcome == "non_blocking_error"
    assert "incorrect event name" in (res.error_message or "")


async def test_timeout_kills_process_group(tmp_path: Path):
    marker = tmp_path / "after-sleep"
    start = time.monotonic()
    res = await execute_command_hook(
        CommandHookConfig(command=f"sleep 30 && touch {marker}", timeout=0.3),
        _PAYLOAD,
        _ctx(tmp_path),
        HookEvent.PRE_TOOL_USE,
    )
    elapsed = time.monotonic() - start
    assert res.outcome == "cancelled"
    assert elapsed < 5
    assert not marker.exists()


async def test_async_hook_fire_and_forget(tmp_path: Path):
    marker = tmp_path / "bg-marker"
    res = await execute_command_hook(
        CommandHookConfig.model_validate(
            {"type": "command", "command": f"sleep 0.2 && touch {marker}", "async": True}
        ),
        _PAYLOAD,
        _ctx(tmp_path),
        HookEvent.PRE_TOOL_USE,
    )
    assert res.outcome == "success"
    assert res.backgrounded is True
    assert not marker.exists()  # 立即返回，不等待
    import asyncio

    await asyncio.sleep(0.6)
    assert marker.exists()


async def test_powershell_not_supported(tmp_path: Path):
    res = await execute_command_hook(
        CommandHookConfig(command="echo x", shell="powershell"),
        _PAYLOAD,
        _ctx(tmp_path),
        HookEvent.PRE_TOOL_USE,
    )
    assert res.outcome == "non_blocking_error"
