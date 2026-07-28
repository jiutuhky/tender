"""Hook 执行上下文：会话身份与 stdin payload 基座。

字段拼写对齐 CC coreSchemas.ts 的 BaseHookInputSchema：
session_id / transcript_path / cwd / permission_mode? / agent_id? / agent_type?。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HookContext:
    """一次 hook 触发所处的会话上下文。

    - ``cwd``：hook 子进程的工作目录（宿主侧 workspace；sandbox 模式下 hook
      仍在宿主执行，与 CC 语义一致）。
    - ``project_root``：注入 ``CLAUDE_PROJECT_DIR`` 的项目根（server 进程 CWD）。
    - ``transcript_path``：对齐 CC 字段；hagent 暂无 transcript 文件，
      路径可能不存在（已知差异，见 spec §5）。
    - ``agent_id``/``agent_type``：仅当 hook 从子代理内触发时携带。
    """

    session_id: str
    cwd: Path
    project_root: Path
    transcript_path: Path
    permission_mode: str | None = None
    agent_id: str | None = None
    agent_type: str | None = None

    def base_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "session_id": self.session_id,
            "transcript_path": str(self.transcript_path),
            "cwd": str(self.cwd),
        }
        if self.permission_mode is not None:
            payload["permission_mode"] = self.permission_mode
        if self.agent_id is not None:
            payload["agent_id"] = self.agent_id
        if self.agent_type is not None:
            payload["agent_type"] = self.agent_type
        return payload

    def for_subagent(self, agent_id: str, agent_type: str) -> HookContext:
        return replace(self, agent_id=agent_id, agent_type=agent_type)
