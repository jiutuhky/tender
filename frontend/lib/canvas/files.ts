import {
  fetchAllDocuments,
  listWorkspaceFiles,
  uploadProjectFile,
} from "@/lib/hagent/api";
import { uniquePath } from "./model";
import type { CanvasEntity } from "./model";

export interface ImportFile {
  file: File;
  path: string;
}

/** readEntries 必须循环到空批次，浏览器一次通常只返回前 100 个目录成员。 */
export async function filesFromDrop(
  transfer: DataTransfer,
): Promise<ImportFile[]> {
  const entries = Array.from(transfer.items)
    .map((item) => item.webkitGetAsEntry?.())
    .filter((entry): entry is FileSystemEntry => Boolean(entry));
  if (!entries.length)
    return Array.from(transfer.files).map((file) => ({
      file,
      path: file.name,
    }));
  const files: ImportFile[] = [];
  const visit = async (entry: FileSystemEntry, parent: string) => {
    const path = `${parent}${entry.name}`;
    if (entry.isFile) {
      const file = await new Promise<File>((resolve, reject) =>
        (entry as FileSystemFileEntry).file(resolve, reject),
      );
      files.push({ file, path });
    } else if (entry.isDirectory) {
      const reader = (entry as FileSystemDirectoryEntry).createReader();
      for (;;) {
        const batch = await new Promise<FileSystemEntry[]>((resolve, reject) =>
          reader.readEntries(resolve, reject),
        );
        if (!batch.length) break;
        for (const child of batch) await visit(child, `${path}/`);
      }
    }
  };
  for (const entry of entries) await visit(entry, "");
  return files;
}

export interface UploadItem extends ImportFile {
  id: string;
  status: "queued" | "working" | "processing" | "ready" | "error";
  error?: string;
  originSha256?: string;
  previewUrl?: string;
  parsing?: boolean;
}

export async function uploadBatch(
  projectId: string,
  files: ImportFile[],
  onChange: (items: UploadItem[]) => void,
  signal?: AbortSignal,
): Promise<UploadItem[]> {
  signal?.throwIfAborted();
  const existing = await listWorkspaceFiles(projectId, signal);
  const taken = new Set(existing.map((f) => f.path.replace(/^sources\//, "")));
  if (files.some((item) => /\.pdf$/i.test(item.path))) {
    const documents = await fetchAllDocuments(projectId, signal);
    for (const doc of documents)
      if (doc.origin_sha256)
        taken.add(doc.path.replace(/^sources\//, "").replace(/\.md$/i, ".pdf"));
  }
  const items: UploadItem[] = files.map((input) => ({
    ...input,
    path: uniquePath(input.path, taken),
    id: crypto.randomUUID(),
    status: "queued",
  }));
  signal?.throwIfAborted();
  onChange([...items]);
  for (const item of items) {
    signal?.throwIfAborted();
    item.status = "working";
    onChange(items.map((i) => ({ ...i })));
    try {
      const result = await uploadProjectFile(
        projectId,
        item.file,
        item.path,
        signal,
      );
      signal?.throwIfAborted();
      if (result.parsing) {
        const digest = await crypto.subtle.digest(
          "SHA-256",
          await item.file.arrayBuffer(),
        );
        signal?.throwIfAborted();
        item.originSha256 = Array.from(new Uint8Array(digest), (byte) =>
          byte.toString(16).padStart(2, "0"),
        ).join("");
        item.parsing = true;
        item.status = "processing";
      } else item.status = "ready";
    } catch {
      signal?.throwIfAborted();
      item.status = "error";
      item.error = "上传失败，请重试";
    }
    if (!signal?.aborted) onChange(items.map((i) => ({ ...i })));
  }
  return items;
}

const previews = new Map<string, { body: string; savedAt: number }>();
export async function readTextPreview(
  url: string,
  signal: AbortSignal,
  limit = 48_000,
  maxAge = 15_000,
): Promise<string> {
  const key = `${url}:${limit}`;
  signal.throwIfAborted();
  const cached = previews.get(key);
  if (cached && maxAge > 0 && Date.now() - cached.savedAt < maxAge)
    return cached.body;
  previews.delete(key);
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error("文档内容暂时无法读取");
  const reader = response.body?.getReader();
  if (!reader) return "";
  const decoder = new TextDecoder();
  let text = "";
  try {
    while (text.length < limit) {
      const part = await reader.read();
      if (part.done) break;
      text += decoder.decode(part.value, { stream: true });
    }
  } finally {
    await reader.cancel();
  }
  text = text.slice(0, limit);
  if (previews.size >= 100) previews.delete(previews.keys().next().value!);
  previews.set(key, { body: text, savedAt: Date.now() });
  return text;
}

export function isTextFile(path: string) {
  return /\.(md|markdown|txt|csv|log|rtf)$/i.test(path);
}

/** 演示空间的导入文件保存在 IndexedDB，持久层只存素材标识。 */
async function mediaDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("prose-canvas-media", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("files");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
export async function saveLocalFile(id: string, file: File) {
  const db = await mediaDatabase();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction("files", "readwrite");
      transaction.objectStore("files").put(file, id);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
  } finally {
    db.close();
  }
}
export async function loadLocalFile(id: string): Promise<Blob | undefined> {
  const db = await mediaDatabase();
  try {
    return await new Promise<Blob | undefined>((resolve, reject) => {
      const request = db.transaction("files").objectStore("files").get(id);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  } finally {
    db.close();
  }
}

export async function downloadEntity(entity: CanvasEntity) {
  const blob = entity.src?.startsWith("local:")
    ? await loadLocalFile(entity.src.slice(6))
    : !entity.src
      ? new Blob([entity.body ?? ""], { type: "text/markdown;charset=utf-8" })
      : undefined;
  const url = blob
    ? URL.createObjectURL(blob)
    : (entity.downloadSrc ?? entity.src);
  if (!url || url.startsWith("local:")) throw new Error("文件暂时不可用");
  const extension = entity.src?.split("?")[0]?.split(".").pop();
  const suffix =
    entity.src && extension && /^[a-z0-9]{1,8}$/i.test(extension)
      ? extension
      : "md";
  const link = document.createElement("a");
  link.href = url;
  link.download = entity.path?.split("/").pop() || `${entity.title}.${suffix}`;
  link.click();
  if (blob) setTimeout(() => URL.revokeObjectURL(url), 1000);
}
