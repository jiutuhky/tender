import logging

from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from hagent.sanitize import sanitize_anthropic_thinking_blocks_middleware
from hagent.skills.models import SkillMetadata
from hagent.skills.registry import SkillRegistry
from hagent.subagents.compiler import compile_subagent_runnable


class _Args(BaseModel):
    x: int = 0


def _tool(name):
    return StructuredTool.from_function(name=name, description="t", func=lambda x=0: x, args_schema=_Args)


def test_compile_uses_parent_model_when_spec_omits_model(monkeypatch):
    captured: dict = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return "fake_runnable"

    monkeypatch.setattr("hagent.subagents.compiler.create_agent", fake_create_agent)
    spec = {"name": "x", "description": "y", "system_prompt": "z", "tools": ["*"]}
    runnable = compile_subagent_runnable(
        spec, parent_model="anthropic:claude-sonnet-4-6", parent_tools=[_tool("Read")]
    )
    assert runnable == "fake_runnable"
    assert captured["model"].model == "claude-sonnet-4-6"
    assert captured["system_prompt"] == "z"
    assert captured["name"] == "x"
    assert [t.name for t in captured["tools"]] == ["Read"]


def test_compile_attaches_thinking_sanitizer_middleware(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "hagent.subagents.compiler.create_agent", lambda **kw: captured.update(kw) or "x"
    )
    compile_subagent_runnable(
        {"name": "x", "description": "y", "system_prompt": "z", "tools": ["*"]},
        parent_model="anthropic:claude-sonnet-4-6",
        parent_tools=[_tool("Read")],
    )
    assert sanitize_anthropic_thinking_blocks_middleware in captured["middleware"]


def test_compile_resolves_model_before_create_agent(monkeypatch):
    captured: dict = {}
    resolved_model = object()

    def fake_resolve_model(model: str):
        captured["resolved_from"] = model
        return resolved_model

    monkeypatch.setattr(
        "hagent.subagents.compiler.resolve_model",
        fake_resolve_model,
    )
    monkeypatch.setattr(
        "hagent.subagents.compiler.create_agent",
        lambda **kw: captured.update(kw) or "x",
    )

    compile_subagent_runnable(
        {"name": "x", "description": "y", "system_prompt": "z", "tools": ["*"]},
        parent_model="anthropic:qwen3.6-27b",
        parent_tools=[_tool("Read")],
    )

    assert captured["resolved_from"] == "anthropic:qwen3.6-27b"
    assert captured["model"] is resolved_model


def test_compile_resolves_model_alias(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "hagent.subagents.compiler.create_agent", lambda **kw: captured.update(kw) or "x"
    )
    compile_subagent_runnable(
        {"name": "x", "description": "y", "system_prompt": "z", "tools": ["*"], "model": "haiku"},
        parent_model="anthropic:claude-sonnet-4-6",
        parent_tools=[_tool("Read")],
    )
    assert captured["model"].model == "claude-haiku-4-5"


def test_compile_with_inherit_keeps_parent_model(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "hagent.subagents.compiler.create_agent", lambda **kw: captured.update(kw) or "x"
    )
    compile_subagent_runnable(
        {"name": "x", "description": "y", "system_prompt": "z", "tools": ["*"], "model": "inherit"},
        parent_model="anthropic:claude-sonnet-4-6",
        parent_tools=[_tool("Read")],
    )
    assert captured["model"].model == "claude-sonnet-4-6"


def test_compile_applies_tool_resolution(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "hagent.subagents.compiler.create_agent", lambda **kw: captured.update(kw) or "x"
    )
    parent = [_tool("Read"), _tool("Edit"), _tool("Write")]
    compile_subagent_runnable(
        {
            "name": "x",
            "description": "y",
            "system_prompt": "z",
            "tools": ["*"],
            "disallowed_tools": ["Edit", "Write"],
        },
        parent_model="anthropic:claude-sonnet-4-6",
        parent_tools=parent,
    )
    assert [t.name for t in captured["tools"]] == ["Read"]


def test_compile_warns_on_unknown_tools(monkeypatch, caplog):
    monkeypatch.setattr("hagent.subagents.compiler.create_agent", lambda **kw: "x")
    with caplog.at_level(logging.WARNING, logger="hagent.subagents.compiler"):
        compile_subagent_runnable(
            {"name": "x", "description": "y", "system_prompt": "z", "tools": ["Read", "Ghost"]},
            parent_model="anthropic:claude-sonnet-4-6",
            parent_tools=[_tool("Read")],
        )
    assert "Ghost" in caplog.text


def test_compile_preloads_declared_skills(monkeypatch, tmp_path):
    captured = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.subagents.compiler.create_agent", fake_create_agent)
    monkeypatch.setattr("hagent.subagents.compiler.resolve_model", lambda m: m)

    skill_dir = tmp_path / "review"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: Review code.\n---\n# Review\nRead the diff.",
        encoding="utf-8",
    )
    registry = SkillRegistry([
        SkillMetadata(
            name="review",
            description="Review code.",
            skill_file=skill_dir / "SKILL.md",
            base_dir=skill_dir,
            source_label="Test",
        )
    ])

    compile_subagent_runnable(
        {
            "name": "x",
            "description": "y",
            "system_prompt": "base",
            "tools": ["*"],
            "skills": ["review"],
        },
        parent_model="anthropic:claude-sonnet-4-6",
        parent_tools=[_tool("Read")],
        skill_registry=registry,
    )

    assert "base" in captured["system_prompt"]
    assert "Preloaded skill: review" in captured["system_prompt"]
    assert "Base directory for this skill:" in captured["system_prompt"]
    assert "Read the diff." in captured["system_prompt"]


def test_compile_preloads_skill_with_materializer_base_dir(monkeypatch, tmp_path):
    captured = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.subagents.compiler.create_agent", fake_create_agent)
    monkeypatch.setattr("hagent.subagents.compiler.resolve_model", lambda m: m)

    skill_dir = tmp_path / "review"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: Review code.\n---\n# Review\nRead ${CLAUDE_SKILL_DIR}/r.md.",
        encoding="utf-8",
    )
    registry = SkillRegistry([
        SkillMetadata(
            name="review",
            description="Review code.",
            skill_file=skill_dir / "SKILL.md",
            base_dir=skill_dir,
            source_label="Test",
        )
    ])

    class _FakeMaterializer:
        def materialize(self, skill):
            return f"/tmp/hagent/skills/zz/{skill.name}"

    compile_subagent_runnable(
        {
            "name": "x",
            "description": "y",
            "system_prompt": "base",
            "tools": ["*"],
            "skills": ["review"],
        },
        parent_model="anthropic:claude-sonnet-4-6",
        parent_tools=[_tool("Read")],
        skill_registry=registry,
        materializer=_FakeMaterializer(),
    )

    assert "Base directory for this skill: /tmp/hagent/skills/zz/review" in captured["system_prompt"]
    assert "Read /tmp/hagent/skills/zz/review/r.md." in captured["system_prompt"]
    assert str(skill_dir) not in captured["system_prompt"]


def test_compile_does_not_preload_disabled_skills(monkeypatch, tmp_path, caplog):
    captured = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("hagent.subagents.compiler.create_agent", fake_create_agent)
    monkeypatch.setattr("hagent.subagents.compiler.resolve_model", lambda m: m)

    skill_dir = tmp_path / "secret"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: Secret skill.\ndisable-model-invocation: true\n---\n# Secret",
        encoding="utf-8",
    )
    registry = SkillRegistry([
        SkillMetadata(
            name="secret",
            description="Secret skill.",
            skill_file=skill_dir / "SKILL.md",
            base_dir=skill_dir,
            source_label="Test",
            disable_model_invocation=True,
        )
    ])

    with caplog.at_level(logging.WARNING, logger="hagent.subagents.compiler"):
        compile_subagent_runnable(
            {
                "name": "x",
                "description": "y",
                "system_prompt": "base",
                "tools": ["*"],
                "skills": ["secret"],
            },
            parent_model="anthropic:claude-sonnet-4-6",
            parent_tools=[_tool("Read")],
            skill_registry=registry,
        )

    assert captured["system_prompt"] == "base"
    assert "disabled skill secret" in caplog.text
