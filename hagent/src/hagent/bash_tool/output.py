"""Output persistence helpers for the Bash runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OutputSummary:
    inline_text: str
    truncated: bool
    persisted_output_path: str | None
    persisted_output_size: int


class OutputManager:
    """Creates and finalizes per-task output logs."""

    def __init__(self, workspace_root: Path, *, inline_threshold: int = 30_000) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.inline_threshold = inline_threshold
        self.output_dir = self.workspace_root / ".hagent" / "tool-results"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_output_file(self, task_id: str) -> Path:
        path = self.output_dir / f"{task_id}.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(mode=0o600, exist_ok=True)
        return path

    def finalize_foreground(self, output_path: Path) -> OutputSummary:
        size = output_path.stat().st_size
        truncated = size > self.inline_threshold
        if truncated:
            preview = self._read_preview(output_path)
            return OutputSummary(
                inline_text=preview,
                truncated=True,
                persisted_output_path=str(output_path),
                persisted_output_size=size,
            )

        data = self._read_all(output_path)
        output_path.unlink(missing_ok=True)
        return OutputSummary(
            inline_text=data,
            truncated=False,
            persisted_output_path=None,
            persisted_output_size=size,
        )

    def read_text(self, output_path: Path) -> str:
        return output_path.read_text(encoding="utf-8", errors="replace")

    def _read_preview(self, output_path: Path) -> str:
        with output_path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read(self.inline_threshold)

    def _read_all(self, output_path: Path) -> str:
        with output_path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
