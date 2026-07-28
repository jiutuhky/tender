"""简版 session transcript（JSONL）。

CC 的 hook payload 带 transcript_path；hagent 没有完整 transcript 体系，
这里按「一行一条消息」追加 user / assistant 文本，让 hook 脚本里的
`jq .transcript_path` 用法有落点。与 CC 的完整 transcript 格式不对等
（已知差异，spec §5）。
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

TRANSCRIPTS_DIR = Path("/tmp/hagent/transcripts")


def transcript_path(session_id: str) -> Path:
    return TRANSCRIPTS_DIR / f"{session_id}.jsonl"


def append_transcript(session_id: str, role: str, content: str) -> None:
    if not content:
        return
    try:
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {"role": role, "content": content, "ts": time.time()},
            ensure_ascii=False,
        )
        with transcript_path(session_id).open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as exc:
        logger.warning("transcript 追加失败 %s: %s", session_id, exc)
