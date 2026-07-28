from pathlib import Path

from hagent.bash_tool.permissions import (
    BashPermissionConfig,
    BashPermissionDecision,
    evaluate_bash_permission,
)


def assert_decision(
    decision: BashPermissionDecision, action: str, reason_contains: str
) -> None:
    assert decision.action == action
    assert reason_contains in decision.reason


def test_deny_rules_beat_ask_and_allow_rules() -> None:
    config = BashPermissionConfig(
        allow_rules=("Bash(rm *)",),
        ask_rules=("Bash(rm *)",),
        deny_rules=("Bash(rm *)",),
    )

    assert_decision(evaluate_bash_permission("rm tmp.txt", config), "deny", "deny rule")


def test_ask_rules_beat_allow_rules() -> None:
    config = BashPermissionConfig(
        allow_rules=("Bash(pytest:*)",),
        ask_rules=("Bash(pytest:*)",),
    )

    assert_decision(evaluate_bash_permission("pytest -q", config), "ask", "ask rule")


def test_exact_prefix_and_wildcard_rule_matching() -> None:
    exact = BashPermissionConfig(allow_rules=("Bash(git status)",))
    prefix = BashPermissionConfig(allow_rules=("Bash(pytest:*)",))
    wildcard = BashPermissionConfig(allow_rules=("Bash(rm *)",))

    assert evaluate_bash_permission("git status", exact).action == "allow"
    assert evaluate_bash_permission("pytest tests/test_core.py -v", prefix).action == "allow"
    assert evaluate_bash_permission("rm build.log", wildcard).action == "allow"


def test_safe_read_only_commands_are_auto_allowed() -> None:
    for command in (
        "pwd",
        "ls -la",
        "git status --short",
        "git diff -- src/hagent/core.py",
        "rg Bash src tests",
        "grep -R hagent src",
        "find src -maxdepth 2 -type f",
        "cat pyproject.toml",
        "head -n 5 pyproject.toml",
        "tail -n 5 pyproject.toml",
        "wc -l pyproject.toml",
        "stat pyproject.toml",
        "file pyproject.toml",
    ):
        assert_decision(evaluate_bash_permission(command), "allow", "read-only")


def test_dangerous_removals_are_denied_or_asked() -> None:
    assert evaluate_bash_permission("rm -rf /").action == "deny"
    assert evaluate_bash_permission("rm -rf src/hagent").action in {"ask", "deny"}


def test_bypass_style_default_allows_redirections_without_prompt(tmp_path: Path) -> None:
    config = BashPermissionConfig(workspace_root=tmp_path)

    assert_decision(
        evaluate_bash_permission("echo value > /etc/hosts", config),
        "allow",
        "bypass",
    )


def test_bypass_style_default_allows_complex_commands_without_prompt() -> None:
    assert_decision(
        evaluate_bash_permission("echo $(cat secret.txt)"),
        "allow",
        "bypass",
    )


def test_sandbox_compatibility_field_does_not_bypass_permissions() -> None:
    decision = evaluate_bash_permission("sudo id")

    assert decision.action == "deny"


def test_pipe_to_destructive_command_is_not_auto_allowed() -> None:
    assert evaluate_bash_permission("rg foo | rm -rf src/hagent").action in {"ask", "deny"}


def test_pipe_to_privilege_escalation_is_denied() -> None:
    assert evaluate_bash_permission("cat a | sudo tee /etc/hosts").action == "deny"


def test_find_delete_is_not_auto_allowed() -> None:
    assert evaluate_bash_permission("find . -delete").action == "ask"


def test_git_diff_output_option_is_allowed_in_bypass_style_default() -> None:
    assert evaluate_bash_permission("git diff --output=/tmp/patch").action == "allow"


def test_trailing_compound_separators_are_allowed_in_bypass_style_default() -> None:
    assert evaluate_bash_permission("ls &&").action == "allow"
    assert evaluate_bash_permission("pwd |").action == "allow"


def test_find_fls_is_allowed_in_bypass_style_default() -> None:
    assert evaluate_bash_permission("find . -fls /tmp/find.out").action == "allow"


def test_raw_newline_or_carriage_return_command_is_not_auto_allowed() -> None:
    assert evaluate_bash_permission("ls\nrm -rf src/hagent").action == "ask"
    assert evaluate_bash_permission("pwd\rrm -rf src/hagent").action == "ask"


def test_rg_preprocessor_option_is_allowed_in_bypass_style_default() -> None:
    assert evaluate_bash_permission("rg --pre sh -n foo src").action == "allow"
    assert evaluate_bash_permission("rg --pre=sh -n foo src").action == "allow"


def test_allow_rules_do_not_override_unsafe_compound_commands() -> None:
    config = BashPermissionConfig(
        allow_rules=(
            "Bash(pytest:*)",
            "Bash(python -m pytest:*)",
            "Bash(npm run test:*)",
        )
    )

    assert evaluate_bash_permission("pytest && rm -rf src/hagent", config).action == "ask"
    assert evaluate_bash_permission("python -m pytest && touch owned", config).action == "allow"
    assert evaluate_bash_permission("npm run test ; rm build.log", config).action == "allow"
    assert evaluate_bash_permission("python -m pytest |& touch owned", config).action == "allow"
    assert evaluate_bash_permission("python -m pytest &>> /tmp/owned", config).action == "allow"
    assert evaluate_bash_permission("python -m pytest >& /tmp/owned", config).action == "allow"


def test_allow_rules_can_allow_single_write_like_test_commands() -> None:
    config = BashPermissionConfig(
        allow_rules=(
            "Bash(python -m pytest:*)",
            "Bash(npm test:*)",
            "Bash(npm run test:*)",
        )
    )

    assert evaluate_bash_permission("python -m pytest -q", config).action == "allow"
    assert evaluate_bash_permission("npm test -- --runInBand", config).action == "allow"
    assert evaluate_bash_permission("npm run test -- --watch=false", config).action == "allow"


def test_bypass_style_default_allows_development_write_commands() -> None:
    for command in (
        "touch generated.txt",
        "mkdir -p build/cache",
        "mv old.txt new.txt",
        "cp source.txt dest.txt",
        "sed -i s/foo/bar/g file.txt",
        "python -m compileall src",
        "npm install",
        "pip install -e .",
        "git add src/hagent/core.py",
    ):
        assert_decision(evaluate_bash_permission(command), "allow", "bypass")
