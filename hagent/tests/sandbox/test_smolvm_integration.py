"""Task A12 — L3 集成(真 Firecracker):全链 + 孤儿治理端到端。

需要:KVM 可读写、firecracker、sudoers、docker(镜像烘焙)。
HAGENT_TEST_SMOLVM=1 开启;首跑会构建 boot image(分钟级)。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.smolvm


@pytest.fixture
def sb():
    from hagent.sandbox.smolvm.sandbox import HagentSmolVMSandbox

    sandbox = HagentSmolVMSandbox.start(project_id="itestchain")
    yield sandbox
    sandbox.close()


class NoopReconciler:
    def plan(self):
        return []

    def apply(self, _action):
        return None

    def reap_errors(self):
        return None


def test_full_chain_exec_files_timeout_pause_close(sb):
    # —— exec:python3 探针 + workdir 语义 ——
    resp = sb.execute("python3 --version")
    assert resp.exit_code == 0
    assert "Python 3." in resp.output

    resp = sb.execute("pwd")
    assert resp.output == "/workspace\n", "命令必须在 /workspace 下执行(docker 对齐)"

    resp = sb.execute("echo $HOME-$LANG")
    assert resp.output == "/workspace-C.UTF-8\n", "safe env 必须注入(docker 对齐)"

    # —— upload → 沙箱内回读 → download 往返 ——
    payload = "你好 smolvm\n".encode("utf-8")
    up = sb.upload_files([("/workspace/sub/hello.txt", payload)])
    assert up[0].error is None, f"upload 失败: {up[0].error}"
    resp = sb.execute("cat /workspace/sub/hello.txt")
    assert resp.exit_code == 0
    assert resp.output == "你好 smolvm\n"

    down = sb.download_files(["/workspace/sub/hello.txt", "/workspace/nope.txt"])
    assert down[0].content == payload
    assert down[1].error == "file_not_found"

    # —— stderr 前缀与退出码透传 ——
    resp = sb.execute("printf 'out\\n'; printf 'err\\n' >&2; exit 7")
    assert resp.exit_code == 7
    assert resp.output == "out\n[stderr] err\n"

    # —— 超时 → exit 124(不污染会话,后续命令照常)——
    resp = sb.execute("sleep 30", timeout=2)
    assert resp.exit_code == 124
    assert resp.output == "command timed out after 2s"
    resp = sb.execute("echo alive")
    assert resp.output == "alive\n"

    # —— pause / resume ——
    sb.pause()
    sb.resume()
    resp = sb.execute("echo resumed")
    assert resp.output == "resumed\n"

    # —— close 后拒绝执行 ——
    sb.close()
    resp = sb.execute("echo dead")
    assert resp.exit_code == 137


def test_bash_tool_through_sandbox_shell_provider(sb, tmp_path):
    """真实 SSH argv 路径:Bash 工具经 SandboxShellProvider → BashRuntime。

    e2e 曾在此翻车('HagentSmolVMSandbox' object has no attribute '_container'):
    Bash 工具不走 sandbox.execute(),而是 command_argv 宿主子进程通道。
    对齐 docker 侧 test_bash_tool_parity_through_sandbox_shell_provider。
    """
    from pathlib import Path

    from hagent.bash_tool import create_bash_tool
    from hagent.bash_tool.runtime import BashRuntime
    from hagent.sandbox.providers.shell import SandboxShellProvider

    # Host side
    host_runtime = BashRuntime(tmp_path)
    host_bash = create_bash_tool(workspace_root=tmp_path, runtime=host_runtime, permissions=None)
    host_out = host_bash.invoke({"command": "printf 'hi\\n'"})

    # Sandbox side — real smolvm(SSH 兜底通道)
    provider = SandboxShellProvider(sandbox=sb, workspace_root=Path(sb.workspace_dir))
    sb_runtime = BashRuntime(tmp_path, shell_provider=provider)
    sb_bash = create_bash_tool(workspace_root=tmp_path, runtime=sb_runtime, permissions=None)
    sb_out = sb_bash.invoke({"command": "printf 'hi\\n'"})

    def normalize(text: str) -> str:
        lines = [ln for ln in text.splitlines() if not ln.startswith("__HAGENT_PWD__:")]
        return "\n".join(ln.rstrip() for ln in lines if ln.strip()).strip()

    assert normalize(host_out) == normalize(sb_out)

    # cwd 跨调用持久化(__HAGENT_PWD__ 哨兵回读)
    sb_bash.invoke({"command": "mkdir -p sub && cd sub"})
    out = sb_bash.invoke({"command": "pwd"})
    assert "/workspace/sub" in out

    host_runtime.close()
    sb_runtime.close()


def test_orphan_governance_end_to_end(tmp_path):
    """模拟 server 崩溃重启:活跃会话 VM 收养、无主 VM 清场、DB 无泄漏。"""
    from smolvm import SmolVMManager

    from hagent.sandbox.smolvm.reconciler import SmolVMReconciler
    from hagent.sandbox.smolvm.sandbox import HagentSmolVMSandbox
    from hagent.sandbox.supervisor import SandboxSupervisor
    from hagent.server.leases import LeaseStore

    leases = LeaseStore(tmp_path / "sessions.db")

    # 活跃会话 + 对应 VM(收养对象):起 VM 后「崩溃」。忠实模拟进程死:
    # OS 会关掉客户端 fd(vm.close 只收连接不停 VM),VM 照跑(F1)。
    # 只 del 不关连接会让旧句柄与收养句柄在同进程内争 vsock 通道
    # (实测 CONNECT handshake 偶发失败),那不是真实崩溃形态。
    adopt_target = HagentSmolVMSandbox.start(project_id="adoptme0")
    adopt_vm_id = adopt_target.manifest.container_id
    project_id = "adoptme0"
    leases.ensure(project_id, sandbox_kind="smolvm", node="local")
    leases.update_metadata(project_id, sandbox_id=adopt_vm_id)
    leases.update_state(project_id, state="running", desired_state="running")
    adopt_target._lifecycle.vm.close()  # 崩溃 = 连接断、VM 活
    del adopt_target

    # 无主 VM(清场对象):无 session 行
    reclaim_target = HagentSmolVMSandbox.start(project_id="reclaimme")
    reclaim_vm_id = reclaim_target.manifest.container_id
    reclaim_target._lifecycle.vm.close()
    del reclaim_target

    adopted: dict[str, object] = {}
    reconciler = SmolVMReconciler(
        manager=SmolVMManager(),
        leases=leases,
        adopt_fn=HagentSmolVMSandbox.adopt,
        on_adopted=lambda pid, sandbox: adopted.__setitem__(pid, sandbox),
    )
    supervisor = SandboxSupervisor(reconciler=reconciler)
    try:
        supervisor.startup_reclaim()

        # 收养断言：句柄可用，项目租约恢复为 running。
        assert project_id in adopted, "活跃项目的 RUNNING VM 必须被收养"
        adopted_sb = adopted[project_id]
        resp = adopted_sb.execute("echo adopted")
        assert resp.output == "adopted\n"
        assert leases.get(project_id).sandbox_state == "running"

        # 清场断言:无主 VM 从 SmolVM DB 消失
        manager = SmolVMManager()
        remaining = {vm.vm_id for vm in manager.list_vms()}
        assert reclaim_vm_id not in remaining, "无主 hagent- VM 必须被清场"
        assert adopt_vm_id in remaining
    finally:
        supervisor.shutdown()
        sandbox = adopted.get(project_id)
        if sandbox is not None:
            sandbox.close()
        # 兜底:测试残留不外泄
        manager = SmolVMManager()
        for vm_id in (adopt_vm_id, reclaim_vm_id):
            try:
                manager.delete(vm_id)
            except Exception:  # noqa: BLE001
                pass


def test_sandbox_ls_visibility(sb, capsys):
    """hagent sandbox ls 能看到 smolvm VM(hagent- 前缀)。"""
    from hagent.cli import _sandbox_ls

    assert _sandbox_ls() == 0
    out = capsys.readouterr().out
    assert sb.manifest.container_id in out


def test_paused_vm_exempt_from_health_and_resumes(sb, tmp_path):
    """缺陷回归(L3,真 Firecracker):idle GC 冻结的 VM 不被健康巡检误杀,
    唤醒后数据仍在、可正常执行。

    单测用 fake 抓不到根因——SDK `vm.run()` 对非 RUNNING 状态的前置断言
    (facade.py)只在真 VM 上触发,正是它让 paused VM 探针必失败。
    """
    from hagent.sandbox.smolvm.health import SmolVMHealthChecker
    from hagent.server.leases import LeaseStore

    up = sb.upload_files([("/workspace/sentinel.txt", b"alive\n")])
    assert up[0].error is None

    sb.pause()
    assert sb.manifest.paused is True
    # 直连探针在冻结态确实失败——证明健康巡检的豁免是必要的,不是恰好通过
    assert sb.health_check() is False
    # 健康巡检把 paused 视为健康(据 manifest.paused 豁免,不探冻结 VM)
    checker = SmolVMHealthChecker(
        targets_fn=lambda: [("project-health", sb)],
        drop_fn=lambda project_id, sandbox, before_drop, after_drop: True,
        leases=LeaseStore(tmp_path / "health.db"),
        workspace_root=tmp_path / "workspaces",
    )
    assert checker.check(sb) is True

    sb.resume()
    assert sb.manifest.paused is False
    resp = sb.execute("cat /workspace/sentinel.txt")
    assert resp.exit_code == 0
    assert resp.output == "alive\n", "唤醒后 VM 未被杀重建,workspace 数据仍在"
    assert checker.check(sb) is True, "唤醒后恢复正常探活"


def test_health_failure_kills_and_lazily_rebuilds_project_vm(tmp_path, monkeypatch):
    """真实 VM 连续探活失败后被清理，并由同一项目的下一次运行重建。"""
    from smolvm import SmolVMManager

    from hagent.sandbox import SandboxKind
    from hagent.sandbox.pool import SandboxPool
    from hagent.sandbox.smolvm.health import SmolVMHealthChecker
    from hagent.sandbox.smolvm.sandbox import HagentSmolVMSandbox
    from hagent.sandbox.supervisor import SandboxSupervisor
    from hagent.server.leases import LeaseStore, SandboxState
    from hagent.server.manager import SessionManager
    from hagent.server.sessions import SessionStore

    project_id = "healthrb"
    pool = SandboxPool(
        sandbox_factory=lambda: HagentSmolVMSandbox.start(),
        project_sandbox_factory=lambda pid: HagentSmolVMSandbox.start(project_id=pid),
        min_size=0,
        max_size=1,
    )
    db_path = tmp_path / "health-rebuild.db"
    leases = LeaseStore(db_path)
    manager = SessionManager(
        store=SessionStore(db_path),
        lease_store=leases,
        sandbox_pool=pool,
        workspace_root=tmp_path / "workspaces",
    )
    session = manager.create_session(
        project_id=project_id,
        sandbox_kind=SandboxKind.SMOLVM,
    )
    sandbox = manager.ensure_sandbox(session.id)
    old_vm_id = sandbox.manifest.container_id
    checker = SmolVMHealthChecker(
        targets_fn=manager.live_sandboxes,
        drop_fn=manager.drop_sandbox,
        leases=leases,
        workspace_root=manager.workspace_root,
        event_fn=manager.emit_project_event,
    )
    supervisor = SandboxSupervisor(
        reconciler=NoopReconciler(),
        health_checker=checker,
    )
    monkeypatch.setattr(sandbox, "health_check", lambda: False)

    try:
        for _ in range(3):
            supervisor._health_once()

        assert manager.get_project_sandbox(project_id) is None
        assert leases.get(project_id).sandbox_state == SandboxState.ORPHANED.value
        with SmolVMManager() as vm_manager:
            assert old_vm_id not in {vm.vm_id for vm in vm_manager.list_vms()}

        rebuilt = manager.ensure_sandbox(session.id)
        assert rebuilt.manifest.container_id != old_vm_id
        assert rebuilt.manifest.container_id.startswith("hagent-healthrb-")
        assert leases.get(project_id).sandbox_state == SandboxState.RUNNING.value
    finally:
        supervisor.shutdown()
        manager.shutdown()


def test_snapshot_persist_restore_roundtrip(tmp_path):
    """DISK 快照保留工作区与 agent 自装环境增量，且全程无泄漏。"""
    from smolvm import SmolVMManager

    from hagent.sandbox.smolvm.sandbox import HagentSmolVMSandbox

    sandbox = HagentSmolVMSandbox.start(project_id="itestsnap")
    vm_id = sandbox.manifest.container_id
    restored = None
    snapshot_id = None
    try:
        payload = "快照前写入的数据\n".encode("utf-8")
        up = sandbox.upload_files([("/workspace/persisted.txt", payload)])
        assert up[0].error is None
        installed = sandbox.execute(
            "mkdir -p /workspace/.local/bin "
            "&& printf '#!/bin/sh\\necho agent-env\\n' "
            "> /workspace/.local/bin/hagent-agent-tool "
            "&& chmod +x /workspace/.local/bin/hagent-agent-tool"
        )
        assert installed.exit_code == 0

        # 模拟池 GC 两级降档:pause → persist(快照 + 全拆,释放内存额度)
        sandbox.pause()
        snapshot_id = sandbox.persist_to_snapshot()

        with SmolVMManager() as manager:
            vm_ids = [vm.vm_id for vm in manager.list_vms()]
            assert vm_id not in vm_ids, "persist 后 VM 必须已删除(内存/TAP/IP 释放)"
            snap_ids = [s.snapshot_id for s in manager.list_snapshots()]
            assert snapshot_id in snap_ids, "快照必须独立于 VM 存活"

        # 恢复:全新 boot 回原 vm_id,workspace 数据原样在
        restored = HagentSmolVMSandbox.restore(snapshot_id, project_id="itestsnap")
        assert restored.manifest.container_id == vm_id, "DISK restore 回原 VM 身份"
        resp = restored.execute("cat /workspace/persisted.txt")
        assert resp.exit_code == 0
        assert resp.output == "快照前写入的数据\n"
        env_resp = restored.execute("/workspace/.local/bin/hagent-agent-tool")
        assert env_resp.exit_code == 0
        assert env_resp.output == "agent-env\n"
    finally:
        if restored is not None:
            restored.close()
        else:
            sandbox.close()

    # 收尾无泄漏:restored VM 拆除后,已消费的快照被顺手清理
    with SmolVMManager() as manager:
        assert vm_id not in [vm.vm_id for vm in manager.list_vms()]
        if snapshot_id is not None:
            assert snapshot_id not in [
                s.snapshot_id for s in manager.list_snapshots()
            ], "已消费快照须清理(一次性语义,防磁盘泄漏)"


def test_deleted_snapshot_silently_cold_starts_with_canonical_workspace(tmp_path):
    """真删 DISK 快照后，项目无感冷启动并由 canonical workspace 重建。"""
    from smolvm import SmolVMManager

    from hagent.sandbox import SandboxKind
    from hagent.sandbox.pool import SandboxPool
    from hagent.sandbox.smolvm.sandbox import HagentSmolVMSandbox
    from hagent.server.leases import LeaseStore, SandboxState
    from hagent.server.manager import SessionManager
    from hagent.server.project_workspace import ProjectWorkspace
    from hagent.server.sessions import SessionStore
    from hagent.server.workspace_materialization import WorkspaceMaterializer

    project_id = "snapfallback"
    workspace_root = tmp_path / "workspaces"
    workspace = ProjectWorkspace(workspace_root)
    workspace.initialize(project_id)
    host_file = workspace.path_for(project_id) / "deliverables" / "技术方案.md"
    host_file.write_text("canonical 成果", encoding="utf-8")
    revision = workspace.commit(
        project_id,
        summary="chat_turn: 生成技术方案",
        run_id="run-snapshot-fallback",
        session_id="session-snapshot-fallback",
        kind="chat_turn",
    )
    assert revision is not None

    pool = SandboxPool(
        sandbox_factory=lambda: HagentSmolVMSandbox.start(),
        project_sandbox_factory=lambda pid: HagentSmolVMSandbox.start(project_id=pid),
        restore_factory=lambda snapshot_id, pid: HagentSmolVMSandbox.restore(
            snapshot_id, project_id=pid
        ),
        min_size=0,
        max_size=1,
        idle_pause_seconds=0,
        idle_evict_seconds=0,
    )
    db_path = tmp_path / "snapshot-fallback.db"
    leases = LeaseStore(db_path)
    manager = SessionManager(
        store=SessionStore(db_path),
        lease_store=leases,
        sandbox_pool=pool,
        workspace_root=workspace_root,
        workspace_materializer=WorkspaceMaterializer(workspace),
    )
    pool.set_persist_fn(manager.persist_sandbox)
    session = manager.create_session(
        project_id=project_id,
        sandbox_kind=SandboxKind.SMOLVM,
    )
    first = manager.ensure_sandbox(session.id)
    first_vm_id = first.manifest.container_id

    try:
        pool._gc_pass()
        pool._gc_pass()
        snapshotted = leases.get(project_id)
        assert snapshotted.sandbox_state == SandboxState.SNAPSHOTTED.value
        assert snapshotted.snapshot_id is not None
        with SmolVMManager() as smolvm_manager:
            smolvm_manager.delete_snapshot(snapshotted.snapshot_id)

        rebuilt = manager.ensure_sandbox(session.id)

        assert rebuilt.manifest.container_id != first_vm_id
        response = rebuilt.execute("cat /workspace/deliverables/技术方案.md")
        assert response.exit_code == 0
        assert response.output == "canonical 成果"
        saved = leases.get(project_id)
        assert saved.sandbox_state == SandboxState.RUNNING.value
        assert saved.snapshot_id is None
        assert saved.materialized_revision == revision
    finally:
        manager.shutdown()


def test_kill9_vm_mid_conversation_preserves_checkpointed_turns(tmp_path):
    """活跃对话中 kill -9 VM:健康巡检清场后重发消息,已 checkpoint 的轮次成果完整无损。"""
    import os
    import signal
    import time

    from smolvm import SmolVMManager

    from hagent.sandbox import SandboxKind
    from hagent.sandbox.pool import SandboxPool
    from hagent.sandbox.smolvm.health import SmolVMHealthChecker
    from hagent.sandbox.smolvm.sandbox import HagentSmolVMSandbox
    from hagent.sandbox.supervisor import SandboxSupervisor
    from hagent.server.leases import LeaseStore
    from hagent.server.manager import SessionManager
    from hagent.server.project_workspace import ProjectWorkspace
    from hagent.server.runs import RunStore
    from hagent.server.sessions import SessionStore
    from hagent.server.workspace_checkpoint import WorkspaceCheckpointer
    from hagent.server.workspace_materialization import WorkspaceMaterializer

    project_id = "kill9"
    workspace_root = tmp_path / "workspaces"
    workspace = ProjectWorkspace(workspace_root)
    workspace.initialize(project_id)

    pool = SandboxPool(
        sandbox_factory=lambda: HagentSmolVMSandbox.start(),
        project_sandbox_factory=lambda pid: HagentSmolVMSandbox.start(project_id=pid),
        min_size=0,
        max_size=1,
    )
    db_path = tmp_path / "kill9.db"
    leases = LeaseStore(db_path)
    runs = RunStore(db_path)
    manager = SessionManager(
        store=SessionStore(db_path),
        lease_store=leases,
        sandbox_pool=pool,
        workspace_root=workspace_root,
        workspace_materializer=WorkspaceMaterializer(workspace),
        project_workspace=workspace,
        run_store=runs,
        workspace_checkpointer=WorkspaceCheckpointer(
            workspace=workspace, runs=runs, leases=leases
        ),
    )
    session = manager.create_session(
        project_id=project_id, sandbox_kind=SandboxKind.SMOLVM
    )
    checker = SmolVMHealthChecker(
        targets_fn=manager.live_sandboxes,
        drop_fn=manager.drop_sandbox,
        leases=leases,
        workspace_root=manager.workspace_root,
        event_fn=manager.emit_project_event,
    )
    supervisor = SandboxSupervisor(
        reconciler=NoopReconciler(),
        health_checker=checker,
    )

    try:
        # 轮 1:agent 在 VM 内写产物,轮末 checkpoint 落 canonical workspace
        sandbox = manager.ensure_sandbox(session.id)
        old_vm_id = sandbox.manifest.container_id
        run = manager.create_chat_turn(session.id, summary="chat_turn: 写技术方案")
        manager.mark_run_running(run.id)
        resp = sandbox.execute(
            "mkdir -p /workspace/deliverables"
            " && printf '第一轮成果\\n' > /workspace/deliverables/方案.md"
        )
        assert resp.exit_code == 0
        result = manager.checkpoint_run(run.id, sandbox=sandbox)
        assert result.commit_sha is not None

        # 活跃对话中 kill -9 VM 进程(猝死,非优雅关停)
        with SmolVMManager() as vm_manager:
            info = vm_manager.get(old_vm_id)
        assert info.pid is not None
        os.kill(info.pid, signal.SIGKILL)
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                os.kill(info.pid, 0)
            except OSError:
                break
            time.sleep(0.2)

        # 生产同款清场机制:真健康探活三连败 → drop(不 monkeypatch)
        for _ in range(3):
            supervisor._health_once()
        assert manager.get_project_sandbox(project_id) is None

        # 重发消息:ensure 冷重建 + 物化注入,前轮成果完整无损
        rebuilt = manager.ensure_sandbox(session.id)
        assert rebuilt.manifest.container_id != old_vm_id
        resp = rebuilt.execute("cat /workspace/deliverables/方案.md")
        assert resp.exit_code == 0
        assert resp.output == "第一轮成果\n"
        assert (
            leases.get(project_id).materialized_revision
            == workspace.head(project_id)
        )
    finally:
        supervisor.shutdown()
        manager.shutdown()
