from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from deepagents.backends.protocol import ExecuteResponse, FileUploadResponse

from hagent.sandbox import SandboxKind
from hagent.sandbox.pool import SandboxLease
from hagent.server.leases import LeaseStore, SandboxState
from hagent.server.manager import SessionManager
from hagent.server.project_workspace import ProjectWorkspace
from hagent.server.sessions import SessionStore
from hagent.server.workspace_materialization import WorkspaceMaterializer


class LocalGuestSandbox:
    """用本地目录模拟 guest，只保留 sandbox 公共协议行为。"""

    def __init__(self, root: Path):
        self.id = "sandbox-project-alpha"
        self.workspace_dir = str(root)
        self.manifest = MagicMock(
            container_id="hagent-projecta-a1b2c3",
            image_tag="hagent-sandbox",
            runtime="test",
            paused=False,
        )
        self.upload_error_paths: set[str] = set()

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
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
            if path in self.upload_error_paths:
                responses.append(FileUploadResponse(path=path, error="写入失败"))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            responses.append(FileUploadResponse(path=path, error=None))
        return responses


def _environment(tmp_path: Path, *, restore_error: Exception | None = None):
    workspace_root = tmp_path / "workspaces"
    workspace = ProjectWorkspace(workspace_root)
    workspace.initialize("project-alpha")
    db = tmp_path / "hagent.db"
    sessions = SessionStore(db)
    leases = LeaseStore(db)
    guest_root = tmp_path / "guest"
    guest_root.mkdir()
    sandbox = LocalGuestSandbox(guest_root)
    pool = MagicMock(node_id="local")
    pool.acquire.return_value = SandboxLease(sandbox, "project-alpha")
    pool.acquire_restored.side_effect = restore_error
    manager = SessionManager(
        store=sessions,
        lease_store=leases,
        sandbox_pool=pool,
        workspace_root=workspace_root,
        workspace_materializer=WorkspaceMaterializer(workspace),
    )
    session = manager.create_session(
        project_id="project-alpha", sandbox_kind=SandboxKind.SMOLVM
    )
    return manager, leases, workspace, session, guest_root, sandbox


def test_cold_sandbox_receives_canonical_workspace_and_clean_git_baseline(tmp_path):
    manager, leases, workspace, session, guest, _ = _environment(tmp_path)
    host = workspace.path_for("project-alpha")
    (host / "sources" / "招标文件.md").write_text("第一版", encoding="utf-8")
    (host / "tmp" / "草稿.txt").write_text("不应注入", encoding="utf-8")
    revision = workspace.commit(
        "project-alpha",
        summary="upload: 招标文件",
        run_id="upload-1",
        session_id=session.id,
        kind="upload",
    )

    assert manager.ensure_sandbox(session.id) is not None

    assert (guest / "sources" / "招标文件.md").read_text(encoding="utf-8") == "第一版"
    assert not (guest / "tmp" / "草稿.txt").exists()
    assert (guest / ".git").is_dir()
    status = subprocess.run(
        ["git", "-C", str(guest), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""
    assert revision is not None
    guest_revision = subprocess.run(
        ["git", "-C", str(guest), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert guest_revision != revision
    assert leases.get("project-alpha").materialized_revision == revision


def test_missing_project_snapshot_silently_cold_starts_with_complete_workspace(
    tmp_path, monkeypatch
):
    manager, leases, workspace, session, guest, sandbox = _environment(
        tmp_path, restore_error=FileNotFoundError("快照已被清理")
    )
    host = workspace.path_for("project-alpha")
    (host / "deliverables" / "技术方案.md").write_text(
        "已持久化成果", encoding="utf-8"
    )
    revision = workspace.commit(
        "project-alpha",
        summary="chat_turn: 生成技术方案",
        run_id="run-1",
        session_id=session.id,
        kind="chat_turn",
    )
    assert revision is not None
    leases.update_snapshot("project-alpha", "snap-deleted")
    leases.update_state("project-alpha", state=SandboxState.SNAPSHOTTED.value)
    deleted: list[str] = []
    monkeypatch.setattr("hagent.server.manager._delete_snapshot_quiet", deleted.append)

    assert manager.ensure_sandbox(session.id) is sandbox

    assert deleted == ["snap-deleted"]
    assert (guest / "deliverables" / "技术方案.md").read_text(
        encoding="utf-8"
    ) == "已持久化成果"
    saved = leases.get("project-alpha")
    assert saved.snapshot_id is None
    assert saved.materialized_revision == revision


def test_live_sandbox_catches_up_to_new_revision_including_deletions(tmp_path):
    manager, leases, workspace, session, guest, _ = _environment(tmp_path)
    host = workspace.path_for("project-alpha")
    source = host / "sources" / "招标文件.md"
    removed = host / "deliverables" / "旧章节.md"
    source.write_text("第一版", encoding="utf-8")
    removed.write_text("旧内容", encoding="utf-8")
    workspace.commit(
        "project-alpha",
        summary="upload: 初始材料",
        run_id="upload-1",
        session_id=session.id,
        kind="upload",
    )
    manager.ensure_sandbox(session.id)

    source.write_text("第二版", encoding="utf-8")
    removed.unlink()
    added = host / "structured" / "响应矩阵.json"
    added.write_text('{"状态":"已追平"}', encoding="utf-8")
    revision = workspace.commit(
        "project-alpha",
        summary="upload: 补遗材料",
        run_id="upload-2",
        session_id=session.id,
        kind="upload",
    )

    manager.ensure_sandbox(session.id)

    assert (guest / "sources" / "招标文件.md").read_text(encoding="utf-8") == "第二版"
    assert not (guest / "deliverables" / "旧章节.md").exists()
    assert (guest / "structured" / "响应矩阵.json").read_text(
        encoding="utf-8"
    ) == '{"状态":"已追平"}'
    status = subprocess.run(
        ["git", "-C", str(guest), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""
    assert revision is not None
    assert leases.get("project-alpha").materialized_revision == revision


def test_failed_catch_up_does_not_advance_materialized_revision(tmp_path):
    manager, leases, workspace, session, guest, _ = _environment(tmp_path)
    host = workspace.path_for("project-alpha")
    source = host / "sources" / "招标文件.md"
    source.write_text("第一版", encoding="utf-8")
    first_revision = workspace.commit(
        "project-alpha",
        summary="upload: 初始材料",
        run_id="upload-1",
        session_id=session.id,
        kind="upload",
    )
    sandbox = manager.ensure_sandbox(session.id)
    assert first_revision is not None

    source.write_text("第二版", encoding="utf-8")
    workspace.commit(
        "project-alpha",
        summary="upload: 补遗材料",
        run_id="upload-2",
        session_id=session.id,
        kind="upload",
    )
    sandbox.upload_error_paths.add(str(guest / "sources" / "招标文件.md"))

    with pytest.raises(RuntimeError, match="项目工作区追平失败"):
        manager.ensure_sandbox(session.id)

    assert leases.get("project-alpha").materialized_revision == first_revision


def test_cold_materialization_excludes_even_tracked_gitignored_files(tmp_path):
    manager, _, workspace, session, guest, _ = _environment(tmp_path)
    host = workspace.path_for("project-alpha")
    ignored = host / "tmp" / "被强制跟踪.txt"
    ignored.write_text("仍不应注入", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(host), "add", "--force", "tmp/被强制跟踪.txt"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(host), "commit", "-m", "test: 强制跟踪忽略文件"],
        check=True,
        capture_output=True,
    )

    manager.ensure_sandbox(session.id)

    assert not (guest / "tmp" / "被强制跟踪.txt").exists()


def test_failed_cold_materialization_retries_full_sync_on_next_ensure(tmp_path):
    manager, leases, workspace, session, guest, sandbox = _environment(tmp_path)
    host = workspace.path_for("project-alpha")
    source = host / "sources" / "招标文件.md"
    source.write_text("必须完整注入", encoding="utf-8")
    revision = workspace.commit(
        "project-alpha",
        summary="upload: 招标文件",
        run_id="upload-1",
        session_id=session.id,
        kind="upload",
    )
    assert revision is not None
    leases.update_metadata("project-alpha", materialized_revision=revision)
    sandbox.upload_error_paths.add(str(guest / "sources" / "招标文件.md"))

    with pytest.raises(RuntimeError, match="项目工作区注入失败"):
        manager.ensure_sandbox(session.id)
    sandbox.upload_error_paths.clear()

    manager.ensure_sandbox(session.id)

    assert (guest / "sources" / "招标文件.md").read_text(
        encoding="utf-8"
    ) == "必须完整注入"


def test_sync_project_workspace_injects_upload_into_active_lease(tmp_path):
    manager, leases, workspace, session, guest, _ = _environment(tmp_path)
    manager.ensure_sandbox(session.id)

    workspace.apply_changes(
        "project-alpha",
        updated={"sources/补遗澄清.md": "第一号补遗".encode()},
        deleted=(),
    )
    revision = workspace.commit(
        "project-alpha",
        summary="upload: sources/补遗澄清.md",
        kind="upload",
        paths=["sources/补遗澄清.md"],
    )

    assert manager.sync_project_workspace("project-alpha") is True

    assert (guest / "sources" / "补遗澄清.md").read_text(encoding="utf-8") == "第一号补遗"
    assert leases.get("project-alpha").materialized_revision == revision
    status = subprocess.run(
        ["git", "-C", str(guest), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""


def test_sync_project_workspace_without_lease_never_creates_vm(tmp_path):
    manager, _, workspace, _, guest, _ = _environment(tmp_path)
    workspace.apply_changes(
        "project-alpha",
        updated={"sources/招标文件.md": "冷项目上传".encode()},
        deleted=(),
    )
    workspace.commit(
        "project-alpha",
        summary="upload: sources/招标文件.md",
        kind="upload",
        paths=["sources/招标文件.md"],
    )

    assert manager.sync_project_workspace("project-alpha") is False

    manager._pool.acquire.assert_not_called()
    manager._pool.acquire_restored.assert_not_called()
    assert not (guest / "sources" / "招标文件.md").exists()


def test_catch_up_reloads_files_when_gitignore_stops_ignoring_them(tmp_path):
    manager, _, workspace, session, guest, _ = _environment(tmp_path)
    host = workspace.path_for("project-alpha")
    ignored = host / "tmp" / "恢复同步.txt"
    ignored.write_text("现在应注入", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(host), "add", "--force", "tmp/恢复同步.txt"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(host), "commit", "-m", "test: 跟踪忽略文件"],
        check=True,
        capture_output=True,
    )
    manager.ensure_sandbox(session.id)
    assert not (guest / "tmp" / "恢复同步.txt").exists()

    gitignore = host / ".gitignore"
    gitignore.write_text(
        gitignore.read_text(encoding="utf-8").replace("tmp/\n", ""),
        encoding="utf-8",
    )
    workspace.commit(
        "project-alpha",
        summary="project: tmp 纳入工作区",
        run_id="system-1",
        session_id=session.id,
        kind="system",
    )

    manager.ensure_sandbox(session.id)

    assert (guest / "tmp" / "恢复同步.txt").read_text(
        encoding="utf-8"
    ) == "现在应注入"
