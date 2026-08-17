from hagent.config import (
    HagentConfig,
    load_base_prompt,
    PROMPT_PATH,
)


def test_prompt_path_resolves_to_repo_prompts():
    assert PROMPT_PATH.name == "hagent_base.zh.md"
    assert PROMPT_PATH.exists()


def test_load_base_prompt_returns_non_empty_chinese():
    text = load_base_prompt()
    assert len(text) > 1000
    # 含必要的中文字符（"你是 Prose" 出现在首段）
    assert "你是 Prose" in text


def test_hagent_config_defaults(monkeypatch):
    monkeypatch.delenv("HAGENT_MODEL", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("HAGENT_SKILLS_PATHS", raising=False)
    cfg = HagentConfig.from_env()
    assert cfg.model == "anthropic:claude-sonnet-4-6"
    assert cfg.langsmith_tracing is False
    assert cfg.skills_paths is None


def test_hagent_config_env_overrides(monkeypatch):
    monkeypatch.setenv("HAGENT_MODEL", "anthropic:claude-opus-4-7")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("HAGENT_MAX_TOKENS", "24000")
    monkeypatch.setenv("HAGENT_SKILLS_PATHS", "/tmp/skills:Tmp")
    cfg = HagentConfig.from_env()
    assert cfg.model == "anthropic:claude-opus-4-7"
    assert cfg.langsmith_tracing is True
    assert cfg.max_tokens == 24000
    assert cfg.skills_paths == "/tmp/skills:Tmp"


def test_sandbox_section_describes_mechanism_per_provider():
    from hagent.config import _sandbox_section

    smol = _sandbox_section("HagentSmolVMSandbox", "/workspace")
    docker = _sandbox_section("HagentDockerSandbox", "/workspace")
    assert "docker exec" not in smol, "smolvm 走 SSH/vsock,不得再硬写 docker exec"
    assert "SSH/vsock" in smol
    assert "docker exec" in docker
    # 沙箱基础设施错误处理指引(与 sandbox/errors.py 契约 marker 对齐)
    for section in (smol, docker):
        assert "[sandbox_unavailable:<reason>]" in section
        assert "**不要**执行沙箱运维命令" in section
    assert _sandbox_section("FilesystemBackend", "/x") == ""
