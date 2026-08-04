"""审计完整性：全部写动作留痕；对象表禁止绕过 service 直写（静态守护）。"""

import re
from pathlib import Path

from hagent.assets.model import Actor

from .conftest import make_item

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "hagent"

OBJECT_TABLES = ("documents", "matrices", "matrix_items", "matrix_revisions", "asset_events")

STORE_WRITE_METHODS = (
    "insert_document",
    "set_document_blobs",
    "insert_matrix",
    "update_matrix",
    "insert_item",
    "update_item_row",
    "delete_item",
    "delete_stage",
    "promote_draft_items",
    "insert_revision",
    "append_event",
)


def test_every_write_action_leaves_exactly_one_event(service, agent_actor, user_actor):
    on_behalf = Actor(kind="agent_on_behalf", ref="run-007")
    service.register_document(
        "proj-1", path="inputs/招标文件.md", sha256="a" * 64, doc_type="tender", actor=agent_actor
    )
    service.start_draft("proj-1", "technical", actor=agent_actor)
    service.start_draft("proj-1", "business", actor=agent_actor)
    service.submit_records(
        "proj-1", "technical", section="items",
        records=[make_item(1), make_item(2)], actor=agent_actor,
    )
    service.set_meta("proj-1", "technical", set={"project_name": "X"}, actor=agent_actor)
    service.update_item("proj-1", "technical", "TECH-001", set={"mandatory": True}, actor=agent_actor)
    service.move_item(
        "proj-1", from_matrix="technical", to_matrix="business",
        item_id="TECH-002", new_id="BIZ-001", actor=agent_actor,
    )
    service.publish("proj-1", "technical", actor=agent_actor)
    service.publish("proj-1", "business", actor=agent_actor)
    service.set_item_response_status(
        "proj-1", "business", "BIZ-001", status="compliant", actor=on_behalf
    )
    service.confirm_item("proj-1", "business", "BIZ-001", actor=user_actor)
    service.drop_item("proj-1", "technical", "TECH-001", reason="废标条款撤销", actor=user_actor)

    events = service.list_events("proj-1")
    assert [e.action for e in events] == [
        "register_document",
        "start_matrix_draft",
        "start_matrix_draft",
        "submit_matrix_records",
        "set_matrix_meta",
        "update_matrix_item",
        "move_matrix_item",
        "publish_matrix",
        "publish_matrix",
        "set_item_response_status",
        "confirm_matrix_item",
        "drop_matrix_item",
    ]
    for ev in events:
        assert ev.ts and ev.actor_kind and ev.target
    kinds = {e.actor_kind for e in events}
    assert kinds == {"agent", "agent_on_behalf", "user"}


def _py_files_outside_store():
    for path in SRC_ROOT.rglob("*.py"):
        if path.name == "store.py" and path.parent.name == "assets":
            continue
        yield path


def test_object_table_sql_lives_only_in_assets_store():
    pattern = re.compile(
        r"(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(?:%s)\b" % "|".join(OBJECT_TABLES),
        re.IGNORECASE,
    )
    offenders = [
        str(path.relative_to(SRC_ROOT))
        for path in _py_files_outside_store()
        if pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"对象表 SQL 只允许出现在 assets/store.py：{offenders}"


def test_store_write_methods_called_only_from_service():
    pattern = re.compile(r"\.(?:%s)\(" % "|".join(STORE_WRITE_METHODS))
    offenders = [
        str(path.relative_to(SRC_ROOT))
        for path in _py_files_outside_store()
        if path.read_text(encoding="utf-8") != ""
        and not (path.name == "service.py" and path.parent.name == "assets")
        and pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"AssetStore 写方法只允许 service.py 调用：{offenders}"
