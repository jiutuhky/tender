import os

import pytest


@pytest.fixture(autouse=True)
def isolate_dotenv_file(monkeypatch, tmp_path):
    from hagent import config as hagent_config

    original_environ = os.environ.copy()
    monkeypatch.setattr(hagent_config, "ENV_PATH", tmp_path / ".env.missing")
    yield
    os.environ.clear()
    os.environ.update(original_environ)
