from __future__ import annotations

import io
import json
import os
import shlex
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from hagent.server.auth import require_api_key
from hagent.server.routers.sessions import get_session_manager, get_store

router = APIRouter(dependencies=[Depends(require_api_key)])

# 在容器内列目录的脚本：输出与 host 分支同构的 JSON（path 相对 workspace_dir）。
# 依赖容器里有 python3（skill 本身也用 python3 跑解析脚本，故必然存在）。
_LIST_SCRIPT = (
    "import os,sys,json\n"
    "base=sys.argv[1]; target=sys.argv[2]\n"
    "if not os.path.exists(target): print('[]'); sys.exit(0)\n"
    "if os.path.isfile(target):\n"
    "    print(json.dumps([{'path':os.path.relpath(target,base),'type':'file','size':os.path.getsize(target)}],ensure_ascii=False)); sys.exit(0)\n"
    "out=[]\n"
    "for n in sorted(os.listdir(target)):\n"
    "    p=os.path.join(target,n); f=os.path.isfile(p)\n"
    "    out.append({'path':os.path.relpath(p,base),'type':'file' if f else 'dir','size':os.path.getsize(p) if f else None})\n"
    "print(json.dumps(out,ensure_ascii=False))\n"
)


def _resolve_inside(workspace_dir: str, sub: str) -> Path:
    base = Path(workspace_dir).resolve()
    target = (base / sub.lstrip("/")).resolve()
    if not target.is_relative_to(base):
        raise HTTPException(status_code=400, detail="path traversal")
    return target


def _resolve_sandbox_path(workspace_dir: str, path: str) -> str:
    """Compute the absolute sandbox-internal path and reject traversal.

    Raises HTTPException(400) when the resulting path escapes workspace_dir or
    contains '..' segments. Accepts both absolute (under workspace_dir) and
    relative inputs.
    """
    from pathlib import PurePosixPath

    base = PurePosixPath(workspace_dir or "/").as_posix().rstrip("/") or "/"
    raw = path if path.startswith("/") else f"{base}/{path.lstrip('/')}"
    pp = PurePosixPath(raw)
    if any(part == ".." for part in pp.parts):
        raise HTTPException(status_code=400, detail="path traversal not allowed")
    resolved = pp.as_posix()
    if not (resolved == base or resolved.startswith(base.rstrip("/") + "/")):
        raise HTTPException(status_code=400, detail="path outside sandbox workspace")
    return resolved


def _get_session(sid: str):
    """Return SessionState, preferring manager.store; fallback to get_store()."""
    try:
        mgr = get_session_manager()
        return mgr, mgr.store.get(sid)
    except RuntimeError:
        return None, get_store().get(sid)


def _host_workspace(mgr, session) -> str:
    if mgr is not None:
        return mgr.workspace_dir(session.id)
    root = Path(os.environ.get("HAGENT_WORKSPACE_ROOT", "/tmp/hagent/workspaces"))
    return str(root / "projects" / session.project_id / "workspace")


@router.get("/sessions/{sid}/files")
def list_files(sid: str, path: str = "") -> list[dict]:
    mgr, s = _get_session(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")

    # sandbox 模式：在容器内列目录（host workspace_dir 看不到容器内生成的文件）。
    sandbox = mgr.get_sandbox(sid) if mgr is not None else None
    if sandbox is not None:
        target = _resolve_sandbox_path(sandbox.workspace_dir, path)
        cmd = f"python3 -c {shlex.quote(_LIST_SCRIPT)} {shlex.quote(sandbox.workspace_dir)} {shlex.quote(target)}"
        resp = sandbox.execute(cmd)
        if resp.exit_code != 0:
            raise HTTPException(status_code=500, detail=f"sandbox list failed: {resp.output}")
        try:
            return json.loads(resp.output)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail=f"sandbox list parse error: {resp.output[:200]}")

    workspace_dir = _host_workspace(mgr, s)
    base = _resolve_inside(workspace_dir, path)
    if not base.exists():
        return []
    if base.is_file():
        return [{"path": str(base.relative_to(workspace_dir)), "type": "file", "size": base.stat().st_size}]
    return [
        {
            "path": str(child.relative_to(workspace_dir)),
            "type": "dir" if child.is_dir() else "file",
            "size": child.stat().st_size if child.is_file() else None,
        }
        for child in sorted(base.iterdir())
        if child.name != ".git"
    ]


@router.get("/sessions/{sid}/files/{file_path:path}")
def download_file(sid: str, file_path: str):
    mgr, s = _get_session(sid)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")

    sandbox = mgr.get_sandbox(sid) if mgr is not None else None
    if sandbox is not None:
        target = _resolve_sandbox_path(sandbox.workspace_dir, file_path)
        resps = sandbox.download_files([target])
        if not resps or resps[0].error or resps[0].content is None:
            raise HTTPException(status_code=404, detail="file not found")
        return StreamingResponse(io.BytesIO(resps[0].content), media_type="application/octet-stream")

    target = _resolve_inside(_host_workspace(mgr, s), file_path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path=str(target))


@router.post("/sessions/{sid}/files")
async def upload_file(sid: str) -> dict:
    # 票6:上传归属 project(spec §4.4),session 级上传路径废弃。
    raise HTTPException(
        status_code=410,
        detail="session 级上传已废弃,请改用 POST /projects/{pid}/files",
    )
