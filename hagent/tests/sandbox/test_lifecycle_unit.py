from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hagent.sandbox.docker.lifecycle import DockerContainerLifecycle, ContainerStartError
from hagent.sandbox.docker.runtime import RUNTIME_RUNC, RUNTIME_RUNSC


@pytest.fixture
def mock_docker_client():
    with patch("hagent.sandbox.docker.lifecycle.docker.from_env") as mock_from_env:
        client = MagicMock()
        mock_from_env.return_value = client
        yield client


def test_start_uses_selected_runtime_and_safe_env(mock_docker_client):
    container = MagicMock()
    container.id = "abc123def456"
    container.status = "running"
    container.exec_run.return_value = (0, b"Python 3.12.0")
    mock_docker_client.containers.run.return_value = container

    with patch("hagent.sandbox.docker.lifecycle.select_runtime", return_value=RUNTIME_RUNSC), \
         patch("hagent.sandbox.docker.lifecycle.ensure_image", return_value="hagent/sandbox:dev"):
        lc = DockerContainerLifecycle(image_tag="hagent/sandbox:dev")
        lc.start()

    args, kwargs = mock_docker_client.containers.run.call_args
    assert kwargs["runtime"] == RUNTIME_RUNSC
    assert kwargs["detach"] is True
    assert kwargs["network"] == "bridge"
    # secrets must NOT be passed in env
    assert "ANTHROPIC_API_KEY" not in (kwargs.get("environment") or {})
    assert "AWS_SECRET_ACCESS_KEY" not in (kwargs.get("environment") or {})


def test_start_falls_back_to_runc_when_runsc_unavailable(mock_docker_client):
    container = MagicMock(id="abc", status="running")
    container.exec_run.return_value = (0, b"Python 3.12.0")
    mock_docker_client.containers.run.return_value = container
    with patch("hagent.sandbox.docker.lifecycle.select_runtime", return_value=RUNTIME_RUNC), \
         patch("hagent.sandbox.docker.lifecycle.ensure_image", return_value="hagent/sandbox:dev"):
        lc = DockerContainerLifecycle(image_tag="hagent/sandbox:dev")
        lc.start()
    _, kwargs = mock_docker_client.containers.run.call_args
    assert kwargs["runtime"] == RUNTIME_RUNC


def test_start_raises_container_start_error_on_runtime_failure(mock_docker_client):
    from docker.errors import APIError
    mock_docker_client.containers.run.side_effect = APIError("OCI runtime create failed")
    with patch("hagent.sandbox.docker.lifecycle.select_runtime", return_value=RUNTIME_RUNC), \
         patch("hagent.sandbox.docker.lifecycle.ensure_image", return_value="hagent/sandbox:dev"):
        lc = DockerContainerLifecycle(image_tag="hagent/sandbox:dev")
        with pytest.raises(ContainerStartError):
            lc.start()


def test_stop_removes_container(mock_docker_client):
    container = MagicMock(id="abc", status="running")
    container.exec_run.return_value = (0, b"Python 3.12.0")
    mock_docker_client.containers.run.return_value = container
    with patch("hagent.sandbox.docker.lifecycle.select_runtime", return_value=RUNTIME_RUNC), \
         patch("hagent.sandbox.docker.lifecycle.ensure_image", return_value="hagent/sandbox:dev"):
        lc = DockerContainerLifecycle(image_tag="hagent/sandbox:dev")
        lc.start()
        lc.stop()
    container.stop.assert_called_once()
    container.remove.assert_called_once()


def test_await_ready_timeout_cleans_up_container(mock_docker_client, monkeypatch):
    """Readiness probe failure should stop+remove the container, not leak it."""
    container = MagicMock(id="abc", status="running")
    # exec_run never returns exit_code==0 → readiness probe keeps failing
    container.exec_run.return_value = (1, b"")
    mock_docker_client.containers.run.return_value = container

    # Squash the readiness timeout so the test runs fast
    monkeypatch.setattr(
        "hagent.sandbox.docker.lifecycle.READINESS_TIMEOUT_SECONDS",
        0.05,
    )

    with patch("hagent.sandbox.docker.lifecycle.select_runtime", return_value=RUNTIME_RUNC), \
         patch("hagent.sandbox.docker.lifecycle.ensure_image", return_value="hagent/sandbox:dev"):
        lc = DockerContainerLifecycle(image_tag="hagent/sandbox:dev")
        with pytest.raises(ContainerStartError):
            lc.start()

    # Critical: the half-started container must be cleaned up so it doesn't leak.
    container.stop.assert_called()
    container.remove.assert_called()


def test_start_internal_fallback_from_runsc_to_runc_on_api_error(mock_docker_client):
    """When select_runtime picks runsc but containers.run errors, lifecycle retries with runc."""
    from docker.errors import APIError

    container = MagicMock(id="abc", status="running")
    container.exec_run.return_value = (0, b"Python 3.12.0")

    # First call (runsc) raises APIError; second call (runc) succeeds.
    mock_docker_client.containers.run.side_effect = [
        APIError("OCI runtime create failed (runsc)"),
        container,
    ]

    with patch("hagent.sandbox.docker.lifecycle.select_runtime", return_value=RUNTIME_RUNSC), \
         patch("hagent.sandbox.docker.lifecycle.ensure_image", return_value="hagent/sandbox:dev"):
        lc = DockerContainerLifecycle(image_tag="hagent/sandbox:dev")
        manifest = lc.start()

    assert manifest.runtime == RUNTIME_RUNC
    assert mock_docker_client.containers.run.call_count == 2
    # Second call should have runtime=runc
    _, second_kwargs = mock_docker_client.containers.run.call_args_list[1]
    assert second_kwargs["runtime"] == RUNTIME_RUNC
