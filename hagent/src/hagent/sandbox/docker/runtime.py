"""gVisor runtime detection helpers."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

RUNTIME_RUNC = "runc"
RUNTIME_RUNSC = "runsc"

_DAEMON_JSON_PATH = Path("/etc/docker/daemon.json")

logger = logging.getLogger(__name__)


class RuntimeUnavailable(RuntimeError):
    """Raised when a required docker runtime cannot be found."""


def _read_configured_runtimes() -> set[str]:
    path = _DAEMON_JSON_PATH
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("daemon.json at %s could not be parsed; assuming no extra runtimes", path)
        return set()
    runtimes = data.get("runtimes") or {}
    return set(runtimes.keys()) | {RUNTIME_RUNC}


def select_runtime(prefer: str = RUNTIME_RUNSC) -> str:
    """Pick a docker runtime, preferring gVisor when available.

    Falls back to runc with a WARNING. Set ``HAGENT_SANDBOX_REQUIRE_RUNSC=1``
    to make the absence of runsc fatal (production hardening).
    """
    configured = _read_configured_runtimes()
    require = os.environ.get("HAGENT_SANDBOX_REQUIRE_RUNSC") == "1"
    if prefer == RUNTIME_RUNSC and RUNTIME_RUNSC in configured:
        return RUNTIME_RUNSC
    if prefer == RUNTIME_RUNSC and require:
        raise RuntimeUnavailable(
            "gVisor (runsc) is required (HAGENT_SANDBOX_REQUIRE_RUNSC=1) but not "
            "present in /etc/docker/daemon.json runtimes."
        )
    logger.warning(
        "gVisor (runsc) not configured; falling back to docker default runtime (%s). "
        "Isolation strength is reduced. Configure /etc/docker/daemon.json to enable runsc.",
        RUNTIME_RUNC,
    )
    return RUNTIME_RUNC
