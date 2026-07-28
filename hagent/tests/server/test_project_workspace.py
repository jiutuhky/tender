from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from hagent.server.project_workspace import ProjectWorkspace


def test_initialize_creates_canonical_git_workspace(tmp_path: Path) -> None:
    workspaces = ProjectWorkspace(tmp_path)

    workspace = workspaces.initialize("project-1")

    assert workspace == tmp_path / "projects" / "project-1" / "workspace"
    assert {
        path.name for path in workspace.iterdir() if path.is_dir() and path.name != ".git"
    } == {"sources", "structured", "deliverables", "tmp"}
    assert (workspace / ".git").is_dir()
    assert (workspace / ".gitignore").read_text(encoding="utf-8") == (
        "tmp/\n.cache/\n__pycache__/\n*.pyc\nnode_modules/\n.venv/\n"
    )
    assert workspaces.head("project-1")


def test_commit_records_revision_and_structured_trailers(tmp_path: Path) -> None:
    workspaces = ProjectWorkspace(tmp_path)
    workspace = workspaces.initialize("project-1")
    (workspace / "structured" / "matrix.json").write_text('{"rows": []}\n', encoding="utf-8")

    revision = workspaces.commit(
        "project-1",
        summary="chat_turn: 提取响应矩阵",
        run_id="run-123",
        session_id="session-456",
        kind="chat_turn",
    )

    assert revision == workspaces.head("project-1")
    latest = workspaces.history("project-1", limit=1)[0]
    assert latest.sha == revision
    assert latest.summary == "chat_turn: 提取响应矩阵"
    assert latest.run_id == "run-123"
    assert latest.session_id == "session-456"
    assert latest.kind == "chat_turn"
    assert latest.interrupted is False


def test_upload_commit_without_run_omits_run_trailers(tmp_path: Path) -> None:
    workspaces = ProjectWorkspace(tmp_path)
    workspace = workspaces.initialize("project-1")
    (workspace / "sources" / "招标文件.md").write_text("# 招标\n", encoding="utf-8")

    revision = workspaces.commit(
        "project-1",
        summary="upload: sources/招标文件.md",
        kind="upload",
        paths=["sources/招标文件.md"],
    )

    assert revision == workspaces.head("project-1")
    latest = workspaces.history("project-1", limit=1)[0]
    assert latest.kind == "upload"
    assert latest.run_id is None
    assert latest.session_id is None
    assert latest.interrupted is False


def test_interrupted_commit_records_trailer(tmp_path: Path) -> None:
    workspaces = ProjectWorkspace(tmp_path)
    workspace = workspaces.initialize("project-1")
    (workspace / "deliverables" / "partial.md").write_text("未完成\n", encoding="utf-8")

    workspaces.commit(
        "project-1",
        summary="chat_turn: 保存中断成果",
        run_id="run-interrupted",
        session_id="session-1",
        kind="chat_turn",
        interrupted=True,
    )

    assert workspaces.history("project-1", limit=1)[0].interrupted is True


def test_concurrent_commits_are_serialized_per_project(tmp_path: Path) -> None:
    workspaces = ProjectWorkspace(tmp_path)
    workspace = workspaces.initialize("project-1")
    (workspace / "structured" / "one.json").write_text("1\n", encoding="utf-8")
    (workspace / "structured" / "two.json").write_text("2\n", encoding="utf-8")
    barrier = Barrier(2)

    def commit_file(name: str) -> str:
        barrier.wait()
        return workspaces.commit(
            "project-1",
            summary=f"chat_turn: 提交 {name}",
            run_id=f"run-{name}",
            session_id=f"session-{name}",
            kind="chat_turn",
            paths=[f"structured/{name}.json"],
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        revisions = list(executor.map(commit_file, ("one", "two")))

    assert len(set(revisions)) == 2
    history = workspaces.history("project-1", limit=2)
    assert {revision.run_id for revision in history} == {"run-one", "run-two"}


def test_commit_without_changes_is_a_noop(tmp_path: Path) -> None:
    workspaces = ProjectWorkspace(tmp_path)
    workspaces.initialize("project-1")
    original_head = workspaces.head("project-1")

    revision = workspaces.commit(
        "project-1",
        summary="chat_turn: 仅查询",
        run_id="run-empty",
        session_id="session-1",
        kind="chat_turn",
    )

    assert revision is None
    assert workspaces.head("project-1") == original_head
    assert len(workspaces.history("project-1")) == 1


def test_list_and_read_files_expose_committed_workspace_content(tmp_path: Path) -> None:
    workspaces = ProjectWorkspace(tmp_path)
    workspace = workspaces.initialize("project-1")
    (workspace / "sources" / "招标文件.md").write_text("# 招标文件\n", encoding="utf-8")
    (workspace / "deliverables" / "技术方案.md").write_text("# 技术方案\n", encoding="utf-8")
    (workspace / "tmp" / "scratch.txt").write_text("临时内容", encoding="utf-8")
    (workspace / ".cache").mkdir()
    (workspace / ".cache" / "cache.bin").write_bytes(b"cache")
    (workspace / "structured" / "__pycache__").mkdir()
    (workspace / "structured" / "__pycache__" / "module.pyc").write_bytes(b"pyc")
    (workspace / "structured" / "other.pyc").write_bytes(b"pyc")
    (workspace / "node_modules").mkdir()
    (workspace / "node_modules" / "package.json").write_text("{}", encoding="utf-8")
    (workspace / ".venv").mkdir()
    (workspace / ".venv" / "pyvenv.cfg").write_text("home = /usr/bin", encoding="utf-8")
    workspaces.commit(
        "project-1",
        summary="upload: 导入招标文件",
        run_id="run-upload",
        session_id="session-1",
        kind="upload",
    )

    files = workspaces.list_files("project-1")

    assert [(file.path, file.size) for file in files] == [
        (".gitignore", len((workspace / ".gitignore").read_bytes())),
        ("deliverables/技术方案.md", len("# 技术方案\n".encode())),
        ("sources/招标文件.md", len("# 招标文件\n".encode())),
    ]
    assert workspaces.read_file("project-1", "sources/招标文件.md") == "# 招标文件\n".encode()
