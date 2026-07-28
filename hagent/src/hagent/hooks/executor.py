"""command 型 hook 的子进程执行器。

对齐 CC execCommandHook（hooks.ts:747）：
- ``bash -c <command>``（hagent 仅支持 POSIX；``shell: powershell`` 报
  non-blocking error）。
- stdin 写入 payload JSON + 尾随 ``\\n``（CC 刻意行为，bash ``read -r`` 需要）。
- env 注入 ``CLAUDE_PROJECT_DIR``（项目根，非 workspace）。
- 超时：per-hook ``timeout``（秒）否则事件默认（工具类 600s / SessionEnd 1.5s）；
  超时杀整个进程组，outcome=cancelled。
- ``async:true`` 做 fire-and-forget（spawn 后不等待，输出忽略）；CC 的
  「stdout 首行 {"async":true} 动态后台化」与 asyncRewake 不支持（已知差异）。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal as signal_module
from typing import Any, Mapping

from hagent.hooks.context import HookContext
from hagent.hooks.events import HookEvent, default_timeout_s
from hagent.hooks.results import HookExecutionResult, classify_command_output
from hagent.hooks.schema import CommandHookConfig

logger = logging.getLogger(__name__)


def _hook_env(ctx: HookContext, env: Mapping[str, str] | None) -> dict[str, str]:
    merged = dict(os.environ if env is None else env)
    merged["CLAUDE_PROJECT_DIR"] = str(ctx.project_root)
    return merged


def _payload_stdin(payload: Mapping[str, Any]) -> bytes:
    # 尾随 \n 对齐 CC hooks.ts:1001-1005
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


async def _kill_process_group(proc: asyncio.subprocess.Process) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(proc.pid), signal_module.SIGKILL)
    with contextlib.suppress(Exception):
        await proc.wait()


async def execute_command_hook(
    hook: CommandHookConfig,
    payload: Mapping[str, Any],
    ctx: HookContext,
    event: HookEvent,
    *,
    env: Mapping[str, str] | None = None,
) -> HookExecutionResult:
    if hook.shell == "powershell":
        return HookExecutionResult(
            outcome="non_blocking_error",
            error_message="hagent 不支持 powershell hook（仅 POSIX bash）",
        )

    timeout = (
        hook.timeout
        if hook.timeout is not None
        else default_timeout_s(event, "command")
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "bash",
            "-c",
            hook.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(ctx.cwd),
            env=_hook_env(ctx, env),
            start_new_session=True,  # 独立进程组，超时可整组 kill
        )
    except OSError as exc:
        return HookExecutionResult(
            outcome="non_blocking_error",
            error_message=f"Failed to spawn hook command: {exc}",
        )

    stdin_data = _payload_stdin(payload)

    if hook.async_ or hook.async_rewake:
        # fire-and-forget：写入 stdin 后即返回，不等待也不消费输出
        async def _feed_and_forget() -> None:
            with contextlib.suppress(Exception):
                await proc.communicate(stdin_data)

        asyncio.get_running_loop().create_task(_feed_and_forget())
        return HookExecutionResult(outcome="success", backgrounded=True)

    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(stdin_data), timeout=timeout
        )
    except asyncio.TimeoutError:
        await _kill_process_group(proc)
        return HookExecutionResult(
            outcome="cancelled",
            stderr=f"Hook cancelled: timed out after {timeout}s",
        )
    except asyncio.CancelledError:
        await _kill_process_group(proc)
        raise

    return classify_command_output(
        command_desc=hook.command,
        exit_code=proc.returncode if proc.returncode is not None else 1,
        stdout=stdout_b.decode("utf-8", errors="replace"),
        stderr=stderr_b.decode("utf-8", errors="replace"),
        event=event,
    )
