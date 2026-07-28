"""per-session HookRunner 注册表。

server 路径的 HookRunner 必须全 session 唯一（once 状态、settings 快照都
绑定 session 生命周期）：create_session / get_or_build_agent / post_message /
delete_session 共用这里的实例。settings 在 session 首次构建 runner 时快照，
改配置需新建 session（与 skills/subagents 的缓存语义一致）。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from hagent.hooks import HookContext, load_hook_settings
from hagent.hooks.runner import HookRunner

logger = logging.getLogger(__name__)

_TRANSCRIPTS_DIR = Path("/tmp/hagent/transcripts")

# sid -> HookRunner | None（None 表示已扫描过且无 hook 配置，避免重复扫盘）
_runners: dict[str, HookRunner | None] = {}
# SessionStart hook 的 additionalContext，暂存到首条消息注入
_pending_session_context: dict[str, str] = {}


def get_or_build_hook_runner(sid: str, workspace_dir: str) -> HookRunner | None:
    if sid in _runners:
        return _runners[sid]
    settings = load_hook_settings(Path.cwd(), env=os.environ)
    if settings.empty:
        _runners[sid] = None
        return None
    runner = HookRunner(
        settings,
        HookContext(
            session_id=sid,
            # hook 在宿主执行（CC 语义）；sandbox 模式下这里是 host 侧 session 目录
            cwd=Path(workspace_dir),
            project_root=Path.cwd(),
            transcript_path=_TRANSCRIPTS_DIR / f"{sid}.jsonl",
        ),
    )
    _runners[sid] = runner
    return runner


def get_hook_runner(sid: str) -> HookRunner | None:
    return _runners.get(sid)


def set_pending_session_context(sid: str, context: str) -> None:
    _pending_session_context[sid] = context


def pop_pending_session_context(sid: str) -> str | None:
    return _pending_session_context.pop(sid, None)


def clear_session(sid: str) -> None:
    _runners.pop(sid, None)
    _pending_session_context.pop(sid, None)
