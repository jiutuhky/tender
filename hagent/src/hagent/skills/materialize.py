"""SkillMaterializer — upload a skill's full directory tree into a sandbox.

In sandbox mode the model's file/bash tools execute *inside* the container, so a
skill's host-side ``base_dir`` is unreachable. Only the SKILL.md body survives
(it is read into the prompt as a string); references/, scripts/, assets/, etc.
are invisible. This class uploads the whole skill directory into a container
path and returns that path for use as the rendered "Base directory", mirroring
Claude Code's bundled-skill extraction (extractBundledSkillFiles -> prependBaseDir).
"""

from __future__ import annotations

import logging
import secrets
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from hagent.skills.models import SkillMetadata

if TYPE_CHECKING:
    from hagent.sandbox.protocol import HagentSandboxProtocol

logger = logging.getLogger(__name__)

SKILL_ROOT = "/tmp/hagent/skills"


class SkillMaterializer:
    """Lazily upload skill directory trees into a sandbox container, memoized.

    A per-instance random nonce isolates this materializer's files from any
    other (e.g. when a pooled container is reused across sessions).
    """

    def __init__(self, sandbox: "HagentSandboxProtocol") -> None:
        self._sandbox = sandbox
        self._root = PurePosixPath(SKILL_ROOT) / secrets.token_hex(4)
        self._memo: dict[str, str] = {}

    def materialize(self, skill: SkillMetadata) -> str:
        """Upload ``skill``'s directory tree into the container; return its base_dir.

        Memoized by skill name — repeated calls return the cached container path
        without re-uploading. Files whose resolved target escapes ``base_dir``
        (e.g. symlinks pointing outside the skill) are skipped.
        """
        cached = self._memo.get(skill.name)
        if cached is not None:
            return cached

        container_base = self._root / skill.name
        base_dir = skill.base_dir.resolve()
        uploads: list[tuple[str, bytes]] = []
        for path in sorted(base_dir.rglob("*")):
            if not path.is_file():
                continue
            if not _within(path, base_dir):
                logger.warning(
                    "skill %s: skipping file escaping base_dir: %s", skill.name, path
                )
                continue
            rel = path.relative_to(base_dir)
            try:
                content = path.read_bytes()
            except OSError as exc:  # noqa: BLE001
                logger.warning("skill %s: cannot read %s: %s", skill.name, path, exc)
                continue
            uploads.append((str(container_base / rel.as_posix()), content))

        if uploads:
            for resp in self._sandbox.upload_files(uploads):
                if resp.error:
                    logger.warning(
                        "skill %s: upload failed for %s: %s",
                        skill.name,
                        resp.path,
                        resp.error,
                    )

        result = str(container_base)
        self._memo[skill.name] = result
        return result


def _within(path: Path, base_dir: Path) -> bool:
    try:
        return path.resolve().is_relative_to(base_dir)
    except (OSError, ValueError):
        return False
