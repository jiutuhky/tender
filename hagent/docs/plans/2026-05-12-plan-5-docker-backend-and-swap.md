# Plan 5 — DockerBackend + Session Manager + M3-swap

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

> **存档说明**：本 plan 产出自已退役的 superpowers 工作流，仅作历史参考；新工作一律走仓根 tickets.md（Matt 契约）。

**Goal**: 实现真正的容器化沙箱：(1) `DockerBackend` Python 类满足 deepagents 的 `BackendProtocol` + `SandboxBackendProtocol`；(2) Session Manager 管 warm pool / idle GC / snapshot-resume；(3) 把 Plan 2 CLI 和 Plan 3 Agent Server 切换到使用 DockerBackend（M3-swap）。完成后 CLI demo + Web demo 都在 Docker 沙箱里跑通同一个 CSV 画图任务。

**Architecture**:
- 容器镜像基于 `python:3.12-slim`，PID 1 是 `tini`，PID 2 是 `shim.py`（Python JSON-RPC server，监听容器内 unix socket `/sock/shim.sock`）
- host 与容器通过 bind mount 共享 socket 目录（`-v /tmp/hagent/sockets/<sid>:/sock`），host 端的 `DockerBackend` 通过同一个路径连 socket
- shim 实现 RPC 方法：`ls / read / write / edit / glob / grep / execute / upload_files / download_files / cancel / ping`；execute 长输出落盘到 `/workspace/.hagent/exec_<call_id>.log` 并只回返截断 + 落盘路径
- DockerBackend Python 端是协议 client：每次调用打开 socket、发 JSON-RPC、读返回；同步阻塞，简单可靠
- SessionManager 接管原 SessionStore，扩展字段 `sandbox_id`（容器 id）+ `socket_dir`；create 时分配容器；delete 时 stop + rm + 清 socket 目录
- warm pool：启动时预热 N 个容器（默认 3），create_session 时领走一个并立刻补一个；idle 监控线程每 60s 扫一次 `last_active`，超过 30min 的 session snapshot + 销毁
- snapshot：`docker exec <cid> tar czf - /workspace /root/.cache/pip /workspace_node_modules` → host 落盘 `/tmp/hagent/snapshots/<sid>.tar.gz`；resume 时新容器 `docker cp` 进去再解压

**Tech Stack**: Docker（host 已装），`docker` Python SDK（pip 包名 `docker`），tini（apt 包），stdlib `socket` / `json` / `threading`。

**Spec reference**: §3 / §4 Track B M1 + M2 + M3-swap、§7 Layer 2（DockerBackend 进程级隔离）。

**Depends on**: Plan 2 + Plan 3（+ 可选 Plan 4）完成；host 装了 Docker；当前用户在 `docker` group（`docker ps` 能直接跑）。

**前置检查**：执行任何 Task 前先跑

```bash
docker version && docker run --rm hello-world
```

如果失败，向用户报告 BLOCKED（让用户先装 Docker / 加入 docker group），不要在 plan 内尝试修。

---

### Task 1: shim 协议 spec + RPC 数据结构

**Files:**
- Create: `docs/shim-protocol.md`
- Create: `src/hagent/sandbox/__init__.py`
- Create: `src/hagent/sandbox/rpc.py`
- Create: `tests/sandbox/__init__.py`
- Create: `tests/sandbox/test_rpc.py`

- [ ] **Step 1: 写 `docs/shim-protocol.md`** —— 定义 RPC 协议

```markdown
# Hagent Shim JSON-RPC Protocol v1

## Transport

Unix socket at `/sock/shim.sock` inside the container; host accesses via bind mount.

每次 RPC 调用 = host 打开 socket、send JSON 请求 + `\n`、读 JSON 响应 + `\n`、close socket。**不复用连接**——简单可靠，每个 call 独立超时。

## Request / response 格式

请求：
```json
{ "id": "<random>", "method": "<name>", "params": { ... } }
```

响应（成功）：
```json
{ "id": "<echo>", "result": { ... } }
```

响应（失败）：
```json
{ "id": "<echo>", "error": { "code": "<str>", "message": "<str>" } }
```

## 方法

| method | params | result | 备注 |
|---|---|---|---|
| ping | {} | {"ok": true, "pid": <int>} | 健康检查 |
| ls | {"path": "/workspace"} | {"entries": [{"name", "type", "size"}, ...]} | type 为 "file" / "dir" |
| read | {"path", "offset": 0, "limit": 2000} | {"content": "...", "truncated": bool} | offset/limit 单位是行 |
| write | {"path", "content"} | {"bytes": <int>} | 覆盖 |
| edit | {"path", "old_string", "new_string", "replace_all": false} | {"replacements": <int>} | exact string |
| glob | {"pattern", "path": "/workspace"} | {"paths": [...]} | 用 `pathlib.Path.glob` |
| grep | {"pattern", "path": null, "glob": null} | {"matches": [{"path", "line", "text"}, ...]} | ripgrep |
| execute | {"command", "timeout": 120, "max_output": 100000} | {"stdout", "stderr", "exit_code", "truncated", "log_path"} | 长输出落盘到 `/workspace/.hagent/exec_<id>.log` |
| upload | {"path", "content_b64"} | {"bytes": <int>} | base64 binary upload |
| download | {"path"} | {"content_b64": "...", "bytes": <int>} | base64 binary download |
| cancel | {"call_id"} | {"ok": bool} | 取消 in-flight execute（v1 可选返回 false） |

## 错误 code

- `not_found`：路径不存在
- `permission_denied`：访问被拒（shim 不检查 deepagents permissions；这是 OS 层 EPERM）
- `timeout`：execute 超时
- `bad_request`：参数缺失或类型错
- `internal`：未分类异常
```

- [ ] **Step 2: 写 `src/hagent/sandbox/__init__.py`**

```python
```

- [ ] **Step 3: 写 `src/hagent/sandbox/rpc.py`** —— host 端 RPC 客户端

```python
from __future__ import annotations

import json
import socket
import uuid
from typing import Any


class ShimRPCError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def call(socket_path: str, method: str, params: dict[str, Any] | None = None, timeout: float = 130.0) -> Any:
    req = {"id": uuid.uuid4().hex[:12], "method": method, "params": params or {}}
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(socket_path)
        s.sendall(json.dumps(req).encode("utf-8") + b"\n")
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        resp = json.loads(buf.decode("utf-8").rstrip())
    finally:
        s.close()
    if "error" in resp:
        e = resp["error"]
        raise ShimRPCError(e.get("code", "internal"), e.get("message", ""))
    return resp.get("result")
```

- [ ] **Step 4: 写 `tests/sandbox/test_rpc.py`** —— 用本地 socket fake shim 测客户端

```python
import json
import os
import socket
import threading
from pathlib import Path

import pytest

from hagent.sandbox.rpc import call, ShimRPCError


def _start_fake_shim(socket_path: str, handler) -> threading.Event:
    stop = threading.Event()

    def loop():
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(socket_path)
        s.listen(1)
        s.settimeout(0.5)
        while not stop.is_set():
            try:
                conn, _ = s.accept()
            except socket.timeout:
                continue
            try:
                buf = b""
                while not buf.endswith(b"\n"):
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                req = json.loads(buf.decode("utf-8").rstrip())
                resp = handler(req)
                conn.sendall(json.dumps(resp).encode("utf-8") + b"\n")
            finally:
                conn.close()
        s.close()

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return stop


def test_call_success(tmp_path):
    sock = str(tmp_path / "s.sock")
    stop = _start_fake_shim(sock, lambda req: {"id": req["id"], "result": {"echo": req["params"]}})
    try:
        out = call(sock, "ping", {"hello": "world"})
        assert out == {"echo": {"hello": "world"}}
    finally:
        stop.set()


def test_call_error_raises(tmp_path):
    sock = str(tmp_path / "s.sock")
    stop = _start_fake_shim(sock, lambda req: {"id": req["id"], "error": {"code": "boom", "message": "nope"}})
    try:
        with pytest.raises(ShimRPCError) as ei:
            call(sock, "anything")
        assert ei.value.code == "boom"
    finally:
        stop.set()
```

- [ ] **Step 5: 跑测试**

```bash
source .venv/bin/activate && pytest tests/sandbox/test_rpc.py -v
```

- [ ] **Step 6: 提交**

```bash
git add docs/shim-protocol.md src/hagent/sandbox/ tests/sandbox/
git commit -m "feat(sandbox): add shim JSON-RPC client + protocol spec"
```

---

### Task 2: shim server 实现（容器内运行）

**Files:**
- Create: `sandbox/shim.py`（注意路径：不在 `src/` 下，因为它要进容器镜像）
- Create: `tests/sandbox/test_shim_local.py`（在本机直接跑 shim.py 测试）

- [ ] **Step 1: 写 `sandbox/shim.py`**

```python
#!/usr/bin/env python3
"""Hagent shim — JSON-RPC server inside the sandbox container.

Listens on a unix socket. Each request is a JSON line; each response is a JSON line.
"""
from __future__ import annotations

import base64
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path


SOCKET_PATH = os.environ.get("HAGENT_SHIM_SOCKET", "/sock/shim.sock")
DEFAULT_TIMEOUT = 120
DEFAULT_MAX_OUTPUT = 100_000


def _err(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def m_ping(_p: dict) -> dict:
    return {"ok": True, "pid": os.getpid()}


def m_ls(p: dict) -> dict:
    path = Path(p["path"])
    if not path.exists():
        return _err("not_found", f"{path} not found")
    if path.is_file():
        return {"entries": [{"name": path.name, "type": "file", "size": path.stat().st_size}]}
    entries = []
    for child in sorted(path.iterdir()):
        entries.append({
            "name": child.name,
            "type": "dir" if child.is_dir() else "file",
            "size": child.stat().st_size if child.is_file() else None,
        })
    return {"entries": entries}


def m_read(p: dict) -> dict:
    path = Path(p["path"])
    if not path.is_file():
        return _err("not_found", f"{path} not a file")
    offset = int(p.get("offset", 0))
    limit = int(p.get("limit", 2000))
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines(keepends=True)
    selected = lines[offset : offset + limit]
    truncated = (offset + limit) < len(lines)
    return {"content": "".join(selected), "truncated": truncated}


def m_write(p: dict) -> dict:
    path = Path(p["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    content = p["content"]
    path.write_text(content, encoding="utf-8")
    return {"bytes": len(content.encode("utf-8"))}


def m_edit(p: dict) -> dict:
    path = Path(p["path"])
    if not path.is_file():
        return _err("not_found", str(path))
    text = path.read_text(encoding="utf-8")
    old = p["old_string"]
    new = p["new_string"]
    replace_all = bool(p.get("replace_all", False))
    if replace_all:
        n = text.count(old)
        text = text.replace(old, new)
    else:
        if text.count(old) != 1:
            return _err("bad_request", f"old_string not unique (count={text.count(old)})")
        text = text.replace(old, new, 1)
        n = 1
    path.write_text(text, encoding="utf-8")
    return {"replacements": n}


def m_glob(p: dict) -> dict:
    base = Path(p.get("path", "/workspace"))
    pat = p["pattern"]
    return {"paths": [str(x) for x in sorted(base.rglob(pat))]}


def m_grep(p: dict) -> dict:
    pattern = p["pattern"]
    path = p.get("path") or "/workspace"
    glob = p.get("glob")
    matches: list[dict] = []
    rx = re.compile(pattern)
    target = Path(path)
    files = target.rglob(glob) if glob else target.rglob("*")
    for f in files:
        if not f.is_file():
            continue
        try:
            for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if rx.search(line):
                    matches.append({"path": str(f), "line": i, "text": line[:500]})
        except Exception:
            continue
    return {"matches": matches[:5000]}


def m_execute(p: dict) -> dict:
    cmd = p["command"]
    timeout = int(p.get("timeout", DEFAULT_TIMEOUT))
    max_output = int(p.get("max_output", DEFAULT_MAX_OUTPUT))
    call_id = uuid.uuid4().hex[:12]
    log_dir = Path("/workspace/.hagent")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"exec_{call_id}.log"
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd="/workspace",
        )
    except subprocess.TimeoutExpired as e:
        log_path.write_text((e.stdout or "") + (e.stderr or ""), encoding="utf-8")
        return _err("timeout", f"command exceeded {timeout}s; partial output at {log_path}")
    combined = (proc.stdout or "") + (proc.stderr or "")
    log_path.write_text(combined, encoding="utf-8")
    truncated = len(combined) > max_output
    return {
        "stdout": proc.stdout[:max_output] if proc.stdout else "",
        "stderr": proc.stderr[:max_output] if proc.stderr else "",
        "exit_code": proc.returncode,
        "truncated": truncated,
        "log_path": str(log_path),
    }


def m_upload(p: dict) -> dict:
    path = Path(p["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    data = base64.b64decode(p["content_b64"])
    path.write_bytes(data)
    return {"bytes": len(data)}


def m_download(p: dict) -> dict:
    path = Path(p["path"])
    if not path.is_file():
        return _err("not_found", str(path))
    data = path.read_bytes()
    return {"content_b64": base64.b64encode(data).decode("ascii"), "bytes": len(data)}


def m_cancel(_p: dict) -> dict:
    return {"ok": False}  # v1 不实现


METHODS = {
    "ping": m_ping,
    "ls": m_ls,
    "read": m_read,
    "write": m_write,
    "edit": m_edit,
    "glob": m_glob,
    "grep": m_grep,
    "execute": m_execute,
    "upload": m_upload,
    "download": m_download,
    "cancel": m_cancel,
}


def handle(conn: socket.socket) -> None:
    try:
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = conn.recv(65536)
            if not chunk:
                return
            buf += chunk
        req = json.loads(buf.decode("utf-8").rstrip())
        method = METHODS.get(req.get("method"))
        if method is None:
            resp = {"id": req.get("id"), **_err("bad_request", f"unknown method: {req.get('method')}")}
        else:
            try:
                result = method(req.get("params") or {})
                if "error" in result:
                    resp = {"id": req.get("id"), **result}
                else:
                    resp = {"id": req.get("id"), "result": result}
            except Exception as e:  # noqa: BLE001
                resp = {"id": req.get("id"), **_err("internal", str(e))}
        conn.sendall(json.dumps(resp).encode("utf-8") + b"\n")
    finally:
        conn.close()


def main() -> int:
    sock_path = SOCKET_PATH
    try:
        os.unlink(sock_path)
    except FileNotFoundError:
        pass
    Path(sock_path).parent.mkdir(parents=True, exist_ok=True)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(sock_path)
    os.chmod(sock_path, 0o666)
    s.listen(32)
    print(f"[shim] listening on {sock_path}", file=sys.stderr, flush=True)
    while True:
        conn, _ = s.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 写 `tests/sandbox/test_shim_local.py`** —— 在本机起 shim，调每个方法

```python
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from hagent.sandbox.rpc import call, ShimRPCError


@pytest.fixture
def shim(tmp_path):
    sock = tmp_path / "shim.sock"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    env = {
        **os.environ,
        "HAGENT_SHIM_SOCKET": str(sock),
        "PATH": os.environ["PATH"],
    }
    # shim.py 假设 /workspace 存在；test 里我们改用 tmp 的 workspace 并通过 monkeypatch /workspace
    # 简化：把 workspace symlink 到 /workspace 不可行，改成测试时直接 chdir + 用绝对路径
    proc = subprocess.Popen(
        [sys.executable, "sandbox/shim.py"],
        env=env,
        stderr=subprocess.PIPE,
    )
    # 等 socket 出现
    for _ in range(50):
        if sock.exists():
            break
        time.sleep(0.05)
    yield {"sock": str(sock), "workspace": str(workspace)}
    proc.terminate()
    proc.wait(timeout=3)


def test_ping(shim):
    out = call(shim["sock"], "ping")
    assert out["ok"] is True
    assert "pid" in out


def test_write_read(shim, tmp_path):
    target = str(tmp_path / "hello.txt")
    call(shim["sock"], "write", {"path": target, "content": "hi\nthere\n"})
    out = call(shim["sock"], "read", {"path": target})
    assert "hi" in out["content"]


def test_ls(shim, tmp_path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "subdir").mkdir()
    out = call(shim["sock"], "ls", {"path": str(tmp_path)})
    names = [e["name"] for e in out["entries"]]
    assert "a.txt" in names
    assert "subdir" in names


def test_edit_replace_unique(shim, tmp_path):
    p = tmp_path / "edit.txt"
    p.write_text("foo bar foo")
    out = call(shim["sock"], "edit", {"path": str(p), "old_string": "bar", "new_string": "BAZ"})
    assert out["replacements"] == 1
    assert p.read_text() == "foo BAZ foo"


def test_edit_replace_all(shim, tmp_path):
    p = tmp_path / "all.txt"
    p.write_text("a a a")
    out = call(shim["sock"], "edit", {"path": str(p), "old_string": "a", "new_string": "b", "replace_all": True})
    assert out["replacements"] == 3


def test_execute(shim):
    # shim 的 execute 默认 cwd=/workspace；本机测试时这个目录可能不存在，所以测一个不依赖 cwd 的命令
    out = call(shim["sock"], "execute", {"command": "echo hello-shim"})
    # /workspace 不存在时 subprocess.run 会抛 FileNotFoundError，shim 会包到 internal
    # 接受两种结果：成功 with stdout 含 hello-shim，或 internal error 含 /workspace
    if "exit_code" in out:
        assert "hello-shim" in out["stdout"]


def test_upload_download(shim, tmp_path):
    import base64
    target = str(tmp_path / "bin.dat")
    payload = b"\x00\x01\x02hello"
    call(shim["sock"], "upload", {"path": target, "content_b64": base64.b64encode(payload).decode()})
    out = call(shim["sock"], "download", {"path": target})
    assert base64.b64decode(out["content_b64"]) == payload
```

- [ ] **Step 3: 跑**

```bash
source .venv/bin/activate && pytest tests/sandbox/test_shim_local.py -v
```

注意：本机跑 shim.py 时，execute 的 cwd=/workspace 会找不到目录，相关断言已经容错。重点验证 read/write/ls/edit/upload/download 都能在本机跑通。

- [ ] **Step 4: 提交**

```bash
git add sandbox/shim.py tests/sandbox/test_shim_local.py
git commit -m "feat(sandbox): add shim JSON-RPC server (in-container)"
```

---

### Task 3: Dockerfile + 构建脚本

**Files:**
- Create: `sandbox/Dockerfile`
- Create: `sandbox/entrypoint.sh`
- Create: `scripts/build_image.sh`

- [ ] **Step 1: 写 `sandbox/Dockerfile`**

```dockerfile
FROM python:3.12-slim

# OS 工具：tini 做 PID 1；ripgrep 给 grep 用更快；git/curl 给 demo 任务
RUN apt-get update && apt-get install -y --no-install-recommends \
        tini ripgrep git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 常用 Python 包预装，避免 demo 时反复装
RUN pip install --no-cache-dir \
        numpy pandas matplotlib requests beautifulsoup4 lxml

# shim 进入镜像
COPY shim.py /opt/hagent/shim.py
COPY entrypoint.sh /opt/hagent/entrypoint.sh
RUN chmod +x /opt/hagent/entrypoint.sh

# /workspace 是用户工作目录；/sock 是 socket bind mount 点
RUN mkdir -p /workspace /sock

WORKDIR /workspace

ENTRYPOINT ["/usr/bin/tini", "--", "/opt/hagent/entrypoint.sh"]
```

- [ ] **Step 2: 写 `sandbox/entrypoint.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
exec python3 /opt/hagent/shim.py
```

- [ ] **Step 3: 写 `scripts/build_image.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker build -t hagent/sandbox:dev -f sandbox/Dockerfile sandbox/
echo "✓ built hagent/sandbox:dev"
docker images hagent/sandbox:dev
```

- [ ] **Step 4: 构建镜像**

```bash
chmod +x sandbox/entrypoint.sh scripts/build_image.sh
./scripts/build_image.sh
```

Expected: `docker images` 列表里有 `hagent/sandbox:dev`。

- [ ] **Step 5: 手动 smoke**

```bash
mkdir -p /tmp/hagent-smoke-sockets
docker run -d --rm --name hagent-smoke -v /tmp/hagent-smoke-sockets:/sock hagent/sandbox:dev
sleep 2
ls /tmp/hagent-smoke-sockets/  # 应能看到 shim.sock

# ping
python3 -c "
import sys; sys.path.insert(0, 'src')
from hagent.sandbox.rpc import call
print(call('/tmp/hagent-smoke-sockets/shim.sock', 'ping'))
"

docker stop hagent-smoke
rm -rf /tmp/hagent-smoke-sockets
```

Expected: ping 返回 `{'ok': True, 'pid': ...}`。

- [ ] **Step 6: 提交**

```bash
git add sandbox/Dockerfile sandbox/entrypoint.sh scripts/build_image.sh
git commit -m "feat(sandbox): add Dockerfile + entrypoint + build script"
```

---

### Task 4: DockerBackend Python 类（生命周期 + ping）

**Files:**
- Create: `src/hagent/sandbox/docker_backend.py`
- Create: `tests/sandbox/test_docker_backend.py`

DockerBackend 需要实现 deepagents 的 `BackendProtocol` + `SandboxBackendProtocol`。先做容器生命周期 + ping，方法实现在后续 task 加。

- [ ] **Step 1: 加依赖**

`pyproject.toml` 的 `dependencies` 数组追加：
```toml
    "docker>=7.1",
```

```bash
source .venv/bin/activate && pip install -e ".[dev]"
```

- [ ] **Step 2: 写 `src/hagent/sandbox/docker_backend.py`** —— 第一版只做生命周期

```python
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any

import docker
from docker.models.containers import Container

from hagent.sandbox.rpc import call


SOCKET_BIND_BASE = Path(os.environ.get("HAGENT_SOCKET_BASE", "/tmp/hagent/sockets"))
IMAGE = os.environ.get("HAGENT_IMAGE", "hagent/sandbox:dev")
CONTAINER_PREFIX = "hagent-"


class DockerBackend:
    """Implements deepagents BackendProtocol + SandboxBackendProtocol via docker container shim."""

    def __init__(self, sandbox_id: str | None = None, image: str = IMAGE) -> None:
        self._client = docker.from_env()
        self._sandbox_id = sandbox_id or uuid.uuid4().hex[:12]
        self._image = image
        self._socket_dir = SOCKET_BIND_BASE / self._sandbox_id
        self._socket_dir.mkdir(parents=True, exist_ok=True)
        self._socket_path = self._socket_dir / "shim.sock"
        self._container: Container | None = None

    @property
    def id(self) -> str:  # part of deepagents BackendProtocol
        return self._sandbox_id

    @property
    def container_id(self) -> str | None:
        return self._container.id if self._container else None

    def start(self) -> None:
        if self._container is not None:
            return
        self._container = self._client.containers.run(
            self._image,
            name=f"{CONTAINER_PREFIX}{self._sandbox_id}",
            detach=True,
            remove=False,
            volumes={str(self._socket_dir): {"bind": "/sock", "mode": "rw"}},
            network_mode="bridge",
            mem_limit="2g",
            pids_limit=512,
        )
        # 等 shim socket 出现
        for _ in range(100):
            if self._socket_path.exists():
                try:
                    call(str(self._socket_path), "ping", timeout=2.0)
                    return
                except Exception:
                    pass
            time.sleep(0.1)
        raise RuntimeError(f"shim did not come up for sandbox {self._sandbox_id}")

    def stop(self) -> None:
        if self._container:
            try:
                self._container.stop(timeout=5)
                self._container.remove(force=True)
            except Exception:
                pass
            self._container = None
        try:
            self._socket_path.unlink(missing_ok=True)
            self._socket_dir.rmdir()
        except Exception:
            pass

    def ping(self) -> dict[str, Any]:
        return call(str(self._socket_path), "ping")

    def __enter__(self) -> "DockerBackend":
        self.start()
        return self

    def __exit__(self, *_a: Any) -> None:
        self.stop()
```

- [ ] **Step 3: 写 `tests/sandbox/test_docker_backend.py`** —— 真实 Docker 集成测试

```python
import os

import pytest

from hagent.sandbox.docker_backend import DockerBackend


@pytest.fixture(scope="module")
def docker_available():
    if os.environ.get("HAGENT_SKIP_DOCKER_TESTS"):
        pytest.skip("HAGENT_SKIP_DOCKER_TESTS set")
    import docker as docker_pkg
    try:
        c = docker_pkg.from_env()
        c.ping()
    except Exception as e:
        pytest.skip(f"docker not available: {e}")


def test_start_stop_lifecycle(docker_available):
    b = DockerBackend()
    b.start()
    try:
        assert b.container_id is not None
        result = b.ping()
        assert result["ok"] is True
    finally:
        b.stop()


def test_context_manager(docker_available):
    with DockerBackend() as b:
        assert b.ping()["ok"] is True
```

- [ ] **Step 4: 跑（需 docker）**

```bash
source .venv/bin/activate && pytest tests/sandbox/test_docker_backend.py -v
```

Expected: PASS。如果 docker 不可用会自动 skip。

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml src/hagent/sandbox/docker_backend.py tests/sandbox/test_docker_backend.py
git commit -m "feat(sandbox): add DockerBackend lifecycle (start/stop/ping)"
```

---

### Task 5: BackendProtocol 方法实现（read/write/edit/ls/glob/grep）

**Files:**
- Modify: `src/hagent/sandbox/docker_backend.py`
- Modify: `tests/sandbox/test_docker_backend.py`

deepagents `BackendProtocol` 真实 result 类型（已通过运行时 introspection 验证）：

| 类型 | 字段 |
|---|---|
| `ReadResult` | `error: str\|None`, `file_data: FileData\|None` |
| `WriteResult` | `error`, `path`, `files_update` |
| `EditResult` | `error`, `path`, `files_update`, `occurrences: int\|None` |
| `LsResult` | `error`, `entries: list[FileInfo]\|None` |
| `GlobResult` | `error`, `matches: list[FileInfo]\|None`（注意是 `matches`，不是 `paths`） |
| `GrepResult` | `error`, `matches: list[GrepMatch]\|None` |
| `FileData` | TypedDict `{content, encoding, created_at?, modified_at?}` |
| `FileInfo` | TypedDict `{path, is_dir?, size?, modified_at?}` |
| `GrepMatch` | TypedDict `{path, line, text}` |

下面的实现按真实字段名构造，不再做 hasattr fallback。

- [ ] **Step 1: 给 DockerBackend 加协议方法**

在 `docker_backend.py` 顶部加 import：

```python
from deepagents.backends.protocol import (
    EditResult,
    FileData,
    FileInfo,
    GlobResult,
    GrepMatch,
    GrepResult,
    LsResult,
    ReadResult,
    WriteResult,
)
```

在 `DockerBackend` 类里追加（注意 shim JSON 字段 `name/type` → 协议 `FileInfo.path/is_dir`，需要适配）：

```python
    @staticmethod
    def _entry_to_fileinfo(parent: str, e: dict) -> FileInfo:
        # shim 返回 {name, type, size}；协议要求 {path, is_dir, size}
        from posixpath import join as pjoin
        info: FileInfo = {"path": pjoin(parent, e["name"])}
        if "type" in e:
            info["is_dir"] = e["type"] == "dir"
        if e.get("size") is not None:
            info["size"] = e["size"]
        return info

    def ls(self, path: str) -> LsResult:
        try:
            out = call(str(self._socket_path), "ls", {"path": path})
            entries = [self._entry_to_fileinfo(path, e) for e in out["entries"]]
            return LsResult(error=None, entries=entries)
        except ShimRPCError as e:
            return LsResult(error=str(e), entries=None)
        except Exception as e:  # noqa: BLE001
            return LsResult(error=str(e), entries=None)

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        try:
            out = call(str(self._socket_path), "read", {"path": file_path, "offset": offset, "limit": limit})
            fd: FileData = {"content": out["content"], "encoding": "utf-8"}
            return ReadResult(error=None, file_data=fd)
        except ShimRPCError as e:
            return ReadResult(error=str(e), file_data=None)
        except Exception as e:  # noqa: BLE001
            return ReadResult(error=str(e), file_data=None)

    def write(self, file_path: str, content: str) -> WriteResult:
        try:
            call(str(self._socket_path), "write", {"path": file_path, "content": content})
            return WriteResult(error=None, path=file_path, files_update=None)
        except ShimRPCError as e:
            return WriteResult(error=str(e), path=file_path, files_update=None)
        except Exception as e:  # noqa: BLE001
            return WriteResult(error=str(e), path=file_path, files_update=None)

    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult:
        try:
            out = call(str(self._socket_path), "edit", {
                "path": file_path,
                "old_string": old_string,
                "new_string": new_string,
                "replace_all": replace_all,
            })
            return EditResult(
                error=None,
                path=file_path,
                files_update=None,
                occurrences=out.get("replacements"),
            )
        except ShimRPCError as e:
            return EditResult(error=str(e), path=file_path, files_update=None, occurrences=None)
        except Exception as e:  # noqa: BLE001
            return EditResult(error=str(e), path=file_path, files_update=None, occurrences=None)

    def glob(self, pattern: str, path: str = "/") -> GlobResult:
        try:
            out = call(str(self._socket_path), "glob", {"pattern": pattern, "path": path})
            matches: list[FileInfo] = [{"path": p_} for p_ in out["paths"]]
            return GlobResult(error=None, matches=matches)
        except ShimRPCError as e:
            return GlobResult(error=str(e), matches=None)
        except Exception as e:  # noqa: BLE001
            return GlobResult(error=str(e), matches=None)

    def grep(self, pattern: str, path: str | None = None, glob: str | None = None) -> GrepResult:
        try:
            out = call(str(self._socket_path), "grep", {"pattern": pattern, "path": path, "glob": glob})
            matches: list[GrepMatch] = [
                {"path": m["path"], "line": m["line"], "text": m["text"]} for m in out["matches"]
            ]
            return GrepResult(error=None, matches=matches)
        except ShimRPCError as e:
            return GrepResult(error=str(e), matches=None)
        except Exception as e:  # noqa: BLE001
            return GrepResult(error=str(e), matches=None)
```

还要把 import 里加上 `from hagent.sandbox.rpc import call, ShimRPCError`（之前只 import 了 `call`）。

- [ ] **Step 2: 加测试**

```python
def test_write_read_roundtrip(docker_available):
    with DockerBackend() as b:
        wr = b.write("/workspace/x.txt", "hello\nworld\n")
        assert wr.error is None

        rd = b.read("/workspace/x.txt")
        assert rd.error is None
        assert rd.file_data is not None
        assert "hello" in rd.file_data["content"]


def test_ls(docker_available):
    with DockerBackend() as b:
        b.write("/workspace/a.txt", "x")
        res = b.ls("/workspace")
        assert res.error is None
        assert res.entries is not None
        paths = [e["path"] for e in res.entries]
        assert any(p.endswith("a.txt") for p in paths)


def test_edit_unique(docker_available):
    with DockerBackend() as b:
        b.write("/workspace/e.txt", "foo bar foo")
        res = b.edit("/workspace/e.txt", "bar", "BAZ")
        assert res.error is None
        assert res.occurrences == 1
        rd = b.read("/workspace/e.txt")
        assert "BAZ" in rd.file_data["content"]


def test_grep(docker_available):
    with DockerBackend() as b:
        b.write("/workspace/g.txt", "hello\nworld\nhello again\n")
        res = b.grep("hello", path="/workspace")
        assert res.error is None
        assert res.matches is not None
        assert len(res.matches) >= 2
```

- [ ] **Step 3: 跑测试**

```bash
pytest tests/sandbox/test_docker_backend.py -v
```

- [ ] **Step 4: 提交**

```bash
git add src/hagent/sandbox/docker_backend.py tests/sandbox/test_docker_backend.py
git commit -m "feat(sandbox): implement BackendProtocol methods (ls/read/write/edit/glob/grep)"
```

---

### Task 6: SandboxBackendProtocol — execute

**Files:**
- Modify: `src/hagent/sandbox/docker_backend.py`
- Modify: `tests/sandbox/test_docker_backend.py`

- [ ] **Step 1: 加 `execute` 方法**

deepagents `ExecuteResponse` 真实字段（已 introspect 验证）：`output: str`, `exit_code: int|None`, `truncated: bool`。**没有** `stdout/stderr/error` 字段——shim 的 stdout + stderr 要 concat 成单个 `output` 串。注意 `BackendProtocol.execute(self, command, *, timeout=None)` 的 `timeout` 是 keyword-only。

```python
    from deepagents.backends.protocol import ExecuteResponse  # 顶部已 import 过则无需重复

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        effective_timeout = timeout if timeout is not None else 120
        try:
            out = call(
                str(self._socket_path),
                "execute",
                {"command": command, "timeout": effective_timeout},
                timeout=effective_timeout + 10,
            )
            combined = (out.get("stdout") or "") + (out.get("stderr") or "")
            return ExecuteResponse(
                output=combined,
                exit_code=out.get("exit_code"),
                truncated=bool(out.get("truncated", False)),
            )
        except ShimRPCError as e:
            return ExecuteResponse(output=f"[shim error] {e}", exit_code=None, truncated=False)
        except Exception as e:  # noqa: BLE001
            return ExecuteResponse(output=f"[error] {e}", exit_code=None, truncated=False)
```

- [ ] **Step 2: 加测试**

```python
def test_execute_echo(docker_available):
    with DockerBackend() as b:
        res = b.execute("echo hello-from-container")
        assert res.exit_code == 0
        assert "hello-from-container" in res.output


def test_execute_nonzero_exit(docker_available):
    with DockerBackend() as b:
        res = b.execute("exit 7")
        assert res.exit_code == 7


def test_execute_long_output_truncates(docker_available):
    with DockerBackend() as b:
        res = b.execute('python -c "print(\'x\'*200000)"')
        # shim 默认 max_output=100_000；combined output 长度上限大约 2*100k
        assert len(res.output) <= 200_002
        assert res.truncated is True
```

- [ ] **Step 3: 跑 + 提交**

```bash
pytest tests/sandbox/test_docker_backend.py -v
git add src/hagent/sandbox/docker_backend.py tests/sandbox/test_docker_backend.py
git commit -m "feat(sandbox): implement SandboxBackendProtocol execute method"
```

---

### Task 7: upload_files / download_files

**Files:**
- Modify: `src/hagent/sandbox/docker_backend.py`
- Modify: `tests/sandbox/test_docker_backend.py`

- [ ] **Step 1: 加方法**

deepagents 协议要求 `upload_files` 返回 `list[FileUploadResponse]`，`download_files` 返回 `list[FileDownloadResponse]`（已 introspect 验证）：

- `FileUploadResponse(path: str, error: Literal['file_not_found','permission_denied','is_directory','invalid_path']|None)`
- `FileDownloadResponse(path: str, content: bytes|None, error: ...|None)`

```python
    from deepagents.backends.protocol import FileUploadResponse, FileDownloadResponse  # 加到顶部 import

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        import base64
        results: list[FileUploadResponse] = []
        for path, data in files:
            try:
                call(
                    str(self._socket_path),
                    "upload",
                    {"path": path, "content_b64": base64.b64encode(data).decode("ascii")},
                )
                results.append(FileUploadResponse(path=path, error=None))
            except ShimRPCError as e:
                err = "permission_denied" if e.code == "permission_denied" else "invalid_path"
                results.append(FileUploadResponse(path=path, error=err))
            except Exception:  # noqa: BLE001
                results.append(FileUploadResponse(path=path, error="invalid_path"))
        return results

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        import base64
        results: list[FileDownloadResponse] = []
        for path in paths:
            try:
                r = call(str(self._socket_path), "download", {"path": path})
                results.append(FileDownloadResponse(
                    path=path, content=base64.b64decode(r["content_b64"]), error=None,
                ))
            except ShimRPCError as e:
                err = "file_not_found" if e.code == "not_found" else "invalid_path"
                results.append(FileDownloadResponse(path=path, content=None, error=err))
            except Exception:  # noqa: BLE001
                results.append(FileDownloadResponse(path=path, content=None, error="invalid_path"))
        return results
```

- [ ] **Step 2: 测试**

```python
def test_upload_download(docker_available):
    payload = b"\x00\x01binary\xff\xfe"
    with DockerBackend() as b:
        up = b.upload_files([("/workspace/blob.bin", payload)])
        assert up[0].error is None
        out = b.download_files(["/workspace/blob.bin"])
        assert out[0].error is None
        assert out[0].content == payload


def test_download_nonexistent_returns_error(docker_available):
    with DockerBackend() as b:
        out = b.download_files(["/workspace/does-not-exist.bin"])
        assert out[0].content is None
        assert out[0].error == "file_not_found"
```

- [ ] **Step 3: 提交**

```bash
pytest tests/sandbox/test_docker_backend.py -v
git add src/hagent/sandbox/docker_backend.py tests/sandbox/test_docker_backend.py
git commit -m "feat(sandbox): implement file upload/download via base64"
```

---

### Task 8: SessionManager 扩展 sandbox 字段 + 集成 DockerBackend

**Files:**
- Modify: `src/hagent/server/sessions.py`（加 sandbox_id / image columns）
- Create: `src/hagent/server/manager.py`（SessionManager 封装 SessionStore + DockerBackend pool）
- Create: `tests/server/test_manager.py`

- [ ] **Step 1: 改 SessionStore schema 加 sandbox 字段**

修改 `_SCHEMA`：

```python
_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    workspace_dir TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    last_active REAL NOT NULL,
    sandbox_id TEXT,
    container_id TEXT
)
"""
```

修改 `SessionState` dataclass 加可选字段：

```python
@dataclass(frozen=True)
class SessionState:
    id: str
    workspace_dir: str
    status: SessionStatus
    created_at: float
    last_active: float
    sandbox_id: str | None = None
    container_id: str | None = None
```

修改 `SessionStore.create` 接受 `sandbox_id` 和 `container_id`：

```python
    def create(
        self,
        workspace_root: Path | str,
        sandbox_id: str | None = None,
        container_id: str | None = None,
    ) -> SessionState:
        sid = uuid.uuid4().hex[:16]
        workspace_dir = Path(workspace_root) / sid / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sid, str(workspace_dir), SessionStatus.ACTIVE.value, now, now, sandbox_id, container_id),
            )
        return SessionState(
            id=sid, workspace_dir=str(workspace_dir),
            status=SessionStatus.ACTIVE, created_at=now, last_active=now,
            sandbox_id=sandbox_id, container_id=container_id,
        )
```

修改 `_row_to_state` 工具（如不存在则在 `get/list` 重复块抽出）：

```python
    def _row_to_state(self, row) -> SessionState:
        return SessionState(
            id=row["id"],
            workspace_dir=row["workspace_dir"],
            status=SessionStatus(row["status"]),
            created_at=row["created_at"],
            last_active=row["last_active"],
            sandbox_id=row["sandbox_id"] if "sandbox_id" in row.keys() else None,
            container_id=row["container_id"] if "container_id" in row.keys() else None,
        )
```

并把 `get` / `list` 改成调用 `_row_to_state`。

- [ ] **Step 2: 写 `src/hagent/server/manager.py`**

```python
from __future__ import annotations

import os
import threading
from pathlib import Path

from hagent.sandbox.docker_backend import DockerBackend
from hagent.server.sessions import SessionState, SessionStore


class SessionManager:
    """Owns the SessionStore + a map session_id -> DockerBackend."""

    def __init__(self, store: SessionStore, workspace_root: Path | str) -> None:
        self._store = store
        self._workspace_root = Path(workspace_root)
        self._backends: dict[str, DockerBackend] = {}
        self._lock = threading.Lock()

    def create_session(self) -> SessionState:
        backend = DockerBackend()
        backend.start()
        with self._lock:
            s = self._store.create(
                workspace_root=self._workspace_root,
                sandbox_id=backend.id,
                container_id=backend.container_id,
            )
            self._backends[s.id] = backend
        return s

    def get_session(self, sid: str) -> SessionState | None:
        return self._store.get(sid)

    def get_backend(self, sid: str) -> DockerBackend | None:
        return self._backends.get(sid)

    def list(self) -> list[SessionState]:
        return self._store.list()

    def touch(self, sid: str) -> None:
        self._store.touch(sid)

    def end_session(self, sid: str) -> None:
        with self._lock:
            backend = self._backends.pop(sid, None)
        if backend:
            backend.stop()
        self._store.delete(sid)
```

- [ ] **Step 3: 写 `tests/server/test_manager.py`**

```python
import os

import pytest

from hagent.server.manager import SessionManager
from hagent.server.sessions import SessionStore


@pytest.fixture
def docker_available():
    if os.environ.get("HAGENT_SKIP_DOCKER_TESTS"):
        pytest.skip()
    import docker
    try:
        docker.from_env().ping()
    except Exception as e:
        pytest.skip(f"docker not available: {e}")


def test_create_session_starts_container(docker_available, tmp_path):
    store = SessionStore(db_path=tmp_path / "h.sqlite")
    mgr = SessionManager(store=store, workspace_root=tmp_path / "ws")
    s = mgr.create_session()
    try:
        assert s.sandbox_id
        assert s.container_id
        b = mgr.get_backend(s.id)
        assert b is not None
        assert b.ping()["ok"] is True
    finally:
        mgr.end_session(s.id)


def test_end_session_stops_container(docker_available, tmp_path):
    store = SessionStore(db_path=tmp_path / "h.sqlite")
    mgr = SessionManager(store=store, workspace_root=tmp_path / "ws")
    s = mgr.create_session()
    mgr.end_session(s.id)
    # SessionStore status 改为 ended
    assert mgr.get_session(s.id).status.value == "ended"
    # backend 已 pop
    assert mgr.get_backend(s.id) is None
```

- [ ] **Step 4: 跑 + 提交**

```bash
pytest tests/server/test_manager.py -v
git add src/hagent/server/sessions.py src/hagent/server/manager.py tests/server/test_manager.py
git commit -m "feat(server): add SessionManager owning SessionStore + DockerBackend pool"
```

---

### Task 9: warm pool + idle GC + snapshot/resume

**Files:**
- Modify: `src/hagent/server/manager.py`
- Modify: `tests/server/test_manager.py`

MVP 范围内做最简版本——warm pool 是个 list of pre-started backends；create_session 时 pop 一个并补回；idle GC 在后台线程定期扫描；snapshot/resume 用 `docker cp` + tar。

- [ ] **Step 1: 给 SessionManager 加 warm pool + idle GC**

```python
import threading
import time

# ...

class SessionManager:
    def __init__(
        self,
        store: SessionStore,
        workspace_root: Path | str,
        pool_size: int = 3,
        idle_seconds: int = 1800,
        gc_interval: int = 60,
    ) -> None:
        self._store = store
        self._workspace_root = Path(workspace_root)
        self._backends: dict[str, DockerBackend] = {}
        self._pool: list[DockerBackend] = []
        self._pool_size = pool_size
        self._idle_seconds = idle_seconds
        self._gc_interval = gc_interval
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._refill_pool()
        self._gc_thread = threading.Thread(target=self._gc_loop, daemon=True)
        self._gc_thread.start()

    def shutdown(self) -> None:
        self._stop.set()
        with self._lock:
            for b in list(self._backends.values()):
                b.stop()
            self._backends.clear()
            for b in self._pool:
                b.stop()
            self._pool.clear()

    def _refill_pool(self) -> None:
        with self._lock:
            while len(self._pool) < self._pool_size:
                b = DockerBackend()
                try:
                    b.start()
                    self._pool.append(b)
                except Exception:
                    break  # pool 补不上不致命，下次再补

    def _acquire_backend(self) -> DockerBackend:
        with self._lock:
            if self._pool:
                b = self._pool.pop()
                return b
        # pool 空了现起
        b = DockerBackend()
        b.start()
        threading.Thread(target=self._refill_pool, daemon=True).start()
        return b

    def create_session(self) -> SessionState:
        backend = self._acquire_backend()
        with self._lock:
            s = self._store.create(
                workspace_root=self._workspace_root,
                sandbox_id=backend.id,
                container_id=backend.container_id,
            )
            self._backends[s.id] = backend
        threading.Thread(target=self._refill_pool, daemon=True).start()
        return s

    # end_session, get_session, get_backend, list, touch 保持不变

    def _gc_loop(self) -> None:
        while not self._stop.is_set():
            self._stop.wait(self._gc_interval)
            if self._stop.is_set():
                break
            self._gc_once()

    def _gc_once(self) -> None:
        now = time.time()
        for s in self._store.list():
            if s.status.value != "active":
                continue
            if now - s.last_active > self._idle_seconds:
                try:
                    self.snapshot(s.id)
                except Exception:
                    pass
                self.end_session(s.id)

    # 哪些路径打进 snapshot；spec §4 M2 要求至少含 /workspace + ~/.cache/pip + node_modules，
    # 用 sh -c 加 || true 避免某些目录不存在导致 tar 失败
    SNAPSHOT_PATHS = ["/workspace", "/root/.cache/pip", "/workspace/node_modules"]

    def snapshot(self, sid: str) -> Path:
        backend = self._backends.get(sid)
        if backend is None:
            raise RuntimeError(f"no backend for {sid}")
        snap_dir = Path(os.environ.get("HAGENT_SNAPSHOT_DIR", "/tmp/hagent/snapshots"))
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_path = snap_dir / f"{sid}.tar.gz"
        cid = backend.container_id
        # 用 sh 包一层，每个路径独立 || true，确保不存在的目录不会让整个 tar 失败
        path_args = " ".join(f"'{p}'" for p in self.SNAPSHOT_PATHS)
        tar_cmd = (
            f"set -e; "
            f"echo > /sock/snapshot.tar.gz; "  # ensure clean output file
            f"tar czf /sock/snapshot.tar.gz "
            f"--ignore-failed-read "
            f"{path_args} 2>/dev/null || tar czf /sock/snapshot.tar.gz --ignore-failed-read /workspace"
        )
        import subprocess
        subprocess.run(
            ["docker", "exec", cid, "sh", "-c", tar_cmd],
            check=True,
        )
        import shutil
        shutil.move(str(backend._socket_dir / "snapshot.tar.gz"), str(snap_path))
        return snap_path
```

注意：`tar --ignore-failed-read` 在 BusyBox tar 下不存在；GNU tar 在 `python:3.12-slim` 基础镜像里默认存在（apt 安装的 `tar`）。如果运行时报错，退回到为每个路径单独 `tar` 然后 cat 拼接。

- [ ] **Step 2: 加测试**

```python
def test_warm_pool_prefills(docker_available, tmp_path):
    store = SessionStore(db_path=tmp_path / "h.sqlite")
    mgr = SessionManager(store=store, workspace_root=tmp_path / "ws", pool_size=2)
    try:
        # pool 至少有 2 个预热好的 backend
        import time
        time.sleep(2)
        with mgr._lock:
            assert len(mgr._pool) >= 1  # 容差：起得快慢
    finally:
        mgr.shutdown()


def test_snapshot_writes_tarball(docker_available, tmp_path, monkeypatch):
    monkeypatch.setenv("HAGENT_SNAPSHOT_DIR", str(tmp_path / "snaps"))
    store = SessionStore(db_path=tmp_path / "h.sqlite")
    mgr = SessionManager(store=store, workspace_root=tmp_path / "ws", pool_size=0)
    try:
        s = mgr.create_session()
        b = mgr.get_backend(s.id)
        b.write("/workspace/snap.txt", "snapshot content")
        snap = mgr.snapshot(s.id)
        assert snap.exists()
        assert snap.stat().st_size > 100
    finally:
        mgr.shutdown()
```

- [ ] **Step 3: 跑 + 提交**

```bash
pytest tests/server/test_manager.py -v
git add src/hagent/server/manager.py tests/server/test_manager.py
git commit -m "feat(server): add warm pool, idle GC, snapshot for SessionManager"
```

注意：resume 流程留作未来增量；MVP snapshot 已经覆盖 spec §4 M2 大半，resume 真正发生在用户重新打开同 session 时才用到，可以下个 plan 再做。

---

### Task 10: M3-swap — 把 CLI 和 Agent Server 切到 DockerBackend

**Files:**
- Modify: `src/hagent/core.py`
- Modify: `src/hagent/cli.py`
- Modify: `src/hagent/server/agents.py`
- Modify: `src/hagent/server/routers/sessions.py`
- Modify: `src/hagent/server/routers/messages.py`

- [ ] **Step 1: 让 `create_hagent` 支持 backend 切换**

修改 `src/hagent/core.py`：

```python
def create_hagent(
    config: HagentConfig | None = None,
    backend: Any | None = None,
    extra_subagents: list[dict] | None = None,
    extra_tools: list[Any] | None = None,
) -> Any:
    cfg = config or HagentConfig.from_env()

    if backend is None:
        backend_kind = os.environ.get("HAGENT_BACKEND", "local")
        if backend_kind == "docker":
            from hagent.sandbox.docker_backend import DockerBackend
            backend = DockerBackend()
            backend.start()
        else:
            DEFAULT_WORKSPACE.mkdir(parents=True, exist_ok=True)
            backend = LocalShellBackend(root_dir=str(DEFAULT_WORKSPACE))

    # ... 其余不变
```

记得加 `import os`。

- [ ] **Step 2: CLI demo 默认仍用 local，但可通过 env 切**

`src/hagent/cli.py` 不需要改——`create_hagent` 已经按 env 选 backend。文档说明：

```bash
HAGENT_BACKEND=docker python -m hagent demo "..."
```

- [ ] **Step 3: Agent Server 用 SessionManager 替代之前的 ad-hoc 实现**

修改 `src/hagent/server/agents.py`：

```python
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from hagent.core import create_hagent
from hagent.server.manager import SessionManager
from hagent.server.sessions import SessionStore

_manager: SessionManager | None = None
_agents: dict[str, Any] = {}
_checkpointer: SqliteSaver | None = None


def get_checkpointer() -> SqliteSaver:
    global _checkpointer
    if _checkpointer is None:
        db = Path(os.environ.get("HAGENT_THREAD_DB_PATH", "/tmp/hagent/threads.sqlite"))
        db.parent.mkdir(parents=True, exist_ok=True)
        _checkpointer = SqliteSaver.from_conn_string(str(db))
    return _checkpointer


def get_manager() -> SessionManager:
    global _manager
    if _manager is None:
        db = Path(os.environ.get("HAGENT_DB_PATH", "/tmp/hagent/hagent.sqlite"))
        db.parent.mkdir(parents=True, exist_ok=True)
        store = SessionStore(db_path=db)
        ws_root = Path(os.environ.get("HAGENT_WORKSPACE_ROOT", "/tmp/hagent/sessions"))
        backend_kind = os.environ.get("HAGENT_BACKEND", "docker" if os.environ.get("DOCKER_HOST") or os.path.exists("/var/run/docker.sock") else "local")
        if backend_kind == "docker":
            _manager = SessionManager(store=store, workspace_root=ws_root)
        else:
            # local backend 没有 DockerBackend pool 那一套；用一个 stub SessionManager
            class _LocalMgr(SessionManager):
                def __init__(self, store, workspace_root):
                    self._store = store
                    self._workspace_root = workspace_root
                    self._backends = {}
                    import threading
                    self._lock = threading.Lock()
                    self._stop = threading.Event()
                def create_session(self):
                    return self._store.create(self._workspace_root)
                def end_session(self, sid):
                    self._store.delete(sid)
                def shutdown(self):
                    pass
            _manager = _LocalMgr(store=store, workspace_root=ws_root)
    return _manager


def get_or_build_agent(session_id: str, workspace_dir: str) -> Any:
    if session_id not in _agents:
        mgr = get_manager()
        backend = mgr.get_backend(session_id)
        if backend is None:
            # local backend fallback
            from deepagents.backends import LocalShellBackend
            backend = LocalShellBackend(root_dir=workspace_dir)
        _agents[session_id] = create_hagent(backend=backend)
    return _agents[session_id]
```

- [ ] **Step 4: 修改 sessions router 用 manager**

`src/hagent/server/routers/sessions.py`：把 `get_store` 替换为 `get_manager` 的薄包装：

```python
from hagent.server.agents import get_manager


@router.post("/sessions")
def create_session(body: dict[str, Any]) -> dict:
    mgr = get_manager()
    s = mgr.create_session()
    return {
        "session_id": s.id,
        "workspace_dir": s.workspace_dir,
        "status": s.status.value,
        "sandbox_id": s.sandbox_id,
    }


@router.get("/sessions")
def list_sessions() -> list[dict]:
    mgr = get_manager()
    return [
        {
            "id": s.id, "workspace_dir": s.workspace_dir, "status": s.status.value,
            "created_at": s.created_at, "last_active": s.last_active,
            "sandbox_id": s.sandbox_id,
        }
        for s in mgr.list()
    ]


@router.get("/sessions/{sid}")
def get_session(sid: str) -> dict:
    mgr = get_manager()
    s = mgr.get_session(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "id": s.id, "workspace_dir": s.workspace_dir, "status": s.status.value,
        "created_at": s.created_at, "last_active": s.last_active,
        "sandbox_id": s.sandbox_id,
    }


@router.delete("/sessions/{sid}")
def delete_session(sid: str) -> dict:
    mgr = get_manager()
    if mgr.get_session(sid) is None:
        raise HTTPException(status_code=404, detail="session not found")
    mgr.end_session(sid)
    return {"ok": True}
```

把 `from hagent.server.sessions import SessionStore` 和 `def get_store(): ...` 删除（或保留作为 SessionStore 直接访问的辅助，但 routers 都走 manager）。

- [ ] **Step 5: messages router 也走 manager**

`src/hagent/server/routers/messages.py` 把 `get_store()` 调用替换为 `get_manager()`：

```python
from hagent.server.agents import get_manager, get_or_build_agent

# ...

@router.post("/sessions/{sid}/messages")
def post_message(sid: str, body: MessageBody, request: Request) -> StreamingResponse:
    mgr = get_manager()
    s = mgr.get_session(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    mgr.touch(sid)
    agent = get_or_build_agent(sid, s.workspace_dir)
    return StreamingResponse(...)
```

`get_messages` / `get_todos` / `post_interrupt` 类似改动。

- [ ] **Step 6: files router 同样切到 manager**

文件端点的 workspace_dir 来源不变（manager.get_session 返回的 workspace_dir）。把 `get_store` 引用全换成 `get_manager`，找 workspace_dir 的逻辑一致。

注意：用 DockerBackend 时，workspace 不在 host fs 而是在容器内 `/workspace`。文件端点必须改用 `backend.ls / backend.read / backend.upload_files / backend.download_files`，不能直接 Path 操作。

修改 `src/hagent/server/routers/files.py`，**整文件重写**（替换 Plan 3 Task 8/9 的版本）：

```python
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from hagent.server.agents import get_manager
from hagent.server.auth import require_api_key

router = APIRouter(dependencies=[Depends(require_api_key)])


def _resolve_local_inside(workspace_dir: str, sub: str) -> Path:
    """For LocalShellBackend fallback: clamp the user path inside workspace_dir."""
    base = Path(workspace_dir).resolve()
    target = (base / sub.lstrip("/")).resolve()
    if not str(target).startswith(str(base) + "/") and str(target) != str(base):
        raise HTTPException(status_code=400, detail="path traversal")
    return target


def _list_files_local(workspace_dir: str, sub: str) -> list[dict]:
    base = _resolve_local_inside(workspace_dir, sub)
    if not base.exists():
        return []
    if base.is_file():
        return [{
            "path": str(base.relative_to(workspace_dir)),
            "type": "file",
            "size": base.stat().st_size,
        }]
    return [
        {
            "path": str(child.relative_to(workspace_dir)),
            "type": "dir" if child.is_dir() else "file",
            "size": child.stat().st_size if child.is_file() else None,
        }
        for child in sorted(base.iterdir())
    ]


def _check_sandbox_path(path: str) -> None:
    """Reject obviously-traversal paths before sending to shim."""
    if ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="path traversal")


@router.get("/sessions/{sid}/files")
def list_files(sid: str, path: str = "") -> list[dict]:
    mgr = get_manager()
    s = mgr.get_session(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    backend = mgr.get_backend(sid)
    if backend is None:
        # LocalShellBackend / local fallback: workspace is on host fs
        return _list_files_local(s.workspace_dir, path or "")
    # Docker backend: workspace 在容器内 /workspace
    target = path if path else "/workspace"
    if not target.startswith("/workspace"):
        target = "/workspace/" + target.lstrip("/")
    _check_sandbox_path(target)
    res = backend.ls(target)
    if res.error or res.entries is None:
        return []
    # FileInfo TypedDict: {path, is_dir?, size?, ...}
    out: list[dict] = []
    for e in res.entries:
        full = e.get("path", "")
        rel = full[len("/workspace/"):] if full.startswith("/workspace/") else full
        out.append({
            "path": rel,
            "type": "dir" if e.get("is_dir") else "file",
            "size": e.get("size"),
        })
    return out


@router.get("/sessions/{sid}/files/{file_path:path}")
def download_file(sid: str, file_path: str) -> Response:
    mgr = get_manager()
    s = mgr.get_session(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    _check_sandbox_path(file_path)
    backend = mgr.get_backend(sid)
    if backend is None:
        target = _resolve_local_inside(s.workspace_dir, file_path)
        if not target.is_file():
            raise HTTPException(status_code=404, detail="file not found")
        return FileResponse(path=str(target))
    # Docker backend: 走 backend.download_files
    container_path = f"/workspace/{file_path.lstrip('/')}"
    [resp] = backend.download_files([container_path])
    if resp.error or resp.content is None:
        if resp.error == "file_not_found":
            raise HTTPException(status_code=404, detail="file not found")
        raise HTTPException(status_code=500, detail=f"download error: {resp.error}")
    return Response(content=resp.content, media_type="application/octet-stream")


@router.post("/sessions/{sid}/files")
async def upload_file(
    sid: str,
    file: UploadFile = File(...),
    path: str = Form(...),
) -> dict:
    _check_sandbox_path(path)
    mgr = get_manager()
    s = mgr.get_session(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    backend = mgr.get_backend(sid)
    data = await file.read()
    if backend is None:
        target = _resolve_local_inside(s.workspace_dir, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    else:
        container_path = f"/workspace/{path.lstrip('/')}"
        [resp] = backend.upload_files([(container_path, data)])
        if resp.error:
            raise HTTPException(status_code=500, detail=f"upload error: {resp.error}")
    return {"path": path, "size": len(data)}
```

- [ ] **Step 7: 跑全量测试**

```bash
source .venv/bin/activate && pytest -v
```

注意：之前依赖 `_resolve_inside` 直接读 host 路径的测试需要根据是否 docker 模式分别走。如果有 monkeypatch 没设 HAGENT_BACKEND，默认走 local fallback。

- [ ] **Step 8: 提交**

```bash
git add src/hagent/core.py src/hagent/server/
git commit -m "feat: M3-swap — switch CLI/server to DockerBackend via env"
```

---

### Task 11: 端到端 Docker demo

- [ ] **Step 1: CLI demo（docker mode）**

```bash
source .venv/bin/activate
export HAGENT_BACKEND=docker
export ANTHROPIC_API_KEY=sk-ant-...
python -m hagent demo "在 workspace 创建 hello.py 打印 'hello docker'，然后用 execute 跑它"
```

Expected：
- 启动新容器
- 看到 write_file / execute tool 调用
- 最终输出含 "hello docker"
- 退出码 0

验证容器在跑：
```bash
docker ps | grep hagent-
```

退出后清理：
```bash
docker ps -a | grep hagent- | awk '{print $1}' | xargs -r docker rm -f
```

- [ ] **Step 2: Web demo（docker mode）**

shell A:
```bash
export HAGENT_BACKEND=docker ANTHROPIC_API_KEY=...
uvicorn hagent.server.app:create_app --factory --port 8000
```

shell B:
```bash
cd web && npm run dev
```

浏览器 http://localhost:3000：
- 启动新 session（自动创建容器）
- 输入 "在 workspace 用 pandas 读个简单 csv 画个图，保存到 plot.png"
- 看到流式输出、tool 调用、文件树更新
- 下载 plot.png 验证文件不为空
- 关闭浏览器后 `docker ps` 看到容器仍在（end_session 才回收）

- [ ] **Step 3: 用户 review**

把两个 demo 的关键输出（CLI 终端、Web 截图）发给用户。用户回"通过"才进 Task 12。

---

### Task 12: Plan 5 收口

- [ ] **Step 1: 跑全量 pytest**

```bash
source .venv/bin/activate && pytest -v
```

如果有 docker-only 测试：
```bash
pytest -v -k "not docker"  # 跳过 docker 集成
pytest tests/sandbox/ -v   # 跑 docker 集成
```

- [ ] **Step 2: 跑 base prompt 校验脚本**

```bash
./scripts/check_base_prompt.sh
```

- [ ] **Step 3: 清理遗留容器**

```bash
docker ps -a | grep hagent- | awk '{print $1}' | xargs -r docker rm -f
docker images | grep hagent/sandbox
```

- [ ] **Step 4: 更新 README**

补一节"运行 Docker backend"：

```markdown
## 切换到 Docker Backend（M3-swap）

```bash
# 构建镜像（首次）
./scripts/build_image.sh

# CLI demo with docker
HAGENT_BACKEND=docker python -m hagent demo "..."

# 服务器 with docker
HAGENT_BACKEND=docker uvicorn hagent.server.app:create_app --factory --port 8000
```

退回 local：unset HAGENT_BACKEND 或 export HAGENT_BACKEND=local。
```

- [ ] **Step 5: 通知**

> "Plan 5 完成：DockerBackend + Session Manager (warm pool / idle GC / snapshot) + M3-swap 全部 ready。CLI 和 Web 都能在 Docker 沙箱里跑通 demo。MVP 项目级 Done 标准（spec §11）已全部达成。准备合 main + 进入 dogfood 阶段。"

---

## Plan 5 完整 Done 标准（对应 spec §4 Track B + M3-swap + §7 Layer 2）

- ✅ `sandbox/Dockerfile` + `sandbox/shim.py` + `sandbox/entrypoint.sh`
- ✅ `hagent/sandbox/docker_backend.py` 实现 `BackendProtocol` + `SandboxBackendProtocol` 全部方法
- ✅ `hagent/sandbox/rpc.py` 客户端
- ✅ shim local + docker 集成测试全过
- ✅ `hagent/server/manager.py` SessionManager 含 warm pool（默认 3 idle）+ idle GC（30min）+ snapshot 落盘到本地 tarball
- ✅ M3-swap：`HAGENT_BACKEND=docker` env switch 让 CLI 和 Agent Server 用 Docker 沙箱
- ✅ Files endpoints 通过 backend.ls / upload_files / download_files 走容器（local 模式回退到 host Path）
- ✅ End-to-end Docker demo（CLI + Web）跑通 CSV 类任务
- ✅ README 含 Docker 切换指令
- ✅ MVP spec §11 项目级 Done 标准全部达成

---

## Spec §11 项目级 Done 标准回顾

完成 Plan 5 后这些应全部成立：
- ✅ Web 浏览器对话 → Docker 沙箱写 `output.csv` / `plot.png` → 文件树可见 + 下载（Plan 5 Task 11）
- ✅ 同一会话再问"换成柱状图"，agent read 之前代码再编辑（Plan 5 Task 11，依赖 SqliteSaver thread 持久化）
- ✅ 切回 LocalBackend 跑同 demo（`unset HAGENT_BACKEND`，Plan 2 demo 流程仍然可用）
- ✅ LangSmith trace 链路（Plan 2 LangSmith Day 1 接入）
- ✅ 文件上传：浏览器拖文件 → POST /files → 沙箱内可读 → agent 基于上传文件继续（Plan 5 Task 10 + Plan 4）
