// 溯源预览纯逻辑(票03):签可用性分层判定、源行号→渲染块映射。
// 零 DOM 依赖,组件只消费判定结果。容错分层的口径以本模块为准,三类互不串扰:
//   签不可用(缺 document_id / 注册表未就绪 / 载入失败 / 不在注册表)→ 置灰 + 悬停原因;
//   文件读取失败 → 面板错误态 + 重试(TracePanel 错误边界,不经本模块);
//   line_span 缺失/越界/落空行 → 「未能定位」黄条,照常开文档,不滚动不高亮。

import type { SourceRef } from "@/lib/hagent/matrix";
import type { DocBlock } from "./blocks";

/** 文档注册表载入状态(traceContext 持有):签的置灰原因据此分流 */
export type RegistryStatus = "loading" | "ready" | "failed";

export type RefUsability =
  | { usable: true; documentId: string }
  | { usable: false; reason: string };

/** 签可用性分层判定:不可用时给出悬停原因说明(坏数据可见,不静默吞掉) */
export function assessSourceRef(
  ref: SourceRef,
  registryStatus: RegistryStatus,
  registry: ReadonlyMap<string, unknown> | null,
): RefUsability {
  const id = ref.document_id;
  if (!id) return { usable: false, reason: "该来源未标注文档，无法溯源" };
  if (registryStatus === "loading") return { usable: false, reason: "文档注册表载入中，请稍候" };
  if (registryStatus === "failed")
    return { usable: false, reason: "文档注册表载入失败，重新打开抽屉可重试" };
  if (!registry?.has(id))
    return { usable: false, reason: "来源文档不在项目文档注册表中，请人工核对" };
  return { usable: true, documentId: id };
}

export type SpanAnchor =
  | { status: "located"; startLine: number; endLine: number; blockIndices: number[] }
  | { status: "unlocatable" };

/** 源行号→渲染块映射:与 line_span(1-based 闭区间)相交的块整块命中。
 *  契约为 [start, end];LLM 数据防御性取 min/max(单点 [n] 视作 [n, n],反序照常成立)。
 *  缺失、非整数、越界、或行区全落在空行上(无可高亮块)一律判未能定位。 */
export function locateSpan(
  blocks: readonly DocBlock[],
  span: number[] | undefined,
  totalLines: number,
): SpanAnchor {
  if (!span?.length || !span.every((n) => Number.isInteger(n))) return { status: "unlocatable" };
  const startLine = Math.min(...span);
  const endLine = Math.max(...span);
  if (startLine < 1 || endLine > totalLines) return { status: "unlocatable" };
  const blockIndices: number[] = [];
  blocks.forEach((b, i) => {
    if (b.startLine <= endLine && b.endLine >= startLine) blockIndices.push(i);
  });
  if (blockIndices.length === 0) return { status: "unlocatable" };
  return { status: "located", startLine, endLine, blockIndices };
}
