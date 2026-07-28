import pytest


@pytest.fixture(autouse=True)
def host_mode_default(monkeypatch):
    """测试环境显式 host 模式:server 默认 kind 已切 smolvm(spec D5),
    不兜底会让每个 POST /sessions 走 preflight 并可能真起 VM。
    需要验证默认链路的测试自行覆盖 env / mock preflight。
    """
    import os

    from hagent.server.routers.sessions import set_default_sandbox_kind

    if "HAGENT_SANDBOX_KIND" not in os.environ:
        monkeypatch.setenv("HAGENT_SANDBOX_KIND", "none")
    # create_app 会写模块级默认 kind;逐测试重置防串扰
    set_default_sandbox_kind(None)
    yield
    set_default_sandbox_kind(None)
