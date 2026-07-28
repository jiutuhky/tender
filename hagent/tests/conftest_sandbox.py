"""Fake sandbox fixture for parity tests (does not need docker)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterator

import pytest

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox

from hagent.sandbox.protocol import HagentSandboxProtocol, SandboxKind


class _LocalTmpSandbox(BaseSandbox, HagentSandboxProtocol):
    """BaseSandbox subclass that 'executes' via local subprocess in a tmp root.

    Used to validate the Hagent contract (LLM-visible tool output parity) without
    requiring a real container.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._id = "fake-tmp-" + root.name

    @property
    def id(self) -> str:
        return self._id

    @property
    def kind(self) -> SandboxKind:
        return SandboxKind.DOCKER

    @property
    def workspace_dir(self) -> str:
        return str(self._root)

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        proc = subprocess.run(
            ["/bin/bash", "-c", command],
            cwd=str(self._root),
            capture_output=True,
            text=True,
            timeout=timeout or 30,
        )
        # Mirror BaseSandbox output format: stdout + [stderr] prefixed lines
        parts = []
        if proc.stdout:
            parts.append(proc.stdout)
        if proc.stderr:
            for line in proc.stderr.rstrip("\n").split("\n"):
                if line:
                    parts.append(f"[stderr] {line}\n")
        return ExecuteResponse(
            output="".join(parts),
            exit_code=proc.returncode,
            truncated=False,
        )

    def upload_files(self, files):
        out = []
        for path, content in files:
            target = self._resolve(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            out.append(FileUploadResponse(path=str(target), error=None))
        return out

    def download_files(self, paths):
        out = []
        for path in paths:
            target = self._resolve(path)
            if not target.exists():
                out.append(FileDownloadResponse(path=path, content=None, error="file_not_found"))
                continue
            out.append(FileDownloadResponse(path=path, content=target.read_bytes(), error=None))
        return out

    def close(self) -> None:
        shutil.rmtree(self._root, ignore_errors=True)

    def _resolve(self, path: str) -> Path:
        if path.startswith(str(self._root)):
            return Path(path)
        return self._root / path.lstrip("/")


@pytest.fixture
def fake_sandbox(tmp_path: Path) -> Iterator[_LocalTmpSandbox]:
    root = tmp_path / "sandbox"
    root.mkdir()
    sb = _LocalTmpSandbox(root)
    yield sb
    sb.close()
