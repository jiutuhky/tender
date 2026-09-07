"use client";

import { useId, useRef, useState } from "react";
import { useWorkspaceStore } from "@/lib/store/workspace";
import { MatrixWriteConflictError } from "@/lib/hagent/api";
import { prettyLabel } from "@/lib/hagent/naming";
import {
  fmtLineSpan,
  fmtSourceRefs,
  type MatrixType,
  type MatrixItemRow,
  type ResponseStatus,
  type RequirementItem,
  type SourceRef,
} from "@/lib/hagent/matrix";
import { assessSourceRef } from "@/lib/trace/refs";
import { CheckIcon, FileIcon } from "@/components/ui/icons";
import { useTrace, type TraceClaim } from "./traceContext";

type ClaimInfo = Omit<TraceClaim, "itemKey" | "refs" | "refIndex">;

/** 来源使用文件名与章节表达，定位行号作为辅助信息；不可用原因始终可读。 */
export function SourceChips({
  refs,
  itemKey,
  claim,
}: {
  refs: SourceRef[];
  itemKey: string;
  claim?: ClaimInfo;
}) {
  const trace = useTrace();
  const sourceId = useId();
  if (!refs.length) return <p className="rd-muted">未提供原文来源</p>;
  if (!trace)
    return (
      <span className="rd-muted">
        {fmtSourceRefs(refs) || "未提供原文定位"}
      </span>
    );
  return (
    <div className="rd-sources">
      {refs.map((ref, i) => {
        const doc = ref.document_id
          ? trace.registry?.get(ref.document_id)
          : null;
        const name = doc
          ? prettyLabel(doc.path.split("/").pop() || doc.path)
          : "来源文档";
        const usability = assessSourceRef(
          ref,
          trace.registryStatus,
          trace.registry,
        );
        const chipKey = `${itemKey}:${i}`;
        const reasonId = `${sourceId}-${i}`;
        return (
          <div className="rd-source" key={chipKey}>
            <button
              type="button"
              className="rd-source-link"
              data-chip-key={chipKey}
              aria-disabled={!usability.usable || undefined}
              aria-describedby={!usability.usable ? reasonId : undefined}
              onClick={() => {
                if (usability.usable)
                  trace.openTrace(
                    ref,
                    chipKey,
                    claim
                      ? { ...claim, itemKey, refs, refIndex: i }
                      : undefined,
                  );
              }}
            >
              <FileIcon width={15} height={15} aria-hidden="true" />
              <span>
                查看原文 · {name}
                {ref.section ? ` / ${ref.section}` : ""}
              </span>
            </button>
            {fmtLineSpan(ref.line_span) && (
              <span className="rd-source-lines">
                {fmtLineSpan(ref.line_span)}
              </span>
            )}
            {!usability.usable && (
              <span id={reasonId} className="rd-source-reason">
                {usability.reason}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** 规则与分包的来源列表，缺失提示与条目保持一致。 */
export function SourceRow({
  refs,
  itemKey,
  claim,
}: {
  refs: SourceRef[];
  itemKey: string;
  claim?: ClaimInfo;
}) {
  return (
    <div className="cv-src-row">
      <SourceChips refs={refs} itemKey={itemKey} claim={claim} />
    </div>
  );
}

/** 条目底部来源行:签身份取条目业务 id,缺 id 回退 useId 稳定实例键 */
export function SourceLine({
  item,
  type,
  index,
}: {
  item: RequirementItem;
  type: MatrixType;
  index: number;
}) {
  const fallbackId = useId();

  return (
    <SourceChips
      refs={item.source_refs ?? []}
      itemKey={item.id ?? fallbackId}
      claim={{
        matrixType: type,
        itemId: item.id ?? null,
        label: item.id ?? `#${index + 1}`,
        title: item.title || "未命名条目",
        requirementText: item.requirement_text ?? "",
        mandatory: !!item.mandatory,
        paramNature: item.param_nature ?? null,
        highRisk: item.risk_level === "high",
      }}
    />
  );
}

/* ---------- 条目行人工动作(确认 / 应答状态标注,REST 落对象库) ---------- */

/** 签面文案与语义色修饰类同源:与状态徽标口径一致(绿=合规、蓝=正偏离、橙=负偏离) */
export const RESPONSE_STATUS_OPTS: Array<{
  k: ResponseStatus;
  label: string;
  cls: string;
}> = [
  { k: "compliant", label: "合规", cls: "is-compliant" },
  { k: "positive_deviation", label: "正偏离", cls: "is-positive" },
  { k: "negative_deviation", label: "负偏离", cls: "is-negative" },
];

/** 人工动作的在途/失败态 + 落库调用,按条目局部呈现不打扰其余条目。
 *  条目行与预览层对照条共用同一份 —— 冲突提示等口径只写一遍。 */
export function useItemAction(type: MatrixType) {
  const confirmItem = useWorkspaceStore((s) => s.confirmItem);
  const setItemResponseStatus = useWorkspaceStore(
    (s) => s.setItemResponseStatus,
  );
  const inFlight = useRef(new Set<string>());
  const [busyIds, setBusyIds] = useState(new Set<string>());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [savedIds, setSavedIds] = useState(new Set<string>());
  const runItemAction = (id: string, action: () => Promise<void>) => {
    if (inFlight.current.has(id)) return;
    inFlight.current.add(id);
    setBusyIds(new Set(inFlight.current));
    setErrors((cur) => ({ ...cur, [id]: "" }));
    setNotice("");
    setSavedIds((cur) => {
      const next = new Set(cur);
      next.delete(id);
      return next;
    });
    action()
      .then(() => {
        setNotice(`${id} 已保存`);
        setSavedIds((cur) => new Set(cur).add(id));
      })
      .catch((e: unknown) => {
        const msg =
          e instanceof MatrixWriteConflictError
            ? "该条目已被其他会话更新，已刷新为最新版本，请核对后重试"
            : "保存失败，请检查连接后重试。原有状态已保留。";
        setErrors((cur) => ({ ...cur, [id]: msg }));
      })
      .finally(() => {
        inFlight.current.delete(id);
        setBusyIds(new Set(inFlight.current));
      });
  };
  return {
    busyIds,
    errors,
    notice,
    savedIds,
    confirm: (itemId: string) =>
      runItemAction(itemId, () => confirmItem(type, itemId)),
    setStatus: (itemId: string, status: ResponseStatus) =>
      runItemAction(itemId, () => setItemResponseStatus(type, itemId, status)),
  };
}

export function ItemActions({
  row,
  busy,
  error,
  onConfirm,
  onSetStatus,
  showHint = true,
}: {
  row: MatrixItemRow;
  busy: boolean;
  error: string | null;
  onConfirm: () => void;
  onSetStatus: (status: ResponseStatus) => void;
  showHint?: boolean;
}) {
  return (
    <div className="cv-item-actions" aria-busy={busy}>
      <div className="rd-response">
        <span className="rd-field-label">应答判断</span>
        <div
          className="rd-response-options"
          role="group"
          aria-label="应答状态标注"
        >
          {RESPONSE_STATUS_OPTS.map((o) => {
            const active = row.response_status === o.k;
            return (
              <button
                key={o.k}
                type="button"
                className={active ? `is-active ${o.cls}` : o.cls}
                aria-pressed={active}
                disabled={busy}
                onClick={() => {
                  if (!active) onSetStatus(o.k);
                }}
              >
                {o.label}
              </button>
            );
          })}
        </div>
      </div>
      <button
        type="button"
        className={row.confirmed ? "cv-item-confirm is-on" : "cv-item-confirm"}
        disabled={busy || row.confirmed}
        onClick={onConfirm}
      >
        {/* 勾号走 Phosphor 图标,不用 Unicode 图形字符 ✓ */}
        {row.confirmed ? (
          <>
            <CheckIcon width={12} height={12} aria-hidden="true" />
            已核验
          </>
        ) : busy ? (
          "保存中…"
        ) : (
          "核验确认"
        )}
      </button>
      {showHint && (
        <span className="rd-action-hint">
          核验确认仅标记已核对，不代表合规。
        </span>
      )}
      {row.response_note && (
        <span className="cv-item-note">备注 {row.response_note}</span>
      )}
      {error && (
        <span className="cv-item-action-err" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
