from __future__ import annotations

import getpass
import importlib.util
import logging
import os
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from hagent.bash_tool.permissions import BashPermissionConfig
from hagent.sandbox.protocol import SandboxKind

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = REPO_ROOT / ".env"
PROMPT_PATH = REPO_ROOT / "prompts" / "hagent_base.zh.md"

DEFAULT_MODEL = "anthropic:claude-sonnet-4-6"
DEFAULT_ANTHROPIC_COMPAT_MAX_TOKENS = 32_000
DEFAULT_BASH_ALLOW_RULES = (
    "Bash(pytest:*)",
    "Bash(python -m pytest:*)",
    "Bash(npm test:*)",
    "Bash(npm run test:*)",
)


def load_env_file() -> None:
    load_dotenv(dotenv_path=ENV_PATH, override=False)


def resolve_sessions_db_path() -> str:
    """sessions / 对象库共用的 SQLite 路径：单一 env 链，server 与 stdio MCP
    子进程都从这里解析，保证跨进程共享同一文件。"""
    return os.environ.get(
        "HAGENT_SESSIONS_DB",
        os.environ.get("HAGENT_DB_PATH", "/tmp/hagent/sessions.db"),
    )


def load_base_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


# Backend class names that indicate sandbox mode. Mirrors CC's
# SandboxManager.isSandboxingEnabled() gate: render-time, dynamic, and
# omitted entirely when the agent is running on the host filesystem.
_SANDBOX_BACKEND_NAMES = frozenset(
    {"HagentDockerSandbox", "HagentDaytonaSandbox", "HagentSmolVMSandbox"}
)


def _sandbox_section(sandbox_type: str, working_directory: str) -> str:
    """Build the sandbox advisory section, or empty string when not sandboxed.

    Modeled on Claude Code's ``getSimpleSandboxSection()`` in
    ``src/tools/BashTool/prompt.ts``:

    * Returns ``''`` when no sandbox is active, so the LLM sees no sandbox
      text at all in host mode (saves tokens, avoids misleading guidance).
    * Mirrors CC's structure (``## Command sandbox`` title, one-line summary,
      ``Filesystem``/``Network`` JSON, bullet items) so Claude-trained behavior
      carries over.
    * Sticks to facts that match Hagent's *actual* sandbox shape: container
      boundary (CC Mode B, policy-locked, no per-call bypass), default-open
      network, no secrets in container, ``/workspace`` as the artifact dir.

    CC items dropped because they conflict with Hagent's design:
    ``dangerouslyDisableSandbox`` SOP (the flag is schema-only here, not
    honored), ``$TMPDIR`` advice (container ``/tmp`` is writable, no $TMPDIR
    convention), and the ``allowUnsandboxedCommands`` Mode A branch.
    """
    if sandbox_type not in _SANDBOX_BACKEND_NAMES:
        return ""
    workspace = working_directory or "/workspace"
    filesystem = (
        '{"write":{"allowOnly":["' + workspace + '"]},'
        '"hostPaths":"not reachable from inside the container"}'
    )
    return (
        "\n\n## Command sandbox\n"
        f"当前 session 的 Bash 命令默认在 sandbox 容器（{sandbox_type}）内运行。"
        "sandbox 控制哪些目录和网络主机可以被命令访问或修改。\n"
        "\n"
        "The sandbox has the following restrictions:\n"
        f"Filesystem: {filesystem}\n"
        'Network: {"allowedHosts":"*"}\n'
        "Secrets: not injected (no ANTHROPIC_API_KEY, AWS_*, SSH_*, etc. inside the container)\n"
        "\n"
        " - All commands MUST run inside the sandbox container — the container "
        "boundary is the only trust boundary, and there is no per-command bypass.\n"
        " - Bash 工具的 `dangerouslyDisableSandbox` 参数仅为 schema 与 Claude Code 对齐而保留，"
        "Hagent **不会**遵循它；每条命令都通过 `docker exec` 路由。\n"
        " - Host paths (e.g. `~/`, `/etc/`, `/Users/...`) are NOT reachable from inside "
        "the container — attempts to read or write them will fail.\n"
        f" - 工作产物写到 `{workspace}/` 下；用户可通过 session 文件 API 下载。\n"
    )


def render_base_prompt(
    *,
    sandbox_type: str,
    working_directory: str,
    is_git_repo: bool,
    shell: str,
    model: str,
) -> str:
    model_provider, _, model_id = model.partition(":")
    values = {
        "sandbox_type": sandbox_type,
        "working_directory": working_directory,
        "is_git_repo": "是" if is_git_repo else "否",
        "platform": platform.platform(),
        "shell": shell,
        "model_provider": model_provider or "unknown",
        "model_id": model_id or model,
        "knowledge_cutoff": os.environ.get("HAGENT_KNOWLEDGE_CUTOFF", "unknown"),
    }
    prompt = load_base_prompt()
    for key, value in values.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", str(value))
    return prompt + _sandbox_section(sandbox_type, working_directory)


# ---------------------------------------------------------------------------
# sandbox 启动预检(spec D5):smolvm → docker → none 降级链
# ---------------------------------------------------------------------------

# server 侧默认 provider;CLI demo 默认仍是 none(开发权宜,与现状一致)
DEFAULT_SERVER_SANDBOX_KIND = "smolvm"


def _probe_kvm() -> str | None:
    if not os.path.exists("/dev/kvm"):
        return "缺 /dev/kvm(内核未启用 KVM);WSL2 参考 docs 固化 wsl.conf"
    if not os.access("/dev/kvm", os.R_OK | os.W_OK):
        return "无 /dev/kvm 读写权限;修复: sudo usermod -aG kvm $USER 后重新登录"
    return None


def _probe_firecracker() -> str | None:
    if shutil.which("firecracker") is None:
        return "缺 firecracker 二进制;修复: smolvm setup"
    return None


def _probe_sudoers() -> str | None:
    path = f"/etc/sudoers.d/smolvm-runtime-{getpass.getuser()}"
    if not os.path.exists(path):
        return f"缺 sudoers 配置 {path};修复: smolvm setup"
    return None


def _probe_smolvm_import() -> str | None:
    if importlib.util.find_spec("smolvm") is None:
        return "smolvm 未安装;修复: pip install smolvm==0.0.25"
    return None


def _probe_docker() -> str | None:
    try:
        import docker

        docker.from_env().ping()
    except Exception as exc:  # noqa: BLE001
        return f"docker daemon 不可达: {exc}"
    return None


def preflight_sandbox_kind(requested: str | None = None) -> SandboxKind:
    """按降级链探测得到实际可用的 sandbox kind。

    smolvm 逐项探测(kvm 读写 / firecracker / sudoers / smolvm 可导入),
    每项失败打印 WARNING 与修复命令;``HAGENT_SANDBOX_REQUIRE`` 命中时
    预检失败直接 RuntimeError(生产强约束,不静默降级)。
    """
    raw = requested or os.environ.get("HAGENT_SANDBOX_KIND") or DEFAULT_SERVER_SANDBOX_KIND
    kind = SandboxKind.from_str(raw)
    require = os.environ.get("HAGENT_SANDBOX_REQUIRE", "").strip().lower()

    if kind is SandboxKind.SMOLVM:
        problems = [
            p
            for p in (
                _probe_kvm(),
                _probe_firecracker(),
                _probe_sudoers(),
                _probe_smolvm_import(),
            )
            if p is not None
        ]
        if problems:
            for problem in problems:
                logger.warning("smolvm 预检未过: %s", problem)
            if require == "smolvm":
                raise RuntimeError(
                    "HAGENT_SANDBOX_REQUIRE=smolvm 但预检失败: " + "; ".join(problems)
                )
            logger.warning("sandbox 降级: smolvm → docker")
            kind = SandboxKind.DOCKER

    if kind is SandboxKind.DOCKER:
        problem = _probe_docker()
        if problem is not None:
            logger.warning("docker 预检未过: %s", problem)
            if require == "docker":
                raise RuntimeError(f"HAGENT_SANDBOX_REQUIRE=docker 但预检失败: {problem}")
            logger.warning("sandbox 降级: docker → none")
            kind = SandboxKind.NONE

    return kind


def _positive_int_from_env(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    value = int(raw)
    if value <= 0:
        msg = f"{name} must be a positive integer"
        raise ValueError(msg)
    return value


@dataclass(frozen=True)
class HagentConfig:
    model: str
    langsmith_tracing: bool
    bash_permissions: BashPermissionConfig = field(
        default_factory=lambda: BashPermissionConfig(allow_rules=DEFAULT_BASH_ALLOW_RULES)
    )
    max_tokens: int | None = None
    skills_paths: str | None = None
    agents_paths: str | None = None
    sandbox_kind: SandboxKind = SandboxKind.NONE
    hooks_settings_paths: str | None = None
    hooks_disabled: bool = False

    @classmethod
    def from_env(cls) -> "HagentConfig":
        return cls(
            model=os.environ.get("HAGENT_MODEL", DEFAULT_MODEL),
            langsmith_tracing=os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true",
            max_tokens=_positive_int_from_env("HAGENT_MAX_TOKENS"),
            skills_paths=os.environ.get("HAGENT_SKILLS_PATHS") or None,
            agents_paths=os.environ.get("HAGENT_AGENTS_PATHS") or None,
            sandbox_kind=SandboxKind.from_str(os.environ.get("HAGENT_SANDBOX_KIND", "none")),
            hooks_settings_paths=os.environ.get("HAGENT_HOOKS_SETTINGS_PATHS") or None,
            hooks_disabled=os.environ.get("HAGENT_HOOKS_DISABLED", "").strip().lower()
            in {"1", "true", "yes", "on"},
        )
