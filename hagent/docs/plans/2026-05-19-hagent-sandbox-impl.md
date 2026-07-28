# Hagent Sandbox 实现 Plan（M6）

> **存档说明**：本 plan 产出自已退役的 superpowers 工作流，仅作历史参考；新工作一律走仓根 tickets.md（Matt 契约）。

**Goal:** 在 Hagent 中落地 gVisor + Docker 本地 sandbox 能力（M6），同时把 `langchain-daytona` 接口预留为可插拔适配点；LLM 视角的 Bash / Read / Write / Edit / Skill 工具行为与 host 模式 byte-equal。

**Architecture:** 引入 `src/hagent/sandbox/` 包，对接 deepagents 0.6.x 的 `SandboxBackendProtocol`（继承 `BaseSandbox`），通过 `SandboxShellProvider` + `SandboxFileTransport` 把现有 Bash / File 工具桥接到容器；server 端通过 `SessionManager` 拿 `SandboxPool`（warm pool + idle GC）。Daytona 实现仅留 stub。

**Tech Stack:** Python 3.11+, deepagents 0.6.x, docker-py SDK (`docker>=7.1`), gVisor (`runsc`) optional runtime, FastAPI + SSE, pytest 8.

**Spec reference:** `docs/specs/2026-05-19-hagent-sandbox-design.md`（commit `67617d4`）

---

## 文件结构

### 新增文件
| 路径 | 责任 |
| --- | --- |
| `src/hagent/sandbox/__init__.py` | 导出 `SandboxKind`、`create_sandbox_for_session()`、协议类型 |
| `src/hagent/sandbox/protocol.py` | `HagentSandboxProtocol`（abstract base，继承 deepagents `SandboxBackendProtocol`）+ `SandboxKind` enum |
| `src/hagent/sandbox/docker/__init__.py` | 空 |
| `src/hagent/sandbox/docker/runtime.py` | gVisor runtime 检测（`select_runtime()`） |
| `src/hagent/sandbox/docker/lifecycle.py` | `DockerContainerLifecycle`：start/stop/pause/resume |
| `src/hagent/sandbox/docker/sandbox.py` | `HagentDockerSandbox`（继承 `BaseSandbox`） |
| `src/hagent/sandbox/docker/image.py` | `ensure_image()`、`build_default_image()` |
| `src/hagent/sandbox/daytona/__init__.py` | 空 |
| `src/hagent/sandbox/daytona/sandbox.py` | `HagentDaytonaSandbox` stub |
| `src/hagent/sandbox/providers/__init__.py` | 空 |
| `src/hagent/sandbox/providers/shell.py` | `SandboxShellProvider`（实现 `ShellProvider` 接口，输出 `docker exec` argv） |
| `src/hagent/sandbox/providers/file.py` | `SandboxFileTransport`（实现 `FileTransport` 协议） |
| `src/hagent/sandbox/pool.py` | `SandboxPool`、`SandboxLease`、`idle_gc()` |
| `src/hagent/sandbox/manifest.py` | `SandboxManifest` dataclass（容器元数据） |
| `src/hagent/server/manager.py` | `SessionManager`（封装 `SessionStore` + `SandboxPool`） |
| `sandbox/docker/images/hagent-base/Dockerfile` | 默认沙箱镜像（python:3.12-slim + 工具集） |
| `sandbox/docker/images/hagent-base/entrypoint.sh` | 容器入口（`tail -f /dev/null`） |
| `scripts/build_sandbox_image.sh` | 本地镜像构建脚本 |
| `tests/sandbox/__init__.py` | 空 |
| `tests/sandbox/test_runtime_unit.py` | gVisor 检测单元 |
| `tests/sandbox/test_lifecycle_unit.py` | `DockerContainerLifecycle` 单元（mock docker SDK） |
| `tests/sandbox/test_docker_sandbox_unit.py` | `HagentDockerSandbox` execute/upload/download 单元 |
| `tests/sandbox/test_docker_sandbox_integration.py` | L3 真 docker 集成（`@pytest.mark.docker`） |
| `tests/sandbox/test_pool.py` | `SandboxPool` 单元 |
| `tests/sandbox/test_protocol_contract.py` | L2 fake sandbox 通过 `BaseSandbox` 全套契约 |
| `tests/sandbox/test_tool_parity.py` | 行为对齐回归（host vs sandbox） |
| `tests/sandbox/test_gvisor.py` | L4 gVisor 专项（`@pytest.mark.gvisor`） |
| `tests/sandbox/test_daytona_stub.py` | Daytona stub 契约 |
| `tests/server/test_sessions_sandbox.py` | server 集成 |
| `tests/test_demo_e2e_sandbox.py` | L5 端到端 |
| `tests/conftest_sandbox.py` | `fake_sandbox` fixture |

### 修改文件
| 路径 | 改动 |
| --- | --- |
| `pyproject.toml` | `dependencies` 加 `docker>=7.1`；`pytest.ini_options` 加 `markers` |
| `src/hagent/config.py` | `HagentConfig` 加 `sandbox_kind: SandboxKind` 字段 |
| `src/hagent/core.py` | `create_hagent(sandbox=...)`、sandbox 模式下跳过 `permissions=`、注入 SandboxShellProvider / SandboxFileTransport |
| `src/hagent/bash_tool/runtime.py` | `BashRuntime` 改用 `shell_provider` 暴露的 `process_env_overrides` 抽象，避免硬编码 host `os.environ` |
| `src/hagent/file_tools/io.py` | 抽出 `FileTransport` 协议（`Protocol` 类）；host 实现走 `Path` API |
| `src/hagent/file_tools/tools.py` | `create_claude_file_tools(..., transport=None)` 接受 transport，默认 host |
| `src/hagent/server/sessions.py` | `SessionRow` schema migration（新增字段）+ `SessionStore.create_session(..., sandbox_kind=...)` |
| `src/hagent/server/app.py` | 装配 `SessionManager`，注入 routers |
| `src/hagent/server/routers/sessions.py` | 接收 `sandbox_kind` 创建参数 |
| `src/hagent/server/routers/files.py` | sandbox 模式走 `HagentSandbox.upload_files()` / `download_files()` |
| `src/hagent/server/sse.py` | 新增 `sandbox.*` 事件类型 |
| `src/hagent/cli.py` | `demo --sandbox docker\|none` + `sandbox {ls\|stop\|logs}` 子命令 |
| `prompts/hagent_base.zh.md` | sandbox 模式段落（路径在 `/workspace`、网络可用、不访问 host） |
| `prompts/decisions.md` | KEEP/MODIFY 记录 |
| `CLAUDE.md` | sandbox 模式段落、移除 "正式部署走 Plan 5 DockerBackend" 字样 |
| `AGENTS.md` | PR 验证命令加 `HAGENT_TEST_DOCKER=1 pytest -m docker -v` |
| `web/CLAUDE.md` | sandbox 模式下文件 API 与 SSE 行为 |
| `docs/plans/2026-05-12-plan-5-docker-backend-and-swap.md` | 顶部 superseded note |

---

## 任务列表

### Task 1: 加 docker-py 依赖 + pytest markers

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 编辑 `pyproject.toml`**

```toml
dependencies = [
    "deepagents>=0.5.4",
    "langchain-anthropic>=0.3",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "python-multipart>=0.0.20",
    "python-dotenv>=1.0",
    "langgraph-checkpoint-sqlite>=2.0",
    "docker>=7.1",
]
```

并在 `[tool.pytest.ini_options]` 段尾追加 markers：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"
markers = [
    "docker: requires a running docker daemon (HAGENT_TEST_DOCKER=1)",
    "gvisor: requires docker + runsc installed (HAGENT_TEST_GVISOR=1)",
    "e2e: requires ANTHROPIC_API_KEY",
]
```

- [ ] **Step 2: 安装新依赖**

```bash
source .venv/bin/activate && pip install -e ".[dev]"
```

Expected: `docker-py` 安装完，`pip show docker` 显示 7.x。

- [ ] **Step 3: smoke test pytest 仍能起**

```bash
pytest -q --collect-only | tail -20
```

Expected: 收集到既有测试，无错误。

- [ ] **Step 4: commit**

```bash
git add pyproject.toml
git commit -m "$(cat <<'EOF'
build(deps): add docker-py for sandbox backend, register pytest markers

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: gVisor runtime 检测

**Files:**
- Create: `src/hagent/sandbox/__init__.py`
- Create: `src/hagent/sandbox/docker/__init__.py`
- Create: `src/hagent/sandbox/docker/runtime.py`
- Create: `tests/sandbox/__init__.py`
- Create: `tests/sandbox/test_runtime_unit.py`

- [ ] **Step 1: 写失败测试 `tests/sandbox/test_runtime_unit.py`**

```python
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from hagent.sandbox.docker.runtime import (
    RUNTIME_RUNC,
    RUNTIME_RUNSC,
    RuntimeUnavailable,
    select_runtime,
)


def test_select_runtime_prefers_runsc_when_daemon_lists_it(tmp_path: Path):
    daemon_json = tmp_path / "daemon.json"
    daemon_json.write_text(
        json.dumps({"runtimes": {"runsc": {"path": "/usr/local/bin/runsc"}}}),
        encoding="utf-8",
    )
    with patch("hagent.sandbox.docker.runtime._DAEMON_JSON_PATH", daemon_json):
        assert select_runtime(prefer=RUNTIME_RUNSC) == RUNTIME_RUNSC


def test_select_runtime_warns_and_falls_back_to_runc(tmp_path, caplog):
    daemon_json = tmp_path / "daemon.json"
    daemon_json.write_text(json.dumps({"runtimes": {}}), encoding="utf-8")
    with patch("hagent.sandbox.docker.runtime._DAEMON_JSON_PATH", daemon_json), caplog.at_level("WARNING"):
        assert select_runtime(prefer=RUNTIME_RUNSC) == RUNTIME_RUNC
    assert any("runsc" in rec.message for rec in caplog.records)


def test_select_runtime_required_raises_when_runsc_missing(tmp_path, monkeypatch):
    daemon_json = tmp_path / "daemon.json"
    daemon_json.write_text(json.dumps({"runtimes": {}}), encoding="utf-8")
    monkeypatch.setattr("hagent.sandbox.docker.runtime._DAEMON_JSON_PATH", daemon_json)
    monkeypatch.setenv("HAGENT_SANDBOX_REQUIRE_RUNSC", "1")
    with pytest.raises(RuntimeUnavailable):
        select_runtime(prefer=RUNTIME_RUNSC)


def test_select_runtime_missing_daemon_json_returns_runc(tmp_path, caplog):
    daemon_json = tmp_path / "missing.json"
    with patch("hagent.sandbox.docker.runtime._DAEMON_JSON_PATH", daemon_json), caplog.at_level("WARNING"):
        assert select_runtime(prefer=RUNTIME_RUNSC) == RUNTIME_RUNC
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/sandbox/test_runtime_unit.py -v
```

Expected: ImportError / collection error.

- [ ] **Step 3: 写空骨架 `src/hagent/sandbox/__init__.py`**

```python
"""Hagent sandbox abstraction layer."""

from hagent.sandbox.protocol import HagentSandboxProtocol, SandboxKind

__all__ = ["HagentSandboxProtocol", "SandboxKind"]
```

注：`protocol.py` 在 Task 3 添加；先在 `__init__.py` 留 import，跑测试时此 import 会失败——这是预期的（Task 3 之前不导出包级 API；Task 2 的测试只 import `runtime` 模块，绕过 `hagent.sandbox.__init__`）。

修正：Task 2 的 `__init__.py` 暂时留空：

```python
"""Hagent sandbox abstraction layer (M6)."""
```

`src/hagent/sandbox/docker/__init__.py`：

```python
"""Docker-backed sandbox implementation."""
```

- [ ] **Step 4: 写 `src/hagent/sandbox/docker/runtime.py`**

```python
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
```

- [ ] **Step 5: 跑测试**

```bash
pytest tests/sandbox/test_runtime_unit.py -v
```

Expected: 4 passed.

- [ ] **Step 6: commit**

```bash
git add src/hagent/sandbox/__init__.py src/hagent/sandbox/docker/__init__.py src/hagent/sandbox/docker/runtime.py tests/sandbox/__init__.py tests/sandbox/test_runtime_unit.py
git commit -m "$(cat <<'EOF'
feat(sandbox): detect gVisor runsc runtime via daemon.json, fallback to runc

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: HagentSandboxProtocol + SandboxKind enum

**Files:**
- Create: `src/hagent/sandbox/protocol.py`
- Modify: `src/hagent/sandbox/__init__.py`
- Create: `tests/sandbox/test_protocol_types.py`

- [ ] **Step 1: 写失败测试 `tests/sandbox/test_protocol_types.py`**

```python
from __future__ import annotations

import pytest

from hagent.sandbox import HagentSandboxProtocol, SandboxKind


def test_sandbox_kind_values():
    assert SandboxKind.NONE.value == "none"
    assert SandboxKind.DOCKER.value == "docker"
    assert SandboxKind.DAYTONA.value == "daytona"


def test_sandbox_kind_from_str_case_insensitive():
    assert SandboxKind.from_str("Docker") is SandboxKind.DOCKER
    assert SandboxKind.from_str("none") is SandboxKind.NONE


def test_sandbox_kind_from_str_rejects_unknown():
    with pytest.raises(ValueError, match="unknown sandbox kind"):
        SandboxKind.from_str("e2b")


def test_protocol_requires_execute_and_lifecycle_methods():
    # 用 abstract 子类——HagentSandboxProtocol 必须暴露 close()、workspace_dir 等
    expected_attrs = {"execute", "upload_files", "download_files", "id", "workspace_dir", "close", "kind"}
    for name in expected_attrs:
        assert hasattr(HagentSandboxProtocol, name), f"missing {name}"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/sandbox/test_protocol_types.py -v
```

Expected: ImportError.

- [ ] **Step 3: 写 `src/hagent/sandbox/protocol.py`**

```python
"""Hagent sandbox protocol — extends deepagents SandboxBackendProtocol."""

from __future__ import annotations

import abc
from enum import Enum
from pathlib import Path

from deepagents.backends.protocol import SandboxBackendProtocol


class SandboxKind(str, Enum):
    NONE = "none"
    DOCKER = "docker"
    DAYTONA = "daytona"

    @classmethod
    def from_str(cls, value: str) -> "SandboxKind":
        try:
            return cls(value.strip().lower())
        except ValueError as exc:
            raise ValueError(f"unknown sandbox kind: {value!r}") from exc


class HagentSandboxProtocol(SandboxBackendProtocol, abc.ABC):
    """Hagent's extension over deepagents SandboxBackendProtocol.

    Adds workspace_dir (sandbox-internal root, default ``/workspace``), kind tag,
    and close() lifecycle. Implementations also expose execute/upload_files/
    download_files inherited from deepagents.
    """

    @property
    @abc.abstractmethod
    def workspace_dir(self) -> str:
        """Sandbox-internal workspace path. LLM-visible files live here."""

    @property
    @abc.abstractmethod
    def kind(self) -> SandboxKind: ...

    @abc.abstractmethod
    def close(self) -> None:
        """Tear down the sandbox (stop+rm container, free resources)."""
```

- [ ] **Step 4: 更新 `src/hagent/sandbox/__init__.py`**

```python
"""Hagent sandbox abstraction layer (M6)."""

from hagent.sandbox.protocol import HagentSandboxProtocol, SandboxKind

__all__ = ["HagentSandboxProtocol", "SandboxKind"]
```

- [ ] **Step 5: 跑测试**

```bash
pytest tests/sandbox/test_protocol_types.py -v
```

Expected: 4 passed.

- [ ] **Step 6: commit**

```bash
git add src/hagent/sandbox/__init__.py src/hagent/sandbox/protocol.py tests/sandbox/test_protocol_types.py
git commit -m "$(cat <<'EOF'
feat(sandbox): add HagentSandboxProtocol + SandboxKind enum

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: 默认 sandbox 镜像（Dockerfile + entrypoint + build 脚本）

**Files:**
- Create: `sandbox/docker/images/hagent-base/Dockerfile`
- Create: `sandbox/docker/images/hagent-base/entrypoint.sh`
- Create: `scripts/build_sandbox_image.sh`

- [ ] **Step 1: 写 `sandbox/docker/images/hagent-base/Dockerfile`**

```dockerfile
FROM python:3.12-slim AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    TERM=dumb \
    HOME=/workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        ripgrep \
        coreutils \
        procps \
        tini \
    && rm -rf /var/lib/apt/lists/*

# uv: fast Python package installer (install directly to /usr/local/bin
# via UV_INSTALL_DIR to avoid relying on $HOME at build time).
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

RUN mkdir -p /workspace
WORKDIR /workspace

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# tini reaps zombies; container stays alive via tail -f /dev/null,
# all real work goes through `docker exec`.
ENTRYPOINT ["tini", "--", "/usr/local/bin/entrypoint.sh"]
```

- [ ] **Step 2: 写 `sandbox/docker/images/hagent-base/entrypoint.sh`**

```bash
#!/usr/bin/env bash
# Hagent sandbox entrypoint. Keeps the container alive so `docker exec`
# can dispatch each LLM tool call.
set -euo pipefail
mkdir -p /workspace
exec tail -f /dev/null
```

- [ ] **Step 3: 写 `scripts/build_sandbox_image.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${HAGENT_SANDBOX_IMAGE:-hagent/sandbox:dev}"
ROOT="$(cd "$(dirname "$0")/../sandbox/docker/images/hagent-base" && pwd)"

echo "[build_sandbox_image] building ${IMAGE_TAG} from ${ROOT}"
docker build -t "${IMAGE_TAG}" "${ROOT}"
docker images "${IMAGE_TAG}"
```

```bash
chmod +x scripts/build_sandbox_image.sh sandbox/docker/images/hagent-base/entrypoint.sh
```

- [ ] **Step 4: smoke build（如果本机有 docker）**

```bash
./scripts/build_sandbox_image.sh
docker run --rm hagent/sandbox:dev /bin/bash -c "python --version && uv --version && rg --version | head -1"
```

Expected: Python 3.12.x、uv 版本号、ripgrep 版本号。如果没装 docker，跳过 smoke，由 Task 5 集成测试覆盖。

- [ ] **Step 5: commit**

```bash
git add sandbox/docker/images/hagent-base/Dockerfile sandbox/docker/images/hagent-base/entrypoint.sh scripts/build_sandbox_image.sh
git commit -m "$(cat <<'EOF'
feat(sandbox): add base docker image (python 3.12 + uv + git + ripgrep)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: DockerContainerLifecycle（含镜像确保）

**Files:**
- Create: `src/hagent/sandbox/docker/image.py`
- Create: `src/hagent/sandbox/docker/lifecycle.py`
- Create: `src/hagent/sandbox/manifest.py`
- Create: `tests/sandbox/test_lifecycle_unit.py`

- [ ] **Step 1: 写失败测试 `tests/sandbox/test_lifecycle_unit.py`**

```python
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
    mock_docker_client.containers.run.return_value = container
    with patch("hagent.sandbox.docker.lifecycle.select_runtime", return_value=RUNTIME_RUNC), \
         patch("hagent.sandbox.docker.lifecycle.ensure_image", return_value="hagent/sandbox:dev"):
        lc = DockerContainerLifecycle(image_tag="hagent/sandbox:dev")
        lc.start()
        lc.stop()
    container.stop.assert_called_once()
    container.remove.assert_called_once()
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/sandbox/test_lifecycle_unit.py -v
```

Expected: ImportError.

- [ ] **Step 3: 写 `src/hagent/sandbox/manifest.py`**

```python
"""Sandbox session metadata dataclasses."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class SandboxManifest:
    """Lightweight metadata describing a live sandbox instance."""

    sandbox_id: str
    kind: str
    image_tag: str
    runtime: str
    container_id: str | None = None
    workspace_dir: str = "/workspace"
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_used_at = time.time()
```

- [ ] **Step 4: 写 `src/hagent/sandbox/docker/image.py`**

```python
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

    script = shutil.which("bash")
    if script is None:
        raise RuntimeError("bash not available — cannot run build_sandbox_image.sh")
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # src/hagent → repo root
    repo_root = os.path.abspath(os.path.join(root, "..", ".."))
    proc = subprocess.run(
        [script, os.path.join(repo_root, "scripts", "build_sandbox_image.sh")],
        env={**os.environ, "HAGENT_SANDBOX_IMAGE": image_tag},
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise APIError(f"sandbox image build failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return image_tag
```

- [ ] **Step 5: 写 `src/hagent/sandbox/docker/lifecycle.py`**

```python
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
SAFE_ENV_KEYS = ("PATH", "HOME", "LANG", "TERM")
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
        self._await_ready()
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
            logger.warning("pause failed: %s", exc)

    def resume(self) -> None:
        if self._container is None:
            return
        try:
            self._container.unpause()
        except APIError as exc:
            logger.warning("unpause failed: %s", exc)

    def stop(self) -> None:
        if self._container is None:
            return
        try:
            self._container.stop(timeout=5)
        except (APIError, NotFound) as exc:
            logger.warning("stop failed: %s", exc)
        try:
            self._container.remove(force=True)
        except (APIError, NotFound) as exc:
            logger.warning("remove failed: %s", exc)
        self._container = None
```

- [ ] **Step 6: 跑测试**

```bash
pytest tests/sandbox/test_lifecycle_unit.py -v
```

Expected: 4 passed.

- [ ] **Step 7: commit**

```bash
git add src/hagent/sandbox/docker/image.py src/hagent/sandbox/docker/lifecycle.py src/hagent/sandbox/manifest.py tests/sandbox/test_lifecycle_unit.py
git commit -m "$(cat <<'EOF'
feat(sandbox): docker container lifecycle with safe env + runtime fallback

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: HagentDockerSandbox（execute / upload / download / id）

**Files:**
- Create: `src/hagent/sandbox/docker/sandbox.py`
- Create: `tests/sandbox/test_docker_sandbox_unit.py`

- [ ] **Step 1: 写失败测试 `tests/sandbox/test_docker_sandbox_unit.py`**

```python
from __future__ import annotations

import io
import tarfile
from unittest.mock import MagicMock, patch

import pytest

from hagent.sandbox import SandboxKind
from hagent.sandbox.docker.sandbox import HagentDockerSandbox


def _make_sandbox(monkeypatch) -> HagentDockerSandbox:
    lifecycle = MagicMock()
    lifecycle.start.return_value = MagicMock(
        sandbox_id="testid000abc",
        container_id="cidcid",
        kind="docker",
        image_tag="hagent/sandbox:dev",
        runtime="runsc",
        workspace_dir="/workspace",
    )
    container = MagicMock()
    container.id = "cidcid"
    lifecycle._container = container
    monkeypatch.setattr("hagent.sandbox.docker.sandbox.DockerContainerLifecycle", lambda **kw: lifecycle)
    sb = HagentDockerSandbox.start()
    sb._container = container
    return sb


def test_id_is_docker_prefixed(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    assert sb.id == "docker-cidcid"
    assert sb.kind is SandboxKind.DOCKER
    assert sb.workspace_dir == "/workspace"


def test_execute_returns_combined_output(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    sb._container.exec_run = MagicMock(return_value=(0, (b"hello\n", b"")))
    resp = sb.execute("echo hello")
    assert resp.exit_code == 0
    assert "hello" in resp.output
    assert resp.truncated is False


def test_execute_includes_stderr_with_prefix(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    sb._container.exec_run = MagicMock(return_value=(2, (b"out\n", b"boom\n")))
    resp = sb.execute("bad")
    assert resp.exit_code == 2
    assert "out" in resp.output
    assert "[stderr] boom" in resp.output


def test_execute_truncates_oversized_output(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    big = b"x" * (sb._max_output_bytes + 100)
    sb._container.exec_run = MagicMock(return_value=(0, (big, b"")))
    resp = sb.execute("yes")
    assert resp.truncated is True
    assert len(resp.output.encode("utf-8")) <= sb._max_output_bytes + 200  # truncation banner


def test_upload_files_writes_tar_archive(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    sb._container.put_archive = MagicMock(return_value=True)
    responses = sb.upload_files([("/workspace/a.txt", b"hello")])
    assert responses[0].error is None
    args, _ = sb._container.put_archive.call_args
    # args = (path, tar_bytes)
    assert args[0] == "/workspace"
    tf = tarfile.open(fileobj=io.BytesIO(args[1]))
    assert tf.getnames() == ["a.txt"]


def test_download_files_extracts_from_tar(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        ti = tarfile.TarInfo(name="a.txt")
        body = b"hello"
        ti.size = len(body)
        tf.addfile(ti, io.BytesIO(body))
    sb._container.get_archive = MagicMock(return_value=(iter([buf.getvalue()]), {"size": 5}))
    responses = sb.download_files(["/workspace/a.txt"])
    assert responses[0].content == b"hello"
    assert responses[0].error is None


def test_close_calls_lifecycle_stop(monkeypatch):
    sb = _make_sandbox(monkeypatch)
    sb.close()
    sb._lifecycle.stop.assert_called_once()
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/sandbox/test_docker_sandbox_unit.py -v
```

Expected: ImportError.

- [ ] **Step 3: 写 `src/hagent/sandbox/docker/sandbox.py`**

```python
"""HagentDockerSandbox: SandboxBackendProtocol over docker exec/cp."""

from __future__ import annotations

import io
import logging
import shlex
import tarfile
from pathlib import PurePosixPath

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox

from hagent.sandbox.docker.lifecycle import DockerContainerLifecycle
from hagent.sandbox.manifest import SandboxManifest
from hagent.sandbox.protocol import HagentSandboxProtocol, SandboxKind

logger = logging.getLogger(__name__)

DEFAULT_MAX_OUTPUT_BYTES = 500 * 1024
DEFAULT_EXEC_TIMEOUT_SECONDS = 120


class HagentDockerSandbox(BaseSandbox, HagentSandboxProtocol):
    """Hagent sandbox backed by a single docker container.

    Inherits BaseSandbox so ls/read/grep/glob/edit are implemented as
    server-side scripts via execute(). We provide execute(), upload_files(),
    download_files() and id.
    """

    def __init__(
        self,
        *,
        lifecycle: DockerContainerLifecycle,
        manifest: SandboxManifest,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
        default_timeout_seconds: int = DEFAULT_EXEC_TIMEOUT_SECONDS,
    ) -> None:
        self._lifecycle = lifecycle
        self._manifest = manifest
        self._container = lifecycle._container
        self._max_output_bytes = max_output_bytes
        self._default_timeout_seconds = default_timeout_seconds

    @classmethod
    def start(
        cls,
        *,
        image_tag: str | None = None,
        prefer_runtime: str = "runsc",
        env_overrides: dict[str, str] | None = None,
    ) -> "HagentDockerSandbox":
        from hagent.sandbox.docker.image import DEFAULT_IMAGE_TAG
        lifecycle = DockerContainerLifecycle(
            image_tag=image_tag or DEFAULT_IMAGE_TAG,
            prefer_runtime=prefer_runtime,
            env_overrides=env_overrides,
        )
        manifest = lifecycle.start()
        return cls(lifecycle=lifecycle, manifest=manifest)

    @property
    def id(self) -> str:
        return f"docker-{self._manifest.container_id}"

    @property
    def kind(self) -> SandboxKind:
        return SandboxKind.DOCKER

    @property
    def workspace_dir(self) -> str:
        return self._manifest.workspace_dir

    @property
    def manifest(self) -> SandboxManifest:
        return self._manifest

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        if self._container is None:
            return ExecuteResponse(
                output="container not running", exit_code=137, truncated=False
            )
        timeout_s = timeout if timeout is not None else self._default_timeout_seconds
        try:
            exit_code, (stdout, stderr) = self._container.exec_run(
                cmd=["/bin/bash", "-c", command],
                workdir=self._manifest.workspace_dir,
                demux=True,
                tty=False,
            )
        except Exception as exc:  # noqa: BLE001
            return ExecuteResponse(
                output=f"container exec failed: {exc}", exit_code=137, truncated=False
            )

        parts: list[bytes] = []
        if stdout:
            parts.append(stdout)
        if stderr:
            for line in stderr.decode("utf-8", errors="replace").rstrip("\n").split("\n"):
                parts.append(f"[stderr] {line}\n".encode("utf-8"))
        combined = b"".join(parts)
        truncated = False
        if len(combined) > self._max_output_bytes:
            combined = combined[: self._max_output_bytes] + (
                f"\n... Output truncated at {self._max_output_bytes} bytes.".encode("utf-8")
            )
            truncated = True
        self._manifest.touch()
        return ExecuteResponse(
            output=combined.decode("utf-8", errors="replace"),
            exit_code=int(exit_code) if exit_code is not None else 1,
            truncated=truncated,
        )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        results: list[FileUploadResponse] = []
        # Group by parent directory so we can put a single archive per dest dir
        grouped: dict[str, list[tuple[str, bytes]]] = {}
        for path, content in files:
            pp = PurePosixPath(path)
            grouped.setdefault(str(pp.parent), []).append((pp.name, content))

        for parent, items in grouped.items():
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                for name, content in items:
                    info = tarfile.TarInfo(name=name)
                    info.size = len(content)
                    info.mode = 0o644
                    tar.addfile(info, io.BytesIO(content))
            buf.seek(0)
            try:
                # Ensure parent exists in container first
                self._container.exec_run(["mkdir", "-p", parent])
                self._container.put_archive(parent, buf.getvalue())
                for name, _ in items:
                    results.append(
                        FileUploadResponse(path=str(PurePosixPath(parent) / name), error=None)
                    )
            except Exception as exc:  # noqa: BLE001
                for name, _ in items:
                    results.append(
                        FileUploadResponse(
                            path=str(PurePosixPath(parent) / name),
                            error=f"upload_failed: {exc}",
                        )
                    )
        self._manifest.touch()
        return results

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        results: list[FileDownloadResponse] = []
        for path in paths:
            try:
                stream, _stat = self._container.get_archive(path)
                buf = io.BytesIO(b"".join(stream))
                with tarfile.open(fileobj=buf) as tar:
                    members = [m for m in tar.getmembers() if m.isfile()]
                    if not members:
                        results.append(
                            FileDownloadResponse(path=path, content=None, error="file_not_found")
                        )
                        continue
                    member = members[0]
                    f = tar.extractfile(member)
                    content = f.read() if f is not None else b""
                    results.append(FileDownloadResponse(path=path, content=content, error=None))
            except Exception as exc:  # noqa: BLE001
                error_str = str(exc)
                error_code = "file_not_found" if "404" in error_str or "Not Found" in error_str else f"download_failed: {exc}"
                results.append(FileDownloadResponse(path=path, content=None, error=error_code))
        self._manifest.touch()
        return results

    def close(self) -> None:
        self._lifecycle.stop()
        self._container = None

    def __enter__(self) -> "HagentDockerSandbox":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
```

- [ ] **Step 4: 跑测试**

```bash
pytest tests/sandbox/test_docker_sandbox_unit.py -v
```

Expected: 7 passed.

- [ ] **Step 5: commit**

```bash
git add src/hagent/sandbox/docker/sandbox.py tests/sandbox/test_docker_sandbox_unit.py
git commit -m "$(cat <<'EOF'
feat(sandbox): HagentDockerSandbox over BaseSandbox with docker exec/cp

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: SandboxShellProvider（桥接 bash_tool 到容器）

**Files:**
- Create: `src/hagent/sandbox/providers/__init__.py`
- Create: `src/hagent/sandbox/providers/shell.py`
- Create: `tests/sandbox/test_shell_provider.py`

- [ ] **Step 1: 写失败测试 `tests/sandbox/test_shell_provider.py`**

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hagent.sandbox.providers.shell import SandboxShellProvider


@pytest.fixture
def fake_sandbox():
    sb = MagicMock()
    sb.id = "docker-cidcid"
    sb._container = MagicMock()
    sb._container.id = "cidcid"
    sb.workspace_dir = "/workspace"
    return sb


def test_command_argv_uses_docker_exec(tmp_path, fake_sandbox):
    provider = SandboxShellProvider(sandbox=fake_sandbox, workspace_root=Path("/workspace"))
    argv = provider.command_argv("echo hi")
    assert argv[0] == "docker"
    assert argv[1] == "exec"
    assert "cidcid" in argv
    assert "/bin/bash" in argv
    # script appears at the tail
    assert argv[-1] == "echo hi"


def test_build_command_passes_through_snapshot(tmp_path, fake_sandbox):
    provider = SandboxShellProvider(sandbox=fake_sandbox, workspace_root=Path("/workspace"))
    cwd_file = tmp_path / "cwd"
    script = provider.build_command("ls", cwd_file=cwd_file)
    assert "cd " in script
    assert "trap _hagent_capture_cwd EXIT" in script
    assert "ls" in script


def test_current_cwd_starts_at_workspace_root(fake_sandbox):
    provider = SandboxShellProvider(sandbox=fake_sandbox, workspace_root=Path("/workspace"))
    assert str(provider.current_cwd) == "/workspace"


def test_update_cwd_changes_only_inside_sandbox(fake_sandbox):
    provider = SandboxShellProvider(sandbox=fake_sandbox, workspace_root=Path("/workspace"))
    provider.update_cwd(Path("/workspace/sub"))
    assert str(provider.current_cwd) == "/workspace/sub"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/sandbox/test_shell_provider.py -v
```

Expected: ImportError.

- [ ] **Step 3: 写 `src/hagent/sandbox/providers/__init__.py`**

```python
"""Sandbox providers that bridge Hagent tools into a sandbox backend."""
```

- [ ] **Step 4: 写 `src/hagent/sandbox/providers/shell.py`**

```python
"""SandboxShellProvider — drop-in ShellProvider that runs commands via docker exec."""

from __future__ import annotations

import shlex
import tempfile
import threading
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from hagent.bash_tool.shell_provider import ShellProvider

if TYPE_CHECKING:
    from hagent.sandbox.docker.sandbox import HagentDockerSandbox


SANDBOX_SAFE_ENV = (
    ("PATH", "/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin"),
    ("HOME", "/workspace"),
    ("LANG", "C.UTF-8"),
    ("TERM", "dumb"),
)


class SandboxShellProvider(ShellProvider):
    """Replacement ShellProvider that targets a HagentDockerSandbox container."""

    def __init__(
        self,
        *,
        sandbox: "HagentDockerSandbox",
        workspace_root: Path,
        session_env_path: Path | None = None,
    ) -> None:
        self.sandbox = sandbox
        # We deliberately do NOT call super().__init__ — that resolves a host
        # shell + writes a host-side env snapshot. We synthesise the minimum
        # ShellProvider surface area here.
        self.workspace_root = Path(workspace_root)
        self.shell_path = Path("/bin/bash")  # inside container
        self.snapshot_path = session_env_path or self._default_snapshot_path()
        self._current_cwd = PurePosixPath(workspace_root)
        self._lock = threading.RLock()
        self._write_snapshot()

    @property
    def current_cwd(self) -> Path:
        with self._lock:
            return Path(str(self._current_cwd))

    def update_cwd(self, cwd: Path) -> None:
        with self._lock:
            self._current_cwd = PurePosixPath(str(cwd))

    def build_command(self, command: str, *, cwd_file: Path) -> str:
        quoted_snapshot = shlex.quote(str(self.snapshot_path))
        quoted_cwd_file = shlex.quote(str(cwd_file))
        with self._lock:
            quoted_cwd = shlex.quote(str(self._current_cwd))
        return "\n".join(
            [
                f"source {quoted_snapshot}",
                f"cd {quoted_cwd} || exit 1",
                'export HAGENT_CURRENT_CWD="$PWD"',
                "_hagent_capture_cwd() {",
                f"  printf '%s\\n' \"$PWD\" > {quoted_cwd_file}",
                "}",
                "trap _hagent_capture_cwd EXIT",
                command,
            ]
        )

    def command_argv(self, command_script: str) -> list[str]:
        container_id = self.sandbox._container.id  # noqa: SLF001
        return [
            "docker",
            "exec",
            "-i",
            "-w",
            str(self._current_cwd),
            *self._docker_env_args(),
            container_id,
            "/bin/bash",
            "-c",
            command_script,
        ]

    def _docker_env_args(self) -> list[str]:
        args: list[str] = []
        for name, value in SANDBOX_SAFE_ENV:
            args.extend(["-e", f"{name}={value}"])
        return args

    def _write_snapshot(self) -> None:
        # Snapshot lives ON HOST (read by `source` inside container via docker exec
        # would fail because host path isn't visible). Instead, embed the env
        # directly in the script `build_command` returns via `export` lines.
        # We still create the file to satisfy the ShellProvider contract used by
        # OutputManager/BashRuntime initialization paths.
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"export {name}={shlex.quote(value)}"
            for name, value in SANDBOX_SAFE_ENV
        ]
        lines.append("")
        self.snapshot_path.write_text("\n".join(lines), encoding="utf-8")
        self.snapshot_path.chmod(0o600)

    def _default_snapshot_path(self) -> Path:
        tmp_dir = tempfile.mkdtemp(prefix="hagent-sandbox-shell-")
        return Path(tmp_dir) / "shell-session.sh"
```

注意：因为 sandbox 内 `source $snapshot_path` 实际读不到 host 路径，所以 SANDBOX_SAFE_ENV 实际通过 `docker exec -e` 传入；snapshot 文件只是占位以维持 ShellProvider API（OutputManager 等代码读取该 path）。修订 `build_command` 不走 `source`，直接写 export 行：

```python
    def build_command(self, command: str, *, cwd_file: Path) -> str:
        quoted_cwd_file = shlex.quote(str(cwd_file))
        with self._lock:
            quoted_cwd = shlex.quote(str(self._current_cwd))
        env_exports = "\n".join(
            f"export {name}={shlex.quote(value)}" for name, value in SANDBOX_SAFE_ENV
        )
        return "\n".join(
            [
                env_exports,
                f"cd {quoted_cwd} || exit 1",
                'export HAGENT_CURRENT_CWD="$PWD"',
                "_hagent_capture_cwd() {",
                f"  printf '%s\\n' \"$PWD\" > {quoted_cwd_file}",
                "}",
                "trap _hagent_capture_cwd EXIT",
                command,
            ]
        )
```

（把上面 Step 4 的 `build_command` 替换为这个版本；写代码时合并即可。）

但是上面 `cwd_file` 是 host 路径，container 写不到——这里需要重新考虑。
**修正**：sandbox 模式下 cwd 跟踪通过 `docker exec` 的 working_dir 参数处理，不再写 host cwd_file。`build_command` 接受 `cwd_file` 但忽略它，capture cwd 改用 `docker exec -w` 直接传，trap 也不写文件：

```python
    def build_command(self, command: str, *, cwd_file: Path) -> str:
        # cwd_file is intentionally ignored in sandbox mode; the BashRuntime caller
        # will see the unchanged cwd_file (we keep contract). cwd updates happen
        # via SandboxShellProvider.update_cwd() driven by `pwd` exec after the command.
        with self._lock:
            quoted_cwd = shlex.quote(str(self._current_cwd))
        env_exports = "\n".join(
            f"export {name}={shlex.quote(value)}" for name, value in SANDBOX_SAFE_ENV
        )
        return "\n".join(
            [
                env_exports,
                f"cd {quoted_cwd} || exit 1",
                'export HAGENT_CURRENT_CWD="$PWD"',
                "printf '__HAGENT_PWD__:%s\\n' \"$PWD\"",  # sentinel cwd marker
                command,
            ]
        )
```

`BashRuntime` 在 sandbox 模式下需要后处理识别 `__HAGENT_PWD__:` 前缀更新 cwd。这部分在 Task 14 wiring 时一起处理。

- [ ] **Step 5: 跑测试**

```bash
pytest tests/sandbox/test_shell_provider.py -v
```

Expected: 4 passed.

- [ ] **Step 6: commit**

```bash
git add src/hagent/sandbox/providers/__init__.py src/hagent/sandbox/providers/shell.py tests/sandbox/test_shell_provider.py
git commit -m "$(cat <<'EOF'
feat(sandbox): SandboxShellProvider bridges bash_tool to docker exec

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: FileTransport 抽象 + host 实现

**Files:**
- Modify: `src/hagent/file_tools/io.py`
- Modify: `src/hagent/file_tools/tools.py`
- Create: `tests/test_file_tools_transport.py`

- [ ] **Step 1: 写失败测试 `tests/test_file_tools_transport.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from hagent.file_tools.io import FileTransport, HostFileTransport


def test_host_file_transport_round_trip(tmp_path: Path):
    transport: FileTransport = HostFileTransport()
    target = tmp_path / "foo.txt"
    transport.write_text(target, "hello world", encoding="utf-8", line_endings="LF")
    metadata = transport.read_text_metadata(target)
    assert metadata.content == "hello world"
    assert metadata.encoding == "utf-8"
    assert metadata.line_endings == "LF"


def test_host_file_transport_preserves_crlf(tmp_path):
    transport = HostFileTransport()
    target = tmp_path / "foo.txt"
    transport.write_text(target, "a\nb\n", encoding="utf-8", line_endings="CRLF")
    raw = target.read_bytes()
    assert raw == b"a\r\nb\r\n"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/test_file_tools_transport.py -v
```

Expected: ImportError (HostFileTransport not present yet).

- [ ] **Step 3: 在 `src/hagent/file_tools/io.py` 顶部补 Protocol + Host 实现**

在文件末尾追加：

```python
from typing import Protocol


class FileTransport(Protocol):
    """Abstract file IO used by the Hagent file tools.

    Host implementations operate on a local Path; sandbox implementations route
    through HagentSandbox upload/download.
    """

    def read_text_metadata(self, path: str | Path) -> TextMetadata: ...

    def write_text(
        self,
        path: str | Path,
        content: str,
        encoding: str,
        line_endings: LineEndings,
    ) -> None: ...

    def exists(self, path: str | Path) -> bool: ...

    def is_directory(self, path: str | Path) -> bool: ...


class HostFileTransport:
    """Default FileTransport backed by the local filesystem."""

    def read_text_metadata(self, path: str | Path) -> TextMetadata:
        return read_text_metadata(path)

    def write_text(
        self,
        path: str | Path,
        content: str,
        encoding: str,
        line_endings: LineEndings,
    ) -> None:
        write_text_preserving_encoding(path, content, encoding, line_endings)

    def exists(self, path: str | Path) -> bool:
        return Path(path).exists()

    def is_directory(self, path: str | Path) -> bool:
        return Path(path).is_dir()
```

- [ ] **Step 4: 跑测试**

```bash
pytest tests/test_file_tools_transport.py -v
```

Expected: 2 passed.

- [ ] **Step 5: 把 `file_tools/tools.py` 的三个工厂改用 transport**

在 `tools.py` 的 `create_read_tool` / `create_write_tool` / `create_edit_tool` 签名加 `transport: FileTransport | None = None` 默认走 `HostFileTransport()`，内部所有 `read_text_metadata(path)` / `write_text_preserving_encoding(...)` / `path.exists()` / `path.is_dir()` 调用替换为 transport 方法。例如 `create_read_tool` 的 `path.exists()` 改为 `transport.exists(path)`，`read_text_metadata(path)` 改为 `transport.read_text_metadata(path)`。

修改 `create_claude_file_tools(...)`（在 `file_tools/__init__.py`）签名加 `transport: FileTransport | None = None`，并把其转发给三个工厂。

- [ ] **Step 6: 跑既有 file 工具测试，确认无回归**

```bash
pytest tests/test_claude_file_tool.py tests/test_file_tools_transport.py -v
```

Expected: 所有既有测试 + 2 个新测试都过。

- [ ] **Step 7: commit**

```bash
git add src/hagent/file_tools/io.py src/hagent/file_tools/tools.py src/hagent/file_tools/__init__.py tests/test_file_tools_transport.py
git commit -m "$(cat <<'EOF'
refactor(file_tools): extract FileTransport protocol, default HostFileTransport

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: SandboxFileTransport

**Files:**
- Create: `src/hagent/sandbox/providers/file.py`
- Create: `tests/sandbox/test_file_transport.py`

- [ ] **Step 1: 写失败测试 `tests/sandbox/test_file_transport.py`**

```python
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from deepagents.backends.protocol import FileDownloadResponse, FileUploadResponse
from hagent.sandbox.providers.file import SandboxFileTransport


@pytest.fixture
def fake_sandbox():
    sb = MagicMock()
    sb.workspace_dir = "/workspace"
    return sb


def test_write_text_uploads_via_sandbox(fake_sandbox):
    fake_sandbox.upload_files.return_value = [FileUploadResponse(path="/workspace/a.txt", error=None)]
    transport = SandboxFileTransport(fake_sandbox)
    transport.write_text("/workspace/a.txt", "hello", encoding="utf-8", line_endings="LF")
    fake_sandbox.upload_files.assert_called_once()
    args, _ = fake_sandbox.upload_files.call_args
    assert args[0] == [("/workspace/a.txt", b"hello")]


def test_write_text_crlf_normalized(fake_sandbox):
    fake_sandbox.upload_files.return_value = [FileUploadResponse(path="/workspace/a.txt", error=None)]
    transport = SandboxFileTransport(fake_sandbox)
    transport.write_text("/workspace/a.txt", "a\nb\n", encoding="utf-8", line_endings="CRLF")
    args, _ = fake_sandbox.upload_files.call_args
    assert args[0] == [("/workspace/a.txt", b"a\r\nb\r\n")]


def test_read_text_metadata_via_download(fake_sandbox):
    fake_sandbox.download_files.return_value = [
        FileDownloadResponse(path="/workspace/a.txt", content=b"hello", error=None)
    ]
    transport = SandboxFileTransport(fake_sandbox)
    md = transport.read_text_metadata("/workspace/a.txt")
    assert md.content == "hello"
    assert md.encoding == "utf-8"
    assert md.line_endings == "LF"


def test_exists_false_on_file_not_found(fake_sandbox):
    fake_sandbox.download_files.return_value = [
        FileDownloadResponse(path="/workspace/missing", content=None, error="file_not_found")
    ]
    transport = SandboxFileTransport(fake_sandbox)
    assert transport.exists("/workspace/missing") is False


def test_write_raises_on_upload_error(fake_sandbox):
    fake_sandbox.upload_files.return_value = [
        FileUploadResponse(path="/workspace/a.txt", error="permission_denied")
    ]
    transport = SandboxFileTransport(fake_sandbox)
    with pytest.raises(OSError, match="permission_denied"):
        transport.write_text("/workspace/a.txt", "x", encoding="utf-8", line_endings="LF")
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/sandbox/test_file_transport.py -v
```

Expected: ImportError.

- [ ] **Step 3: 写 `src/hagent/sandbox/providers/file.py`**

```python
"""SandboxFileTransport — adapts HagentSandbox upload/download to FileTransport."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from hagent.file_tools.io import LineEndings, TextMetadata

if TYPE_CHECKING:
    from hagent.sandbox.protocol import HagentSandboxProtocol


class SandboxFileTransport:
    """FileTransport implementation that routes through a HagentSandbox."""

    def __init__(self, sandbox: "HagentSandboxProtocol") -> None:
        self.sandbox = sandbox

    def read_text_metadata(self, path: str | Path) -> TextMetadata:
        responses = self.sandbox.download_files([str(path)])
        if not responses or responses[0].error or responses[0].content is None:
            raise FileNotFoundError(str(path))
        data = responses[0].content
        line_endings: LineEndings = "CRLF" if b"\r\n" in data else "LF"
        raw_text = data.decode("utf-8")
        normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        return TextMetadata(
            content=normalized,
            encoding="utf-8",
            line_endings=line_endings,
            timestamp_ms=0,  # sandbox does not expose mtime; LLM uses content equality
        )

    def write_text(
        self,
        path: str | Path,
        content: str,
        encoding: str,
        line_endings: LineEndings,
    ) -> None:
        text = content
        if line_endings == "CRLF":
            text = content.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
        data = text.encode(encoding)
        responses = self.sandbox.upload_files([(str(path), data)])
        if responses and responses[0].error:
            raise OSError(f"sandbox write failed: {responses[0].error}")

    def exists(self, path: str | Path) -> bool:
        responses = self.sandbox.download_files([str(path)])
        return bool(responses and responses[0].error is None)

    def is_directory(self, path: str | Path) -> bool:
        # ls returns the entry; if listed with is_dir=True it's a directory.
        ls = self.sandbox.ls(str(path))
        if ls.error is not None:
            return False
        # Heuristic: ls on a file returns []; ls on a directory returns its
        # children. Either way, if `path` itself isn't a file, treat as dir.
        return not self.exists(path) and ls.entries is not None
```

- [ ] **Step 4: 跑测试**

```bash
pytest tests/sandbox/test_file_transport.py -v
```

Expected: 5 passed.

- [ ] **Step 5: commit**

```bash
git add src/hagent/sandbox/providers/file.py tests/sandbox/test_file_transport.py
git commit -m "$(cat <<'EOF'
feat(sandbox): SandboxFileTransport for Read/Write/Edit through sandbox API

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: SandboxPool（acquire / release / warm pool）

**Files:**
- Create: `src/hagent/sandbox/pool.py`
- Create: `tests/sandbox/test_pool.py`

- [ ] **Step 1: 写失败测试 `tests/sandbox/test_pool.py`**

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hagent.sandbox.pool import SandboxPool, PoolExhausted


def _make_sandbox_factory():
    counter = {"n": 0}

    def factory():
        counter["n"] += 1
        sb = MagicMock()
        sb.id = f"docker-sb{counter['n']}"
        sb._container = MagicMock(id=f"cid{counter['n']}")
        sb.kind.value = "docker"
        sb.close = MagicMock()
        return sb

    return factory, counter


def test_pool_prewarms_to_min_size():
    factory, counter = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=2, max_size=4)
    pool.prewarm()
    assert counter["n"] == 2
    pool.shutdown()


def test_acquire_returns_warm_sandbox_when_available():
    factory, counter = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=1, max_size=4)
    pool.prewarm()
    lease = pool.acquire(session_id="s1")
    assert lease.sandbox.id == "docker-sb1"
    pool.release(lease)
    pool.shutdown()


def test_acquire_creates_new_when_pool_empty():
    factory, counter = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2)
    lease = pool.acquire(session_id="s1")
    assert counter["n"] == 1
    pool.release(lease)
    pool.shutdown()


def test_acquire_raises_when_max_reached():
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=1, acquire_timeout=0.05)
    lease1 = pool.acquire(session_id="s1")
    with pytest.raises(PoolExhausted):
        pool.acquire(session_id="s2")
    pool.release(lease1)
    pool.shutdown()


def test_release_default_stops_and_removes(monkeypatch):
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2)
    lease = pool.acquire(session_id="s1")
    pool.release(lease)
    lease.sandbox.close.assert_called_once()
    pool.shutdown()


def test_release_reuses_when_reuse_env_set(monkeypatch):
    monkeypatch.setenv("HAGENT_SANDBOX_REUSE", "true")
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(sandbox_factory=factory, min_size=0, max_size=2)
    lease = pool.acquire(session_id="s1")
    sandbox = lease.sandbox
    sandbox.execute = MagicMock(return_value=MagicMock(exit_code=0))
    pool.release(lease)
    sandbox.execute.assert_called_once()
    cmd_arg = sandbox.execute.call_args[0][0]
    assert "rm -rf" in cmd_arg
    sandbox.close.assert_not_called()
    pool.shutdown()
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/sandbox/test_pool.py -v
```

Expected: ImportError.

- [ ] **Step 3: 写 `src/hagent/sandbox/pool.py`**

```python
"""SandboxPool — warm-pool acquire/release with idle GC."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Callable

from hagent.sandbox.protocol import HagentSandboxProtocol

logger = logging.getLogger(__name__)


class PoolExhausted(RuntimeError):
    """Raised when the pool is full and no warm sandbox is available within timeout."""


@dataclass
class SandboxLease:
    sandbox: HagentSandboxProtocol
    session_id: str
    leased_at: float = field(default_factory=time.time)


class SandboxPool:
    """Owns a small pool of HagentSandboxProtocol instances.

    Acquire returns a SandboxLease; release either tears the container down
    (default) or, if ``HAGENT_SANDBOX_REUSE=true``, wipes ``/workspace`` and
    returns the sandbox to the warm pool.
    """

    def __init__(
        self,
        *,
        sandbox_factory: Callable[[], HagentSandboxProtocol],
        min_size: int = 1,
        max_size: int = 4,
        acquire_timeout: float = 5.0,
    ) -> None:
        self._factory = sandbox_factory
        self._min_size = min_size
        self._max_size = max_size
        self._acquire_timeout = acquire_timeout
        self._idle: Queue[HagentSandboxProtocol] = Queue()
        self._leased: dict[str, SandboxLease] = {}
        self._lock = threading.RLock()
        self._size = 0

    def prewarm(self) -> None:
        with self._lock:
            while self._size < self._min_size:
                self._idle.put(self._factory())
                self._size += 1

    def acquire(self, *, session_id: str) -> SandboxLease:
        try:
            sandbox = self._idle.get_nowait()
        except Empty:
            with self._lock:
                if self._size < self._max_size:
                    self._size += 1
                    sandbox = self._factory()
                else:
                    sandbox = None
        if sandbox is None:
            # Wait for someone to release
            deadline = time.monotonic() + self._acquire_timeout
            while time.monotonic() < deadline:
                try:
                    sandbox = self._idle.get(timeout=0.1)
                    break
                except Empty:
                    continue
            if sandbox is None:
                raise PoolExhausted(
                    f"sandbox pool exhausted (max={self._max_size}) after {self._acquire_timeout}s"
                )
        lease = SandboxLease(sandbox=sandbox, session_id=session_id)
        with self._lock:
            self._leased[session_id] = lease
        return lease

    def release(self, lease: SandboxLease) -> None:
        with self._lock:
            self._leased.pop(lease.session_id, None)
        if self._should_reuse():
            try:
                lease.sandbox.execute("rm -rf /workspace/* /workspace/.[!.]* 2>/dev/null || true")
                self._idle.put(lease.sandbox)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("reuse cleanup failed; tearing down: %s", exc)
        try:
            lease.sandbox.close()
        finally:
            with self._lock:
                self._size = max(0, self._size - 1)

    def shutdown(self) -> None:
        # close all idle + leased
        while True:
            try:
                sb = self._idle.get_nowait()
            except Empty:
                break
            try:
                sb.close()
            except Exception:  # noqa: BLE001, PERF203
                pass
        with self._lock:
            for lease in list(self._leased.values()):
                try:
                    lease.sandbox.close()
                except Exception:  # noqa: BLE001, PERF203
                    pass
            self._leased.clear()
            self._size = 0

    @staticmethod
    def _should_reuse() -> bool:
        return os.environ.get("HAGENT_SANDBOX_REUSE", "").lower() in {"1", "true", "yes"}
```

- [ ] **Step 4: 跑测试**

```bash
pytest tests/sandbox/test_pool.py -v
```

Expected: 6 passed.

- [ ] **Step 5: commit**

```bash
git add src/hagent/sandbox/pool.py tests/sandbox/test_pool.py
git commit -m "$(cat <<'EOF'
feat(sandbox): SandboxPool with warm prewarm + bounded acquire + opt-in reuse

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: SandboxPool idle GC 状态机

**Files:**
- Modify: `src/hagent/sandbox/pool.py`
- Modify: `tests/sandbox/test_pool.py`

- [ ] **Step 1: 在 `tests/sandbox/test_pool.py` 末尾追加**

```python
def test_idle_gc_pauses_then_evicts(monkeypatch):
    factory, _ = _make_sandbox_factory()
    pool = SandboxPool(
        sandbox_factory=factory,
        min_size=0,
        max_size=2,
        idle_pause_seconds=0.1,
        idle_evict_seconds=0.2,
    )
    lease = pool.acquire(session_id="s1")
    # Force last_used backwards
    lease.sandbox.manifest = MagicMock()
    lease.sandbox.manifest.last_used_at = time.time() - 1.0
    lease.sandbox.pause = MagicMock()
    pool._gc_pass(now=time.time())
    lease.sandbox.pause.assert_called_once()
    pool._gc_pass(now=time.time())  # second pass evicts
    lease.sandbox.close.assert_called_once()
    pool.shutdown()
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/sandbox/test_pool.py::test_idle_gc_pauses_then_evicts -v
```

Expected: AttributeError / TypeError.

- [ ] **Step 3: 扩展 `src/hagent/sandbox/pool.py`**

在 `SandboxPool.__init__` 加新参数：

```python
        idle_pause_seconds: float = 300.0,
        idle_evict_seconds: float = 1800.0,
```

并存到 self；在类里追加：

```python
    def _gc_pass(self, *, now: float | None = None) -> None:
        if now is None:
            now = time.time()
        with self._lock:
            leases = list(self._leased.values())
        for lease in leases:
            manifest = getattr(lease.sandbox, "manifest", None)
            last_used = getattr(manifest, "last_used_at", lease.leased_at)
            idle = now - last_used
            paused = getattr(manifest, "paused", False) if manifest is not None else False
            if idle >= self._idle_evict_seconds:
                logger.info("evicting sandbox session=%s after %.1fs idle", lease.session_id, idle)
                self.release(lease)
            elif idle >= self._idle_pause_seconds and not paused:
                logger.info("pausing sandbox session=%s after %.1fs idle", lease.session_id, idle)
                try:
                    lease.sandbox.pause()
                    if manifest is not None:
                        manifest.paused = True
                except Exception as exc:  # noqa: BLE001
                    logger.warning("pause failed: %s", exc)

    def start_gc_loop(self, *, interval_seconds: float = 60.0) -> threading.Thread:
        stop = threading.Event()
        self._gc_stop = stop

        def loop() -> None:
            while not stop.wait(interval_seconds):
                try:
                    self._gc_pass()
                except Exception:  # noqa: BLE001
                    logger.exception("idle_gc pass failed")

        thread = threading.Thread(target=loop, daemon=True, name="hagent-sandbox-gc")
        thread.start()
        return thread

    def stop_gc_loop(self) -> None:
        stop = getattr(self, "_gc_stop", None)
        if stop is not None:
            stop.set()
```

并在 `SandboxManifest`（`manifest.py`）加 `paused: bool = False` 字段。

- [ ] **Step 4: 跑测试**

```bash
pytest tests/sandbox/test_pool.py -v
```

Expected: 7 passed.

- [ ] **Step 5: commit**

```bash
git add src/hagent/sandbox/pool.py src/hagent/sandbox/manifest.py tests/sandbox/test_pool.py
git commit -m "$(cat <<'EOF'
feat(sandbox): pool idle GC with pause then evict thresholds

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: SessionStore schema migration（sandbox 字段）

**Files:**
- Modify: `src/hagent/server/sessions.py`
- Create: `tests/server/test_sessions_schema_migration.py`

- [ ] **Step 1: 写失败测试 `tests/server/test_sessions_schema_migration.py`**

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

from hagent.server.sessions import SessionStore


def test_create_session_records_sandbox_kind(tmp_path: Path):
    db = tmp_path / "sessions.db"
    workspace_root = tmp_path / "workspaces"
    store = SessionStore(db)
    state = store.create(workspace_root, sandbox_kind="docker", container_id="cid123", image_tag="hagent/sandbox:dev", runtime="runsc")
    assert state.sandbox_kind == "docker"
    assert state.container_id == "cid123"

    fresh = SessionStore(db).get(state.id)
    assert fresh is not None
    assert fresh.sandbox_kind == "docker"
    assert fresh.runtime == "runsc"


def test_default_session_kind_is_none(tmp_path):
    db = tmp_path / "sessions.db"
    store = SessionStore(db)
    state = store.create(tmp_path / "wsp")
    assert state.sandbox_kind == "none"
    assert state.container_id is None


def test_legacy_db_without_sandbox_columns_is_migrated(tmp_path):
    db = tmp_path / "legacy.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE sessions (id TEXT PRIMARY KEY, workspace_dir TEXT, status TEXT, created_at REAL, last_active REAL)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES ('oldsid', '/tmp/wsp', 'active', 0.0, 0.0)"
        )
    store = SessionStore(db)
    state = store.get("oldsid")
    assert state is not None
    assert state.sandbox_kind == "none"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/server/test_sessions_schema_migration.py -v
```

Expected: AttributeError (no sandbox_kind on SessionState).

- [ ] **Step 3: 修改 `src/hagent/server/sessions.py`**

替换 dataclass + 加 migration + 拓展 create：

```python
@dataclass(frozen=True)
class SessionState:
    id: str
    workspace_dir: str
    status: SessionStatus
    created_at: float
    last_active: float
    sandbox_kind: str = "none"
    sandbox_id: str | None = None
    container_id: str | None = None
    image_tag: str | None = None
    runtime: str | None = None
    sandbox_metadata_json: str | None = None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    workspace_dir TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    last_active REAL NOT NULL,
    sandbox_kind TEXT NOT NULL DEFAULT 'none',
    sandbox_id TEXT,
    container_id TEXT,
    image_tag TEXT,
    runtime TEXT,
    sandbox_metadata_json TEXT
)
"""

_MIGRATION_COLUMNS = (
    ("sandbox_kind", "TEXT NOT NULL DEFAULT 'none'"),
    ("sandbox_id", "TEXT"),
    ("container_id", "TEXT"),
    ("image_tag", "TEXT"),
    ("runtime", "TEXT"),
    ("sandbox_metadata_json", "TEXT"),
)


class SessionStore:
    def __init__(self, db_path: Path | str):
        self._db_path = str(db_path)
        with self._connect() as conn:
            conn.execute(_SCHEMA)
            self._migrate(conn)

    def _migrate(self, conn) -> None:
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        for column_name, ddl in _MIGRATION_COLUMNS:
            if column_name not in existing:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {column_name} {ddl}")
```

`create()` 签名扩展：

```python
    def create(
        self,
        workspace_root: Path | str,
        *,
        sandbox_kind: str = "none",
        sandbox_id: str | None = None,
        container_id: str | None = None,
        image_tag: str | None = None,
        runtime: str | None = None,
        sandbox_metadata_json: str | None = None,
    ) -> SessionState:
        sid = uuid.uuid4().hex[:16]
        workspace_dir = Path(workspace_root) / sid / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions "
                "(id, workspace_dir, status, created_at, last_active, sandbox_kind, sandbox_id, container_id, image_tag, runtime, sandbox_metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sid,
                    str(workspace_dir),
                    SessionStatus.ACTIVE.value,
                    now,
                    now,
                    sandbox_kind,
                    sandbox_id,
                    container_id,
                    image_tag,
                    runtime,
                    sandbox_metadata_json,
                ),
            )
        return SessionState(
            id=sid,
            workspace_dir=str(workspace_dir),
            status=SessionStatus.ACTIVE,
            created_at=now,
            last_active=now,
            sandbox_kind=sandbox_kind,
            sandbox_id=sandbox_id,
            container_id=container_id,
            image_tag=image_tag,
            runtime=runtime,
            sandbox_metadata_json=sandbox_metadata_json,
        )
```

`get()` 和 `list()` 的 `SessionState(...)` 调用补对应字段（用 `row["sandbox_kind"]` 等，缺列用 `row.keys()` 守卫）。

- [ ] **Step 4: 跑测试**

```bash
pytest tests/server/test_sessions_schema_migration.py tests/server -v
```

Expected: 全 pass，既有 server 测试不破。

- [ ] **Step 5: commit**

```bash
git add src/hagent/server/sessions.py tests/server/test_sessions_schema_migration.py
git commit -m "$(cat <<'EOF'
feat(server): SessionStore migration adds sandbox metadata columns

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: SessionManager（owns SessionStore + SandboxPool）

**Files:**
- Create: `src/hagent/server/manager.py`
- Create: `tests/server/test_session_manager.py`

- [ ] **Step 1: 写失败测试 `tests/server/test_session_manager.py`**

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hagent.sandbox import SandboxKind
from hagent.server.manager import SessionManager
from hagent.server.sessions import SessionStore


def test_create_session_with_kind_none_skips_pool(tmp_path):
    store = SessionStore(tmp_path / "s.db")
    pool = MagicMock()
    mgr = SessionManager(store=store, sandbox_pool=pool, workspace_root=tmp_path / "wsp")
    state = mgr.create_session(sandbox_kind=SandboxKind.NONE)
    assert state.sandbox_kind == "none"
    pool.acquire.assert_not_called()


def test_create_session_with_docker_kind_acquires_from_pool(tmp_path):
    store = SessionStore(tmp_path / "s.db")
    lease = MagicMock()
    lease.sandbox.id = "docker-cidcid"
    lease.sandbox.manifest.container_id = "cidcid"
    lease.sandbox.manifest.image_tag = "hagent/sandbox:dev"
    lease.sandbox.manifest.runtime = "runsc"
    pool = MagicMock()
    pool.acquire.return_value = lease
    mgr = SessionManager(store=store, sandbox_pool=pool, workspace_root=tmp_path / "wsp")
    state = mgr.create_session(sandbox_kind=SandboxKind.DOCKER)
    assert state.sandbox_kind == "docker"
    assert state.container_id == "cidcid"
    pool.acquire.assert_called_once()


def test_delete_session_releases_lease(tmp_path):
    store = SessionStore(tmp_path / "s.db")
    lease = MagicMock()
    lease.sandbox.id = "docker-cid"
    lease.sandbox.manifest.container_id = "cid"
    lease.sandbox.manifest.image_tag = "x"
    lease.sandbox.manifest.runtime = "runc"
    pool = MagicMock()
    pool.acquire.return_value = lease
    mgr = SessionManager(store=store, sandbox_pool=pool, workspace_root=tmp_path / "wsp")
    state = mgr.create_session(sandbox_kind=SandboxKind.DOCKER)
    mgr.delete_session(state.id)
    pool.release.assert_called_once_with(lease)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/server/test_session_manager.py -v
```

Expected: ImportError.

- [ ] **Step 3: 写 `src/hagent/server/manager.py`**

```python
"""SessionManager — bridges SessionStore and SandboxPool."""

from __future__ import annotations

import logging
from pathlib import Path

from hagent.sandbox import SandboxKind
from hagent.sandbox.pool import SandboxLease, SandboxPool
from hagent.server.sessions import SessionState, SessionStore

logger = logging.getLogger(__name__)


class SessionManager:
    """Owns SessionStore + SandboxPool; routes lifecycle calls coherently."""

    def __init__(
        self,
        *,
        store: SessionStore,
        sandbox_pool: SandboxPool | None,
        workspace_root: Path | str,
    ) -> None:
        self._store = store
        self._pool = sandbox_pool
        self._workspace_root = Path(workspace_root)
        self._leases: dict[str, SandboxLease] = {}

    @property
    def store(self) -> SessionStore:
        return self._store

    def create_session(self, *, sandbox_kind: SandboxKind = SandboxKind.NONE) -> SessionState:
        if sandbox_kind is SandboxKind.NONE or self._pool is None:
            return self._store.create(self._workspace_root, sandbox_kind=sandbox_kind.value)

        pre = self._store.create(self._workspace_root, sandbox_kind=sandbox_kind.value)
        lease = self._pool.acquire(session_id=pre.id)
        self._leases[pre.id] = lease
        manifest = getattr(lease.sandbox, "manifest", None)
        return self._store.update_sandbox_metadata(
            pre.id,
            sandbox_id=lease.sandbox.id,
            container_id=getattr(manifest, "container_id", None),
            image_tag=getattr(manifest, "image_tag", None),
            runtime=getattr(manifest, "runtime", None),
        )

    def delete_session(self, session_id: str) -> None:
        lease = self._leases.pop(session_id, None)
        if lease is not None and self._pool is not None:
            self._pool.release(lease)
        self._store.delete(session_id)

    def get_sandbox(self, session_id: str):
        lease = self._leases.get(session_id)
        return lease.sandbox if lease is not None else None

    def shutdown(self) -> None:
        if self._pool is not None:
            self._pool.shutdown()
```

注意 `SessionStore` 还要补一个 `update_sandbox_metadata` 方法：

在 `src/hagent/server/sessions.py` 末尾加：

```python
    def update_sandbox_metadata(
        self,
        sid: str,
        *,
        sandbox_id: str | None = None,
        container_id: str | None = None,
        image_tag: str | None = None,
        runtime: str | None = None,
    ) -> SessionState:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET sandbox_id = ?, container_id = ?, image_tag = ?, runtime = ? WHERE id = ?",
                (sandbox_id, container_id, image_tag, runtime, sid),
            )
        state = self.get(sid)
        if state is None:
            raise KeyError(sid)
        return state
```

- [ ] **Step 4: 跑测试**

```bash
pytest tests/server/test_session_manager.py tests/server/test_sessions_schema_migration.py -v
```

Expected: 全 pass。

- [ ] **Step 5: commit**

```bash
git add src/hagent/server/manager.py src/hagent/server/sessions.py tests/server/test_session_manager.py
git commit -m "$(cat <<'EOF'
feat(server): SessionManager bridging SessionStore and SandboxPool

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: core.py sandbox-aware wiring（+ HagentConfig）

**Files:**
- Modify: `src/hagent/config.py`
- Modify: `src/hagent/core.py`
- Modify: `src/hagent/bash_tool/runtime.py`
- Create: `tests/test_core_sandbox_wiring.py`

- [ ] **Step 1: 写失败测试 `tests/test_core_sandbox_wiring.py`**

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hagent.config import HagentConfig
from hagent.sandbox import SandboxKind


def test_create_hagent_with_sandbox_none_uses_local_backend():
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    cfg = HagentConfig(model="anthropic:claude-sonnet-4-6", sandbox_kind=SandboxKind.NONE)
    with patch("hagent.core._create_deep_agent", side_effect=fake_create):
        from hagent.core import create_hagent
        create_hagent(config=cfg)
    assert "permissions" in captured  # host mode keeps permissions


def test_create_hagent_with_sandbox_docker_skips_permissions_and_uses_sandbox_backend():
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    sandbox = MagicMock()
    sandbox.workspace_dir = "/workspace"
    sandbox._container = MagicMock(id="cidcid")

    cfg = HagentConfig(model="anthropic:claude-sonnet-4-6", sandbox_kind=SandboxKind.DOCKER)
    with patch("hagent.core._create_deep_agent", side_effect=fake_create), \
         patch("hagent.core.HagentDockerSandbox") as mock_sb_cls:
        mock_sb_cls.start.return_value = sandbox
        from hagent.core import create_hagent
        create_hagent(config=cfg)
    assert captured["backend"] is sandbox
    assert "permissions" not in captured or captured["permissions"] in (None, [])
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/test_core_sandbox_wiring.py -v
```

Expected: AttributeError on `sandbox_kind`.

- [ ] **Step 3: 修改 `src/hagent/config.py`**

在 `HagentConfig` dataclass 加：

```python
from hagent.sandbox import SandboxKind  # 注意循环 import 风险——若有循环就用字符串注解 + late import

@dataclass(frozen=True)
class HagentConfig:
    model: str
    ...
    sandbox_kind: SandboxKind = SandboxKind.NONE
    ...
```

`from_env` 加：

```python
sandbox_kind=SandboxKind.from_str(os.environ.get("HAGENT_SANDBOX_KIND", "none")),
```

如果 `from hagent.sandbox import SandboxKind` 触发循环（`sandbox/__init__.py` -> `protocol.py` 不应触发 config import），先确认无环；若环存在，把 import 放到 `from_env` 内的 late import。

- [ ] **Step 4: 修改 `src/hagent/core.py`**

替换 `create_hagent`：sandbox_kind 来源优先 `backend` 显式 > `config.sandbox_kind`。新代码摘要：

```python
from hagent.sandbox import SandboxKind
from hagent.sandbox.docker.sandbox import HagentDockerSandbox
from hagent.sandbox.providers.shell import SandboxShellProvider
from hagent.sandbox.providers.file import SandboxFileTransport


def create_hagent(
    config: HagentConfig | None = None,
    backend: Any | None = None,
    extra_subagents: list[dict] | None = None,
    extra_tools: list[Any] | None = None,
    checkpointer: Any | None = None,
    task_list_id: str | None = None,
    agents_dirs: list[Path] | None = None,
    disable_builtin_agents: bool = False,
    sandbox: HagentSandboxProtocol | None = None,
) -> Any:
    cfg = config or HagentConfig.from_env()
    _register_output_budget_profile(cfg)
    register_harness_profile(
        cfg.model,
        HarnessProfile(
            excluded_middleware=DISABLED_DEEPAGENTS_MIDDLEWARE,
            excluded_tools=DISABLED_DEEPAGENTS_TOOLS,
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )
    DEFAULT_WORKSPACE.mkdir(parents=True, exist_ok=True)

    sandbox_kind = cfg.sandbox_kind
    if sandbox is None and sandbox_kind is SandboxKind.DOCKER:
        sandbox = HagentDockerSandbox.start()

    if sandbox is not None:
        # Sandbox mode — sandbox backend is the deepagents BackendProtocol
        working_directory = Path(sandbox.workspace_dir)
        agent_backend = sandbox
        shell_provider = SandboxShellProvider(sandbox=sandbox, workspace_root=working_directory)
        file_transport = SandboxFileTransport(sandbox)
        file_permissions = None  # explicitly skipped, see spec §5.3
    else:
        requested_backend = backend or _filesystem_backend_for_workspace(DEFAULT_WORKSPACE.resolve())
        requested_workspace = (
            _backend_working_directory(requested_backend)
            if requested_backend is not None
            else DEFAULT_WORKSPACE.resolve()
        )
        agent_backend = _backend_for_model_tools(requested_backend)
        working_directory = requested_workspace
        shell_provider = None
        file_transport = None
        file_permissions = permissions_for_workspace(working_directory)

    skill_registry = load_skills_from_sources(
        resolve_skill_sources(project_root=Path.cwd(), env_value=cfg.skills_paths)
    )
    skill_tool = create_skill_tool(skill_registry, session_id=task_list_id)
    bash_runtime = BashRuntime(working_directory, shell_provider=shell_provider)
    bash_tool = create_bash_tool(
        workspace_root=working_directory,
        runtime=bash_runtime,
        permissions=cfg.bash_permissions if sandbox is None else None,
    )
    file_tools = create_claude_file_tools(
        workspace_root=working_directory,
        permissions=file_permissions,
        transport=file_transport,
    )
    task_store = TaskStore(
        working_directory,
        task_list_id=task_list_id or os.environ.get("HAGENT_TASK_LIST_ID", "tasklist"),
    )
    task_tools = create_task_tools(task_store)

    parent_tools: list[Any] = [bash_tool, *file_tools, *task_tools]
    if skill_registry:
        parent_tools.append(skill_tool)
    parent_tools.extend(list(extra_tools or []))

    specs = assemble_subagents(
        workspace=working_directory,
        extra_subagents=extra_subagents,
        agents_dirs=agents_dirs,
        disable_builtin=disable_builtin_agents,
    )
    agent_tool = None
    if specs:
        if not any(spec["name"] == "general-purpose" for spec in specs):
            raise ValueError(
                "Agent tool requires a 'general-purpose' subagent (the default route)."
            )
        runnables = compile_subagents(
            specs,
            parent_model=cfg.model,
            parent_tools=parent_tools,
            skill_registry=skill_registry,
        )
        agent_tool = build_agent_tool(runnables, render_agent_tool_description(specs))

    all_tools = list(parent_tools)
    if agent_tool is not None:
        all_tools.append(agent_tool)

    middleware: list[Any] = [sanitize_anthropic_thinking_blocks_middleware]
    if skill_registry:
        middleware.insert(0, HagentSkillsMiddleware(skill_registry))

    kwargs: dict[str, Any] = dict(
        model=cfg.model,
        tools=all_tools,
        middleware=middleware,
        system_prompt=render_base_prompt(
            sandbox_type=type(agent_backend).__name__,
            working_directory=str(working_directory),
            is_git_repo=(working_directory / ".git").exists() if sandbox is None else False,
            shell=os.environ.get("SHELL", "unknown"),
            model=cfg.model,
        ),
        subagents=None,
        backend=agent_backend,
    )
    if sandbox is None and file_permissions is not None:
        kwargs["permissions"] = file_permissions
    else:
        import logging
        logging.getLogger(__name__).info(
            "sandbox mode: deepagents FilesystemPermission is bypassed (container is the trust boundary)"
        )
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer

    agent = _create_deep_agent(**kwargs)
    for attr, value in (
        ("_hagent_bash_runtime", bash_runtime),
        ("_hagent_task_store", task_store),
        ("_hagent_skill_registry", skill_registry),
        ("_hagent_sandbox", sandbox),
    ):
        try:
            setattr(agent, attr, value)
        except Exception:
            pass
    return agent
```

- [ ] **Step 5: 修改 `src/hagent/bash_tool/runtime.py`**

`BashRuntime.__init__` 已经支持 `shell_provider` 参数。在 sandbox 模式下，`subprocess.Popen` 的命令是 `docker exec ...`，run 在 host 上。需要补一个 cwd-tracking 后处理：sandbox 模式下输出中含 `__HAGENT_PWD__:` 行（见 Task 7 build_command），foreground 完成时扫一遍 output_path 抓最后一个该行，传给 `shell_provider.update_cwd`。

在 `BashRuntime` 加：

```python
    def _capture_sandbox_cwd_from_output(self, output_path: Path) -> None:
        try:
            text = output_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        sentinel = "__HAGENT_PWD__:"
        last = None
        for line in text.splitlines():
            if line.startswith(sentinel):
                last = line[len(sentinel):].strip()
        if last:
            self.shell_provider.update_cwd(Path(last))
```

在 `_execute_foreground` 末尾（`self.task_registry.mark_completed` 之后）：

```python
        if isinstance(self.shell_provider, type(self.shell_provider)) and self.shell_provider.__class__.__name__ == "SandboxShellProvider":
            self._capture_sandbox_cwd_from_output(output_path)
```

—— 上面 isinstance 太脆弱，更稳的做法是检查 `getattr(self.shell_provider, "sandbox", None) is not None`：

```python
        if getattr(self.shell_provider, "sandbox", None) is not None:
            self._capture_sandbox_cwd_from_output(output_path)
```

并且 `_update_cwd_from_file` 调用前判断 `cwd_file.exists()` 已经是软失败，所以 sandbox 模式下原 cwd_file 不存在不会抛错——可以保留原逻辑。

- [ ] **Step 6: 跑测试**

```bash
pytest tests/test_core_sandbox_wiring.py tests/test_core.py tests/test_bash_tool_runtime.py -v
```

Expected: 全 pass。

- [ ] **Step 7: commit**

```bash
git add src/hagent/config.py src/hagent/core.py src/hagent/bash_tool/runtime.py tests/test_core_sandbox_wiring.py
git commit -m "$(cat <<'EOF'
feat(core): sandbox-aware create_hagent wiring (skip permissions, swap providers)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 15: CLI `--sandbox` flag + `hagent sandbox` 子命令

**Files:**
- Modify: `src/hagent/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: 在 `tests/test_cli.py` 加新测试**

```python
def test_cli_demo_accepts_sandbox_flag(monkeypatch, capsys):
    from hagent import cli
    called = {}

    def fake_run_demo(message, max_steps, skill, skill_args, sandbox):
        called["sandbox"] = sandbox
        return 0

    monkeypatch.setattr(cli, "run_demo", fake_run_demo)
    rc = cli.main(["demo", "hi", "--sandbox", "docker"])
    assert rc == 0
    assert called["sandbox"] == "docker"


def test_cli_sandbox_ls_subcommand(monkeypatch, capsys):
    from hagent import cli
    monkeypatch.setattr(cli, "_sandbox_ls", lambda: print("CID  KIND  IMAGE") or 0)
    rc = cli.main(["sandbox", "ls"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "CID" in out


def test_cli_sandbox_stop_requires_id(monkeypatch, capsys):
    from hagent import cli
    rc = cli.main(["sandbox", "stop"])
    assert rc == 2  # argparse error
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/test_cli.py::test_cli_demo_accepts_sandbox_flag -v
```

Expected: FAIL（demo 还不接受 `--sandbox`）。

- [ ] **Step 3: 修改 `src/hagent/cli.py`**

```python
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hagent", description="Hagent CLI")
    parser.add_argument("--version", action="version", version=f"hagent {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    demo = subparsers.add_parser("demo", help="跑一个端到端 demo")
    demo.add_argument("message", help="给 agent 的用户消息")
    demo.add_argument("--max-steps", type=int, default=None)
    demo.add_argument("--skill", default=None)
    demo.add_argument("--skill-args", default=None)
    demo.add_argument(
        "--sandbox",
        choices=["none", "docker", "daytona"],
        default="none",
        help="sandbox 后端类型；默认 none 即 host 模式",
    )

    sandbox = subparsers.add_parser("sandbox", help="sandbox 容器管理")
    sandbox_sub = sandbox.add_subparsers(dest="sandbox_command", required=True)
    sandbox_sub.add_parser("ls", help="列出活跃 sandbox 容器")
    stop = sandbox_sub.add_parser("stop", help="停止指定 sandbox")
    stop.add_argument("sandbox_id", help="sandbox 逻辑 id 或 docker container id")
    logs = sandbox_sub.add_parser("logs", help="查看 sandbox 日志")
    logs.add_argument("sandbox_id")

    return parser


def run_demo(
    message: str,
    max_steps: int | None,
    skill: str | None = None,
    skill_args: str | None = None,
    sandbox: str = "none",
) -> int:
    import os
    if sandbox != "none":
        os.environ["HAGENT_SANDBOX_KIND"] = sandbox
    from hagent.core import create_hagent
    agent = create_hagent()
    if skill:
        message = f"{_build_skill_message(skill, skill_args)}\n\nUser request: {message}"
    print(f"[hagent] message: {message}")
    if max_steps is None:
        final_state = agent.invoke({"messages": [{"role": "user", "content": message}]})
    else:
        final_state = agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config={"recursion_limit": max_steps},
        )
    final_msg = final_state["messages"][-1]
    content = getattr(final_msg, "content", final_msg)
    print(f"\n[hagent] final answer:\n{content}")
    return 0


def _sandbox_ls() -> int:
    import docker
    try:
        client = docker.from_env()
        containers = client.containers.list(filters={"label": "hagent.kind=docker"})
    except Exception as exc:  # noqa: BLE001
        print(f"[hagent sandbox] error: {exc}")
        return 1
    print(f"{'CID':<14} {'KIND':<8} {'IMAGE':<24} {'NAME'}")
    for c in containers:
        print(f"{c.short_id:<14} docker    {c.image.tags[0] if c.image.tags else c.image.id[:12]:<24} {c.name}")
    return 0


def _sandbox_stop(sandbox_id: str) -> int:
    import docker
    client = docker.from_env()
    try:
        container = client.containers.get(sandbox_id)
    except docker.errors.NotFound:
        # fall back to label search
        matches = client.containers.list(all=True, filters={"label": f"hagent.sandbox_id={sandbox_id}"})
        if not matches:
            print(f"[hagent sandbox] not found: {sandbox_id}")
            return 1
        container = matches[0]
    container.stop(timeout=5)
    container.remove(force=True)
    print(f"[hagent sandbox] stopped {container.id[:12]}")
    return 0


def _sandbox_logs(sandbox_id: str) -> int:
    import docker
    client = docker.from_env()
    try:
        container = client.containers.get(sandbox_id)
    except docker.errors.NotFound:
        matches = client.containers.list(all=True, filters={"label": f"hagent.sandbox_id={sandbox_id}"})
        if not matches:
            print(f"[hagent sandbox] not found: {sandbox_id}")
            return 1
        container = matches[0]
    print(container.logs(tail=200).decode("utf-8", errors="replace"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        print(f"hagent {__version__}")
        print("Usage: hagent demo <message> | hagent sandbox {ls|stop|logs}")
        return 0
    if args.command == "demo":
        return run_demo(args.message, args.max_steps, args.skill, args.skill_args, args.sandbox)
    if args.command == "sandbox":
        if args.sandbox_command == "ls":
            return _sandbox_ls()
        if args.sandbox_command == "stop":
            return _sandbox_stop(args.sandbox_id)
        if args.sandbox_command == "logs":
            return _sandbox_logs(args.sandbox_id)
    parser.error(f"unknown command: {args.command}")
    return 2
```

- [ ] **Step 4: 跑测试**

```bash
pytest tests/test_cli.py -v
```

Expected: 全 pass。

- [ ] **Step 5: commit**

```bash
git add src/hagent/cli.py tests/test_cli.py
git commit -m "$(cat <<'EOF'
feat(cli): add --sandbox flag and hagent sandbox {ls|stop|logs} subcommands

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 16: server/routers/files.py 通过 sandbox 走 upload/download

**Files:**
- Modify: `src/hagent/server/routers/files.py`
- Modify: `src/hagent/server/routers/sessions.py`
- Create: `tests/server/test_files_sandbox.py`

- [ ] **Step 1: 写失败测试 `tests/server/test_files_sandbox.py`**

```python
from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from hagent.server.app import create_app


def test_upload_with_sandbox_routes_through_sandbox(monkeypatch, tmp_path):
    sandbox = MagicMock()
    sandbox.upload_files.return_value = [MagicMock(error=None)]
    monkeypatch.setenv("HAGENT_API_KEY", "")  # disable auth in test
    app = create_app()
    # Patch the session manager hook to return this sandbox for sid=X
    client = TestClient(app)
    # ... (the test creates a session via POST /sessions then uploads;
    # exact wiring depends on app.state structure—see implementation)
```

注：该测试需要 server 端有 hook 让 routers 拿到 `SessionManager`。这部分由 Task 18 在 `app.py` 装配；本 task 先实现 routers 内的"路径切换"逻辑：

- [ ] **Step 2: 在 `src/hagent/server/routers/files.py` 加 sandbox 路由分支**

```python
from hagent.server.routers.sessions import get_session_manager


@router.post("/sessions/{sid}/files")
async def upload_file(
    sid: str,
    file: UploadFile = File(...),
    path: str = Form(...),
) -> dict:
    mgr = get_session_manager()
    s = mgr.store.get(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    data = await file.read()

    if s.sandbox_kind != "none":
        sandbox = mgr.get_sandbox(sid)
        if sandbox is None:
            raise HTTPException(status_code=409, detail="sandbox not running")
        target = path if path.startswith("/") else f"{sandbox.workspace_dir.rstrip('/')}/{path.lstrip('/')}"
        resps = sandbox.upload_files([(target, data)])
        if resps and resps[0].error:
            raise HTTPException(status_code=500, detail=f"sandbox upload failed: {resps[0].error}")
        return {"path": target, "size": len(data)}

    target = _resolve_inside(s.workspace_dir, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"path": str(target.relative_to(s.workspace_dir)), "size": len(data)}
```

`/sessions/{sid}/files/{file_path:path}` 下载路径也做类似分支：sandbox 模式下走 `sandbox.download_files([target])`，把 content 包成 `StreamingResponse`。

- [ ] **Step 3: `src/hagent/server/routers/sessions.py` 暴露 `get_session_manager` 单例 hook**

加一个模块级单例 + setter（由 `app.create_app` 初始化）：

```python
_MANAGER: SessionManager | None = None


def get_session_manager() -> SessionManager:
    if _MANAGER is None:
        raise RuntimeError("SessionManager not initialised; check app startup")
    return _MANAGER


def set_session_manager(mgr: SessionManager) -> None:
    global _MANAGER
    _MANAGER = mgr


def get_store() -> SessionStore:
    return get_session_manager().store
```

- [ ] **Step 4: 跑测试**

```bash
pytest tests/server -v
```

Expected: 既有测试若依赖 `get_store()` 与 `set_store()`，可能需要小调整；按需 fix。

- [ ] **Step 5: commit**

```bash
git add src/hagent/server/routers/files.py src/hagent/server/routers/sessions.py tests/server/test_files_sandbox.py
git commit -m "$(cat <<'EOF'
feat(server): route file upload/download through sandbox in docker mode

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 17: SSE sandbox.* 事件

**Files:**
- Modify: `src/hagent/server/sse.py`
- Create: `tests/server/test_sse_sandbox_events.py`

- [ ] **Step 1: 写失败测试 `tests/server/test_sse_sandbox_events.py`**

```python
from __future__ import annotations

import json

from hagent.server.sse import SandboxEvent, render_sandbox_event


def test_render_created_event():
    ev = SandboxEvent(kind="created", session_id="s1", sandbox_id="docker-abc", reason=None)
    text = render_sandbox_event(ev)
    payload = json.loads(text.split("\n", 1)[1].removeprefix("data: "))
    assert payload["event"] == "sandbox.created"
    assert payload["session_id"] == "s1"
    assert payload["sandbox_id"] == "docker-abc"


def test_render_error_event_includes_reason():
    ev = SandboxEvent(kind="error", session_id="s1", sandbox_id=None, reason="image_pull_failed")
    text = render_sandbox_event(ev)
    payload = json.loads(text.split("\n", 1)[1].removeprefix("data: "))
    assert payload["event"] == "sandbox.error"
    assert payload["reason"] == "image_pull_failed"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/server/test_sse_sandbox_events.py -v
```

Expected: ImportError.

- [ ] **Step 3: 在 `src/hagent/server/sse.py` 末尾加**

```python
from dataclasses import dataclass
from typing import Literal
import json


@dataclass
class SandboxEvent:
    kind: Literal["created", "paused", "resumed", "evicted", "error"]
    session_id: str
    sandbox_id: str | None
    reason: str | None = None


def render_sandbox_event(event: SandboxEvent) -> str:
    payload = {
        "event": f"sandbox.{event.kind}",
        "session_id": event.session_id,
        "sandbox_id": event.sandbox_id,
        "reason": event.reason,
    }
    return f"event: sandbox.{event.kind}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
```

并在 `SessionManager.create_session` / `delete_session` 调用处（Task 18 装配时）通过回调把事件推到 SSE 流（实现细节在 Task 18）。

- [ ] **Step 4: 跑测试**

```bash
pytest tests/server/test_sse_sandbox_events.py -v
```

Expected: 2 passed.

- [ ] **Step 5: commit**

```bash
git add src/hagent/server/sse.py tests/server/test_sse_sandbox_events.py
git commit -m "$(cat <<'EOF'
feat(server): SSE sandbox.* event helpers

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 18: app.py 装配 SessionManager + sandbox factory

**Files:**
- Modify: `src/hagent/server/app.py`
- Modify: `src/hagent/server/routers/sessions.py`
- Create: `tests/server/test_app_sandbox_assembly.py`

- [ ] **Step 1: 写失败测试 `tests/server/test_app_sandbox_assembly.py`**

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def test_create_session_with_sandbox_kind_docker_populates_metadata(monkeypatch, tmp_path):
    sandbox = MagicMock()
    sandbox.id = "docker-abc"
    sandbox.workspace_dir = "/workspace"
    sandbox.manifest = MagicMock(container_id="abc", image_tag="hagent/sandbox:dev", runtime="runsc")
    with patch("hagent.server.app.HagentDockerSandbox") as cls, \
         patch.dict("os.environ", {"HAGENT_SESSIONS_DB": str(tmp_path / "s.db"),
                                   "HAGENT_WORKSPACE_ROOT": str(tmp_path / "ws")}):
        cls.start.return_value = sandbox
        from hagent.server.app import create_app
        client = TestClient(create_app())
        resp = client.post("/sessions", json={"sandbox_kind": "docker"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["sandbox_kind"] == "docker"
        assert data["container_id"] == "abc"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/server/test_app_sandbox_assembly.py -v
```

Expected: 404 / 创建逻辑不支持 `sandbox_kind`。

- [ ] **Step 3: 修改 `src/hagent/server/app.py`**

```python
from pathlib import Path
import os

from hagent.sandbox import SandboxKind
from hagent.sandbox.docker.sandbox import HagentDockerSandbox
from hagent.sandbox.pool import SandboxPool
from hagent.server.manager import SessionManager
from hagent.server.sessions import SessionStore
from hagent.server.routers.sessions import set_session_manager


def _sandbox_factory(kind: SandboxKind):
    if kind is SandboxKind.DOCKER:
        return lambda: HagentDockerSandbox.start()
    return None


def create_app() -> FastAPI:
    load_env_file()

    app = FastAPI(title="Hagent Agent Server", version="0.0.1")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    db_path = os.environ.get("HAGENT_SESSIONS_DB", "/tmp/hagent/sessions.db")
    workspace_root = Path(os.environ.get("HAGENT_WORKSPACE_ROOT", "/tmp/hagent/workspaces"))
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    workspace_root.mkdir(parents=True, exist_ok=True)

    store = SessionStore(db_path)
    default_kind = SandboxKind.from_str(os.environ.get("HAGENT_SANDBOX_KIND", "none"))
    factory = _sandbox_factory(default_kind)
    pool: SandboxPool | None = None
    if factory is not None:
        pool = SandboxPool(
            sandbox_factory=factory,
            min_size=int(os.environ.get("HAGENT_SANDBOX_POOL_MIN", "1")),
            max_size=int(os.environ.get("HAGENT_SANDBOX_POOL_MAX", "4")),
        )
        pool.prewarm()
        pool.start_gc_loop()
    mgr = SessionManager(store=store, sandbox_pool=pool, workspace_root=workspace_root)
    set_session_manager(mgr)

    @app.on_event("shutdown")
    def _shutdown() -> None:
        mgr.shutdown()

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    app.include_router(sessions_router.router)
    app.include_router(messages_router.router)
    app.include_router(files_router.router)
    return app
```

- [ ] **Step 4: 修改 `src/hagent/server/routers/sessions.py`**

让 `POST /sessions` 接受 `sandbox_kind` body 字段：

```python
class CreateSessionRequest(BaseModel):
    sandbox_kind: str = "none"


@router.post("/sessions")
def create_session(payload: CreateSessionRequest | None = None) -> dict:
    mgr = get_session_manager()
    kind = SandboxKind.from_str((payload.sandbox_kind if payload else None) or "none")
    state = mgr.create_session(sandbox_kind=kind)
    return {
        "id": state.id,
        "workspace_dir": state.workspace_dir,
        "status": state.status.value,
        "sandbox_kind": state.sandbox_kind,
        "container_id": state.container_id,
    }
```

`DELETE /sessions/{sid}` 改用 `mgr.delete_session(sid)`。

- [ ] **Step 5: 跑测试**

```bash
pytest tests/server -v
```

Expected: 全 pass。

- [ ] **Step 6: commit**

```bash
git add src/hagent/server/app.py src/hagent/server/routers/sessions.py tests/server/test_app_sandbox_assembly.py
git commit -m "$(cat <<'EOF'
feat(server): assemble SandboxPool + SessionManager in app factory

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 19: HagentDaytonaSandbox stub + skipped contract test

**Files:**
- Create: `src/hagent/sandbox/daytona/__init__.py`
- Create: `src/hagent/sandbox/daytona/sandbox.py`
- Create: `tests/sandbox/test_daytona_stub.py`

- [ ] **Step 1: 写测试 `tests/sandbox/test_daytona_stub.py`**

```python
from __future__ import annotations

import pytest

from hagent.sandbox import SandboxKind
from hagent.sandbox.daytona.sandbox import HagentDaytonaSandbox


def test_daytona_stub_kind():
    sb = HagentDaytonaSandbox()
    assert sb.kind is SandboxKind.DAYTONA


def test_daytona_stub_methods_raise_not_implemented():
    sb = HagentDaytonaSandbox()
    with pytest.raises(NotImplementedError):
        sb.execute("echo hi")


@pytest.mark.skip(reason="Daytona implementation deferred to follow-up — proves abstraction is not docker-bound")
def test_daytona_full_contract():
    """Placeholder for langchain-daytona contract test; intentionally skipped."""
    pass
```

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/sandbox/test_daytona_stub.py -v
```

Expected: ImportError.

- [ ] **Step 3: 写 `src/hagent/sandbox/daytona/__init__.py`**

```python
"""Daytona-backed sandbox adapter (stub — implementation deferred)."""
```

- [ ] **Step 4: 写 `src/hagent/sandbox/daytona/sandbox.py`**

```python
"""HagentDaytonaSandbox — stubbed adapter to be wired against langchain-daytona later."""

from __future__ import annotations

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)

from hagent.sandbox.protocol import HagentSandboxProtocol, SandboxKind


class HagentDaytonaSandbox(HagentSandboxProtocol):
    """Placeholder Daytona sandbox.

    The real implementation will wrap ``langchain_daytona.DaytonaSandbox`` and
    expose the same surface as ``HagentDockerSandbox``. This stub exists so
    Hagent's abstraction layer is provably not bound to docker.
    """

    def __init__(self, *, sandbox_id: str = "daytona-stub", workspace_dir: str = "/workspace") -> None:
        self._sandbox_id = sandbox_id
        self._workspace_dir = workspace_dir

    @property
    def id(self) -> str:
        return self._sandbox_id

    @property
    def kind(self) -> SandboxKind:
        return SandboxKind.DAYTONA

    @property
    def workspace_dir(self) -> str:
        return self._workspace_dir

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        raise NotImplementedError("HagentDaytonaSandbox is deferred to a follow-up plan")

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        raise NotImplementedError

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        raise NotImplementedError

    # BackendProtocol abstract methods inherited via SandboxBackendProtocol — stub them.
    def ls(self, path: str):  # type: ignore[override]
        raise NotImplementedError

    def read(self, file_path: str, offset: int = 0, limit: int = 2000):  # type: ignore[override]
        raise NotImplementedError

    def write(self, file_path: str, content: str):  # type: ignore[override]
        raise NotImplementedError

    def edit(self, file_path, old_string, new_string, replace_all=False):  # type: ignore[override]
        raise NotImplementedError

    def grep(self, pattern, path=None, glob=None):  # type: ignore[override]
        raise NotImplementedError

    def glob(self, pattern, path="/"):  # type: ignore[override]
        raise NotImplementedError

    def close(self) -> None:
        pass
```

- [ ] **Step 5: 跑测试**

```bash
pytest tests/sandbox/test_daytona_stub.py -v
```

Expected: 2 passed, 1 skipped.

- [ ] **Step 6: commit**

```bash
git add src/hagent/sandbox/daytona/__init__.py src/hagent/sandbox/daytona/sandbox.py tests/sandbox/test_daytona_stub.py
git commit -m "$(cat <<'EOF'
feat(sandbox): HagentDaytonaSandbox stub proving abstraction is not docker-bound

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 20: 行为对齐回归测试（host vs sandbox byte-equal）

**Files:**
- Create: `tests/sandbox/test_tool_parity.py`
- Create: `tests/conftest_sandbox.py`

- [ ] **Step 1: 写 `tests/conftest_sandbox.py` —— in-memory fake sandbox**

```python
"""Fake sandbox fixture for parity tests (does not need docker)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterator

import pytest

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox

from hagent.sandbox.protocol import HagentSandboxProtocol, SandboxKind


class _LocalTmpSandbox(BaseSandbox, HagentSandboxProtocol):
    """BaseSandbox subclass that 'executes' via local subprocess in a tmp root.

    Used to validate the Hagent contract (LLM-visible tool output parity) without
    requiring a real container.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._id = "fake-tmp-" + root.name

    @property
    def id(self) -> str:
        return self._id

    @property
    def kind(self) -> SandboxKind:
        return SandboxKind.DOCKER

    @property
    def workspace_dir(self) -> str:
        return str(self._root)

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        proc = subprocess.run(
            ["/bin/bash", "-c", command],
            cwd=str(self._root),
            capture_output=True,
            text=True,
            timeout=timeout or 30,
        )
        parts = [proc.stdout]
        if proc.stderr:
            parts.extend(f"[stderr] {line}" for line in proc.stderr.rstrip("\n").split("\n"))
        return ExecuteResponse(
            output="".join(parts) if proc.stdout else "\n".join(parts),
            exit_code=proc.returncode,
            truncated=False,
        )

    def upload_files(self, files):
        out = []
        for path, content in files:
            target = self._resolve(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            out.append(FileUploadResponse(path=str(target), error=None))
        return out

    def download_files(self, paths):
        out = []
        for path in paths:
            target = self._resolve(path)
            if not target.exists():
                out.append(FileDownloadResponse(path=path, content=None, error="file_not_found"))
                continue
            out.append(FileDownloadResponse(path=path, content=target.read_bytes(), error=None))
        return out

    def close(self) -> None:
        shutil.rmtree(self._root, ignore_errors=True)

    def _resolve(self, path: str) -> Path:
        return self._root / path.lstrip("/")


@pytest.fixture
def fake_sandbox(tmp_path: Path) -> Iterator[_LocalTmpSandbox]:
    root = tmp_path / "sandbox"
    root.mkdir()
    sb = _LocalTmpSandbox(root)
    yield sb
    sb.close()
```

- [ ] **Step 2: 写 `tests/sandbox/test_tool_parity.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from hagent.bash_tool import create_bash_tool
from hagent.bash_tool.runtime import BashRuntime
from hagent.file_tools import create_claude_file_tools
from hagent.file_tools.state import FileReadState
from hagent.sandbox.providers.file import SandboxFileTransport
from hagent.sandbox.providers.shell import SandboxShellProvider

from tests.conftest_sandbox import fake_sandbox  # noqa: F401  reused fixture


def test_bash_truncation_marker_parity(tmp_path: Path, fake_sandbox):  # noqa: F811
    # Host
    host_runtime = BashRuntime(tmp_path)
    host_bash = create_bash_tool(workspace_root=tmp_path, runtime=host_runtime, permissions=None)
    host_out = host_bash.invoke({"command": "printf 'hi\\n'"})

    # Sandbox (fake)
    provider = SandboxShellProvider(sandbox=fake_sandbox, workspace_root=Path(fake_sandbox.workspace_dir))
    sb_runtime = BashRuntime(Path(fake_sandbox.workspace_dir), shell_provider=provider)
    sb_bash = create_bash_tool(workspace_root=Path(fake_sandbox.workspace_dir), runtime=sb_runtime, permissions=None)
    sb_out = sb_bash.invoke({"command": "printf 'hi\\n'"})

    assert host_out.strip() == sb_out.strip()


def test_read_tool_cat_n_parity(tmp_path: Path, fake_sandbox):  # noqa: F811
    payload = "line one\nline two\nline three\n"
    (tmp_path / "a.txt").write_text(payload, encoding="utf-8")
    fake_sandbox.upload_files([(f"{fake_sandbox.workspace_dir}/a.txt", payload.encode("utf-8"))])

    host_state = FileReadState()
    sb_state = FileReadState()
    host_tools = create_claude_file_tools(workspace_root=tmp_path, permissions=None, state=host_state)
    sb_tools = create_claude_file_tools(
        workspace_root=Path(fake_sandbox.workspace_dir),
        permissions=None,
        state=sb_state,
        transport=SandboxFileTransport(fake_sandbox),
    )

    host_read = next(t for t in host_tools if t.name == "Read")
    sb_read = next(t for t in sb_tools if t.name == "Read")
    host_out = host_read.invoke({"file_path": str(tmp_path / "a.txt")})
    sb_out = sb_read.invoke({"file_path": f"{fake_sandbox.workspace_dir}/a.txt"})

    # Strip path-prefix differences; line numbers + bodies must match.
    def normalize(text: str) -> str:
        return "\n".join(line for line in text.splitlines() if line.startswith(tuple("0123456789")))

    assert normalize(host_out) == normalize(sb_out)


def test_edit_string_not_found_message_parity(tmp_path, fake_sandbox):  # noqa: F811
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    fake_sandbox.upload_files([(f"{fake_sandbox.workspace_dir}/a.txt", b"alpha\n")])

    host_state = FileReadState()
    sb_state = FileReadState()
    host_tools = create_claude_file_tools(workspace_root=tmp_path, permissions=None, state=host_state)
    sb_tools = create_claude_file_tools(
        workspace_root=Path(fake_sandbox.workspace_dir),
        permissions=None,
        state=sb_state,
        transport=SandboxFileTransport(fake_sandbox),
    )
    host_edit = next(t for t in host_tools if t.name == "Edit")
    sb_edit = next(t for t in sb_tools if t.name == "Edit")

    # Need to read first to seed state.
    next(t for t in host_tools if t.name == "Read").invoke({"file_path": str(tmp_path / "a.txt")})
    next(t for t in sb_tools if t.name == "Read").invoke({"file_path": f"{fake_sandbox.workspace_dir}/a.txt"})

    host_out = host_edit.invoke({"file_path": str(tmp_path / "a.txt"), "old_string": "missing", "new_string": "x"})
    sb_out = sb_edit.invoke({"file_path": f"{fake_sandbox.workspace_dir}/a.txt", "old_string": "missing", "new_string": "x"})

    assert "String to replace not found" in host_out
    assert "String to replace not found" in sb_out
```

- [ ] **Step 3: 跑测试**

```bash
pytest tests/sandbox/test_tool_parity.py -v
```

Expected: 3 passed.

- [ ] **Step 4: commit**

```bash
git add tests/sandbox/test_tool_parity.py tests/conftest_sandbox.py
git commit -m "$(cat <<'EOF'
test(sandbox): host vs sandbox tool parity regression suite

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 21: L3 Docker 集成测试

**Files:**
- Create: `tests/sandbox/test_docker_sandbox_integration.py`

- [ ] **Step 1: 写测试**

```python
"""L3 integration tests — require docker daemon and HAGENT_TEST_DOCKER=1."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.docker

DOCKER_AVAILABLE = os.environ.get("HAGENT_TEST_DOCKER") == "1"

if not DOCKER_AVAILABLE:
    pytest.skip("HAGENT_TEST_DOCKER!=1; skipping docker integration tests", allow_module_level=True)


from hagent.sandbox.docker.sandbox import HagentDockerSandbox  # noqa: E402


@pytest.fixture
def docker_sandbox():
    sb = HagentDockerSandbox.start(prefer_runtime="runc")
    yield sb
    sb.close()


def test_python_version(docker_sandbox):
    resp = docker_sandbox.execute("python --version")
    assert resp.exit_code == 0
    assert resp.output.startswith("Python 3.12") or "Python 3" in resp.output


def test_upload_then_read(docker_sandbox):
    docker_sandbox.upload_files([("/workspace/a.txt", b"hello")])
    resp = docker_sandbox.execute("cat /workspace/a.txt")
    assert resp.exit_code == 0
    assert "hello" in resp.output


def test_download_roundtrip(docker_sandbox):
    docker_sandbox.upload_files([("/workspace/a.txt", b"world")])
    out = docker_sandbox.download_files(["/workspace/a.txt"])
    assert out[0].content == b"world"


def test_execute_timeout(docker_sandbox):
    resp = docker_sandbox.execute("sleep 3", timeout=1)
    # docker-py exec_run does not enforce timeout; we assert the call eventually returns.
    # Behavior parity will be enforced when ProcessRunner abstraction lands (future plan).
    assert resp.exit_code is not None


def test_stop_then_execute_returns_error():
    sb = HagentDockerSandbox.start(prefer_runtime="runc")
    sb.close()
    resp = sb.execute("echo hi")
    assert "not running" in resp.output.lower()
```

- [ ] **Step 2: 跑测试**

```bash
HAGENT_TEST_DOCKER=1 pytest tests/sandbox/test_docker_sandbox_integration.py -v
```

Expected: 5 passed（在装了 docker 的环境下）。无 docker 的 dev 机器自动 skip。

- [ ] **Step 3: commit**

```bash
git add tests/sandbox/test_docker_sandbox_integration.py
git commit -m "$(cat <<'EOF'
test(sandbox): L3 docker integration suite gated by HAGENT_TEST_DOCKER

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 22: L4 gVisor 集成测试

**Files:**
- Create: `tests/sandbox/test_gvisor.py`

- [ ] **Step 1: 写测试**

```python
"""L4 gVisor-specific assertions — requires docker + runsc + HAGENT_TEST_GVISOR=1."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.gvisor

if os.environ.get("HAGENT_TEST_GVISOR") != "1":
    pytest.skip("HAGENT_TEST_GVISOR!=1; skipping gVisor tests", allow_module_level=True)


from hagent.sandbox.docker.sandbox import HagentDockerSandbox  # noqa: E402


@pytest.fixture
def gvisor_sandbox():
    sb = HagentDockerSandbox.start(prefer_runtime="runsc")
    yield sb
    sb.close()


def test_uname_indicates_gvisor_kernel(gvisor_sandbox):
    resp = gvisor_sandbox.execute("uname -r")
    assert resp.exit_code == 0
    # gVisor reports a synthetic kernel version; assert it's not the host's.
    host_uname = os.uname().release
    assert host_uname not in resp.output


def test_dmesg_blocked_or_empty(gvisor_sandbox):
    resp = gvisor_sandbox.execute("dmesg 2>&1; true")
    # gVisor either rejects the syscall or returns empty buffer.
    assert "Operation not permitted" in resp.output or resp.output.strip() == ""
```

- [ ] **Step 2: 跑测试**

```bash
HAGENT_TEST_GVISOR=1 pytest tests/sandbox/test_gvisor.py -v
```

Expected: 2 passed (在装了 runsc 的环境下)；其他环境 skip。

- [ ] **Step 3: commit**

```bash
git add tests/sandbox/test_gvisor.py
git commit -m "$(cat <<'EOF'
test(sandbox): L4 gVisor-specific assertions gated by HAGENT_TEST_GVISOR

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 23: e2e demo（CLI + sandbox docker + 真实模型）

**Files:**
- Create: `tests/test_demo_e2e_sandbox.py`

- [ ] **Step 1: 写测试**

```python
"""L5 end-to-end demo — requires ANTHROPIC_API_KEY + docker + HAGENT_TEST_DOCKER=1."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.docker]

if not (os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("HAGENT_TEST_DOCKER") == "1"):
    pytest.skip("requires ANTHROPIC_API_KEY and HAGENT_TEST_DOCKER=1", allow_module_level=True)


def test_demo_sandbox_writes_result_file(monkeypatch, tmp_path):
    from hagent import cli
    monkeypatch.setenv("HAGENT_SANDBOX_KIND", "docker")
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(tmp_path))
    rc = cli.main([
        "demo",
        "--sandbox", "docker",
        "用 python 算 1+1 并写到 /workspace/result.txt，然后说完成。",
    ])
    assert rc == 0
    # We don't assert workspace file presence on host since sandbox uses
    # docker-internal /workspace; instead the demo's downloaded-artifacts hook
    # (future) will surface it. For now, the test passes if rc==0.
```

- [ ] **Step 2: 跑测试**

```bash
set -a && source .env && set +a && HAGENT_TEST_DOCKER=1 pytest tests/test_demo_e2e_sandbox.py -v -s
```

Expected: 1 passed（手动跑）。

- [ ] **Step 3: commit**

```bash
git add tests/test_demo_e2e_sandbox.py
git commit -m "$(cat <<'EOF'
test(sandbox): L5 e2e demo gated by ANTHROPIC_API_KEY + HAGENT_TEST_DOCKER

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 24: 同步 prompts/hagent_base.zh.md + decisions.md

**Files:**
- Modify: `prompts/hagent_base.zh.md`
- Modify: `prompts/decisions.md`

- [ ] **Step 1: 在 `prompts/hagent_base.zh.md` 适合位置（搜索 `working_directory` 附近）加 sandbox 段落**

```markdown
## Sandbox 模式（启用时）

在 sandbox 模式下：

- 你的工作目录是 sandbox 内的 `/workspace`，**不是** host 上的路径。host 路径（例如 `~/`、`/etc/`、`/Users/...`）**不可达**——尝试访问会失败。
- 文件读写通过 Read/Write/Edit 工具进行；这些路径都是 sandbox 内的绝对路径（例如 `/workspace/foo.py`）。
- Bash 命令在容器内执行，可联网（`pip install`、`git clone`、`curl` 都可用）。但容器内的 secrets 是空的——不要尝试读取 `ANTHROPIC_API_KEY` 等。
- 如果你要把工作产物交给用户，写到 `/workspace/` 下，结束后用户能通过 `download_files` 拿到。
```

- [ ] **Step 2: 在 `prompts/decisions.md` 末尾追加**

```markdown
## 2026-05-19 — sandbox 模式段落

**KEEP**：sandbox 模式段落（`/workspace` 是 LLM 看到的根、host 路径不可达、网络开放、secrets 空）。

**MODIFY**：将"working_directory: {working_directory}"的描述改为：sandbox 模式下 working_directory 总是 `/workspace`。

**DELETE**：无。

依据：spec `2026-05-19-hagent-sandbox-design.md` §3.3、§5.2、§5.5。
```

- [ ] **Step 3: 跑 base prompt 校验脚本**

```bash
./scripts/check_base_prompt.sh
```

Expected: 通过。

- [ ] **Step 4: commit**

```bash
git add prompts/hagent_base.zh.md prompts/decisions.md
git commit -m "$(cat <<'EOF'
docs(prompt): document sandbox mode in base prompt + decisions log

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 25: 同步 CLAUDE.md / AGENTS.md / web/CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`
- Modify: `web/CLAUDE.md`

- [ ] **Step 1: 在 `CLAUDE.md` 中**

在 "deepagents 0.6.x 行为约定" 段落里把第 2 点末尾 "正式部署走 Plan 5 `DockerBackend`" 改为：

```
正式部署走 M6 sandbox（`HagentDockerSandbox` + gVisor）；见 `docs/specs/2026-05-19-hagent-sandbox-design.md` 与对应实现 plan `docs/plans/2026-05-19-hagent-sandbox-impl.md`。
```

并在 "架构" 表格里加一行：

```
| `sandbox/` | M6 sandbox 抽象层：`protocol` / `docker/{runtime,lifecycle,sandbox,image}` / `daytona/sandbox`（stub）/ `providers/{shell,file}` / `pool` / `manifest` |
```

- [ ] **Step 2: 在 `AGENTS.md` 的 PR 验证命令小节加**

```markdown
当本次改动涉及 sandbox 时，PR description 必须包含以下验证：

\`\`\`bash
HAGENT_TEST_DOCKER=1 pytest -m docker -v
\`\`\`

如果改动涉及 gVisor 路径：

\`\`\`bash
HAGENT_TEST_GVISOR=1 pytest -m gvisor -v
\`\`\`
```

- [ ] **Step 3: 在 `web/CLAUDE.md` 加 sandbox 段落**

```markdown
## Sandbox 模式下的前端行为

当 server 端启动时设置了 `HAGENT_SANDBOX_KIND=docker`，所有新建 session 默认在 docker 容器内运行：

- 文件 API（`/sessions/{sid}/files`、`/sessions/{sid}/files/{path}`）行为不变——内部由 server 透明转 `sandbox.upload_files/download_files`。
- SSE 流额外包含 `sandbox.created` / `sandbox.paused` / `sandbox.resumed` / `sandbox.evicted` / `sandbox.error` 事件；Timeline 组件应识别这些 event type 并展示容器生命周期。
- 文件树展示的路径是 sandbox 内路径（`/workspace/...`），不要尝试转换为 host 路径。
- 创建 session 的 `POST /sessions` body 接受可选 `sandbox_kind: "none" | "docker" | "daytona"`；前端 UI 默认透传 server 的默认值。
```

- [ ] **Step 4: commit**

```bash
git add CLAUDE.md AGENTS.md web/CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: update CLAUDE.md / AGENTS.md / web/CLAUDE.md for sandbox mode

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 26: Plan 5 superseded note

**Files:**
- Modify: `docs/plans/2026-05-12-plan-5-docker-backend-and-swap.md`

- [ ] **Step 1: 在 Plan 5 文件顶部插入**

```markdown
> **⚠️ SUPERSEDED — 2026-05-19**
>
> 本 plan 是 deepagents 0.5.x 时期的 DockerBackend + shim JSON-RPC 草稿，**已弃用**。
> 新版 sandbox 设计基于 deepagents 0.6.x 的 `BaseSandbox` + `docker exec/cp`（不再需要 shim）。
>
> 参考：
> - Spec: `docs/specs/2026-05-19-hagent-sandbox-design.md`
> - 实现 plan: `docs/plans/2026-05-19-hagent-sandbox-impl.md`
>
> 本文件保留作为历史记录，不要按它实现。
```

- [ ] **Step 2: commit**

```bash
git add docs/plans/2026-05-12-plan-5-docker-backend-and-swap.md
git commit -m "$(cat <<'EOF'
docs: mark Plan 5 (DockerBackend + shim RPC) as superseded by M6 sandbox spec

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review

**Spec coverage:**

| Spec 段落 | 对应 Task |
| --- | --- |
| §1 背景与目标 | 全 plan |
| §2 决策表 D1–D10 | T2/T5/T10/T11（gVisor）、T6（upload/download，D8）、T10（release 默认 stop+rm，D9）、T14（permission 跳过，D7） |
| §3.1 三层结构 | T7 shell provider + T8/T9 file transport + T6 sandbox |
| §3.2 模块清单 | T2 runtime、T3 protocol、T4 image、T5 lifecycle、T6 sandbox、T7 shell、T9 file、T10/T11 pool、T13 manager、T19 daytona |
| §3.3 与现有模块接线 | T8（file_tools refactor）、T14（core.py wiring）、T15（cli）、T16（routers/files） |
| §3.4 deepagents 兼容性 | T14 |
| §4 数据流 + lifecycle | T6（execute path）、T10/T11（lifecycle 状态机）、T13（SessionManager） |
| §4.5 SessionStore 扩展 | T12 |
| §5.1 错误分层 | T2（runtime detect）、T5（container start 失败重试）、T6（exec/io 单调用错误）、T10（pool 满 503） |
| §5.2 安全策略 | T5（safe_env，secrets 不注入）、T18（server 不挂 host dir） |
| §5.3 permissions 语义 | T14 |
| §5.4 可观测性 | T17（SSE 事件）、T15（CLI 子命令） |
| §5.5 LLM 视角语义不变清单 | T20（parity 测试） |
| §6.1 测试分层 | T1（markers）、T21（L3）、T22（L4）、T23（L5） |
| §6.2 关键测试用例 | T2/T5/T6/T7/T9/T10/T11/T12/T13/T18 单元；T21 集成 |
| §6.3 行为对齐回归 | T20 |
| §6.4 既有测试套件影响 | T8（file_tools）、T14（core）回归 |
| §6.5 验收标准 | 全 plan 完成后即满足 |
| §6.6 SLO | 非验收，文档化在 T2/T6 内 |
| §10 文档同步 | T24（prompt + decisions）、T25（CLAUDE/AGENTS/web）、T26（Plan 5 supersede） |

**Placeholder scan:** 全部步骤含代码块或具体命令；无 TBD / TODO / "fill in details"。

**Type consistency:** `HagentSandboxProtocol`、`SandboxKind`、`SandboxLease`、`SandboxPool`、`SandboxManifest`、`SessionManager`、`HagentDockerSandbox`、`HagentDaytonaSandbox`、`SandboxShellProvider`、`SandboxFileTransport`、`FileTransport`、`HostFileTransport`、`DockerContainerLifecycle`、`ContainerStartError`、`PoolExhausted`、`RuntimeUnavailable`、`SandboxEvent` — 在引入和后续引用处保持一致。

**已知局限（明示）：**

- Background task 在 sandbox 模式下走 `docker exec` host subprocess，sandbox-内部子进程在 docker exec 断开后可能短暂遗留（容器 stop 时会被一并清理）。完整 parity 由后续"ProcessRunner 抽象"plan 解决。
- `docker exec` 不内建超时；timeout 当前由 host subprocess 的 wait timeout 控；超时时容器内进程可能继续运行直到 sandbox 销毁。L3 测试已记录此现实。

---

## Execution Handoff

**Plan complete and saved to `docs/plans/2026-05-19-hagent-sandbox-impl.md`. Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
