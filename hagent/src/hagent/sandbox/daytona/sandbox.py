"""HagentDaytonaSandbox — stubbed adapter to be wired against langchain-daytona later."""

from __future__ import annotations

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)

from hagent.sandbox.protocol import HagentSandboxProtocol, SandboxKind


class HagentDaytonaSandbox(HagentSandboxProtocol):
    """Placeholder Daytona sandbox.

    The real implementation will wrap ``langchain_daytona.DaytonaSandbox`` and
    expose the same surface as ``HagentDockerSandbox``. This stub exists so
    Hagent's abstraction layer is provably not bound to docker.
    """

    def __init__(self, *, sandbox_id: str = "daytona-stub", workspace_dir: str = "/workspace") -> None:
        self._sandbox_id = sandbox_id
        self._workspace_dir = workspace_dir

    @property
    def id(self) -> str:
        return self._sandbox_id

    @property
    def kind(self) -> SandboxKind:
        return SandboxKind.DAYTONA

    @property
    def workspace_dir(self) -> str:
        return self._workspace_dir

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        raise NotImplementedError("HagentDaytonaSandbox is deferred to a follow-up plan")

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        raise NotImplementedError

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        raise NotImplementedError

    # BackendProtocol abstract methods inherited via SandboxBackendProtocol — stub them.
    def ls(self, path: str):  # type: ignore[override]
        raise NotImplementedError

    def read(self, file_path: str, offset: int = 0, limit: int = 2000):  # type: ignore[override]
        raise NotImplementedError

    def write(self, file_path: str, content: str):  # type: ignore[override]
        raise NotImplementedError

    def edit(self, file_path, old_string, new_string, replace_all=False):  # type: ignore[override]
        raise NotImplementedError

    def grep(self, pattern, path=None, glob=None):  # type: ignore[override]
        raise NotImplementedError

    def glob(self, pattern, path="/"):  # type: ignore[override]
        raise NotImplementedError

    def close(self) -> None:
        pass
