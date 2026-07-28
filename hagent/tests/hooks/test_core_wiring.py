"""create_hagent 的 hooks 装配测试（monkeypatch _create_deep_agent 桩）。"""

from __future__ import annotations

import json
from pathlib import Path

from hagent.core import create_hagent
from hagent.hooks.config import LoadedHooks
from hagent.hooks.context import HookContext
from hagent.hooks.events import HookEvent
from hagent.hooks.middleware import HagentHooksMiddleware
from hagent.hooks.runner import HookRunner


def _stub(monkeypatch, captured: dict):
    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return type("FakeAgent", (), {})()

    monkeypatch.setattr("hagent.core._create_deep_agent", fake_create_deep_agent)


def _middleware_names(captured: dict) -> list[str]:
    return [type(m).__name__ for m in captured["middleware"]]


def test_no_hook_settings_no_middleware(monkeypatch, tmp_path: Path):
    captured: dict = {}
    _stub(monkeypatch, captured)
    monkeypatch.chdir(tmp_path)  # 空目录：无 .hagent/settings.json
    monkeypatch.setenv("HAGENT_HOOKS_SETTINGS_PATHS", str(tmp_path / "none.json"))
    agent = create_hagent()
    assert "HagentHooksMiddleware" not in _middleware_names(captured)
    assert agent._hagent_hook_runner is None


def test_hook_settings_inject_middleware_at_head(monkeypatch, tmp_path: Path):
    captured: dict = {}
    _stub(monkeypatch, captured)
    settings = tmp_path / "hooks.json"
    settings.write_text(
        json.dumps(
            {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "true"}]}]}}
        )
    )
    monkeypatch.setenv("HAGENT_HOOKS_SETTINGS_PATHS", str(settings))
    agent = create_hagent()
    names = _middleware_names(captured)
    assert names[0] == "HagentHooksMiddleware"
    runner = agent._hagent_hook_runner
    assert isinstance(runner, HookRunner)
    assert runner.has_hooks(HookEvent.PRE_TOOL_USE)
    # agent 型 hook 的只读工具已注入
    assert {t.name for t in runner._agent_tools} == {"Read", "Grep", "Glob"}


def test_hooks_disabled_env(monkeypatch, tmp_path: Path):
    captured: dict = {}
    _stub(monkeypatch, captured)
    settings = tmp_path / "hooks.json"
    settings.write_text(
        json.dumps(
            {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "true"}]}]}}
        )
    )
    monkeypatch.setenv("HAGENT_HOOKS_SETTINGS_PATHS", str(settings))
    monkeypatch.setenv("HAGENT_HOOKS_DISABLED", "1")
    agent = create_hagent()
    assert "HagentHooksMiddleware" not in _middleware_names(captured)
    assert agent._hagent_hook_runner is None


def test_explicit_hook_runner_wins(monkeypatch, tmp_path: Path):
    captured: dict = {}
    _stub(monkeypatch, captured)
    loaded = LoadedHooks()
    ctx = HookContext(
        session_id="srv-1",
        cwd=tmp_path,
        project_root=tmp_path,
        transcript_path=tmp_path / "t.jsonl",
    )
    runner = HookRunner(loaded, ctx)
    agent = create_hagent(hook_runner=runner)
    assert agent._hagent_hook_runner is runner
    hooks_mw = [
        m for m in captured["middleware"] if isinstance(m, HagentHooksMiddleware)
    ]
    assert len(hooks_mw) == 1 and hooks_mw[0].runner is runner
