"""Docker container lifecycle for a single Hagent sandbox session."""

from __future__ import annotations

import logging
import time
import uuid

import docker
from docker.errors import APIError, NotFound

from hagent.sandbox.docker.image import DEFAULT_IMAGE_TAG, ensure_image
from hagent.sandbox.docker.runtime import RUNTIME_RUNC, select_runtime
from hagent.sandbox.manifest import SandboxManifest

logger = logging.getLogger(__name__)

CONTAINER_NAME_PREFIX = "hagent-sbx-"
DEFAULT_WORKSPACE_DIR = "/workspace"
DEFAULT_SAFE_ENV = {
    "PATH": "/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin",
    "HOME": DEFAULT_WORKSPACE_DIR,
    "LANG": "C.UTF-8",
    "TERM": "dumb",
}
READINESS_PROBE_CMD = ["python3", "-c", "import sys; print(sys.version)"]
READINESS_TIMEOUT_SECONDS = 10


class ContainerStartError(RuntimeError):
    """Raised when the container could not start within the readiness window."""


class DockerContainerLifecycle:
    """Owns the docker container backing a single sandbox."""

    def __init__(
        self,
        *,
        image_tag: str = DEFAULT_IMAGE_TAG,
        prefer_runtime: str = "runsc",
        env_overrides: dict[str, str] | None = None,
    ) -> None:
        self.sandbox_id = uuid.uuid4().hex[:12]
        self.image_tag = image_tag
        self.prefer_runtime = prefer_runtime
        self._client = docker.from_env()
        self._container = None
        self._runtime: str = RUNTIME_RUNC
        self._env = {**DEFAULT_SAFE_ENV, **(env_overrides or {})}

    @property
    def container_id(self) -> str | None:
        return self._container.id if self._container is not None else None

    def start(self) -> SandboxManifest:
        image_tag = ensure_image(self.image_tag)
        self._runtime = select_runtime(prefer=self.prefer_runtime)
        try:
            container = self._client.containers.run(
                image=image_tag,
                name=f"{CONTAINER_NAME_PREFIX}{self.sandbox_id}",
                detach=True,
                tty=False,
                stdin_open=False,
                runtime=self._runtime,
                network="bridge",
                environment=dict(self._env),
                working_dir=DEFAULT_WORKSPACE_DIR,
                labels={"hagent.sandbox_id": self.sandbox_id, "hagent.kind": "docker"},
            )
        except APIError as exc:
            if self._runtime != RUNTIME_RUNC:
                logger.warning("Retrying container start with runc after error: %s", exc)
                self._runtime = RUNTIME_RUNC
                try:
                    container = self._client.containers.run(
                        image=image_tag,
                        name=f"{CONTAINER_NAME_PREFIX}{self.sandbox_id}",
                        detach=True,
                        tty=False,
                        stdin_open=False,
                        runtime=self._runtime,
                        network="bridge",
                        environment=dict(self._env),
                        working_dir=DEFAULT_WORKSPACE_DIR,
                        labels={"hagent.sandbox_id": self.sandbox_id, "hagent.kind": "docker"},
                    )
                except APIError as exc2:
                    raise ContainerStartError(f"docker run failed (runc fallback): {exc2}") from exc2
            else:
                raise ContainerStartError(f"docker run failed: {exc}") from exc

        self._container = container
        try:
            self._await_ready()
        except ContainerStartError:
            # readiness probe failed — clean up the half-started container
            # so it does not leak into the docker host.
            self.stop()
            raise
        return SandboxManifest(
            sandbox_id=self.sandbox_id,
            kind="docker",
            image_tag=image_tag,
            runtime=self._runtime,
            container_id=container.id,
            workspace_dir=DEFAULT_WORKSPACE_DIR,
        )

    def _await_ready(self) -> None:
        deadline = time.monotonic() + READINESS_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            try:
                exit_code, _ = self._container.exec_run(READINESS_PROBE_CMD, demux=False)
                if exit_code == 0:
                    return
            except APIError:
                pass
            time.sleep(0.1)
        raise ContainerStartError(f"sandbox {self.sandbox_id} did not become ready within {READINESS_TIMEOUT_SECONDS}s")

    def pause(self) -> None:
        if self._container is None:
            return
        try:
            self._container.pause()
        except APIError as exc:
            logger.warning("[%s] pause failed: %s", self.sandbox_id, exc)

    def resume(self) -> None:
        if self._container is None:
            return
        try:
            self._container.unpause()
        except APIError as exc:
            logger.warning("[%s] unpause failed: %s", self.sandbox_id, exc)

    def stop(self) -> None:
        if self._container is None:
            return
        try:
            self._container.stop(timeout=5)
        except (APIError, NotFound) as exc:
            logger.warning("[%s] stop failed: %s", self.sandbox_id, exc)
        try:
            self._container.remove(force=True)
        except (APIError, NotFound) as exc:
            logger.warning("[%s] remove failed: %s", self.sandbox_id, exc)
        self._container = None
