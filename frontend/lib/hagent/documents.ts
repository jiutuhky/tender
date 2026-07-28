// 溯源预览数据层:文档注册表与原文内容缓存。
// 不进 workspace store(SSE 批处理是 store 的性能关键路径),模块级单项目缓存:
// 注册表与内容跨抽屉开合复用,按 document_id 缓存、sha256 作内容版本键、项目切换整体失效。

import {
  fetchAllDocuments,
  getWorkspaceFileText,
  type DocumentRecord,
} from "@/lib/hagent/api";

export type { DocumentRecord };

interface ContentEntry {
  sha256: string;
  content: Promise<string>;
}

let cacheProjectId: string | null = null;
let registryPromise: Promise<DocumentRecord[]> | null = null;
const contentCache = new Map<string, ContentEntry>();

/** 单项目缓存:换项目即整体失效(注册表 + 内容)。 */
function ensureProject(pid: string): void {
  if (cacheProjectId !== pid) {
    cacheProjectId = pid;
    registryPromise = null;
    contentCache.clear();
  }
}

/** 文档注册表(项目内复用,in-flight 去重;失败不缓存,下次调用重试)。 */
export function getDocumentRegistry(pid: string): Promise<DocumentRecord[]> {
  ensureProject(pid);
  if (!registryPromise) {
    const p = fetchAllDocuments(pid).catch((err: unknown) => {
      if (registryPromise === p) registryPromise = null;
      throw err;
    });
    registryPromise = p;
  }
  return registryPromise;
}

/** 文档原文:同 document_id 且 sha256 未变时命中缓存(含 in-flight 去重);
 * sha256 变化视为新版本重取;失败不缓存,重试走新请求。 */
export function getDocumentContent(pid: string, doc: DocumentRecord): Promise<string> {
  ensureProject(pid);
  const hit = contentCache.get(doc.id);
  if (hit && hit.sha256 === doc.sha256) return hit.content;
  const content: Promise<string> = getWorkspaceFileText(pid, doc.path).catch(
    (err: unknown) => {
      // 仅当缓存里仍是本次请求时清除,避免误删并发的后来者
      if (contentCache.get(doc.id)?.content === content) contentCache.delete(doc.id);
      throw err;
    },
  );
  contentCache.set(doc.id, { sha256: doc.sha256, content });
  return content;
}

/** 显式清空(登出/测试用;常规项目切换由 pid 判定自动失效)。 */
export function resetDocumentCaches(): void {
  cacheProjectId = null;
  registryPromise = null;
  contentCache.clear();
}
