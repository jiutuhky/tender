"use client";

import { useEffect, useRef, useState } from "react";
import { useWorkspaceStore } from "@/lib/store/workspace";
import { MatrixWriteConflictError } from "@/lib/hagent/api";
import type { ResponseStatus } from "@/lib/hagent/matrix";
import { CheckIcon, ChevronLeftIcon, ChevronRightIcon, WarningIcon } from "@/components/ui/icons";
import { ImportantMark, MandatoryMark, RiskMark } from "./matrixViews";
import { useTrace, type TraceClaim } from "./traceContext";

/** 原文旁的核验区；操作结果直接取对象库状态，切换条目不改变阅读器生命周期。 */
export function TraceInspector({ claim, locationsRef, hasPdf }: {
  claim: TraceClaim; locationsRef: (element: HTMLDivElement | null) => void; hasPdf: boolean;
}) {
  const trace = useTrace();
  const confirmItem = useWorkspaceStore((s) => s.confirmItem);
  const setStatus = useWorkspaceStore((s) => s.setItemResponseStatus);
  const row = useWorkspaceStore((s) => s.matrices[claim.matrixType].itemRows?.find((r) => r.item_id === claim.itemId));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const hasNext = !!trace?.nextPendingCount;
  const save = async (action: () => Promise<void>, advance = false) => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError("");
    try {
      await action();
      if (mounted.current && advance) trace?.nextPending();
    } catch (reason) {
      if (mounted.current) setError(reason instanceof MatrixWriteConflictError ? "条目已更新，请重新核对。" : "保存失败，请重试。");
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  };
  const confirm = () => {
    if (!row) return;
    if (row.confirmed) { trace?.nextPending(); return; }
    void save(() => confirmItem(claim.matrixType, row.item_id), hasNext);
  };
  const currentRefs = claim.refs.map((ref, index) => ({ ref, index })).filter(({ ref }) => ref.document_id === trace?.activeRef?.document_id);

  return <>
    <div className="trace-inspector-head">
      <span className="trace-item-id">{claim.label}</span>
      {trace && trace.claimCount > 1 && trace.claimIndex >= 0 && <div className="trace-item-nav" role="group" aria-label={`第 ${trace.claimIndex + 1} 条，共 ${trace.claimCount} 条`}>
        <button type="button" className="trace-icon-button" title="上一条" aria-label="上一条核验条目" disabled={busy || trace.claimIndex === 0} onClick={() => trace.stepClaim(-1)}><ChevronLeftIcon width={16} height={16} /></button>
        <button type="button" className="trace-icon-button" title="下一条" aria-label="下一条核验条目" disabled={busy || trace.claimIndex === trace.claimCount - 1} onClick={() => trace.stepClaim(1)}><ChevronRightIcon width={16} height={16} /></button>
      </div>}
    </div>
    <div className="trace-inspector-scroll">
      <h2 className="trace-item-title">{claim.title}</h2>
      {(claim.mandatory || claim.paramNature === "▲" || claim.highRisk) && <div className="trace-item-mark">
        {claim.mandatory ? <MandatoryMark full /> : claim.paramNature === "▲" ? <ImportantMark full /> : <RiskMark />}
      </div>}
      <div ref={locationsRef} className="trace-locations" aria-label="原文位置">
        {!hasPdf && currentRefs.map(({ ref, index }) => <button type="button" key={index} className="trace-location" aria-pressed={index === claim.refIndex}
          onClick={() => trace?.openTrace(ref, `${claim.itemKey}:${index}`, { ...claim, refIndex: index })}>
          {ref.section || `来源 ${index + 1}`}
        </button>)}
      </div>
      {claim.requirementText.trim() && <p className="trace-item-copy">{claim.requirementText.trim()}</p>}
    </div>
    {row && <div className="trace-review" aria-busy={busy}>
      <label className={`trace-response${row.response_status ? ` is-${row.response_status}` : ""}`}>
        <span className="trace-response-dot" aria-hidden />
        <select aria-label="应答状态" value={row.response_status ?? ""} disabled={busy} onChange={(e) => {
          const value = e.target.value;
          if (value) void save(() => setStatus(claim.matrixType, row.item_id, value as ResponseStatus));
        }}>
          <option value="" disabled>应答状态</option>
          <option value="compliant">合规</option><option value="positive_deviation">正偏离</option><option value="negative_deviation">负偏离</option>
        </select>
        {row.confirmed && hasNext && <span className="trace-confirmed"><CheckIcon width={13} height={13} />已核验</span>}
      </label>
      {error && <p className="trace-action-error" role="alert"><WarningIcon width={14} height={14} />{error}</p>}
      <div className="trace-review-buttons">
        {!row.confirmed && hasNext && <button type="button" className="trace-skip" disabled={busy} onClick={() => trace?.nextPending()}>跳过</button>}
        <button type="button" className="trace-confirm" disabled={busy || !!row.confirmed && !hasNext} onClick={confirm}>
          {busy ? "保存中…" : row.confirmed ? hasNext ? "继续核验" : "已核验" : hasNext ? "确认并继续" : "确认核验"}
          {row.confirmed && !hasNext ? <CheckIcon width={15} height={15} /> : <ChevronRightIcon width={15} height={15} />}
        </button>
      </div>
    </div>}
  </>;
}
