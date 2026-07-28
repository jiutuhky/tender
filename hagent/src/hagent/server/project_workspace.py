"""项目 canonical workspace：宿主侧目录与 git 持久层。"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Sequence


WORKSPACE_DIRECTORIES = ("sources", "structured", "deliverables", "tmp")
GITIGNORE_CONTENT = "tmp/\n.cache/\n__pycache__/\n*.pyc\nnode_modules/\n.venv/\n"


@dataclass(frozen=True)
class WorkspaceRevision:
    sha: str
    committed_at: float
    summary: str
    run_id: str | None
    session_id: str | None
    kind: str | None
    interrupted: bool


@dataclass(frozen=True)
class WorkspaceFile:
    path: str
    size: int


@dataclass(frozen=True)
class WorkspaceChanges:
    updated: tuple[str, ...]
    deleted: tuple[str, ...]
    full_refresh_required: bool = False


def parse_git_status(output: str) -> WorkspaceChanges:
    """解析 ``git status --porcelain=v1 -z --no-renames`` 输出。"""
    updated: list[str] = []
    deleted: list[str] = []
    for record in output.split("\0"):
        if not record:
            continue
        if len(record) < 4 or record[2] != " ":
            raise RuntimeError(f"无法解析 git status 记录: {record!r}")
        if "D" in record[:2]:
            deleted.append(record[3:])
        else:
            updated.append(record[3:])
    return WorkspaceChanges(updated=tuple(updated), deleted=tuple(deleted))


class ProjectWorkspace:
    """管理 ``{root}/projects/<pid>/workspace`` 下的项目工作区。"""

    def __init__(self, root: Path | str):
        self._root = Path(root)
        self._project_locks: dict[str, Lock] = {}
        self._project_locks_guard = Lock()

    def path_for(self, project_id: str) -> Path:
        return self._root / "projects" / project_id / "workspace"

    def initialize(self, project_id: str) -> Path:
        project_root = self._root / "projects" / project_id
        workspace = project_root / "workspace"
        created_project_root = not project_root.exists()
        try:
            workspace.mkdir(parents=True, exist_ok=True)
            for directory in WORKSPACE_DIRECTORIES:
                (workspace / directory).mkdir(exist_ok=True)
            (workspace / ".gitignore").write_text(GITIGNORE_CONTENT, encoding="utf-8")

            if not (workspace / ".git").is_dir():
                self._git(workspace, "init", "--initial-branch=main")
                self._git(workspace, "config", "user.name", "hagent")
                self._git(workspace, "config", "user.email", "hagent@local")
                self._git(workspace, "add", ".gitignore")
                self._git(workspace, "commit", "-m", "project: 初始化工作区")
            return workspace
        except Exception:
            if created_project_root:
                shutil.rmtree(project_root, ignore_errors=True)
            raise

    def head(self, project_id: str) -> str:
        return self._git(self.path_for(project_id), "rev-parse", "HEAD").strip()

    def commit(
        self,
        project_id: str,
        *,
        summary: str,
        kind: str,
        run_id: str | None = None,
        session_id: str | None = None,
        interrupted: bool = False,
        paths: Sequence[str] | None = None,
    ) -> str | None:
        workspace = self.path_for(project_id)
        with self._lock_for(project_id):
            path_args = [] if paths is None else ["--", *paths]
            self._git(workspace, "add", "--all", *path_args)
            if not self._has_staged_changes(workspace, path_args):
                return None
            # 系统提交（如上传）无 Run/Session 归属，对应 trailer 省略
            trailers = []
            if run_id:
                trailers.append(f"Run-ID: {run_id}")
            if session_id:
                trailers.append(f"Session-ID: {session_id}")
            trailers.append(f"Kind: {kind}")
            if interrupted:
                trailers.append("Interrupted: true")
            message = f"{summary}\n\n" + "\n".join(trailers)
            self._git(workspace, "commit", "-m", message)
            return self._git(workspace, "rev-parse", "HEAD").strip()

    def history(self, project_id: str, *, limit: int = 50) -> list[WorkspaceRevision]:
        output = self._git(
            self.path_for(project_id),
            "log",
            f"--max-count={limit}",
            "--format=%H%x1f%ct%x1f%s%x1f%(trailers:only,unfold=true)%x1e",
        )
        revisions: list[WorkspaceRevision] = []
        for record in output.split("\x1e"):
            record = record.strip("\r\n")
            if not record:
                continue
            sha, committed_at, summary, trailer_text = record.split("\x1f", 3)
            trailers = {}
            for line in trailer_text.splitlines():
                key, separator, value = line.partition(":")
                if separator:
                    trailers[key.strip().lower()] = value.strip()
            revisions.append(
                WorkspaceRevision(
                    sha=sha,
                    committed_at=float(committed_at),
                    summary=summary,
                    run_id=trailers.get("run-id"),
                    session_id=trailers.get("session-id"),
                    kind=trailers.get("kind"),
                    interrupted=trailers.get("interrupted", "false").lower() == "true",
                )
            )
        return revisions

    def list_files(self, project_id: str) -> list[WorkspaceFile]:
        output = self._git(self.path_for(project_id), "ls-files", "-z")
        files: list[WorkspaceFile] = []
        for relative_path in output.split("\0"):
            if not relative_path:
                continue
            path = self._resolve_path(project_id, relative_path)
            if path.is_file():
                files.append(WorkspaceFile(path=relative_path, size=path.stat().st_size))
        return sorted(files, key=lambda file: file.path)

    def ignored_tracked_paths(self, project_id: str) -> set[str]:
        """返回虽被跟踪、但按当前 ``.gitignore`` 应从 guest 排除的路径。"""
        output = self._git(
            self.path_for(project_id),
            "ls-files",
            "--cached",
            "--ignored",
            "--exclude-standard",
            "-z",
        )
        return {path for path in output.split("\0") if path}

    def read_file(self, project_id: str, path: str) -> bytes:
        return self._resolve_data_path(project_id, path).read_bytes()

    def apply_changes(
        self,
        project_id: str,
        *,
        updated: dict[str, bytes],
        deleted: Sequence[str],
    ) -> None:
        """把已完整下载的 guest 变更写入 canonical workspace。"""
        with self._lock_for(project_id):
            for relative_path, content in updated.items():
                target = self._resolve_data_path(project_id, relative_path)
                if target.is_dir():
                    shutil.rmtree(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            for relative_path in deleted:
                target = self._resolve_data_path(project_id, relative_path)
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink(missing_ok=True)

    def changes_since(self, project_id: str, revision: str) -> WorkspaceChanges:
        """返回 ``revision..HEAD`` 的文件变化，重命名按删除加新增处理。"""
        workspace = self.path_for(project_id)
        verify = self._run_git(
            workspace,
            "rev-parse",
            "--verify",
            f"{revision}^{{commit}}",
            check=False,
        )
        if verify.returncode != 0:
            raise ValueError(f"未知项目 revision: {revision}")
        updated = self._git(
            workspace,
            "diff",
            "--no-renames",
            "--name-only",
            "-z",
            "--diff-filter=ACMRTUXB",
            revision,
            "HEAD",
        )
        deleted = self._git(
            workspace,
            "diff",
            "--no-renames",
            "--name-only",
            "-z",
            "--diff-filter=D",
            revision,
            "HEAD",
        )
        updated_paths = tuple(path for path in updated.split("\0") if path)
        deleted_paths = tuple(path for path in deleted.split("\0") if path)
        ignore_rules_changed = any(
            Path(path).name == ".gitignore"
            for path in (*updated_paths, *deleted_paths)
        )
        ignored = self.ignored_tracked_paths(project_id)
        return WorkspaceChanges(
            updated=tuple(
                path
                for path in updated_paths
                if path not in ignored
            ),
            deleted=tuple(
                sorted(set(deleted_paths) | ignored)
            ),
            full_refresh_required=ignore_rules_changed,
        )

    def pending_changes(self, project_id: str) -> WorkspaceChanges:
        """返回 canonical workspace 尚未提交的文件变化。"""
        output = self._git(
            self.path_for(project_id),
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--no-renames",
        )
        return parse_git_status(output)

    def _resolve_path(self, project_id: str, path: str) -> Path:
        workspace = self.path_for(project_id).resolve()
        candidate = (workspace / path).resolve()
        try:
            candidate.relative_to(workspace)
        except ValueError as exc:
            raise ValueError("路径必须位于项目工作区内") from exc
        return candidate

    def _resolve_data_path(self, project_id: str, path: str) -> Path:
        candidate = self._resolve_path(project_id, path)
        relative = candidate.relative_to(self.path_for(project_id).resolve())
        if not relative.parts or relative.parts[0] == ".git":
            raise ValueError("git 元数据不属于项目文件")
        return candidate

    def _lock_for(self, project_id: str) -> Lock:
        with self._project_locks_guard:
            lock = self._project_locks.get(project_id)
            if lock is None:
                lock = Lock()
                self._project_locks[project_id] = lock
            return lock

    @staticmethod
    def _has_staged_changes(workspace: Path, path_args: Sequence[str]) -> bool:
        result = ProjectWorkspace._run_git(
            workspace,
            "diff",
            "--cached",
            "--quiet",
            *path_args,
            check=False,
        )
        if result.returncode not in (0, 1):
            raise subprocess.CalledProcessError(
                result.returncode,
                result.args,
                output=result.stdout,
                stderr=result.stderr,
            )
        return result.returncode == 1

    @staticmethod
    def _git(workspace: Path, *args: str) -> str:
        return ProjectWorkspace._run_git(workspace, *args).stdout

    @staticmethod
    def _run_git(
        workspace: Path, *args: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_LITERAL_PATHSPECS"] = "1"
        return subprocess.run(
            ["git", "-C", str(workspace), *args],
            check=check,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )


_PROJECT_WORKSPACE: ProjectWorkspace | None = None


def set_project_workspace(workspace: ProjectWorkspace | None) -> None:
    global _PROJECT_WORKSPACE
    _PROJECT_WORKSPACE = workspace


def get_project_workspace() -> ProjectWorkspace:
    global _PROJECT_WORKSPACE
    if _PROJECT_WORKSPACE is None:
        root = os.environ.get("HAGENT_WORKSPACE_ROOT", "/tmp/hagent/workspaces")
        _PROJECT_WORKSPACE = ProjectWorkspace(root)
    return _PROJECT_WORKSPACE
