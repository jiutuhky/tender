from hagent.skills.arguments import parse_argument_names, parse_arguments, substitute_arguments


def test_parse_arguments_handles_shell_quotes() -> None:
    assert parse_arguments('src "hello world" $HOME') == ["src", "hello world", "$HOME"]


def test_parse_argument_names_accepts_string_and_list() -> None:
    assert parse_argument_names("scope focus 123") == ["scope", "focus"]
    assert parse_argument_names(["scope", "", "2", "focus"]) == ["scope", "focus"]


def test_substitute_arguments_replaces_claude_code_placeholders() -> None:
    content = "all=$ARGUMENTS first=$ARGUMENTS[0] second=$1 named=$scope"
    rendered = substitute_arguments(
        content,
        'src "unit tests"',
        argument_names=["scope", "focus"],
    )
    assert rendered == 'all=src "unit tests" first=src second=unit tests named=src'


def test_substitute_arguments_appends_when_no_placeholder() -> None:
    assert substitute_arguments("Review carefully.", "src") == "Review carefully.\n\nARGUMENTS: src"


def test_substitute_arguments_leaves_content_when_args_missing() -> None:
    assert substitute_arguments("Review $ARGUMENTS.") == "Review $ARGUMENTS."
