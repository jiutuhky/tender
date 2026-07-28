"""settings 发现/合并/env 覆盖测试。"""

from __future__ import annotations

import json
from pathlib import Path

from hagent.hooks.config import (
    HookRegistration,
    default_settings_paths,
    load_hook_settings,
)
from hagent.hooks.events import HookEvent


def _write_settings(path: Path, hooks: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")


def _cmd(command: str, **extra) -> dict:
    return {"type": "command", "command": command, **extra}


def test_default_paths_order(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "repo"
    paths = default_settings_paths(project, env={}, home=home)
    assert [p for p, _ in paths] == [
        home / ".hagent" / "settings.json",
        project / ".hagent" / "settings.json",
        project / ".hagent" / "settings.local.json",
    ]
    assert [s for _, s in paths] == ["user", "project", "local"]


def test_default_paths_with_claude_compat(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "repo"
    paths = default_settings_paths(
        project, env={"HAGENT_HOOKS_READ_CLAUDE_SETTINGS": "1"}, home=home
    )
    # .claude 兼容层排最前（最低优先级）
    assert paths[0][0] == home / ".claude" / "settings.json"
    assert paths[1][0] == project / ".claude" / "settings.json"
    assert [s for _, s in paths[:2]] == ["claude-user", "claude-project"]


def test_load_merges_three_layers_in_order(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "repo"
    _write_settings(
        home / ".hagent" / "settings.json",
        {"PreToolUse": [{"matcher": "Bash", "hooks": [_cmd("user.sh")]}]},
    )
    _write_settings(
        project / ".hagent" / "settings.json",
        {"PreToolUse": [{"matcher": "Bash", "hooks": [_cmd("project.sh")]}]},
    )
    _write_settings(
        project / ".hagent" / "settings.local.json",
        {"Stop": [{"hooks": [_cmd("local-stop.sh")]}]},
    )
    loaded = load_hook_settings(project, env={}, home=home)
    pre = loaded.for_event(HookEvent.PRE_TOOL_USE)
    assert [(r.hook.command, r.source) for r in pre] == [
        ("user.sh", "user"),
        ("project.sh", "project"),
    ]
    stop = loaded.for_event(HookEvent.STOP)
    assert [(r.hook.command, r.source) for r in stop] == [("local-stop.sh", "local")]
    assert loaded.has(HookEvent.STOP)
    assert not loaded.has(HookEvent.SESSION_END)
    assert not loaded.empty


def test_dedup_key_identical_across_scopes(tmp_path: Path):
    # 去重发生在匹配后（runner 层）；config 层保证同 command 产生同 key
    a = HookRegistration(
        event=HookEvent.PRE_TOOL_USE,
        matcher="Bash",
        hook=__import__("hagent.hooks.schema", fromlist=["CommandHookConfig"]).CommandHookConfig(
            command="check.sh"
        ),
        source="user",
    )
    b = HookRegistration(
        event=HookEvent.PRE_TOOL_USE,
        matcher="Bash",
        hook=a.hook,
        source="local",
    )
    assert a.dedup_key == b.dedup_key


def test_disabled_env_returns_empty(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "repo"
    _write_settings(
        project / ".hagent" / "settings.json",
        {"Stop": [{"hooks": [_cmd("x.sh")]}]},
    )
    loaded = load_hook_settings(
        project, env={"HAGENT_HOOKS_DISABLED": "1"}, home=home
    )
    assert loaded.empty


def test_custom_paths_replace_discovery(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "repo"
    _write_settings(
        project / ".hagent" / "settings.json",
        {"Stop": [{"hooks": [_cmd("default.sh")]}]},
    )
    custom = tmp_path / "custom.json"
    _write_settings(custom, {"Stop": [{"hooks": [_cmd("custom.sh")]}]})
    loaded = load_hook_settings(
        project,
        env={"HAGENT_HOOKS_SETTINGS_PATHS": str(custom)},
        home=home,
    )
    stop = loaded.for_event(HookEvent.STOP)
    assert [r.hook.command for r in stop] == ["custom.sh"]


def test_bad_json_file_skipped(tmp_path: Path, caplog):
    home = tmp_path / "home"
    project = tmp_path / "repo"
    bad = project / ".hagent" / "settings.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not json", encoding="utf-8")
    _write_settings(
        project / ".hagent" / "settings.local.json",
        {"Stop": [{"hooks": [_cmd("ok.sh")]}]},
    )
    loaded = load_hook_settings(project, env={}, home=home)
    assert [r.hook.command for r in loaded.for_event(HookEvent.STOP)] == ["ok.sh"]


def test_unknown_and_unsupported_events_warned(tmp_path: Path, caplog):
    home = tmp_path / "home"
    project = tmp_path / "repo"
    _write_settings(
        project / ".hagent" / "settings.json",
        {
            "NotAnEvent": [{"hooks": [_cmd("a.sh")]}],
            "PreCompact": [{"hooks": [_cmd("b.sh")]}],  # 合法但 hagent 未支持
        },
    )
    with caplog.at_level("WARNING"):
        loaded = load_hook_settings(project, env={}, home=home)
    assert not loaded.has(HookEvent.PRE_TOOL_USE)
    # 未知事件被丢弃；已识别未支持的事件保留配置但发 warning
    assert loaded.has(HookEvent.PRE_COMPACT)
    assert any("未知 hook 事件" in r.message for r in caplog.records)
    assert any("暂未支持" in r.message for r in caplog.records)


def test_claude_settings_read_when_enabled(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "repo"
    _write_settings(
        home / ".claude" / "settings.json",
        {"Stop": [{"hooks": [_cmd("claude.sh")]}]},
    )
    default = load_hook_settings(project, env={}, home=home)
    assert default.empty
    enabled = load_hook_settings(
        project, env={"HAGENT_HOOKS_READ_CLAUDE_SETTINGS": "1"}, home=home
    )
    assert [r.source for r in enabled.for_event(HookEvent.STOP)] == ["claude-user"]
