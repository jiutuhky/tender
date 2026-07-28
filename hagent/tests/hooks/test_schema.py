"""配置/输出 schema 的 alias 往返与校验测试。"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from hagent.hooks.schema import (
    AgentHookConfig,
    CommandHookConfig,
    HookConfig,
    HookJSONOutput,
    HookMatcherConfig,
    HooksSettings,
    HttpHookConfig,
    PromptHookConfig,
)

_adapter: TypeAdapter = TypeAdapter(HookConfig)


def test_command_hook_aliases():
    hook = _adapter.validate_python(
        {
            "type": "command",
            "command": "echo hi",
            "if": "Bash(git *)",
            "timeout": 5,
            "statusMessage": "checking",
            "once": True,
            "async": True,
            "asyncRewake": False,
        }
    )
    assert isinstance(hook, CommandHookConfig)
    assert hook.if_ == "Bash(git *)"
    assert hook.async_ is True
    assert hook.status_message == "checking"
    assert hook.dedup_payload == "bash\0echo hi\0Bash(git *)"


def test_discriminated_union_by_type():
    assert isinstance(
        _adapter.validate_python({"type": "prompt", "prompt": "ok?"}),
        PromptHookConfig,
    )
    assert isinstance(
        _adapter.validate_python({"type": "agent", "prompt": "verify"}),
        AgentHookConfig,
    )
    assert isinstance(
        _adapter.validate_python({"type": "http", "url": "http://localhost:9/h"}),
        HttpHookConfig,
    )
    with pytest.raises(ValidationError):
        _adapter.validate_python({"type": "nope", "command": "x"})


def test_timeout_must_be_positive():
    with pytest.raises(ValidationError):
        _adapter.validate_python({"type": "command", "command": "x", "timeout": 0})


def test_dedup_payload_shell_normalized():
    # 缺省 shell 与显式 bash 视作同一身份（对齐 CC legacy 配置去重）
    a = CommandHookConfig(command="echo x")
    b = _adapter.validate_python({"type": "command", "command": "echo x", "shell": "bash"})
    assert a.dedup_payload == b.dedup_payload


def test_hooks_settings_parses_cc_shape():
    settings = HooksSettings.model_validate(
        {
            "model": "whatever",  # settings.json 的其他键被忽略
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "./check.sh"}],
                    }
                ],
                "Stop": [{"hooks": [{"type": "command", "command": "exit 0"}]}],
            },
        }
    )
    pre = settings.hooks["PreToolUse"]
    assert isinstance(pre[0], HookMatcherConfig)
    assert pre[0].matcher == "Bash"
    assert settings.hooks["Stop"][0].matcher is None


def test_hook_json_output_aliases():
    out = HookJSONOutput.model_validate(
        {
            "continue": False,
            "stopReason": "blocked by policy",
            "suppressOutput": True,
            "decision": "block",
            "reason": "nope",
            "systemMessage": "careful",
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "dangerous",
                "updatedInput": {"command": "ls"},
                "additionalContext": "ctx",
            },
        }
    )
    assert out.continue_ is False
    assert out.stop_reason == "blocked by policy"
    assert out.hook_specific_output is not None
    assert out.hook_specific_output.permission_decision == "deny"
    assert out.hook_specific_output.updated_input == {"command": "ls"}


def test_hook_json_output_async_shape():
    out = HookJSONOutput.model_validate({"async": True, "asyncTimeout": 5000})
    assert out.async_ is True
    assert out.async_timeout == 5000


def test_hook_json_output_rejects_bad_permission_decision():
    with pytest.raises(ValidationError):
        HookJSONOutput.model_validate(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "maybe",
                }
            }
        )
