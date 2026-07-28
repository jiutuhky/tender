import os

from hagent import config as hagent_config
from hagent.server.app import create_app


def test_create_app_loads_dotenv_file(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "HAGENT_MODEL=anthropic:from-dotenv\n"
        "ANTHROPIC_API_KEY=from-dotenv-key\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(hagent_config, "ENV_PATH", env_path, raising=False)
    monkeypatch.delenv("HAGENT_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    create_app()

    assert os.environ["HAGENT_MODEL"] == "anthropic:from-dotenv"
    assert os.environ["ANTHROPIC_API_KEY"] == "from-dotenv-key"


def test_create_app_does_not_override_existing_environment(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("HAGENT_MODEL=anthropic:from-dotenv\n", encoding="utf-8")
    monkeypatch.setattr(hagent_config, "ENV_PATH", env_path, raising=False)
    monkeypatch.setenv("HAGENT_MODEL", "anthropic:from-process")

    create_app()

    assert os.environ["HAGENT_MODEL"] == "anthropic:from-process"
