from __future__ import annotations

import os
from pathlib import Path

from hagent.skills.loader import load_skills_from_sources
from hagent.skills.materialize import SkillMaterializer


class FakeSandbox:
    """Records upload_files calls; satisfies the bits SkillMaterializer touches."""

    def __init__(self) -> None:
        self.uploads: list[list[tuple[str, bytes]]] = []

    def upload_files(self, files: list[tuple[str, bytes]]):
        self.uploads.append(list(files))

        class _Resp:
            def __init__(self, path: str) -> None:
                self.path = path
                self.error = None

        return [_Resp(path) for path, _ in files]


def _skill(root: Path, name: str) -> None:
    skill_dir = root / name
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: Test skill.\n---\n# body\n", encoding="utf-8"
    )
    (skill_dir / "references" / "a.md").write_text("ref-a", encoding="utf-8")
    (skill_dir / "scripts" / "b.sh").write_text("echo b", encoding="utf-8")


def test_materialize_uploads_full_tree_under_container_root(tmp_path: Path) -> None:
    _skill(tmp_path, "review")
    registry = load_skills_from_sources([(tmp_path, "Project Hagent")])
    skill = registry.require("review")
    sandbox = FakeSandbox()

    base = SkillMaterializer(sandbox).materialize(skill)

    assert base.startswith("/tmp/hagent/skills/")
    assert base.endswith("/review")
    uploaded_paths = {path for batch in sandbox.uploads for path, _ in batch}
    assert f"{base}/SKILL.md" in uploaded_paths
    assert f"{base}/references/a.md" in uploaded_paths
    assert f"{base}/scripts/b.sh" in uploaded_paths


def test_materialize_is_memoized_per_skill(tmp_path: Path) -> None:
    _skill(tmp_path, "review")
    registry = load_skills_from_sources([(tmp_path, "Project Hagent")])
    skill = registry.require("review")
    sandbox = FakeSandbox()
    materializer = SkillMaterializer(sandbox)

    first = materializer.materialize(skill)
    upload_count_after_first = len(sandbox.uploads)
    second = materializer.materialize(skill)

    assert first == second
    assert len(sandbox.uploads) == upload_count_after_first  # no re-upload


def test_materialize_skips_symlink_escaping_base_dir(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    _skill(tmp_path, "review")
    link = tmp_path / "review" / "references" / "escape.txt"
    os.symlink(outside, link)
    registry = load_skills_from_sources([(tmp_path, "Project Hagent")])
    skill = registry.require("review")
    sandbox = FakeSandbox()

    base = SkillMaterializer(sandbox).materialize(skill)

    uploaded_paths = {path for batch in sandbox.uploads for path, _ in batch}
    assert f"{base}/references/escape.txt" not in uploaded_paths
    assert f"{base}/references/a.md" in uploaded_paths
