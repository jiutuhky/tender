from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent as _create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import SandboxBackendProtocol
from deepagents.profiles import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    ProviderProfile,
    register_harness_profile,
    register_provider_profile,
)
from hagent.bash_tool import BashRuntime, create_bash_tool
from hagent.config import (
    DEFAULT_ANTHROPIC_COMPAT_MAX_TOKENS,
    HagentConfig,
    render_base_prompt,
)
from hagent.file_tools import create_claude_file_tools
from hagent.grep_tool import create_grep_tools
from hagent.hooks import HookContext, load_hook_settings
from hagent.hooks.middleware import HagentHooksMiddleware
from hagent.hooks.runner import HookRunner
from hagent.mcp_tools import load_prose_mcp_tools
from hagent.permissions import permissions_for_workspace
from hagent.sandbox import HagentSandboxProtocol, SandboxKind
from hagent.sanitize import sanitize_anthropic_thinking_blocks_middleware
from hagent.sandbox.docker.sandbox import HagentDockerSandbox
from hagent.tool_call_repair import repair_invalid_tool_calls_middleware
from hagent.sandbox.providers.file import SandboxFileTransport
from hagent.sandbox.providers.shell import SandboxShellProvider
from hagent.skills import (
    SkillMaterializer,
    create_skill_tool,
    load_skills_from_sources,
    resolve_skill_sources,
)
from hagent.skills.middleware import HagentSkillsMiddleware
from hagent.subagents import (
    assemble_subagents,
    build_agent_tool,
    compile_subagents,
    render_agent_tool_description,
)
from hagent.task_tools import TaskStore, create_task_tools

DEFAULT_WORKSPACE = Path("/tmp/hagent/workspace")
DISABLED_DEEPAGENTS_MIDDLEWARE = frozenset({"SummarizationMiddleware"})
DISABLED_DEEPAGENTS_TOOLS = frozenset(
    {
        "execute",
        "read_file",
        "write_file",
        "edit_file",
        "write_todos",
        # deepagents' built-in filesystem search scaffolding. Replaced by hagent's
        # CC-aligned Grep/Glob (hagent.grep_tool); `ls` has no CC-aligned standalone
        # tool, so directory listing falls back to Bash (`ls`), matching CC.
        "grep",
        "glob",
        "ls",
    }
)


def _backend_working_directory(backend: Any) -> Path:
    cwd = getattr(backend, "cwd", None)
    return Path(cwd).resolve() if cwd is not None else DEFAULT_WORKSPACE.resolve()


def _filesystem_backend_for_workspace(workspace: Path) -> FilesystemBackend:
    return FilesystemBackend(root_dir=workspace, virtual_mode=False)


def _backend_for_model_tools(backend: Any) -> Any:
    if isinstance(backend, SandboxBackendProtocol) or hasattr(backend, "execute"):
        return _filesystem_backend_for_workspace(_backend_working_directory(backend))
    return backend


def _safe_id(value: str) -> str:
    """Make a filesystem-safe slug out of a sandbox id (e.g. 'docker-abc123' -> 'docker-abc123')."""
    import re

    return re.sub(r"[^A-Za-z0-9._-]", "_", value)[:64] or "anonymous"


def _anthropic_compatible_max_tokens(config: HagentConfig) -> int | None:
    if config.max_tokens is not None:
        return config.max_tokens

    provider, separator, model_id = config.model.partition(":")
    if (
        separator
        and provider == "anthropic"
        and model_id
        and not model_id.startswith("claude-")
    ):
        return DEFAULT_ANTHROPIC_COMPAT_MAX_TOKENS
    return None


def _register_output_budget_profile(config: HagentConfig) -> None:
    max_tokens = _anthropic_compatible_max_tokens(config)
    if max_tokens is None:
        return
    register_provider_profile(
        config.model,
        ProviderProfile(init_kwargs={"max_tokens": max_tokens}),
    )


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
    hook_runner: HookRunner | None = None,
    mcp_connection: dict[str, Any] | None = None,
) -> Any:
    """Create a Hagent (deep agent) ready for invocation.

    Args:
        config: HagentConfig with model + bash permissions (defaults to env-derived).
        backend: deepagents backend (defaults to FilesystemBackend on /tmp/hagent/workspace).
            Ignored when sandbox is provided.
        extra_subagents: additional SubagentSpec dicts merged on top of built-ins
            and markdown-discovered agents (last wins by name).
        extra_tools: additional langchain tools appended to the main tool pool.
        checkpointer: optional langgraph checkpointer for resumable runs.
        task_list_id: id for the persistent Hagent task store (defaults to env or 'tasklist').
        agents_dirs: override the markdown agent discovery directories.
            Pass [] to skip discovery entirely.
        disable_builtin_agents: when True, skip the three built-in subagents
            (general-purpose / Explore / Plan). If you also pass no extras,
            no Agent tool is registered. If you pass extras but no
            'general-purpose' replacement, create_hagent raises ValueError —
            the Agent tool's default route requires a 'general-purpose' entry.
        sandbox: explicit sandbox instance. When provided, deepagents
            FilesystemPermission is bypassed (container is the trust boundary).
            Overrides config.sandbox_kind.
        hook_runner: per-session HookRunner（server 路径由 hooks_registry 传入，
            保证 once 状态全 session 唯一）。None 且未禁用时自行从
            .hagent/settings.json 加载（CLI/demo 路径）；无任何 hook 配置时
            不注入 middleware（零开销）。
        mcp_connection: prose MCP 工具面连接（langchain-mcp-adapters Connection
            dict）。server 路径传 loopback HTTP，CLI demo 传 stdio（构造函数见
            hagent.mcp_tools）；None 时不注入 MCP 工具。工具永远宿主执行，
            不随 sandbox 切线。

    Returns:
        A compiled deepagents agent with .stream / .invoke / .ainvoke.
    """
    import logging as _logging

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

    # --- Sandbox resolution ---
    sandbox_kind = cfg.sandbox_kind
    if sandbox is None and sandbox_kind is SandboxKind.DOCKER:
        if backend is not None:
            # Caller already wired a backend (typical in the Agent Server path,
            # where SessionManager+SandboxPool own the container lifecycle and
            # hand the sandbox in via `sandbox=` separately). Auto-starting a
            # second container here would leak a sibling sandbox per session
            # and physically separate the LLM-visible workspace from the
            # one the file API speaks to. Skip and warn instead — callers who
            # want sandbox mode must pass `sandbox=` explicitly.
            _logging.getLogger(__name__).warning(
                "create_hagent: sandbox_kind=docker but a non-sandbox backend "
                "was passed; skipping HagentDockerSandbox.start() to avoid "
                "double-spinning a container. Pass sandbox=<instance> "
                "explicitly to opt into sandbox-backed tools."
            )
        else:
            sandbox = HagentDockerSandbox.start()

    # --- Backend / working directory / provider wiring ---
    if sandbox is not None:
        # LLM-visible workspace (paths shown to model, base for file tools):
        llm_workspace = Path(sandbox.workspace_dir)
        # Host-side scratch dir for BashRuntime outputs, TaskStore, subagent assemble:
        sandbox_id = getattr(sandbox, "id", None) or getattr(
            getattr(sandbox, "_container", None), "id", "anonymous"
        )
        host_workspace = DEFAULT_WORKSPACE / f"sandbox-{_safe_id(str(sandbox_id))}"
        host_workspace.mkdir(parents=True, exist_ok=True)

        agent_backend = sandbox
        shell_provider = SandboxShellProvider(sandbox=sandbox, workspace_root=llm_workspace)
        file_transport: Any = SandboxFileTransport(sandbox)
        file_permissions = None
        # working_directory: LLM-facing (prompts / file tools / expand_file_path)
        # runtime_workspace: host-side scratch (BashRuntime outputs, TaskStore DB)
        working_directory = llm_workspace
        runtime_workspace = host_workspace
    else:
        requested_backend = backend or _filesystem_backend_for_workspace(DEFAULT_WORKSPACE.resolve())
        requested_workspace = (
            _backend_working_directory(requested_backend)
            if requested_backend is not None
            else DEFAULT_WORKSPACE.resolve()
        )
        agent_backend = _backend_for_model_tools(requested_backend)
        working_directory = requested_workspace
        runtime_workspace = working_directory  # host mode: same dir
        shell_provider = None
        file_transport = None
        file_permissions = permissions_for_workspace(working_directory)

    skill_registry = load_skills_from_sources(
        resolve_skill_sources(
            project_root=Path.cwd(),
            env_value=cfg.skills_paths,
        )
    )
    # In sandbox mode the model's file/bash tools run inside the container, so a
    # skill's host base_dir (and its references/scripts/assets) is unreachable.
    # Materialize the skill tree into the container and render container paths.
    skill_materializer = SkillMaterializer(sandbox) if sandbox is not None else None
    skill_tool = create_skill_tool(
        skill_registry, session_id=task_list_id, materializer=skill_materializer
    )
    bash_runtime = (
        BashRuntime(runtime_workspace, shell_provider=shell_provider)
        if shell_provider is not None
        else BashRuntime(runtime_workspace)
    )
    bash_tool = create_bash_tool(
        workspace_root=runtime_workspace,
        runtime=bash_runtime,
        permissions=cfg.bash_permissions if sandbox is None else None,
    )
    file_tools = create_claude_file_tools(
        workspace_root=working_directory,  # LLM-facing: expand paths to /workspace/...
        permissions=file_permissions,
        transport=file_transport,
    )
    # CC-aligned Grep/Glob. In sandbox mode they exec `rg`/`python3` inside the
    # container (sandbox is not None, permissions bypassed); in host mode they run
    # in working_directory with file_permissions gating the search path.
    grep_tools = create_grep_tools(
        workspace_root=working_directory,
        sandbox=sandbox,
        permissions=file_permissions,
    )
    task_store = TaskStore(
        runtime_workspace,  # host-side: write SQLite DB to host scratch dir
        task_list_id=task_list_id or os.environ.get("HAGENT_TASK_LIST_ID", "tasklist"),
    )
    task_tools = create_task_tools(task_store)

    # Hagent-native parent tool pool — subagents inherit from this list
    parent_tools: list[Any] = [bash_tool, *file_tools, *grep_tools, *task_tools]
    if skill_registry:
        parent_tools.append(skill_tool)
    parent_tools.extend(list(extra_tools or []))
    # prose MCP 工具面（票 04）：结构化资产的唯一写通道，真 MCP client 加载；
    # 进 parent_tools 使 subagent（extraction worker）继承同一工具面。
    if mcp_connection is not None:
        parent_tools.extend(load_prose_mcp_tools(mcp_connection))

    # --- Hooks（CC hook 机制移植，spec: docs/specs/2026-07-06-hagent-hooks-design.md） ---
    # hook 永远在宿主执行（CC 语义）：sandbox 模式下 cwd 用 host 侧 scratch。
    hooks_session_id = task_list_id or "local"
    hook_ctx = HookContext(
        session_id=hooks_session_id,
        cwd=runtime_workspace,
        project_root=Path.cwd(),
        transcript_path=Path("/tmp/hagent/transcripts") / f"{hooks_session_id}.jsonl",
    )
    if hook_runner is None and not cfg.hooks_disabled:
        hooks_env = dict(os.environ)
        if cfg.hooks_settings_paths:
            hooks_env["HAGENT_HOOKS_SETTINGS_PATHS"] = cfg.hooks_settings_paths
        hook_settings = load_hook_settings(Path.cwd(), env=hooks_env)
        if not hook_settings.empty:
            hook_runner = HookRunner(hook_settings, hook_ctx)
    if hook_runner is not None:
        # agent 型 hook 的只读工具集（Read/Grep/Glob）
        hook_runner.set_agent_tools(
            [
                t
                for t in [*file_tools, *grep_tools]
                if getattr(t, "name", "") in {"Read", "Grep", "Glob"}
            ]
        )

    # Assemble + compile subagents ourselves; register the CC-aligned Agent tool
    specs = assemble_subagents(
        workspace=working_directory,
        # project_root = server 进程 CWD（仓库），与 LLM workspace 分离；让仓库的
        # .hagent/agents/ 被发现（对齐 skills 的 resolve_skill_sources(project_root=Path.cwd())）。
        project_root=Path.cwd(),
        agents_paths=cfg.agents_paths,
        extra_subagents=extra_subagents,
        agents_dirs=agents_dirs,
        # Note: public kwarg is disable_builtin_agents (clearer to callers);
        # internal kwarg is the shorter disable_builtin.
        disable_builtin=disable_builtin_agents,
    )
    agent_tool = None
    if specs:
        if not any(spec["name"] == "general-purpose" for spec in specs):
            raise ValueError(
                "Agent tool requires a 'general-purpose' subagent (the default route). "
                "Either keep built-ins enabled or include a subagent named 'general-purpose' "
                "in extra_subagents."
            )
        runnables = compile_subagents(
            specs,
            parent_model=cfg.model,
            parent_tools=parent_tools,
            skill_registry=skill_registry,
            materializer=skill_materializer,
            hook_runner=hook_runner,
            hook_context=hook_ctx,
        )
        agent_tool = build_agent_tool(
            runnables, render_agent_tool_description(specs), hook_runner=hook_runner
        )

    all_tools = list(parent_tools)
    if agent_tool is not None:
        all_tools.append(agent_tool)

    # repair 放列表尾部：after_model 节点链按 middleware 逆序执行，
    # 它必须先于 hooks 的 Stop 逻辑、紧跟模型响应运行。
    middleware: list[Any] = [
        sanitize_anthropic_thinking_blocks_middleware,
        repair_invalid_tool_calls_middleware,
    ]
    if skill_registry:
        middleware.insert(0, HagentSkillsMiddleware(skill_registry))
    if hook_runner is not None:
        # 头部注入 = 最外层包裹（PreToolUse 先于一切工具逻辑）
        middleware.insert(0, HagentHooksMiddleware(hook_runner))

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
        _logging.getLogger(__name__).info(
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
        ("_hagent_hook_runner", hook_runner),
    ):
        try:
            setattr(agent, attr, value)
        except Exception:
            pass
    return agent
