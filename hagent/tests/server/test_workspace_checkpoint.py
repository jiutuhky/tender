from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)

from hagent.sandbox import SandboxKind
from hagent.sandbox.pool import SandboxPool
from hagent.server.leases import LeaseStore
from hagent.server.manager import SessionManager
from hagent.server.project_workspace import ProjectWorkspace
from hagent.server.runs import RunStatus, RunStore
from hagent.server.sessions import SessionStore
from hagent.server.workspace_checkpoint import WorkspaceCheckpointer
from hagent.server.workspace_checkpoint import CheckpointFailure
from hagent.server.workspace_materialization import WorkspaceMaterializer


class LocalSandbox:
    def __init__(self, root: Path):
        self.id = "sandbox-project-alpha"
        self.workspace_dir = str(root)
        self.manifest = MagicMock(
            container_id="hagent-projecta-a1b2c3",
            image_tag="hagent-sandbox",
            runtime="test",
            paused=False,
        )
        self.closed = False
        self.baseline_error = False

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        if self.baseline_error and "hagent checkpoint baseline" in command:
            return ExecuteResponse(
                output="guest git 写入失败",
                exit_code=1,
                truncated=False,
            )
        result = subprocess.run(
            ["/bin/bash", "-c", command],
            cwd=self.workspace_dir,
            capture_output=True,
            text=True,
            timeout=timeout or 30,
        )
        return ExecuteResponse(
            output=result.stdout + result.stderr,
            exit_code=result.returncode,
            truncated=False,
        )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        responses = []
        for path, content in files:
            target = Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            responses.append(FileUploadResponse(path=path, error=None))
        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses = []
        for path in paths:
            target = Path(path)
            if not target.is_file():
                responses.append(
                    FileDownloadResponse(path=path, content=None, error="file_not_found")
                )
            else:
                responses.append(
                    FileDownloadResponse(
                        path=path,
                        content=target.read_bytes(),
                        error=None,
                    )
                )
        return responses

    def close(self) -> None:
        self.closed = True


def _checkpoint_environment(tmp_path: Path):
    workspace = ProjectWorkspace(tmp_path / "workspaces")
    workspace.initialize("project-alpha")
    host = workspace.path_for("project-alpha")
    (host / "deliverables" / "待删除.md").write_text("旧稿", encoding="utf-8")
    workspace.commit(
        "project-alpha",
        summary="upload: 初始材料",
        run_id="upload-one",
        session_id="session-one",
        kind="upload",
    )
    db = tmp_path / "hagent.db"
    leases = LeaseStore(db)
    leases.ensure("project-alpha", sandbox_kind=SandboxKind.SMOLVM.value)
    runs = RunStore(db)
    run = runs.create_chat_turn(
        project_id="project-alpha",
        session_id="session-one",
        base_revision=workspace.head("project-alpha"),
        summary="chat_turn: 生成章节",
    )
    runs.mark_running(run.id)
    guest = tmp_path / "guest"
    guest.mkdir()
    sandbox = LocalSandbox(guest)
    revision = WorkspaceMaterializer(workspace).materialize(
        "project-alpha",
        sandbox,
        previous_revision=None,
    )
    leases.update_metadata("project-alpha", materialized_revision=revision)
    checkpointer = WorkspaceCheckpointer(
        workspace=workspace,
        runs=runs,
        leases=leases,
    )
    return workspace, leases, runs, run, sandbox, guest, checkpointer


def test_checkpoint_copies_guest_updates_and_deletions_to_host_git(tmp_path):
    workspace, leases, runs, run, sandbox, guest, checkpointer = (
        _checkpoint_environment(tmp_path)
    )
    (guest / "deliverables" / "待删除.md").unlink()
    (guest / "deliverables" / "技术方案.md").write_text(
        "新方案", encoding="utf-8"
    )
    (guest / "tmp" / "过程文件.txt").write_text("不持久化", encoding="utf-8")

    result = checkpointer.checkpoint(run.id, sandbox=sandbox)

    host = workspace.path_for("project-alpha")
    assert (host / "deliverables" / "技术方案.md").read_text(
        encoding="utf-8"
    ) == "新方案"
    assert not (host / "deliverables" / "待删除.md").exists()
    assert not (host / "tmp" / "过程文件.txt").exists()
    assert set(result.files_changed) == {
        "deliverables/待删除.md",
        "deliverables/技术方案.md",
    }
    assert runs.get(run.id).status is RunStatus.COMMITTED
    assert leases.get("project-alpha").materialized_revision == result.commit_sha
    status = sandbox.execute(
        f"git -C {guest} status --porcelain --untracked-files=all"
    )
    assert status.output == ""


def test_release_project_checkpoints_active_run_before_closing_vm(tmp_path):
    workspace, leases, runs, run, sandbox, guest, checkpointer = (
        _checkpoint_environment(tmp_path)
    )
    sessions = SessionStore(tmp_path / "hagent.db")
    pool = SandboxPool(
        sandbox_factory=lambda: sandbox,
        min_size=0,
        max_size=1,
    )
    manager = SessionManager(
        store=sessions,
        lease_store=leases,
        sandbox_pool=pool,
        workspace_root=tmp_path / "workspaces",
        workspace_materializer=WorkspaceMaterializer(workspace),
        project_workspace=workspace,
        run_store=runs,
        workspace_checkpointer=checkpointer,
    )
    session = manager.create_session(
        project_id="project-alpha",
        sandbox_kind=SandboxKind.SMOLVM,
    )
    manager.ensure_sandbox(session.id)
    (guest / "deliverables" / "释放前成果.md").write_text(
        "必须保全", encoding="utf-8"
    )

    manager.release_project("project-alpha")

    saved = runs.get(run.id)
    assert saved.status is RunStatus.INTERRUPTED
    assert saved.commit_sha is not None
    assert (workspace.path_for("project-alpha") / "deliverables" / "释放前成果.md").read_text(
        encoding="utf-8"
    ) == "必须保全"
    assert sandbox.closed is True


def test_checkpoint_failure_after_host_commit_preserves_commit_details(tmp_path):
    workspace, _, runs, run, sandbox, guest, checkpointer = (
        _checkpoint_environment(tmp_path)
    )
    (guest / "deliverables" / "已落盘.md").write_text("完成", encoding="utf-8")
    sandbox.baseline_error = True

    try:
        checkpointer.checkpoint(run.id, sandbox=sandbox)
    except CheckpointFailure as error:
        result = error.result
    else:  # pragma: no cover
        raise AssertionError("应报告 guest 基线推进失败")

    saved = runs.get(run.id)
    assert result.commit_sha is not None
    assert result.files_changed == ("deliverables/已落盘.md",)
    assert saved.status is RunStatus.INTERRUPTED
    assert saved.commit_sha == result.commit_sha
    assert workspace.history("project-alpha")[0].sha == result.commit_sha


def test_startup_adoption_checkpoints_run_before_recovery_marks_leftovers(tmp_path):
    workspace, leases, runs, run, sandbox, guest, checkpointer = (
        _checkpoint_environment(tmp_path)
    )
    sessions = SessionStore(tmp_path / "hagent.db")
    pool = SandboxPool(
        sandbox_factory=lambda: sandbox,
        min_size=0,
        max_size=1,
    )
    manager = SessionManager(
        store=sessions,
        lease_store=leases,
        sandbox_pool=pool,
        workspace_root=tmp_path / "workspaces",
        project_workspace=workspace,
        run_store=runs,
        workspace_checkpointer=checkpointer,
    )
    (guest / "deliverables" / "重启前成果.md").write_text(
        "已抢救", encoding="utf-8"
    )

    manager.adopt_sandbox("project-alpha", sandbox)
    manager.interrupt_unrecovered_runs()

    saved = runs.get(run.id)
    assert saved.status is RunStatus.INTERRUPTED
    assert saved.commit_sha is not None
    assert workspace.history("project-alpha")[0].run_id == run.id
    assert workspace.read_file(
        "project-alpha", "deliverables/重启前成果.md"
    ) == "已抢救".encode()
