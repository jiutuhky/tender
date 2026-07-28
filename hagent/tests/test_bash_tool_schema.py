import pytest
from pydantic import ValidationError

from hagent.bash_tool import prompt
from hagent.bash_tool.schema import (
    BashInput,
    BashResult,
    get_default_timeout_ms,
    get_max_timeout_ms,
)


def test_bash_input_defaults_match_claude_compatible_schema() -> None:
    payload = BashInput(command="pwd")

    assert payload.command == "pwd"
    assert payload.timeout == 120_000
    assert payload.description is None
    assert payload.run_in_background is None
    assert payload.dangerouslyDisableSandbox is None


def test_bash_input_rejects_timeout_above_maximum() -> None:
    with pytest.raises(ValidationError):
        BashInput(command="pwd", timeout=600_001)


def test_bash_input_rejects_whitespace_only_command_but_preserves_text() -> None:
    with pytest.raises(ValidationError):
        BashInput(command="  ")

    payload = BashInput(command="  pwd  ")

    assert payload.command == "  pwd  "


def test_bash_input_timeout_limits_can_be_configured_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASH_DEFAULT_TIMEOUT_MS", "5000")
    monkeypatch.setenv("BASH_MAX_TIMEOUT_MS", "10000")

    assert get_default_timeout_ms() == 5_000
    assert get_max_timeout_ms() == 10_000
    assert BashInput(command="pwd").timeout == 5_000

    with pytest.raises(ValidationError):
        BashInput(command="pwd", timeout=10_001)


def test_bash_input_env_default_timeout_is_clamped_to_max(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASH_DEFAULT_TIMEOUT_MS", "700000")
    monkeypatch.setenv("BASH_MAX_TIMEOUT_MS", "600000")

    assert BashInput(command="pwd").timeout == get_max_timeout_ms()


def test_bash_result_exposes_later_runtime_fields() -> None:
    result = BashResult(stdout="ok\n", stderr="", exit_code=0)

    assert result.stdout == "ok\n"
    assert result.stderr == ""
    assert result.exit_code == 0
    assert result.interrupted is False
    assert result.background_task_id is None
    assert result.backgrounded_by_user is None
    assert result.assistant_auto_backgrounded is None
    assert result.return_code_interpretation is None
    assert result.no_output_expected is False
    assert result.persisted_output_path is None
    assert result.persisted_output_size is None
    assert result.truncated is False


def test_prompt_constants_use_bash_tool_name() -> None:
    assert prompt.TOOL_NAME == "Bash"
    assert "Executes a given bash command" in prompt.BASH_TOOL_DESCRIPTION
    assert "later integration layer" not in prompt.BASH_TOOL_DESCRIPTION


def test_prompt_parameter_text_matches_claude_compatible_semantics() -> None:
    text = prompt.BASH_TOOL_PARAMETERS

    assert "command" in text and "command to execute" in text
    assert "timeout" in text and "milliseconds" in text and "max" in text
    assert "description" in text and "clear" in text and "active-voice" in text
    assert "run_in_background" in text and "immediate result is not needed" in text
    assert "dangerouslyDisableSandbox" in text
    assert "does not bypass Hagent permission checks" in text
