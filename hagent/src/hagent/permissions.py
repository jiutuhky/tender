from __future__ import annotations

from pathlib import Path

from deepagents import FilesystemPermission

DEFAULT_PERMISSIONS: list[FilesystemPermission] = [
    FilesystemPermission(
        operations=["write"],
        paths=["/etc/**", "/usr/**", "/var/**", "/root/**", "/home/**"],
        mode="deny",
    ),
    FilesystemPermission(
        operations=["read", "write"],
        paths=["/workspace/**", "/tmp/hagent/**"],
        mode="allow",
    ),
]


def permissions_for_workspace(workspace_root: str | Path) -> list[FilesystemPermission]:
    workspace = str(Path(workspace_root).resolve())
    return [
        FilesystemPermission(
            operations=["read", "write"],
            paths=[workspace, f"{workspace}/**"],
            mode="allow",
        ),
        *DEFAULT_PERMISSIONS,
    ]
