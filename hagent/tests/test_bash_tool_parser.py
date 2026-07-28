from hagent.bash_tool.parser import parse_bash_command


def test_parse_simple_command_extracts_command_name_and_arguments() -> None:
    parsed = parse_bash_command("git status --short")

    assert parsed.simple_commands == [("git", ("status", "--short"))]
    assert parsed.redirects == ()
    assert parsed.requires_approval is False


def test_parse_compound_command_splits_simple_commands() -> None:
    parsed = parse_bash_command("pwd && git status; ls -la")

    assert parsed.simple_commands == [
        ("pwd", ()),
        ("git", ("status",)),
        ("ls", ("-la",)),
    ]


def test_parse_pipe_splits_simple_commands() -> None:
    parsed = parse_bash_command("cat a | sudo tee /etc/hosts")

    assert parsed.simple_commands == [
        ("cat", ("a",)),
        ("sudo", ("tee", "/etc/hosts")),
    ]


def test_parse_pipe_and_stderr_splits_simple_commands() -> None:
    parsed = parse_bash_command("python -m pytest |& touch owned")

    assert parsed.simple_commands == [
        ("python", ("-m", "pytest")),
        ("touch", ("owned",)),
    ]


def test_parse_redirects_extracts_operator_and_target() -> None:
    parsed = parse_bash_command("pytest -q > logs/test.out 2>> logs/test.err")

    assert parsed.simple_commands == [("pytest", ("-q",))]
    assert parsed.redirects == ((">", "logs/test.out"), ("2>>", "logs/test.err"))


def test_parse_bash_append_stdout_and_stderr_redirect() -> None:
    parsed = parse_bash_command("python -m pytest &>> /tmp/owned")

    assert parsed.simple_commands == [("python", ("-m", "pytest"))]
    assert parsed.redirects == (("&>>", "/tmp/owned"),)


def test_parse_bash_stdout_and_stderr_redirect() -> None:
    parsed = parse_bash_command("python -m pytest >& /tmp/owned")

    assert parsed.simple_commands == [("python", ("-m", "pytest"))]
    assert parsed.redirects == ((">&", "/tmp/owned"),)


def test_parse_command_substitution_requires_approval_as_complex() -> None:
    parsed = parse_bash_command("echo $(cat secret.txt)")

    assert parsed.requires_approval is True
    assert parsed.reason == "complex"


def test_parse_subshell_requires_approval_as_complex() -> None:
    parsed = parse_bash_command("(cd web && npm test)")

    assert parsed.requires_approval is True
    assert parsed.reason == "complex"


def test_parse_control_flow_requires_approval_as_complex() -> None:
    parsed = parse_bash_command("if test -f pyproject.toml; then cat pyproject.toml; fi")

    assert parsed.requires_approval is True
    assert parsed.reason == "complex"


def test_parse_trailing_compound_separator_requires_approval_as_complex() -> None:
    for command in ("ls &&", "pwd |"):
        parsed = parse_bash_command(command)

        assert parsed.requires_approval is True
        assert parsed.reason == "complex"


def test_parse_raw_newline_or_carriage_return_requires_approval_as_complex() -> None:
    for command in ("ls\nrm -rf src/hagent", "pwd\rrm -rf src/hagent"):
        parsed = parse_bash_command(command)

        assert parsed.requires_approval is True
        assert parsed.reason == "complex"


def test_parse_malformed_command_requires_approval_as_complex() -> None:
    parsed = parse_bash_command("echo 'unterminated")

    assert parsed.simple_commands == []
    assert parsed.requires_approval is True
    assert parsed.reason == "complex"
