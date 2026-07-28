from pathlib import Path

import pytest

from hagent.bash_tool.output import OutputManager


def test_foreground_small_output_returns_inline_and_cleans_log(tmp_path: Path) -> None:
    manager = OutputManager(tmp_path, inline_threshold=100)
    output_path = manager.create_output_file("task-small")
    output_path.write_text("hello", encoding="utf-8")

    summary = manager.finalize_foreground(output_path)

    assert summary.inline_text == "hello"
    assert summary.truncated is False
    assert summary.persisted_output_path is None
    assert summary.persisted_output_size == 5
    assert not output_path.exists()


def test_foreground_large_output_persists_readable_log(tmp_path: Path) -> None:
    manager = OutputManager(tmp_path, inline_threshold=10)
    output_path = manager.create_output_file("task-large")
    output_path.write_text("0123456789abcdef", encoding="utf-8")

    summary = manager.finalize_foreground(output_path)

    assert summary.inline_text == "0123456789"
    assert summary.truncated is True
    assert summary.persisted_output_path == str(output_path)
    assert summary.persisted_output_size == 16
    assert output_path.read_text(encoding="utf-8") == "0123456789abcdef"
    assert output_path.parent == tmp_path / ".hagent" / "tool-results"


def test_foreground_large_output_preview_does_not_read_entire_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manager = OutputManager(tmp_path, inline_threshold=10)
    output_path = manager.create_output_file("task-stream-preview")
    output_path.write_text("0123456789abcdef", encoding="utf-8")

    original_read_text = Path.read_text

    def fail_if_output_read_text(path: Path, *args, **kwargs):
        if path == output_path:
            raise AssertionError("finalize_foreground must not read the full output file")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_if_output_read_text)

    summary = manager.finalize_foreground(output_path)

    assert summary.inline_text == "0123456789"
    assert summary.truncated is True
    assert summary.persisted_output_path == str(output_path)
