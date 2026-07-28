"""Default sandbox image bookkeeping."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

import docker
from docker.errors import APIError, ImageNotFound

DEFAULT_IMAGE_TAG = os.environ.get("HAGENT_SANDBOX_IMAGE", "hagent/sandbox:dev")

logger = logging.getLogger(__name__)


def ensure_image(image_tag: str = DEFAULT_IMAGE_TAG, *, build_if_missing: bool = True) -> str:
    """Return ``image_tag`` if available locally; build it if missing.

    Building only triggers for the default tag (``hagent/sandbox:dev``);
    user-supplied tags raise ``ImageNotFound`` instead.
    """
    client = docker.from_env()
    try:
        client.images.get(image_tag)
        return image_tag
    except ImageNotFound:
        pass

    if not build_if_missing or image_tag != DEFAULT_IMAGE_TAG:
        raise ImageNotFound(f"sandbox image {image_tag!r} not present locally")

    bash_path = shutil.which("bash")
    if bash_path is None:
        raise RuntimeError("bash not available — cannot run build_sandbox_image.sh")
    # 定位 repo root：src/hagent/sandbox/docker/image.py → 上跳 4 级
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    script = os.path.join(repo_root, "scripts", "build_sandbox_image.sh")
    if not os.path.isfile(script):
        raise RuntimeError(f"build script not found: {script}")
    proc = subprocess.run(
        [bash_path, script],
        env={**os.environ, "HAGENT_SANDBOX_IMAGE": image_tag},
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise APIError(f"sandbox image build failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return image_tag
