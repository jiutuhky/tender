"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useWorkspaceStore } from "@/lib/store/workspace";
import { getDocumentRegistry, type DocumentRecord } from "@/lib/hagent/documents";
import { assessSourceRef, type RegistryStatus } from "@/lib/trace/refs";
import type { MatrixType, SourceRef } from "@/lib/hagent/matrix";

// 溯源预览的抽屉层局部状态:文档注册表 + 活跃 ref + 被核验条目(对照区数据)。
// 有意不进全局 workspace store(SSE 批处理是 store 的性能关键路径);
// 状态挂在 CanvasDrawer 上,随抽屉卸载整体销毁 = 「关抽屉整体重置」的生命周期决策。

/** 对照区数据:预览层盖住条目列表后,把「正在核验什么」随签一起带进浮层。
 *  一律是纯数据 —— 不要往里塞 ReactNode,快照会僵死(点完确认对照区不刷新)。
 *  行级管理状态(确认/应答)由对照区按 matrixType + itemId 自行从 store 读实时值。 */
export interface TraceClaim {
  /** 签身份命名空间,与 SourceChips 的 itemKey 同源;切换来源文件时据此重建 activeKey */
  itemKey: string;
  matrixType: MatrixType;
  /** null = 评分项/否决项等无行级管理状态的来源,对照区只呈现文案不给人工动作 */
  itemId: string | null;
  label: string;
  title: string;
  requirementText: string;
  mandatory?: boolean;
  /** 「参数性质」列原文符号(★/▲);对照区据此与条目列表用同一枚标记 */
  paramNature?: "★" | "▲" | null;
  highRisk?: boolean;
  /** 该条目的全部来源,供层内步进器逐条走完 */
  refs: SourceRef[];
  /** 当前落在第几条(0-based) */
  refIndex: number;
}

export interface TraceContextValue {
  /** document_id → 注册表记录;null = 注册表未就绪(载入中或失败),签一律置灰 */
  registry: Map<string, DocumentRecord> | null;
  /** 注册表载入状态:签的置灰原因说明据此分流(lib/trace/refs.assessSourceRef) */
  registryStatus: RegistryStatus;
  projectId: string | null;
  /** 当前活跃 ref(打开预览层的来源);null = 未开层 */
  activeRef: SourceRef | null;
  /** 活跃签身份(条目 id + ref 序号):点亮判定按签而非按值,值相同的重复 ref 只亮被点的那枚 */
  activeKey: string | null;
  /** 每次 openTrace 递增:已活跃的签重点一次也要重新滚动定位 */
  activeSeq: number;
  /** 被核验条目;null = 无对照数据(mock 详情或未带 claim 的调用) */
  activeClaim: TraceClaim | null;
  openTrace: (ref: SourceRef, key: string, claim?: TraceClaim) => void;
  closeTrace: () => void;
  nextPending: () => void;
  nextPendingCount: number;
  claimIndex: number;
  claimCount: number;
  stepClaim: (delta: 1 | -1) => void;
  retryRegistry: () => void;
}

export const TraceContext = createContext<TraceContextValue | null>(null);

/** 来源签/预览层消费;mock 详情等无 Provider 场景返回 null,调用方回退纯文本来源行 */
export function useTrace(): TraceContextValue | null {
  return useContext(TraceContext);
}

/** 抽屉持有的溯源状态源:enabled(真实矩阵卡)才载注册表。
 *  activeDoc 由活跃 ref 对注册表解析而来,是预览层开合与取数的唯一依据。 */
export function useTraceState(enabled: boolean): {
  ctx: TraceContextValue;
  activeDoc: DocumentRecord | null;
} {
  const projectId = useWorkspaceStore((s) => s.projectId);
  const matrices = useWorkspaceStore((s) => s.matrices);
  const [revision, setRevision] = useState(0);
  const [registry, setRegistry] = useState<Map<string, DocumentRecord> | null>(null);
  const [registryStatus, setRegistryStatus] = useState<RegistryStatus>("loading");
  const [active, setActive] = useState<{
    ref: SourceRef;
    key: string;
    seq: number;
    claim: TraceClaim | null;
  } | null>(null);

  // 注册表随抽屉详情按需载入(数据层已做项目级缓存与 in-flight 去重)。
  // 失败不打扰核验主流程:签保持置灰、悬停给出原因(票03 分层容错);
  // 数据层不缓存失败,下次开抽屉自然重试。
  useEffect(() => {
    if (!enabled || !projectId) return;
    let alive = true;
    getDocumentRegistry(projectId)
      .then((records) => {
        if (!alive) return;
        setRegistry(new Map(records.map((r) => [r.id, r])));
        setRegistryStatus("ready");
      })
      .catch((err: unknown) => {
        console.warn("溯源预览：文档注册表载入失败", err);
        if (alive) setRegistryStatus("failed");
      });
    return () => {
      alive = false;
    };
  }, [enabled, projectId, revision]);

  const openTrace = useCallback(
    (ref: SourceRef, key: string, claim?: TraceClaim) =>
      setActive((prev) => ({ ref, key, seq: (prev?.seq ?? 0) + 1, claim: claim ?? null })),
    [],
  );
  const closeTrace = useCallback(() => setActive(null), []);

  const retryRegistry = useCallback(() => {
    setRegistryStatus("loading");
    setRevision((v) => v + 1);
  }, []);
  const reviewClaims = useMemo<TraceClaim[]>(() => {
    const type = active?.claim?.matrixType;
    if (type !== "business" && type !== "technical") return [];
    const slot = matrices[type];
    const rows = new Set((slot.itemRows ?? []).map((row) => row.item_id));
    return (slot.data?.items ?? []).flatMap((item): TraceClaim[] => {
      if (!item.id || !rows.has(item.id)) return [];
      const refs = item.source_refs ?? [];
      const index = refs.findIndex((ref) => assessSourceRef(ref, registryStatus, registry).usable);
      if (index < 0) return [];
      return [{ itemKey: item.id, itemId: item.id, matrixType: type, label: item.id,
        title: item.title || "未命名条目", requirementText: item.requirement_text ?? "",
        mandatory: !!item.mandatory, paramNature: item.param_nature, highRisk: item.risk_level === "high",
        refs, refIndex: index }];
    });
  }, [active?.claim?.matrixType, matrices, registryStatus, registry]);
  const claimIndex = reviewClaims.findIndex((claim) => claim.itemKey === active?.claim?.itemKey);
  const pendingClaims = useMemo(() => {
    const type = active?.claim?.matrixType;
    if (type !== "business" && type !== "technical") return [];
    const confirmed = new Set((matrices[type].itemRows ?? []).filter((row) => row.confirmed).map((row) => row.item_id));
    return [...reviewClaims.slice(claimIndex + 1), ...reviewClaims.slice(0, Math.max(0, claimIndex))]
      .filter((claim) => claim.itemId && !confirmed.has(claim.itemId));
  }, [reviewClaims, claimIndex, active?.claim?.matrixType, matrices]);
  const stepClaim = useCallback((delta: 1 | -1) => {
    const claim = reviewClaims[claimIndex + delta];
    const ref = claim?.refs[claim.refIndex];
    if (claim && ref) openTrace(ref, `${claim.itemKey}:${claim.refIndex}`, claim);
  }, [reviewClaims, claimIndex, openTrace]);
  const nextPending = useCallback(() => {
    const claim = pendingClaims[0];
    const ref = claim?.refs[claim.refIndex];
    if (claim && ref) openTrace(ref, `${claim.itemKey}:${claim.refIndex}`, claim);
  }, [pendingClaims, openTrace]);

  const ctx = useMemo<TraceContextValue>(
    () => ({
      registry,
      registryStatus,
      projectId,
      activeRef: active?.ref ?? null,
      activeKey: active?.key ?? null,
      activeSeq: active?.seq ?? 0,
      activeClaim: active?.claim ?? null,
      openTrace,
      closeTrace,
      nextPending,
      nextPendingCount: pendingClaims.length,
      claimIndex,
      claimCount: reviewClaims.length,
      stepClaim,
      retryRegistry,
    }),
    [registry, registryStatus, projectId, active, openTrace, closeTrace, nextPending, pendingClaims.length, claimIndex, reviewClaims.length, stepClaim, retryRegistry],
  );
  const activeDoc =
    (active?.ref.document_id ? registry?.get(active.ref.document_id) : undefined) ?? null;

  return { ctx, activeDoc };
}
