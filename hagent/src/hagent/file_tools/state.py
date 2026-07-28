from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReadSnapshot:
    path: Path
    content: str
    timestamp_ms: int
    offset: int | None = None
    limit: int | None = None
    is_partial_view: bool = False


class FileReadState:
    def __init__(self) -> None:
        self._snapshots: dict[Path, ReadSnapshot] = {}

    def get(self, path: str | Path) -> ReadSnapshot | None:
        return self._snapshots.get(Path(path).resolve())

    def record_read(
        self,
        path: str | Path,
        content: str,
        timestamp_ms: int,
        offset: int | None,
        limit: int | None,
        is_partial_view: bool = False,
    ) -> None:
        resolved_path = Path(path).resolve()
        self._snapshots[resolved_path] = ReadSnapshot(
            path=resolved_path,
            content=content,
            timestamp_ms=timestamp_ms,
            offset=offset,
            limit=limit,
            is_partial_view=is_partial_view,
        )

    def record_write(
        self,
        path: str | Path,
        content: str,
        timestamp_ms: int,
    ) -> None:
        self.record_read(
            path,
            content,
            timestamp_ms=timestamp_ms,
            offset=None,
            limit=None,
        )
