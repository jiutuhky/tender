from __future__ import annotations

import argparse

from hagent import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hagent", description="Hagent CLI")
    parser.add_argument("--version", action="version", version=f"hagent {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    demo = subparsers.add_parser("demo", help="跑一个端到端 demo")
    demo.add_argument("message", help="给 agent 的用户消息")
    demo.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="可选 recursion_limit；默认使用 deepagents 自带配置",
    )
    demo.add_argument("--skill", default=None, help="启动时请求 agent 调用指定 skill")
    demo.add_argument("--skill-args", default=None, help="传给 --skill 的参数")
    demo.add_argument(
        "--sandbox",
        choices=["none", "docker", "daytona", "smolvm"],
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


def _build_skill_message(skill: str, args: str | None) -> str:
    normalized = skill.strip().lstrip("/")
    if args:
        return f'Use the `Skill` tool with skill: "{normalized}" and args: "{args}".'
    return f'Use the `Skill` tool with skill: "{normalized}".'


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
    # 延迟 import：避免 --help 也要加载完整的 langchain 栈
    from hagent.core import create_hagent
    from hagent.mcp_tools import prose_mcp_disabled, prose_stdio_connection

    # prose MCP 工具面（票 04）：CLI host 模式 stdio 拉起同一 FastMCP 对象，
    # 子进程与宿主共享 SQLite（WAL）；sandbox 模式下工具仍在宿主执行。
    mcp_connection = (
        None if prose_mcp_disabled() else prose_stdio_connection(actor_ref="cli-demo")
    )
    agent = create_hagent(mcp_connection=mcp_connection)
    if skill:
        message = f"{_build_skill_message(skill, skill_args)}\n\nUser request: {message}"
    print(f"[hagent] message: {message}")
    if max_steps is None:
        print("[hagent] running (max_steps=deepagents default)…")
        final_state = agent.invoke({"messages": [{"role": "user", "content": message}]})
    else:
        print(f"[hagent] running (max_steps={max_steps})…")
        final_state = agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config={"recursion_limit": max_steps},
        )
    final_msg = final_state["messages"][-1]
    content = getattr(final_msg, "content", final_msg)
    print(f"\n[hagent] final answer:\n{content}")
    return 0


def _sandbox_ls() -> int:
    print(f"{'CID':<26} {'KIND':<8} {'IMAGE/STATE':<24} {'NAME/PID'}")
    ok = False
    # docker 容器
    try:
        import docker

        client = docker.from_env()
        for c in client.containers.list(filters={"label": "hagent.kind=docker"}):
            image = c.image.tags[0] if c.image.tags else c.image.id[:12]
            print(f"{c.short_id:<26} docker   {image:<24} {c.name}")
        ok = True
    except Exception as exc:  # noqa: BLE001
        print(f"[hagent sandbox] docker 不可用: {exc}")
    # smolvm microVM(hagent- 前缀即本项目的对账键)
    try:
        from smolvm import SmolVMManager

        for vm in SmolVMManager().list_vms():
            if not vm.vm_id.startswith("hagent-"):
                continue
            print(f"{vm.vm_id:<26} smolvm   {vm.status.value:<24} {vm.pid or '-'}")
        ok = True
    except Exception as exc:  # noqa: BLE001
        print(f"[hagent sandbox] smolvm 不可用: {exc}")
    return 0 if ok else 1


def _normalize_smolvm_id(sandbox_id: str) -> str | None:
    """smolvm 对象识别:vm_id(hagent-*)或 sandbox 逻辑 id(smolvm-hagent-*)。"""
    vm_id = sandbox_id.removeprefix("smolvm-")
    return vm_id if vm_id.startswith("hagent-") else None


def _smolvm_stop(vm_id: str, *, from_id=None) -> int:
    """stop → delete → close;stop 失败仍 delete——只有 delete 释放租约(F3)。"""
    from contextlib import suppress

    if from_id is None:
        from smolvm import SmolVM

        from_id = SmolVM.from_id
    try:
        vm = from_id(vm_id)
    except Exception as exc:  # noqa: BLE001
        print(f"[hagent sandbox] not found: {vm_id} ({exc})")
        return 1
    with suppress(Exception):
        vm.stop()
    try:
        vm.delete()
    finally:
        with suppress(Exception):
            vm.close()
    print(f"[hagent sandbox] stopped {vm_id}")
    return 0


def _smolvm_logs(vm_id: str, *, manager_factory=None) -> int:
    """读 SDK data_dir/{vm_id}.log(VM 运行日志,审计三流之一)。"""
    from pathlib import Path

    if manager_factory is None:
        from smolvm import SmolVMManager

        manager_factory = SmolVMManager
    manager = manager_factory()
    try:
        log_path = Path(manager.data_dir) / f"{vm_id}.log"
        if not log_path.is_file():
            print(f"[hagent sandbox] no log for {vm_id}: {log_path}")
            return 1
        lines = log_path.read_text(errors="replace").splitlines()
        print("\n".join(lines[-200:]))
        return 0
    finally:
        close = getattr(manager, "close", None)
        if callable(close):
            close()


def _sandbox_stop(sandbox_id: str) -> int:
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
        return run_demo(args.message, args.max_steps, args.skill, args.skill_args, sandbox=args.sandbox)
    if args.command == "sandbox":
        if args.sandbox_command == "ls":
            return _sandbox_ls()
        if args.sandbox_command == "stop":
            vm_id = _normalize_smolvm_id(args.sandbox_id)
            if vm_id is not None:
                return _smolvm_stop(vm_id)
            return _sandbox_stop(args.sandbox_id)
        if args.sandbox_command == "logs":
            vm_id = _normalize_smolvm_id(args.sandbox_id)
            if vm_id is not None:
                return _smolvm_logs(vm_id)
            return _sandbox_logs(args.sandbox_id)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
