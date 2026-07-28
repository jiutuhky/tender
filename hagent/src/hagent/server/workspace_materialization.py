"""把宿主 canonical workspace 物化到项目沙箱。"""

from __future__ import annotations

import shlex
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from hagent.server.project_workspace import (
    ProjectWorkspace,
    WORKSPACE_DIRECTORIES,
    WorkspaceChanges,
)

if TYPE_CHECKING:
    from hagent.sandbox.protocol import HagentSandboxProtocol


class WorkspaceMaterializer:
    """同步 host git 工作区到 guest，并维护 guest 变更探测基线。"""

    def __init__(self, workspace: ProjectWorkspace):
        self._workspace = workspace

    def materialize(
        self,
        project_id: str,
        sandbox: "HagentSandboxProtocol",
        *,
        previous_revision: str | None,
        force_full: bool = False,
    ) -> str:
        head = self._workspace.head(project_id)
        if force_full or previous_revision is None:
            self._materialize_full(project_id, sandbox)
        elif previous_revision != head:
            try:
                changes = self._workspace.changes_since(project_id, previous_revision)
            except ValueError:
                self._materialize_full(project_id, sandbox)
            else:
                if changes.full_refresh_required:
                    self._materialize_full(project_id, sandbox)
                else:
                    self._apply_changes(project_id, sandbox, changes)
        return head

    def _materialize_full(
        self, project_id: str, sandbox: "HagentSandboxProtocol"
    ) -> None:
        guest_root = PurePosixPath(sandbox.workspace_dir)
        quoted_root = shlex.quote(str(guest_root))
        directories = " ".join(
            shlex.quote(str(guest_root / directory))
            for directory in WORKSPACE_DIRECTORIES
        )
        self._execute(
            sandbox,
            f"mkdir -p {quoted_root} && "
            f"find {quoted_root} -mindepth 1 -maxdepth 1 -exec rm -rf -- {{}} + && "
            f"mkdir -p {directories}",
        )

        ignored = self._workspace.ignored_tracked_paths(project_id)
        uploads = [
            (
                str(guest_root / file.path),
                self._workspace.read_file(project_id, file.path),
            )
            for file in self._workspace.list_files(project_id)
            if file.path not in ignored
        ]
        if uploads:
            self._upload_or_raise(sandbox, uploads, action="注入")

        self._reset_guest_baseline(sandbox, guest_root)

    def _apply_changes(
        self,
        project_id: str,
        sandbox: "HagentSandboxProtocol",
        changes: WorkspaceChanges,
    ) -> None:
        guest_root = PurePosixPath(sandbox.workspace_dir)
        uploads = [
            (
                str(guest_root / path),
                self._workspace.read_file(project_id, path),
            )
            for path in changes.updated
        ]
        if uploads:
            self._upload_or_raise(sandbox, uploads, action="追平")
        if changes.deleted:
            targets = " ".join(
                shlex.quote(str(guest_root / path)) for path in changes.deleted
            )
            self._execute(sandbox, f"rm -rf -- {targets}")
        self._advance_guest_baseline(
            sandbox, guest_root, (*changes.updated, *changes.deleted)
        )

    @staticmethod
    def _upload_or_raise(
        sandbox: "HagentSandboxProtocol",
        uploads: list[tuple[str, bytes]],
        *,
        action: str,
    ) -> None:
        failures = [
            response
            for response in sandbox.upload_files(uploads)
            if response.error is not None
        ]
        if failures:
            details = "; ".join(
                f"{response.path}: {response.error}" for response in failures
            )
            raise RuntimeError(f"项目工作区{action}失败: {details}")

    def _reset_guest_baseline(
        self, sandbox: "HagentSandboxProtocol", guest_root: PurePosixPath
    ) -> None:
        root = shlex.quote(str(guest_root))
        self._execute(
            sandbox,
            f"git -C {root} init -q && "
            f"git -C {root} config user.name hagent && "
            f"git -C {root} config user.email hagent@local && "
            f"git -C {root} add -A && "
            f"git -C {root} commit -q --allow-empty -m 'hagent materialization baseline'",
        )

    def _advance_guest_baseline(
        self,
        sandbox: "HagentSandboxProtocol",
        guest_root: PurePosixPath,
        paths: tuple[str, ...],
    ) -> None:
        if not paths:
            return
        root = shlex.quote(str(guest_root))
        path_args = " ".join(shlex.quote(path) for path in paths)
        self._execute(
            sandbox,
            f"git -C {root} add -A -- {path_args} && "
            f"git -C {root} commit -q --allow-empty -m 'hagent materialization catch-up'",
        )

    @staticmethod
    def _execute(sandbox: "HagentSandboxProtocol", command: str) -> None:
        response = sandbox.execute(command)
        if response.exit_code != 0:
            raise RuntimeError(
                f"项目工作区 guest 命令失败(exit={response.exit_code}): {response.output}"
            )
