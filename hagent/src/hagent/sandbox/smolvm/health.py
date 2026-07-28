"""项目级租约的 SmolVM 健康治理。"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from hagent.sandbox.smolvm.audit import SandboxAuditor
from hagent.server.leases import SandboxState
from hagent.server.runs import RunStatus

if TYPE_CHECKING:
    from hagent.server.project_workspace import ProjectWorkspace
    from hagent.server.runs import RunStore

logger = logging.getLogger(__name__)

RESCUE_MAX_FILES = 200
RESCUE_LIST_TIMEOUT_SECONDS = 10


class SmolVMHealthChecker:
    def __init__(
        self,
        *,
        targets_fn: Callable[[], list[tuple[str, object]]],
        drop_fn: Callable[
            [str, object, Callable[[], None], Callable[[], None]],
            bool,
        ],
        leases,
        workspace_root: Path | str,
        auditor: SandboxAuditor | None = None,
        rescue_max_files: int = RESCUE_MAX_FILES,
        event_fn: Callable[[str, str, object, str | None], None] | None = None,
        project_workspace: ProjectWorkspace | None = None,
        run_store: RunStore | None = None,
    ) -> None:
        self._targets_fn = targets_fn
        self._drop_fn = drop_fn
        self._leases = leases
        self._workspace_root = Path(workspace_root)
        self._auditor = auditor or SandboxAuditor()
        self._rescue_max_files = rescue_max_files
        self._event_fn = event_fn
        self._project_workspace = project_workspace
        self._run_store = run_store

    def targets(self) -> list[tuple[str, object]]:
        return self._targets_fn()

    def check(self, sandbox) -> bool:
        manifest = getattr(sandbox, "manifest", None)
        if getattr(manifest, "paused", False):
            return True
        probe = getattr(sandbox, "health_check", None)
        if not callable(probe):
            return True
        try:
            return bool(probe())
        except Exception:  # noqa: BLE001
            return False

    def on_unhealthy(self, project_id: str, sandbox) -> None:
        def finalize_drop() -> None:
            self._leases.update_state(project_id, state=SandboxState.ORPHANED.value)
            self._auditor.record_event(
                event="health_fail",
                project_id=project_id,
                vm_id=getattr(getattr(sandbox, "manifest", None), "container_id", None),
                detail={"reason": "连续探活失败,杀重建"},
            )
            if self._event_fn is not None:
                self._event_fn("health_fail", project_id, sandbox, "连续探活失败,杀重建")
            logger.warning("project %s 健康巡检杀重建:VM 已清,待下一轮重建", project_id)

        try:
            dropped = self._drop_fn(
                project_id,
                sandbox,
                lambda: self._rescue_artifacts(project_id, sandbox),
                finalize_drop,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("project %s 清残留失败(交给 reaper 兜底): %s", project_id, exc)
            return
        if not dropped:
            logger.info("project %s 健康失败目标已替换，跳过陈旧处置", project_id)

    def _rescue_artifacts(self, project_id: str, sandbox) -> None:
        try:
            workspace = getattr(sandbox, "workspace_dir", "/workspace").rstrip("/")
            listing = sandbox.execute(
                f"find {workspace} -type f | head -{self._rescue_max_files}",
                timeout=RESCUE_LIST_TIMEOUT_SECONDS,
            )
            if listing.exit_code != 0:
                logger.warning(
                    "project %s artifacts 抢救:列文件失败(exit=%s)",
                    project_id,
                    listing.exit_code,
                )
                return
            paths = [
                line.strip()
                for line in listing.output.splitlines()
                if line.strip().startswith(workspace + "/")
                and ".git" not in Path(line.strip()[len(workspace) :].lstrip("/")).parts
            ][: self._rescue_max_files]
            if not paths:
                return
            host_root = self._workspace_root / "projects" / project_id / "workspace"
            rescued_paths: list[str] = []
            for result in sandbox.download_files(paths):
                if result.content is None:
                    continue
                relative = result.path[len(workspace) :].lstrip("/")
                target = host_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(result.content)
                rescued_paths.append(relative)
            if self._project_workspace is not None and rescued_paths:
                active_runs = (
                    self._run_store.active_for_project(project_id)
                    if self._run_store is not None
                    else []
                )
                if active_runs:
                    run = active_runs[0]
                    self._run_store.mark_checkpointing(run.id)
                    commit_sha = self._project_workspace.commit(
                        project_id,
                        summary=run.summary,
                        run_id=run.id,
                        session_id=run.session_id or "",
                        kind=run.kind,
                        interrupted=True,
                        paths=rescued_paths,
                    )
                    self._run_store.finish(
                        run.id,
                        status=RunStatus.INTERRUPTED,
                        commit_sha=commit_sha,
                        error="健康巡检触发兜底抢救",
                    )
                else:
                    self._project_workspace.commit(
                        project_id,
                        summary="lifecycle_rescue: 健康巡检抢救",
                        run_id=f"rescue-{uuid.uuid4().hex[:12]}",
                        session_id="",
                        kind="lifecycle_rescue",
                        interrupted=True,
                        paths=rescued_paths,
                    )
            logger.info(
                "project %s artifacts 抢救:%d/%d 个文件",
                project_id,
                len(rescued_paths),
                len(paths),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("project %s artifacts 抢救失败(不阻断杀重建): %s", project_id, exc)
