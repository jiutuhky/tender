from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hagent.sandbox.docker.runtime import (
    RUNTIME_RUNC,
    RUNTIME_RUNSC,
    RuntimeUnavailable,
    select_runtime,
)


def test_select_runtime_prefers_runsc_when_daemon_lists_it(tmp_path: Path):
    daemon_json = tmp_path / "daemon.json"
    daemon_json.write_text(
        json.dumps({"runtimes": {"runsc": {"path": "/usr/local/bin/runsc"}}}),
        encoding="utf-8",
    )
    with patch("hagent.sandbox.docker.runtime._DAEMON_JSON_PATH", daemon_json):
        assert select_runtime(prefer=RUNTIME_RUNSC) == RUNTIME_RUNSC


def test_select_runtime_warns_and_falls_back_to_runc(tmp_path, caplog):
    daemon_json = tmp_path / "daemon.json"
    daemon_json.write_text(json.dumps({"runtimes": {}}), encoding="utf-8")
    with patch("hagent.sandbox.docker.runtime._DAEMON_JSON_PATH", daemon_json), caplog.at_level("WARNING"):
        assert select_runtime(prefer=RUNTIME_RUNSC) == RUNTIME_RUNC
    assert any("runsc" in rec.message for rec in caplog.records)


def test_select_runtime_required_raises_when_runsc_missing(tmp_path, monkeypatch):
    daemon_json = tmp_path / "daemon.json"
    daemon_json.write_text(json.dumps({"runtimes": {}}), encoding="utf-8")
    monkeypatch.setattr("hagent.sandbox.docker.runtime._DAEMON_JSON_PATH", daemon_json)
    monkeypatch.setenv("HAGENT_SANDBOX_REQUIRE_RUNSC", "1")
    with pytest.raises(RuntimeUnavailable):
        select_runtime(prefer=RUNTIME_RUNSC)


def test_select_runtime_missing_daemon_json_returns_runc(tmp_path, caplog):
    daemon_json = tmp_path / "missing.json"
    with patch("hagent.sandbox.docker.runtime._DAEMON_JSON_PATH", daemon_json), caplog.at_level("WARNING"):
        assert select_runtime(prefer=RUNTIME_RUNSC) == RUNTIME_RUNC
