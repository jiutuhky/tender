"""把一轮 Run 在 guest 中的文件变更持久化到项目 git 工作区。"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath
from threading import Lock
from typing import TYPE_CHECKING

from hagent.server.leases import LeaseStore
from hagent.server.project_workspace import (
    ProjectWorkspace,
    WorkspaceChanges,
    parse_git_status,
)
from hagent.server.runs import RunStatus, RunStore

if TYPE_CHECKING:
    from hagent.sandbox.protocol import HagentSandboxProtocol


@dataclass(frozen=True)
class CheckpointResult:
    run_id: str
    commit_sha: str | None
    files_changed: tuple[str, ...]


class CheckpointFailure(RuntimeError):
    def __init__(self, message: str, *, result: CheckpointResult):
        super().__init__(message)
        self.result = result


class WorkspaceCheckpointer:
    def __init__(
        self,
        *,
        workspace: ProjectWorkspace,
        runs: RunStore,
        leases: LeaseStore,
    ) -> None:
        self._workspace = workspace
        self._runs = runs
        self._leases = leases
        self._locks: dict[str, Lock] = {}
        self._locks_guard = Lock()

    def checkpoint(
        self,
        run_id: str,
        *,
        sandbox: HagentSandboxProtocol | None = None,
        interrupted: bool = False,
        error: str | None = None,
    ) -> CheckpointResult:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(run_id)
        if run.status in {
            RunStatus.COMMITTED,
            RunStatus.INTERRUPTED,
            RunStatus.REJECTED,
        }:
            return CheckpointResult(run.id, run.commit_sha, ())

        with self._lock_for(run.project_id):
            run = self._runs.get(run_id)
            assert run is not None
            if run.status in {
                RunStatus.COMMITTED,
                RunStatus.INTERRUPTED,
                RunStatus.REJECTED,
            }:
                return CheckpointResult(run.id, run.commit_sha, ())
            self._runs.mark_checkpointing(run.id)
            commit_sha: str | None = None
            paths: tuple[str, ...] = ()
            try:
                if sandbox is not None and callable(getattr(sandbox, "execute", None)):
                    changes = self._guest_changes(sandbox)
                    self._copy_guest_changes(run.project_id, sandbox, changes)
                else:
                    changes = self._host_changes(run.project_id)

                paths = tuple(dict.fromkeys((*changes.updated, *changes.deleted)))
                if paths:
                    commit_sha = self._workspace.commit(
                        run.project_id,
                        summary=run.summary,
                        run_id=run.id,
                        session_id=run.session_id,
                        kind=run.kind,
                        interrupted=interrupted,
                        paths=paths,
                    )
                if sandbox is not None and callable(getattr(sandbox, "execute", None)):
                    self._advance_guest_baseline(sandbox, paths)
                head = self._workspace.head(run.project_id)
                if self._leases.get(run.project_id) is not None:
                    self._leases.update_metadata(
                        run.project_id, materialized_revision=head
                    )
                terminal = (
                    RunStatus.INTERRUPTED if interrupted else RunStatus.COMMITTED
                )
                self._runs.finish(
                    run.id,
                    status=terminal,
                    commit_sha=commit_sha,
                    error=error,
                )
                return CheckpointResult(run.id, commit_sha, paths)
            except Exception as exc:
                self._runs.finish(
                    run.id,
                    status=RunStatus.INTERRUPTED,
                    commit_sha=commit_sha,
                    error=error or str(exc),
                )
                raise CheckpointFailure(
                    str(exc),
                    result=CheckpointResult(run.id, commit_sha, paths),
                ) from exc

    def _host_changes(self, project_id: str) -> WorkspaceChanges:
        return self._workspace.pending_changes(project_id)

    def _guest_changes(self, sandbox: HagentSandboxProtocol) -> WorkspaceChanges:
        root = shlex.quote(str(PurePosixPath(sandbox.workspace_dir)))
        response = sandbox.execute(
            f"git -C {root} status --porcelain=v1 -z --untracked-files=all --no-renames"
        )
        if response.exit_code != 0:
            raise RuntimeError(
                f"guest 变更检测失败(exit={response.exit_code}): {response.output}"
            )
        return parse_git_status(response.output)

    def _copy_guest_changes(
        self,
        project_id: str,
        sandbox: HagentSandboxProtocol,
        changes: WorkspaceChanges,
    ) -> None:
        root = PurePosixPath(sandbox.workspace_dir)
        guest_paths = [str(root / path) for path in changes.updated]
        responses = sandbox.download_files(guest_paths) if guest_paths else []
        if len(responses) != len(guest_paths):
            raise RuntimeError("guest 文件下载结果数量不匹配")
        downloaded: dict[str, bytes] = {}
        for relative_path, response in zip(changes.updated, responses, strict=True):
            if response.error is not None or response.content is None:
                raise RuntimeError(
                    f"guest 文件下载失败: {relative_path}: {response.error}"
                )
            downloaded[relative_path] = response.content
        self._workspace.apply_changes(
            project_id,
            updated=downloaded,
            deleted=changes.deleted,
        )

    @staticmethod
    def _advance_guest_baseline(
        sandbox: HagentSandboxProtocol, paths: tuple[str, ...]
    ) -> None:
        if not paths:
            return
        root = shlex.quote(str(PurePosixPath(sandbox.workspace_dir)))
        path_args = " ".join(shlex.quote(path) for path in paths)
        response = sandbox.execute(
            f"git -C {root} add -A -- {path_args} && "
            f"git -C {root} commit -q --allow-empty -m 'hagent checkpoint baseline'"
        )
        if response.exit_code != 0:
            raise RuntimeError(
                f"guest 基线推进失败(exit={response.exit_code}): {response.output}"
            )

    def _lock_for(self, project_id: str) -> Lock:
        with self._locks_guard:
            lock = self._locks.get(project_id)
            if lock is None:
                lock = Lock()
                self._locks[project_id] = lock
            return lock
