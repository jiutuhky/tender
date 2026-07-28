"""简版 transcript JSONL 测试。"""

from __future__ import annotations

import json
from pathlib import Path

from hagent.server import transcript


def test_append_and_read(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(transcript, "TRANSCRIPTS_DIR", tmp_path)
    transcript.append_transcript("sid1", "user", "你好")
    transcript.append_transcript("sid1", "assistant", "回复")
    transcript.append_transcript("sid1", "assistant", "")  # 空内容不写
    lines = (tmp_path / "sid1.jsonl").read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["role"] == "user"
    assert first["content"] == "你好"
    assert "ts" in first


def test_transcript_path(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(transcript, "TRANSCRIPTS_DIR", tmp_path)
    assert transcript.transcript_path("abc") == tmp_path / "abc.jsonl"
