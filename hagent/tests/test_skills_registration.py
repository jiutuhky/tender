from pathlib import Path

from deepagents.backends import FilesystemBackend

from hagent.config import HagentConfig
from hagent.core import create_hagent


def _write_skill(root: Path, name: str) -> None:
    skill_dir = root / ".hagent" / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\ndescription: {name} skill.\n---\n# {name}\n",
        encoding="utf-8",
    )


def test_create_hagent_registers_skill_tool_and_middleware(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return type("FakeAgent", (), {})()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)
    _write_skill(tmp_path, "review")
    monkeypatch.chdir(tmp_path)

    create_hagent(
        config=HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False),
        backend=FilesystemBackend(root_dir=tmp_path, virtual_mode=False),
        agents_dirs=[],
        disable_builtin_agents=True,
    )

    assert "Skill" in {tool.name for tool in captured["tools"]}
    assert any(type(middleware).__name__ == "HagentSkillsMiddleware" for middleware in captured["middleware"])
    assert "skills" not in captured


def test_create_hagent_attaches_skill_registry(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "hagent.core._create_deep_agent",
        lambda **_kwargs: type("FakeAgent", (), {})(),
    )
    _write_skill(tmp_path, "review")
    monkeypatch.chdir(tmp_path)

    agent = create_hagent(
        config=HagentConfig(model="anthropic:claude-sonnet-4-6", langsmith_tracing=False),
        backend=FilesystemBackend(root_dir=tmp_path, virtual_mode=False),
        agents_dirs=[],
        disable_builtin_agents=True,
    )

    registry = getattr(agent, "_hagent_skill_registry")
    assert registry.require("review").name == "review"
