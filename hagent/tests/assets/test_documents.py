"""document registry：同 (project, sha256) 幂等，全部动作留审计。"""

import pytest

from hagent.assets.errors import AssetError

SHA_A = "a" * 64
SHA_B = "b" * 64


def test_register_returns_doc_id_derived_from_sha(service, agent_actor):
    doc = service.register_document(
        "proj-1", path="inputs/招标文件.md", sha256=SHA_A, doc_type="tender", actor=agent_actor
    )
    assert doc.id == "doc-" + "a" * 8
    assert doc.project_id == "proj-1"
    assert doc.path == "inputs/招标文件.md"
    assert doc.sha256 == SHA_A
    assert doc.doc_type == "tender"
    assert doc.created is True
    assert doc.registered_at


def test_register_idempotent_on_project_and_sha(service, agent_actor):
    first = service.register_document(
        "proj-1", path="inputs/招标文件.md", sha256=SHA_A, doc_type="tender", actor=agent_actor
    )
    again = service.register_document(
        "proj-1", path="inputs/改名后的同一文件.md", sha256=SHA_A, doc_type="tender", actor=agent_actor
    )
    assert again.id == first.id
    assert again.created is False
    # 幂等返回既有注册记录，不改写 path
    assert again.path == "inputs/招标文件.md"
    docs, total = service.list_documents("proj-1")
    assert total == 1


def test_same_sha_in_another_project_registers_separately(service, agent_actor):
    a = service.register_document("proj-1", path="x.md", sha256=SHA_A, doc_type=None, actor=agent_actor)
    b = service.register_document("proj-2", path="x.md", sha256=SHA_A, doc_type=None, actor=agent_actor)
    assert a.created and b.created
    _, total_1 = service.list_documents("proj-1")
    _, total_2 = service.list_documents("proj-2")
    assert (total_1, total_2) == (1, 1)


def test_list_documents_paginates(service, agent_actor):
    for ch in "abcde":
        service.register_document("proj-1", path=f"{ch}.md", sha256=ch * 64, doc_type=None, actor=agent_actor)
    page, total = service.list_documents("proj-1", limit=2, offset=4)
    assert total == 5
    assert len(page) == 1


def test_register_rejects_blank_inputs(service, agent_actor):
    with pytest.raises(AssetError):
        service.register_document("", path="x.md", sha256=SHA_A, doc_type=None, actor=agent_actor)
    with pytest.raises(AssetError):
        service.register_document("proj-1", path="", sha256=SHA_A, doc_type=None, actor=agent_actor)
    with pytest.raises(AssetError):
        service.register_document("proj-1", path="x.md", sha256="", doc_type=None, actor=agent_actor)


def test_register_writes_audit_event(service, agent_actor):
    doc = service.register_document(
        "proj-1", path="inputs/招标文件.md", sha256=SHA_A, doc_type="tender", actor=agent_actor
    )
    events = service.list_events("proj-1")
    assert len(events) == 1
    ev = events[0]
    assert ev.action == "register_document"
    assert ev.target == f"documents/{doc.id}"
    assert ev.actor_kind == "agent"
    assert ev.actor_ref == "run-001"
    # 幂等命中不再产生新事件
    service.register_document(
        "proj-1", path="inputs/招标文件.md", sha256=SHA_A, doc_type="tender", actor=agent_actor
    )
    assert len(service.list_events("proj-1")) == 1
