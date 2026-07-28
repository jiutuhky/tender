"""结构化资产服务 —— 对象库的唯一写入口（领域动作层）。

所有写动作在此裁决（状态机、乐观锁）并在同一事务内落审计事件；
REST / MCP adapter 只做协议翻译，不得绕过本层直写对象表。
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import uuid
from collections.abc import Callable
from pathlib import Path

from hagent.assets.errors import AssetError, ConflictError
from hagent.assets.model import (
    ALLOWED_SECTIONS,
    MATRIX_TYPES,
    RESPONSE_MATRIX_TYPES,
    RESPONSE_STATUSES,
    Actor,
    AssetEvent,
    DocumentRecord,
    MatrixInfo,
    MatrixItem,
    MatrixLifecycle,
    MatrixOverview,
    MatrixStatusEntry,
    PublishResult,
    SubmitResult,
)
from hagent.assets.projection import materialize_published_matrices
from hagent.assets.store import DOCUMENTS_FETCH_LIMIT, AssetStore, deep_merge, now_iso
from hagent.assets.validators import (
    FidelityThresholds,
    ValidationReport,
    make_publish_gate,
    run_full_validation,
)

logger = logging.getLogger(__name__)

_DRAFT_STATES = (MatrixLifecycle.DRAFTING, MatrixLifecycle.PUBLISHED_DRAFTING)


class AssetService:
    def __init__(self, store: AssetStore):
        self._store = store

    # —— document registry ——

    def register_document(
        self,
        project_id: str,
        *,
        path: str,
        sha256: str,
        doc_type: str | None,
        actor: Actor,
    ) -> DocumentRecord:
        if not project_id or not path or not sha256:
            raise AssetError(
                "invalid_argument",
                "project_id / path / sha256 均不能为空",
                hint="提供 workspace 相对路径与该文件内容的 sha256",
            )
        with self._store.transaction() as conn:
            existing = self._store.get_document_by_sha(conn, project_id, sha256)
            if existing is not None:
                # 同 project + sha256 幂等：返回既有注册记录，不产生新事件
                return existing
            doc_id = self._new_document_id(conn, sha256)
            registered_at = now_iso()
            self._store.insert_document(
                conn,
                doc_id=doc_id,
                project_id=project_id,
                path=path,
                sha256=sha256,
                doc_type=doc_type,
                registered_at=registered_at,
            )
            self._store.append_event(
                conn,
                project_id=project_id,
                actor_kind=actor.kind,
                actor_ref=actor.ref,
                action="register_document",
                target=f"documents/{doc_id}",
                after={"path": path, "sha256": sha256, "doc_type": doc_type},
            )
        return DocumentRecord(
            id=doc_id,
            project_id=project_id,
            path=path,
            sha256=sha256,
            doc_type=doc_type,
            registered_at=registered_at,
            created=True,
        )

    def _new_document_id(self, conn: sqlite3.Connection, sha256: str) -> str:
        # doc-<hash8>；id 是全局主键，hash8 撞车（不同 sha256）时延长前缀
        for width in range(8, len(sha256) + 1):
            doc_id = f"doc-{sha256[:width]}"
            if not self._store.document_id_exists(conn, doc_id):
                return doc_id
        raise AssetError("document_id_exhausted", f"无法为 sha256={sha256} 生成唯一文档 ID")

    def register_workspace_document(
        self,
        project_id: str,
        *,
        path: str,
        doc_type: str | None,
        workspace_root: Path | str,
        actor: Actor,
    ) -> DocumentRecord:
        """按 workspace 相对路径注册：服务端读文件算 sha256（MCP/REST 共用入口）。"""
        if not path:
            raise AssetError("invalid_argument", "path 不能为空")
        root = Path(workspace_root).resolve()
        full = (root / path).resolve()
        if not full.is_relative_to(root):
            raise AssetError(
                "invalid_path",
                f"path 越出 project workspace：{path}",
                hint="提供 workspace 内的相对路径（如 sources/tender.md）",
            )
        if not full.is_file():
            raise AssetError(
                "file_not_found",
                f"workspace 中不存在文件：{path}",
                hint="确认源文件已上传到 project workspace，路径为 workspace 相对路径",
            )
        sha256 = hashlib.sha256(full.read_bytes()).hexdigest()
        return self.register_document(
            project_id,
            path=full.relative_to(root).as_posix(),
            sha256=sha256,
            doc_type=doc_type,
            actor=actor,
        )

    def list_documents(
        self, project_id: str, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[DocumentRecord], int]:
        with self._store.transaction() as conn:
            return self._store.list_documents(conn, project_id, limit=limit, offset=offset)

    # —— 草稿生命周期 ——

    def start_draft(
        self,
        project_id: str,
        matrix_type: str,
        *,
        discard_manual_states: bool = False,
        actor: Actor,
    ) -> MatrixInfo:
        self._require_matrix_type(matrix_type)
        with self._store.transaction() as conn:
            row = self._store.get_matrix(conn, project_id, matrix_type)
            state = MatrixLifecycle(row["state"]) if row is not None else MatrixLifecycle.EMPTY
            if state in _DRAFT_STATES:
                raise AssetError(
                    "draft_exists",
                    f"{matrix_type} 已有进行中的草稿（state={state.value}）",
                    hint="直接用 submit_matrix_records / 行级工具继续编辑，完成后 publish_matrix",
                )
            if state is MatrixLifecycle.PUBLISHED and not discard_manual_states:
                raise AssetError(
                    "discard_required",
                    f"{matrix_type} 已发布：全量重抽会在发布时丢弃确认/应答状态等人工标注",
                    hint="增量维护请用行级工具（update/drop/move）；确要重抽请显式传 "
                    "discard_manual_states=true",
                )
            meta = json.loads(row["meta_json"]) if row is not None else {}
            new_state = (
                MatrixLifecycle.PUBLISHED_DRAFTING
                if state is MatrixLifecycle.PUBLISHED
                else MatrixLifecycle.DRAFTING
            )
            if row is None:
                self._store.insert_matrix(
                    conn,
                    project_id=project_id,
                    matrix_type=matrix_type,
                    state=new_state.value,
                    meta={},
                    draft_meta={},
                )
            else:
                # 草稿 meta 从当前版复制起步（重抽时项目名等信封字段延续）
                self._store.delete_stage(conn, project_id, matrix_type, "draft")
                self._store.update_matrix(
                    conn, project_id, matrix_type, state=new_state.value, draft_meta=meta
                )
            self._store.append_event(
                conn,
                project_id=project_id,
                actor_kind=actor.kind,
                actor_ref=actor.ref,
                action="start_matrix_draft",
                target=matrix_type,
                before={"state": state.value},
                after={"state": new_state.value, "discard_manual_states": discard_manual_states},
            )
            info = self._matrix_info(conn, project_id, matrix_type)
        return info

    def submit_records(
        self,
        project_id: str,
        matrix_type: str,
        *,
        section: str,
        records: list[dict],
        actor: Actor,
    ) -> SubmitResult:
        self._require_matrix_type(matrix_type)
        self._require_section(matrix_type, section)
        if not records:
            raise AssetError("invalid_records", "records 不能为空")
        with self._store.transaction() as conn:
            row = self._store.get_matrix(conn, project_id, matrix_type)
            state = MatrixLifecycle(row["state"]) if row is not None else MatrixLifecycle.EMPTY
            if state not in _DRAFT_STATES:
                if state is MatrixLifecycle.PUBLISHED:
                    hint = (
                        "已发布矩阵走增量维护（行级 update/drop/move）；"
                        "确要全量重抽先 start_matrix_draft(discard_manual_states=true)"
                    )
                else:
                    hint = "先 start_matrix_draft 开启草稿"
                raise AssetError(
                    "no_draft",
                    f"{matrix_type} 不在草稿态（state={state.value}），submit_matrix_records 仅草稿态可用",
                    hint=hint,
                )
            item_ids = self._assign_item_ids(conn, project_id, matrix_type, section, records)
            for item_id, record in zip(item_ids, records):
                self._store.insert_item(
                    conn,
                    project_id=project_id,
                    matrix_type=matrix_type,
                    stage="draft",
                    item_id=item_id,
                    section=section,
                    payload=record,
                )
            self._store.append_event(
                conn,
                project_id=project_id,
                actor_kind=actor.kind,
                actor_ref=actor.ref,
                action="submit_matrix_records",
                target=f"{matrix_type}/{section}",
                after={"item_ids": item_ids, "records": records},
            )
        return SubmitResult(matrix_type=matrix_type, section=section, stage="draft", item_ids=item_ids)

    def _assign_item_ids(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        matrix_type: str,
        section: str,
        records: list[dict],
    ) -> list[str]:
        if section != "items":
            return [f"{section}:{uuid.uuid4().hex[:8]}" for _ in records]
        item_ids: list[str] = []
        for record in records:
            rid = record.get("id") if isinstance(record, dict) else None
            if not isinstance(rid, str) or not rid:
                raise AssetError(
                    "invalid_records",
                    "items 区段的每条记录必须带非空字符串 id（如 TECH-001）",
                    hint="按矩阵 item shape 补全 id 后重新提交",
                )
            item_ids.append(rid)
        duplicated = sorted(
            {rid for rid in item_ids if item_ids.count(rid) > 1}
            | {
                rid
                for rid in item_ids
                if self._store.get_item(conn, project_id, matrix_type, "draft", rid) is not None
            }
        )
        if duplicated:
            raise AssetError(
                "item_exists",
                f"id 与草稿内既有条目重复或批内重复：{', '.join(duplicated)}（整批未写入）",
                hint="换用未占用的 id，或用 update_matrix_item 修改既有条目",
            )
        return item_ids

    # —— 行级动作（靶点规则：有草稿写草稿，无草稿写当前版） ——

    def update_item(
        self,
        project_id: str,
        matrix_type: str,
        item_id: str,
        *,
        set: dict,  # 参数名对齐 MCP 工具面的 set{}（spec §5），全服务层同名，刻意遮蔽内建
        reason: str | None = None,
        expected_version: int | None = None,
        actor: Actor,
    ) -> MatrixItem:
        self._require_matrix_type(matrix_type)
        if not isinstance(set, dict) or not set:
            raise AssetError("invalid_argument", "set 必须是非空对象")
        if "id" in set:
            raise AssetError(
                "invalid_argument",
                "不允许经 update 改写 id",
                hint="改 id / 挪矩阵请用 move_matrix_item",
            )
        manual_fields = {"response_status", "response_note", "confirmed"} & set.keys()
        if manual_fields:
            raise AssetError(
                "invalid_argument",
                f"字段 {', '.join(sorted(manual_fields))} 不属于条目 payload",
                hint="应答状态用 set_item_response_status，确认用 confirm_matrix_item",
            )
        conflict: MatrixItem | None = None
        updated: MatrixItem | None = None
        with self._store.transaction() as conn:
            _, state = self._matrix_state(conn, project_id, matrix_type)
            stage = self._resolve_stage(matrix_type, state)
            item = self._require_item(conn, project_id, matrix_type, stage, item_id)
            if expected_version is not None and expected_version != item.version:
                self._audit_stale_rejection(
                    conn,
                    project_id,
                    action="update_matrix_item",
                    target=f"{matrix_type}/{item_id}",
                    before={"payload": item.payload, "version": item.version},
                    expected_version=expected_version,
                    current_version=item.version,
                    actor=actor,
                    reason=reason,
                )
                conflict = item
            else:
                merged = {**item.payload, **set}
                changed = self._store.update_item_row(
                    conn, project_id, matrix_type, stage, item_id,
                    expected_version=item.version, payload=merged,
                )
                assert changed, "同事务内的 version 守卫不应落空"
                self._store.append_event(
                    conn,
                    project_id=project_id,
                    actor_kind=actor.kind,
                    actor_ref=actor.ref,
                    action="update_matrix_item",
                    target=f"{matrix_type}/{item_id}",
                    before={"payload": item.payload, "version": item.version},
                    after={"payload": merged, "version": item.version + 1},
                    reason=reason,
                )
                updated = self._store.get_item(conn, project_id, matrix_type, stage, item_id)
        if conflict is not None:
            raise self._version_conflict(matrix_type, item_id, expected_version, conflict.version)
        assert updated is not None
        return updated

    def _audit_stale_rejection(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        *,
        action: str,
        target: str,
        before: dict,
        expected_version: int,
        current_version: int,
        actor: Actor,
        reason: str | None = None,
    ) -> None:
        """冲突也是审计事实：记录被拒的这一笔（事务正常提交后由调用方抛错）。"""
        self._store.append_event(
            conn,
            project_id=project_id,
            actor_kind=actor.kind,
            actor_ref=actor.ref,
            action=action,
            target=target,
            before=before,
            after=None,
            reason=f"乐观锁冲突被拒：expected_version={expected_version}，"
            f"当前 version={current_version}" + (f"；{reason}" if reason else ""),
        )

    @staticmethod
    def _version_conflict(
        matrix_type: str, item_id: str, expected_version: int | None, current_version: int
    ) -> ConflictError:
        return ConflictError(
            f"{matrix_type}/{item_id} 已被并发修改：expected_version={expected_version}，"
            f"当前 version={current_version}",
            current_version=current_version,
            hint=f"用 query_matrix_items 重读该条目，基于 version={current_version} 重试",
        )

    def drop_item(
        self,
        project_id: str,
        matrix_type: str,
        item_id: str,
        *,
        reason: str | None = None,
        actor: Actor,
    ) -> None:
        self._require_matrix_type(matrix_type)
        with self._store.transaction() as conn:
            _, state = self._matrix_state(conn, project_id, matrix_type)
            stage = self._resolve_stage(matrix_type, state)
            item = self._require_item(conn, project_id, matrix_type, stage, item_id)
            self._store.delete_item(conn, project_id, matrix_type, stage, item_id)
            self._store.append_event(
                conn,
                project_id=project_id,
                actor_kind=actor.kind,
                actor_ref=actor.ref,
                action="drop_matrix_item",
                target=f"{matrix_type}/{item_id}",
                before=self._item_audit_view(item),
                after=None,
                reason=reason,
            )

    def move_item(
        self,
        project_id: str,
        *,
        from_matrix: str,
        to_matrix: str,
        item_id: str,
        new_id: str,
        set: dict | None = None,
        reason: str | None = None,
        actor: Actor,
    ) -> MatrixItem:
        self._require_matrix_type(from_matrix)
        self._require_matrix_type(to_matrix)
        if not isinstance(new_id, str) or not new_id:
            raise AssetError("invalid_argument", "new_id 必须是非空字符串（如 BIZ-031）")
        with self._store.transaction() as conn:
            _, from_state = self._matrix_state(conn, project_id, from_matrix)
            from_stage = self._resolve_stage(from_matrix, from_state)
            _, to_state = self._matrix_state(conn, project_id, to_matrix)
            to_stage = self._resolve_stage(to_matrix, to_state)
            item = self._require_item(conn, project_id, from_matrix, from_stage, item_id)
            if item.section != "items":
                raise AssetError(
                    "invalid_argument",
                    f"move 仅适用于 items 区段（{item_id} 属 {item.section}）",
                    hint="非 items 行用 drop + submit 重建",
                )
            if self._store.get_item(conn, project_id, to_matrix, to_stage, new_id) is not None:
                raise AssetError(
                    "item_exists",
                    f"{to_matrix}/{new_id} 已存在，无法移入",
                    hint="换一个未占用的 new_id",
                )
            payload = {**item.payload, **(set or {}), "id": new_id}
            # 人工状态随条目迁移；新落点作为新行从 version=1 起
            self._store.insert_item(
                conn,
                project_id=project_id,
                matrix_type=to_matrix,
                stage=to_stage,
                item_id=new_id,
                section="items",
                payload=payload,
                response_status=item.response_status,
                response_note=item.response_note,
                confirmed=item.confirmed,
            )
            self._store.delete_item(conn, project_id, from_matrix, from_stage, item_id)
            self._store.append_event(
                conn,
                project_id=project_id,
                actor_kind=actor.kind,
                actor_ref=actor.ref,
                action="move_matrix_item",
                target=f"{from_matrix}/{item_id}",
                before=self._item_audit_view(item),
                after={"matrix_type": to_matrix, "item_id": new_id, "payload": payload},
                reason=reason,
            )
            moved = self._store.get_item(conn, project_id, to_matrix, to_stage, new_id)
        assert moved is not None
        return moved

    # —— 人工状态动作（应答状态 / 确认；人工动作由 agent 代录时 actor.kind=agent_on_behalf） ——

    def set_item_response_status(
        self,
        project_id: str,
        matrix_type: str,
        item_id: str,
        *,
        status: str,
        note: str | None = None,
        reason: str | None = None,
        expected_version: int | None = None,
        actor: Actor,
    ) -> MatrixItem:
        self._require_matrix_type(matrix_type)
        if matrix_type not in RESPONSE_MATRIX_TYPES:
            raise AssetError(
                "invalid_argument",
                f"应答状态仅对 {' / '.join(RESPONSE_MATRIX_TYPES)} 的 items 区段有效（矩阵：{matrix_type}）",
            )
        if status not in RESPONSE_STATUSES:
            raise AssetError(
                "invalid_argument",
                f"未知应答状态：{status}",
                hint=f"可用值：{', '.join(RESPONSE_STATUSES)}",
            )
        conflict: MatrixItem | None = None
        updated: MatrixItem | None = None
        with self._store.transaction() as conn:
            _, state = self._matrix_state(conn, project_id, matrix_type)
            stage = self._resolve_stage(matrix_type, state)
            item = self._require_item(conn, project_id, matrix_type, stage, item_id)
            self._require_items_section(item)
            if expected_version is not None and expected_version != item.version:
                self._audit_stale_rejection(
                    conn,
                    project_id,
                    action="set_item_response_status",
                    target=f"{matrix_type}/{item_id}",
                    before={
                        "response_status": item.response_status,
                        "response_note": item.response_note,
                    },
                    expected_version=expected_version,
                    current_version=item.version,
                    actor=actor,
                    reason=reason,
                )
                conflict = item
            else:
                changed = self._store.update_item_row(
                    conn, project_id, matrix_type, stage, item_id,
                    expected_version=item.version,
                    response_status=status,
                    response_note=note,
                )
                assert changed, "同事务内的 version 守卫不应落空"
                self._store.append_event(
                    conn,
                    project_id=project_id,
                    actor_kind=actor.kind,
                    actor_ref=actor.ref,
                    action="set_item_response_status",
                    target=f"{matrix_type}/{item_id}",
                    before={"response_status": item.response_status, "response_note": item.response_note},
                    after={"response_status": status, "response_note": note},
                    reason=reason,
                )
                updated = self._store.get_item(conn, project_id, matrix_type, stage, item_id)
        if conflict is not None:
            raise self._version_conflict(matrix_type, item_id, expected_version, conflict.version)
        assert updated is not None
        return updated

    def confirm_item(
        self,
        project_id: str,
        matrix_type: str,
        item_id: str,
        *,
        expected_version: int | None = None,
        actor: Actor,
    ) -> MatrixItem:
        self._require_matrix_type(matrix_type)
        conflict: MatrixItem | None = None
        updated: MatrixItem | None = None
        with self._store.transaction() as conn:
            _, state = self._matrix_state(conn, project_id, matrix_type)
            stage = self._resolve_stage(matrix_type, state)
            item = self._require_item(conn, project_id, matrix_type, stage, item_id)
            self._require_items_section(item)
            if expected_version is not None and expected_version != item.version:
                self._audit_stale_rejection(
                    conn,
                    project_id,
                    action="confirm_matrix_item",
                    target=f"{matrix_type}/{item_id}",
                    before={"confirmed": item.confirmed},
                    expected_version=expected_version,
                    current_version=item.version,
                    actor=actor,
                )
                conflict = item
            else:
                changed = self._store.update_item_row(
                    conn, project_id, matrix_type, stage, item_id,
                    expected_version=item.version,
                    confirmed=True,
                )
                assert changed, "同事务内的 version 守卫不应落空"
                self._store.append_event(
                    conn,
                    project_id=project_id,
                    actor_kind=actor.kind,
                    actor_ref=actor.ref,
                    action="confirm_matrix_item",
                    target=f"{matrix_type}/{item_id}",
                    before={"confirmed": item.confirmed},
                    after={"confirmed": True},
                )
                updated = self._store.get_item(conn, project_id, matrix_type, stage, item_id)
        if conflict is not None:
            raise self._version_conflict(matrix_type, item_id, expected_version, conflict.version)
        assert updated is not None
        return updated

    @staticmethod
    def _require_items_section(item: MatrixItem) -> None:
        if item.section != "items":
            raise AssetError(
                "invalid_argument",
                f"人工状态仅对 items 区段有效（{item.item_id} 属 {item.section}）",
            )

    def set_meta(self, project_id: str, matrix_type: str, *, set: dict, actor: Actor) -> dict:
        """深合并 envelope；靶点规则：有草稿写 draft_meta，无草稿写当前版 meta。"""
        self._require_matrix_type(matrix_type)
        if not isinstance(set, dict) or not set:
            raise AssetError("invalid_argument", "set 必须是非空对象")
        with self._store.transaction() as conn:
            row, state = self._matrix_state(conn, project_id, matrix_type)
            stage = self._resolve_stage(matrix_type, state)
            before = json.loads(row["draft_meta_json"] if stage == "draft" else row["meta_json"])
            merged = deep_merge(before, set)
            if stage == "draft":
                self._store.update_matrix(conn, project_id, matrix_type, draft_meta=merged)
            else:
                self._store.update_matrix(conn, project_id, matrix_type, meta=merged)
            self._store.append_event(
                conn,
                project_id=project_id,
                actor_kind=actor.kind,
                actor_ref=actor.ref,
                action="set_matrix_meta",
                target=matrix_type,
                before=before,
                after=merged,
            )
        return merged

    # —— publish ——

    def publish(
        self,
        project_id: str,
        matrix_type: str,
        *,
        actor: Actor,
        validate: Callable[[dict, list[MatrixItem]], None] | None = None,
    ) -> PublishResult:
        """原子切换：快照（新当前版全量）→ draft 晋升 current → 清草稿。

        validate 是票 02 校验器的接缝：callable(meta, items)，抛 AssetError 即拒绝发布。
        整个切换在单事务内完成，任一步失败整体回滚。
        """
        self._require_matrix_type(matrix_type)
        with self._store.transaction() as conn:
            row, state = self._matrix_state(conn, project_id, matrix_type)
            if state not in _DRAFT_STATES:
                hint = (
                    "已发布矩阵如需变更走行级工具，或 start_matrix_draft(discard_manual_states=true) 重抽"
                    if state is MatrixLifecycle.PUBLISHED
                    else "先 start_matrix_draft 并提交记录"
                )
                raise AssetError(
                    "invalid_state",
                    f"{matrix_type} 不在草稿态（state={state.value}），无可发布内容",
                    hint=hint,
                )
            draft_meta_raw = row["draft_meta_json"]
            meta = json.loads(draft_meta_raw) if draft_meta_raw is not None else json.loads(row["meta_json"])
            items, _ = self._store.list_items(conn, project_id, matrix_type, "draft")
            if validate is not None:
                validate(meta, items)
            new_rev = row["current_rev"] + 1
            snapshot = {
                "schema_version": "1.0",
                "matrix_type": matrix_type,
                "rev": new_rev,
                "meta": meta,
                "records": [
                    {
                        "item_id": item.item_id,
                        "section": item.section,
                        "payload": item.payload,
                        "response_status": item.response_status,
                        "response_note": item.response_note,
                        "confirmed": item.confirmed,
                        "version": item.version,
                    }
                    for item in items
                ],
            }
            self._store.insert_revision(
                conn,
                project_id=project_id,
                matrix_type=matrix_type,
                rev=new_rev,
                snapshot=snapshot,
                published_at=now_iso(),
                actor=actor.label(),
            )
            self._store.delete_stage(conn, project_id, matrix_type, "current")
            self._store.promote_draft_items(conn, project_id, matrix_type)
            self._store.update_matrix(
                conn,
                project_id,
                matrix_type,
                state=MatrixLifecycle.PUBLISHED.value,
                meta=meta,
                clear_draft_meta=True,
                current_rev=new_rev,
            )
            self._store.append_event(
                conn,
                project_id=project_id,
                actor_kind=actor.kind,
                actor_ref=actor.ref,
                action="publish_matrix",
                target=matrix_type,
                before={"state": state.value, "current_rev": row["current_rev"]},
                after={
                    "state": MatrixLifecycle.PUBLISHED.value,
                    "current_rev": new_rev,
                    "record_count": len(items),
                },
            )
        return PublishResult(
            matrix_type=matrix_type,
            rev=new_rev,
            record_count=len(items),
            state=MatrixLifecycle.PUBLISHED,
        )

    def publish_gated(
        self,
        project_id: str,
        matrix_type: str,
        *,
        workspace_root: Path | str,
        actor: Actor,
        thresholds: FidelityThresholds | None = None,
    ) -> PublishResult:
        """无条件挂全套门禁的发布（票 03）：MCP / REST adapter 一律走此入口，
        不暴露 publish(validate=None) 的可选接缝。

        门禁产出的校验报告（无论放行/拒绝）都落一条校验摘要事件，
        matrix_status 的「最近校验摘要」在发布后不陈旧。"""
        reports: list[ValidationReport] = []
        gate = self.publish_gate(
            project_id,
            matrix_type,
            workspace_root=workspace_root,
            thresholds=thresholds,
            on_report=reports.append,
        )
        try:
            result = self.publish(project_id, matrix_type, actor=actor, validate=gate)
        finally:
            # publish 事务已结束（提交或回滚），摘要事件独立落盘
            for report in reports:
                self._record_validation_summary(project_id, matrix_type, report, actor)
        # 发布物化双轨（票 06）：旧路径投影是 best-effort，失败不影响已完成的发布
        try:
            materialize_published_matrices(self, project_id, workspace_root=workspace_root)
        except Exception:
            logger.warning(
                "发布物化投影失败（best-effort，%s/%s 的发布不受影响）",
                project_id,
                matrix_type,
                exc_info=True,
            )
        return result

    # —— 校验（纯读；票 02） ——

    def validate_matrix(
        self,
        project_id: str,
        matrix_type: str,
        *,
        workspace_root: Path | str,
        thresholds: FidelityThresholds | None = None,
        actor: Actor | None = None,
    ) -> ValidationReport:
        """全套校验（结构 / 组装一致性 / 源文保真），可独立于 publish 单独跑。

        默认纯读：不产生任何对象库写入与审计事件。靶点规则与行级动作一致——
        有草稿校验草稿，无草稿校验当前版。传 actor 时额外落一条校验摘要审计
        事件（matrix_status 的「最近校验摘要」数据源），对象数据仍不被触碰。
        """
        self._require_matrix_type(matrix_type)
        with self._store.transaction() as conn:
            row, state = self._matrix_state(conn, project_id, matrix_type)
            stage = "draft" if state in _DRAFT_STATES else "current"
            if row is None:
                meta: dict = {}
            elif stage == "draft":
                draft_meta_raw = row["draft_meta_json"]
                meta = json.loads(draft_meta_raw if draft_meta_raw is not None else row["meta_json"])
            else:
                meta = json.loads(row["meta_json"])
            items, _ = self._store.list_items(conn, project_id, matrix_type, stage)
            documents, _ = self._store.list_documents(
                conn, project_id, limit=DOCUMENTS_FETCH_LIMIT, offset=0
            )
        report = run_full_validation(
            matrix_type,
            meta=meta,
            items=items,
            documents=documents,
            workspace_root=workspace_root,
            thresholds=thresholds,
        )
        if actor is not None:
            self._record_validation_summary(project_id, matrix_type, report, actor)
        return report

    def _record_validation_summary(
        self, project_id: str, matrix_type: str, report: ValidationReport, actor: Actor
    ) -> None:
        """校验摘要审计事件：matrix_status「最近校验摘要」的数据源，对象数据不被触碰。"""
        with self._store.transaction() as conn:
            self._store.append_event(
                conn,
                project_id=project_id,
                actor_kind=actor.kind,
                actor_ref=actor.ref,
                action="validate_matrix",
                target=matrix_type,
                after={
                    "status": report.status,
                    "checked_items": report.checked_items,
                    "error_count": len(report.errors),
                    "warning_count": len(report.warnings),
                },
            )

    def publish_gate(
        self,
        project_id: str,
        matrix_type: str,
        *,
        workspace_root: Path | str,
        thresholds: FidelityThresholds | None = None,
        on_report: Callable[[ValidationReport], None] | None = None,
    ) -> Callable[[dict, list[MatrixItem]], None]:
        """publish 门禁：publish(validate=service.publish_gate(...)) 即全套校验拦截。

        文档快照在进入 publish 事务前取好，避免门禁回调在事务内再开连接。
        """
        self._require_matrix_type(matrix_type)
        with self._store.transaction() as conn:
            documents, _ = self._store.list_documents(
                conn, project_id, limit=DOCUMENTS_FETCH_LIMIT, offset=0
            )
        return make_publish_gate(
            matrix_type,
            documents=documents,
            workspace_root=workspace_root,
            thresholds=thresholds,
            on_report=on_report,
        )

    def get_revision(self, project_id: str, matrix_type: str, *, rev: int) -> dict | None:
        self._require_matrix_type(matrix_type)
        with self._store.transaction() as conn:
            return self._store.get_revision(conn, project_id, matrix_type, rev)

    # —— 读取 ——

    def get_matrix_info(self, project_id: str, matrix_type: str) -> MatrixInfo:
        self._require_matrix_type(matrix_type)
        with self._store.transaction() as conn:
            return self._matrix_info(conn, project_id, matrix_type)

    def get_matrix_overview(self, project_id: str, matrix_type: str) -> MatrixOverview:
        """envelope + 分组统计（不含条目）；统计口径与靶点规则同（有草稿看草稿）。"""
        self._require_matrix_type(matrix_type)
        with self._store.transaction() as conn:
            info = self._matrix_info(conn, project_id, matrix_type)
            stage = "draft" if info.state in _DRAFT_STATES else "current"
            stats = self._store.item_stats(conn, project_id, matrix_type, stage)
        return MatrixOverview(info=info, stats=stats)

    def matrix_status(self, project_id: str) -> list[MatrixStatusEntry]:
        """四矩阵状态一览：state / 两 stage 记录数 / 最近校验摘要（审计事件投影）。"""
        entries: list[MatrixStatusEntry] = []
        with self._store.transaction() as conn:
            for matrix_type in MATRIX_TYPES:
                info = self._matrix_info(conn, project_id, matrix_type)
                event = self._store.last_event(
                    conn, project_id, action="validate_matrix", target=matrix_type
                )
                last_validation = {"ts": event.ts, **(event.after or {})} if event else None
                entries.append(
                    MatrixStatusEntry(
                        matrix_type=matrix_type,
                        state=info.state,
                        current_rev=info.current_rev,
                        updated_at=info.updated_at,
                        draft_count=self._store.count_items(conn, project_id, matrix_type, "draft"),
                        current_count=self._store.count_items(
                            conn, project_id, matrix_type, "current"
                        ),
                        last_validation=last_validation,
                    )
                )
        return entries

    def query_items(
        self,
        project_id: str,
        matrix_type: str,
        *,
        stage: str | None = None,
        section: str | None = None,
        response_status: str | None = None,
        confirmed: bool | None = None,
        category: str | None = None,
        mandatory: bool | None = None,
        keyword: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[MatrixItem], int]:
        """默认按靶点规则读（有草稿读草稿，无草稿读当前版）；stage 可显式指定。"""
        self._require_matrix_type(matrix_type)
        with self._store.transaction() as conn:
            if stage is None:
                row = self._store.get_matrix(conn, project_id, matrix_type)
                state = MatrixLifecycle(row["state"]) if row is not None else MatrixLifecycle.EMPTY
                stage = "draft" if state in _DRAFT_STATES else "current"
            return self._store.list_items(
                conn,
                project_id,
                matrix_type,
                stage,
                section=section,
                response_status=response_status,
                confirmed=confirmed,
                category=category,
                mandatory=mandatory,
                keyword=keyword,
                limit=limit,
                offset=offset,
            )

    def _matrix_info(
        self, conn: sqlite3.Connection, project_id: str, matrix_type: str
    ) -> MatrixInfo:
        row = self._store.get_matrix(conn, project_id, matrix_type)
        if row is None:
            return MatrixInfo(
                project_id=project_id,
                matrix_type=matrix_type,
                state=MatrixLifecycle.EMPTY,
                meta={},
                draft_meta=None,
                current_rev=0,
                updated_at=None,
            )
        draft_meta_raw = row["draft_meta_json"]
        return MatrixInfo(
            project_id=project_id,
            matrix_type=matrix_type,
            state=MatrixLifecycle(row["state"]),
            meta=json.loads(row["meta_json"]),
            draft_meta=json.loads(draft_meta_raw) if draft_meta_raw is not None else None,
            current_rev=row["current_rev"],
            updated_at=row["updated_at"],
        )

    def _require_item(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        matrix_type: str,
        stage: str,
        item_id: str,
    ) -> MatrixItem:
        item = self._store.get_item(conn, project_id, matrix_type, stage, item_id)
        if item is None:
            raise AssetError(
                "item_not_found",
                f"{matrix_type} 的{'草稿' if stage == 'draft' else '当前版'}中不存在条目 {item_id}",
                hint="用 query_matrix_items 确认条目 id 后重试",
            )
        return item

    @staticmethod
    def _item_audit_view(item: MatrixItem) -> dict:
        return {
            "section": item.section,
            "payload": item.payload,
            "response_status": item.response_status,
            "response_note": item.response_note,
            "confirmed": item.confirmed,
            "version": item.version,
        }

    def _matrix_state(
        self, conn: sqlite3.Connection, project_id: str, matrix_type: str
    ) -> tuple[sqlite3.Row | None, MatrixLifecycle]:
        row = self._store.get_matrix(conn, project_id, matrix_type)
        state = MatrixLifecycle(row["state"]) if row is not None else MatrixLifecycle.EMPTY
        return row, state

    @staticmethod
    def _resolve_stage(matrix_type: str, state: MatrixLifecycle) -> str:
        """行级动作靶点规则：有草稿写草稿，无草稿写当前版（=增量维护）。"""
        if state in _DRAFT_STATES:
            return "draft"
        if state is MatrixLifecycle.PUBLISHED:
            return "current"
        raise AssetError(
            "matrix_empty",
            f"{matrix_type} 尚无任何版本，行级动作无靶点",
            hint="先 start_matrix_draft 开启草稿并 submit_matrix_records 提交记录",
        )

    # —— 校验助手 ——

    @staticmethod
    def _require_matrix_type(matrix_type: str) -> None:
        if matrix_type not in MATRIX_TYPES:
            raise AssetError(
                "invalid_matrix_type",
                f"未知矩阵类型：{matrix_type}",
                hint=f"可用类型：{', '.join(MATRIX_TYPES)}",
            )

    @staticmethod
    def _require_section(matrix_type: str, section: str) -> None:
        allowed = ALLOWED_SECTIONS[matrix_type]
        if section not in allowed:
            raise AssetError(
                "invalid_section",
                f"{matrix_type} 不接受区段 {section}",
                hint=f"可用区段：{', '.join(allowed)}",
            )

    # —— 审计读取 ——

    def list_events(
        self,
        project_id: str,
        *,
        target: str | None = None,
        action: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[AssetEvent]:
        with self._store.transaction() as conn:
            return self._store.list_events(
                conn, project_id, target=target, action=action, limit=limit, offset=offset
            )


# —— 单例接线 ——
# 对象库挂现有 hagent SQLite（与 SessionStore/ProjectStore 同库），路径约定
# 镜像 server/projects.get_project_store：app 装配处 set，未装配时按环境变量兜底自建。
_ASSET_SERVICE: AssetService | None = None


def set_asset_service(service: AssetService | None) -> None:
    global _ASSET_SERVICE
    _ASSET_SERVICE = service


def get_asset_service() -> AssetService:
    global _ASSET_SERVICE
    if _ASSET_SERVICE is None:
        from hagent.config import resolve_sessions_db_path

        db_path = resolve_sessions_db_path()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _ASSET_SERVICE = AssetService(AssetStore(db_path))
    return _ASSET_SERVICE
