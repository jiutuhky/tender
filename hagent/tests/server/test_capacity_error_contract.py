"""准入失败须保留会话、拒绝本轮并返回可重试的结构化错误。"""
import pytest
from fastapi.testclient import TestClient

from hagent.sandbox.ledger import CapacityExceeded
from hagent.sandbox.pool import PoolExhausted
from hagent.server.app import create_app
from tests.server.helpers import create_project_session


@pytest.mark.parametrize('error,reason', [
    (PoolExhausted('pool full'), 'pool_full'),
    (CapacityExceeded('memory full'), 'host_capacity'),
])
def test_capacity_failure_returns_retryable_error(tmp_path, monkeypatch, error, reason):
    monkeypatch.setenv('HAGENT_DB_PATH', str(tmp_path / 'sessions.db'))
    monkeypatch.setenv('HAGENT_WORKSPACE_ROOT', str(tmp_path / 'workspace'))
    monkeypatch.delenv('HAGENT_API_KEY', raising=False)
    client = TestClient(create_app())
    session = create_project_session(client).json()
    def unavailable(*args, **kwargs):
        raise error
    monkeypatch.setattr('hagent.server.routers.messages._session_sandbox', unavailable)
    response = client.post(f"/sessions/{session['session_id']}/messages", json={'content': '开始解析'})
    assert response.status_code == 503
    assert response.headers['Retry-After'] == '30'
    assert response.json()['detail']['code'] == 'sandbox_capacity_unavailable'
    assert response.json()['detail']['reason'] == reason
    assert response.json()['detail']['retry_after_seconds'] == 30
    from hagent.server.routers.sessions import get_session_manager, get_store
    manager = get_session_manager()
    assert get_store().get(session['session_id']) is not None
    assert not manager.has_active_runs(session['project_id'])
