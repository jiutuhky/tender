from hagent.server import agents


def test_get_or_build_agent_uses_filesystem_backend(tmp_path, monkeypatch):
    captured = {}

    def fake_create_hagent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(agents, "_agents", {})
    monkeypatch.setattr(agents, "get_checkpointer", lambda: object())
    monkeypatch.setattr(agents, "create_hagent", fake_create_hagent)

    agent = agents.get_or_build_agent("sid", str(tmp_path))

    assert agent is not None
    assert type(captured["backend"]).__name__ == "FilesystemBackend"
    assert captured["task_list_id"] == "sid"
    assert captured.get("sandbox") is None


def test_get_or_build_agent_passes_sandbox_when_provided(tmp_path, monkeypatch):
    """sandbox= path: create_hagent must receive sandbox= and skip the
    FilesystemBackend kwarg, otherwise core.py would spin a second container."""
    captured = {}

    def fake_create_hagent(**kwargs):
        captured.update(kwargs)
        return object()

    fake_sandbox = object()
    monkeypatch.setattr(agents, "_agents", {})
    monkeypatch.setattr(agents, "get_checkpointer", lambda: object())
    monkeypatch.setattr(agents, "create_hagent", fake_create_hagent)

    agent = agents.get_or_build_agent("sid", str(tmp_path), sandbox=fake_sandbox)

    assert agent is not None
    assert captured.get("sandbox") is fake_sandbox
    assert "backend" not in captured
    assert captured["task_list_id"] == "sid"


def test_close_agent_closes_cached_bash_runtime(monkeypatch):
    class FakeRuntime:
        closed = False

        def close(self):
            self.closed = True

    class FakeAgent:
        def __init__(self):
            self._hagent_bash_runtime = FakeRuntime()

    agent = FakeAgent()
    monkeypatch.setattr(agents, "_agents", {"sid": agent})

    agents.close_agent("sid")

    assert agent._hagent_bash_runtime.closed is True
    assert agents._agents == {}
