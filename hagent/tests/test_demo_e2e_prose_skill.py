"""门控 e2e（票 05 验收）：真实模型 + 真实招标语料，skill 编排走通四矩阵 publish。

新版 bid-response-matrix 是纯工具化编排（无文件流水线）：agent 经 stdio MCP
工具面注册文档、开草稿、提交记录、校验、发布；本测试事后直接读对象库断言
四矩阵 published 且全套校验（含源文保真）pass。

运行：set -a && source .env && set +a && pytest tests/test_demo_e2e_prose_skill.py -v -s
真实语料整份走全流程，token 消耗大，仅验收时手动跑。
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY 未设置，跳过真实模型 e2e 测试",
)

REPO_HAGENT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_HAGENT.parent / "data"
PROJECT = "e2e-prose-skill"


def _pick_corpus() -> Path:
    """取仓内最小的一份真实招标 Markdown，控制 token 消耗。"""
    candidates = sorted(DATA_DIR.glob("*.md"), key=lambda p: p.stat().st_size)
    if not candidates:
        pytest.skip("data/ 下无真实招标语料")
    return candidates[0]


def test_skill_orchestrates_four_matrix_publish(tmp_path, monkeypatch):
    corpus = _pick_corpus()
    db_path = tmp_path / "sessions.db"
    workspace_root = tmp_path / "workspaces"
    workspace = workspace_root / "projects" / PROJECT / "workspace"
    (workspace / "docs").mkdir(parents=True)
    shutil.copy(corpus, workspace / "docs" / "tender.md")

    # host 模式（.env 的 sandbox 配置不适用本测试）；stdio MCP 子进程与本进程
    # 共享的 DB / workspace / skills 约定
    monkeypatch.setenv("HAGENT_SANDBOX_KIND", "none")
    monkeypatch.setenv("HAGENT_SESSIONS_DB", str(db_path))
    monkeypatch.setenv("HAGENT_WORKSPACE_ROOT", str(workspace_root))
    monkeypatch.setenv("HAGENT_SKILLS_PATHS", str(REPO_HAGENT / ".hagent" / "skills"))

    from deepagents.backends import FilesystemBackend

    from hagent.core import create_hagent
    from hagent.mcp_tools import prose_stdio_connection

    agent = create_hagent(
        backend=FilesystemBackend(root_dir=workspace, virtual_mode=False),
        mcp_connection=prose_stdio_connection(actor_ref="e2e-prose-skill"),
    )
    message = (
        'Use the `Skill` tool with skill: "bid-response-matrix".\n\n'
        f"User request: 解析项目 {PROJECT} 的招标文件，生成四个应答矩阵并发布。"
        f"project_id 是 {PROJECT}，源文件在 project workspace 的 docs/tender.md。"
    )
    final_state = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"recursion_limit": 500},
    )
    final = final_state["messages"][-1]
    print("\n[final answer]\n", getattr(final, "content", final))

    from hagent.assets.model import MATRIX_TYPES
    from hagent.assets.service import AssetService
    from hagent.assets.store import AssetStore

    service = AssetService(AssetStore(db_path))

    # 四矩阵全部发布，且发布内容非空
    entries = {e.matrix_type: e for e in service.matrix_status(PROJECT)}
    states = {m: entries[m].state.value for m in MATRIX_TYPES}
    assert states == {m: "published" for m in MATRIX_TYPES}, states
    assert all(entries[m].current_count > 0 for m in MATRIX_TYPES), {
        m: entries[m].current_count for m in MATRIX_TYPES
    }

    # 全套校验（结构 / 一致性 / 源文保真）对发布后的当前版复跑仍 pass
    for matrix_type in MATRIX_TYPES:
        report = service.validate_matrix(PROJECT, matrix_type, workspace_root=workspace)
        assert report.status == "pass", (
            matrix_type,
            [issue.to_dict() for issue in report.errors[:5]],
        )
