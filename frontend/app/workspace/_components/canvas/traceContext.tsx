"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useWorkspaceStore } from "@/lib/store/workspace";
import { getDocumentRegistry, type DocumentRecord } from "@/lib/hagent/documents";
import type { RegistryStatus } from "@/lib/trace/refs";
import type { SourceRef } from "@/lib/hagent/matrix";

// 溯源预览的抽屉层局部状态:文档注册表 + 活跃 ref + 双栏开合。
// 有意不进全局 workspace store(SSE 批处理是 store 的性能关键路径);
// 状态挂在 CanvasDrawer 上,随抽屉卸载整体销毁 = 「关抽屉整体重置」的生命周期决策。

export interface TraceContextValue {
  /** document_id → 注册表记录;null = 注册表未就绪(载入中或失败),签一律置灰 */
  registry: Map<string, DocumentRecord> | null;
  /** 注册表载入状态:签的置灰原因说明据此分流(lib/trace/refs.assessSourceRef) */
  registryStatus: RegistryStatus;
  projectId: string | null;
  /** 当前活跃 ref(打开原文面板的来源);null = 单栏 */
  activeRef: SourceRef | null;
  /** 活跃签身份(条目 id + ref 序号):点亮判定按签而非按值,值相同的重复 ref 只亮被点的那枚 */
  activeKey: string | null;
  /** 每次 openTrace 递增:已活跃的签重点一次也要重新滚动定位 */
  activeSeq: number;
  openTrace: (ref: SourceRef, key: string) => void;
  closeTrace: () => void;
}

export const TraceContext = createContext<TraceContextValue | null>(null);

/** 来源签/原文面板消费;mock 详情等无 Provider 场景返回 null,调用方回退纯文本来源行 */
export function useTrace(): TraceContextValue | null {
  return useContext(TraceContext);
}

/** 抽屉持有的溯源状态源:enabled(真实矩阵卡)才载注册表。
 *  activeDoc 由活跃 ref 对注册表解析而来,是双栏开合与面板取数的唯一依据。 */
export function useTraceState(enabled: boolean): {
  ctx: TraceContextValue;
  activeDoc: DocumentRecord | null;
} {
  const projectId = useWorkspaceStore((s) => s.projectId);
  const [registry, setRegistry] = useState<Map<string, DocumentRecord> | null>(null);
  const [registryStatus, setRegistryStatus] = useState<RegistryStatus>("loading");
  const [active, setActive] = useState<{ ref: SourceRef; key: string; seq: number } | null>(null);

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
        console.warn("溯源预览:文档注册表载入失败", err);
        if (alive) setRegistryStatus("failed");
      });
    return () => {
      alive = false;
    };
  }, [enabled, projectId]);

  const openTrace = useCallback(
    (ref: SourceRef, key: string) => setActive((prev) => ({ ref, key, seq: (prev?.seq ?? 0) + 1 })),
    [],
  );
  const closeTrace = useCallback(() => setActive(null), []);

  const ctx = useMemo<TraceContextValue>(
    () => ({
      registry,
      registryStatus,
      projectId,
      activeRef: active?.ref ?? null,
      activeKey: active?.key ?? null,
      activeSeq: active?.seq ?? 0,
      openTrace,
      closeTrace,
    }),
    [registry, registryStatus, projectId, active, openTrace, closeTrace],
  );
  const activeDoc =
    (active?.ref.document_id ? registry?.get(active.ref.document_id) : undefined) ?? null;

  return { ctx, activeDoc };
}
