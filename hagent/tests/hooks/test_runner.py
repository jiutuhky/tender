"""HookRunner 测试：匹配/去重/once/并行/聚合/同步桥。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from hagent.hooks.config import HookRegistration, LoadedHooks
from hagent.hooks.context import HookContext
from hagent.hooks.events import HookEvent
from hagent.hooks.runner import HookRunner
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


def _reg(
    event: HookEvent,
    command: str,
    matcher: str | None = None,
    source: str = "project",
    **hook_extra,
) -> HookRegistration:
    return HookRegistration(
        event=event,
        matcher=matcher,
        hook=CommandHookConfig.model_validate(
            {"type": "command", "command": command, **hook_extra}
        ),
        source=source,
    )


def _loaded(*regs: HookRegistration) -> LoadedHooks:
    loaded = LoadedHooks()
    for r in regs:
        loaded.by_event.setdefault(r.event, []).append(r)
    return loaded


_PRE_FIELDS = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "tool_use_id": "t1"}


async def test_no_hooks_returns_empty(tmp_path: Path):
    runner = HookRunner(LoadedHooks(), _ctx(tmp_path))
    agg = await runner.arun(HookEvent.PRE_TOOL_USE, _PRE_FIELDS)
    assert not agg.blocked
    assert not runner.has_hooks(HookEvent.PRE_TOOL_USE)


async def test_matcher_filters_by_tool_name(tmp_path: Path):
    mark_bash = tmp_path / "bash.mark"
    mark_read = tmp_path / "read.mark"
    runner = HookRunner(
        _loaded(
            _reg(HookEvent.PRE_TOOL_USE, f"touch {mark_bash}", matcher="Bash"),
            _reg(HookEvent.PRE_TOOL_USE, f"touch {mark_read}", matcher="Read"),
        ),
        _ctx(tmp_path),
    )
    await runner.arun(HookEvent.PRE_TOOL_USE, _PRE_FIELDS)
    assert mark_bash.exists()
    assert not mark_read.exists()


async def test_dedup_last_scope_wins(tmp_path: Path):
    out = tmp_path / "count"
    cmd = f"echo run >> {out}"
    runner = HookRunner(
        _loaded(
            _reg(HookEvent.PRE_TOOL_USE, cmd, matcher="Bash", source="user"),
            _reg(HookEvent.PRE_TOOL_USE, cmd, matcher="Bash", source="local"),
        ),
        _ctx(tmp_path),
    )
    await runner.arun(HookEvent.PRE_TOOL_USE, _PRE_FIELDS)
    assert out.read_text().count("run") == 1  # 同 key 去重，只跑一次


async def test_parallel_execution(tmp_path: Path):
    regs = [
        _reg(HookEvent.PRE_TOOL_USE, f"sleep 0.3; echo {i}") for i in range(3)
    ]
    runner = HookRunner(_loaded(*regs), _ctx(tmp_path))
    start = time.monotonic()
    agg = await runner.arun(HookEvent.PRE_TOOL_USE, _PRE_FIELDS)
    elapsed = time.monotonic() - start
    assert elapsed < 0.8  # 串行则 >= 0.9
    assert len(agg.results) == 3


async def test_once_only_fires_once(tmp_path: Path):
    out = tmp_path / "once.log"
    runner = HookRunner(
        _loaded(
            _reg(HookEvent.PRE_TOOL_USE, f"echo x >> {out}", once=True),
        ),
        _ctx(tmp_path),
    )
    await runner.arun(HookEvent.PRE_TOOL_USE, _PRE_FIELDS)
    await runner.arun(HookEvent.PRE_TOOL_USE, _PRE_FIELDS)
    assert out.read_text().count("x") == 1


async def test_permission_priority_deny_over_ask_over_allow(tmp_path: Path):
    def _json_hook(decision: str, reason: str) -> str:
        payload = json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": reason,
                }
            }
        )
        return f"echo '{payload}'"

    runner = HookRunner(
        _loaded(
            _reg(HookEvent.PRE_TOOL_USE, _json_hook("allow", "fine")),
            _reg(HookEvent.PRE_TOOL_USE, _json_hook("deny", "危险")),
            _reg(HookEvent.PRE_TOOL_USE, _json_hook("ask", "unsure")),
        ),
        _ctx(tmp_path),
    )
    agg = await runner.arun(HookEvent.PRE_TOOL_USE, _PRE_FIELDS)
    assert agg.permission_decision == "deny"
    assert agg.permission_reason == "危险"
    assert agg.blocked  # deny 带 blocking_error


async def test_updated_input_dropped_on_deny(tmp_path: Path):
    allow_update = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": {"command": "ls -la"},
            }
        }
    )
    deny = json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
            }
        }
    )
    runner = HookRunner(
        _loaded(
            _reg(HookEvent.PRE_TOOL_USE, f"echo '{allow_update}'"),
            _reg(HookEvent.PRE_TOOL_USE, f"echo '{deny}'"),
        ),
        _ctx(tmp_path),
    )
    agg = await runner.arun(HookEvent.PRE_TOOL_USE, _PRE_FIELDS)
    assert agg.permission_decision == "deny"
    assert agg.updated_input is None


async def test_stop_event_exit2_blocks(tmp_path: Path):
    runner = HookRunner(
        _loaded(_reg(HookEvent.STOP, "echo 请继续完成任务 >&2; exit 2")),
        _ctx(tmp_path),
    )
    agg = await runner.arun(
        HookEvent.STOP, {"stop_hook_active": False, "last_assistant_message": "done"}
    )
    assert agg.blocked
    assert "请继续完成任务" in agg.block_reason


async def test_stop_matcher_ignored_without_match_query(tmp_path: Path):
    # Stop 无 matchQuery：即使 matcher 不匹配也执行（CC 行为）
    mark = tmp_path / "ran"
    runner = HookRunner(
        _loaded(_reg(HookEvent.STOP, f"touch {mark}", matcher="SomethingElse")),
        _ctx(tmp_path),
    )
    await runner.arun(HookEvent.STOP, {"stop_hook_active": False})
    assert mark.exists()


async def test_stdout_context_only_for_context_events(tmp_path: Path):
    runner = HookRunner(
        _loaded(
            _reg(HookEvent.USER_PROMPT_SUBMIT, "echo 额外上下文"),
            _reg(HookEvent.PRE_TOOL_USE, "echo 不应注入"),
        ),
        _ctx(tmp_path),
    )
    ups = await runner.arun(HookEvent.USER_PROMPT_SUBMIT, {"prompt": "hi"})
    assert ups.contexts == ["额外上下文"]
    pre = await runner.arun(HookEvent.PRE_TOOL_USE, _PRE_FIELDS)
    assert pre.contexts == []  # PreToolUse exit0 stdout 不给模型（CC 语义）


async def test_session_start_skips_http_hooks(tmp_path: Path):
    from hagent.hooks.schema import HttpHookConfig

    reg = HookRegistration(
        event=HookEvent.SESSION_START,
        matcher=None,
        hook=HttpHookConfig(url="http://hooks.test/x"),
        source="project",
    )
    runner = HookRunner(_loaded(reg), _ctx(tmp_path))
    agg = await runner.arun(HookEvent.SESSION_START, {"source": "startup"})
    assert agg.results == []  # http hook 被过滤，无执行


async def test_single_failure_does_not_break_others(tmp_path: Path):
    mark = tmp_path / "ok.mark"
    runner = HookRunner(
        _loaded(
            _reg(HookEvent.PRE_TOOL_USE, "exit 1"),
            _reg(HookEvent.PRE_TOOL_USE, f"touch {mark}"),
        ),
        _ctx(tmp_path),
    )
    agg = await runner.arun(HookEvent.PRE_TOOL_USE, _PRE_FIELDS)
    assert mark.exists()
    assert not agg.blocked
    assert len(agg.non_blocking_errors) == 1


def test_sync_bridge_without_running_loop(tmp_path: Path):
    runner = HookRunner(
        _loaded(_reg(HookEvent.USER_PROMPT_SUBMIT, "echo ctx")),
        _ctx(tmp_path),
    )
    agg = runner.run(HookEvent.USER_PROMPT_SUBMIT, {"prompt": "hi"})
    assert agg.contexts == ["ctx"]


async def test_sync_bridge_inside_running_loop(tmp_path: Path):
    # 防御路径：在事件循环内调用 run() 也不能炸
    runner = HookRunner(
        _loaded(_reg(HookEvent.USER_PROMPT_SUBMIT, "echo ctx")),
        _ctx(tmp_path),
    )
    agg = runner.run(HookEvent.USER_PROMPT_SUBMIT, {"prompt": "hi"})
    assert agg.contexts == ["ctx"]


async def test_system_message_and_continue_false(tmp_path: Path):
    payload = json.dumps(
        {"continue": False, "stopReason": "策略停机", "systemMessage": "注意"}
    )
    runner = HookRunner(
        _loaded(_reg(HookEvent.STOP, f"echo '{payload}'")),
        _ctx(tmp_path),
    )
    agg = await runner.arun(HookEvent.STOP, {"stop_hook_active": False})
    assert agg.prevent_continuation
    assert agg.stop_reason == "策略停机"
    assert agg.system_messages == ["注意"]
    assert agg.blocked
