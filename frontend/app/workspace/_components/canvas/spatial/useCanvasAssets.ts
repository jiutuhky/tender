"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchAllDocuments,
  listWorkspaceFiles,
  type DocumentRecord,
  type WorkspaceFile,
} from "@/lib/hagent/api";
import {
  uploadBatch,
  type ImportFile,
  type UploadItem,
} from "@/lib/canvas/files";

export function useCanvasAssets(projectId: string | null, running: boolean) {
  const [files, setFiles] = useState<WorkspaceFile[]>([]),
    [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [error, setError] = useState(""),
    [uploads, setUploads] = useState<UploadItem[]>([]),
    [busy, setBusy] = useState(false);
  const [progressVisible, setProgressVisible] = useState(true);
  const lifetime = useRef<AbortController | null>(null),
    inFlight = useRef(false);
  const pendingReload = useRef<{
    controller: AbortController;
    promise: Promise<void>;
  } | null>(null);
  const previewUrls = useRef(new Map<string, string>());
  useEffect(() => {
    const urls = previewUrls.current;
    return () => {
      for (const url of urls.values()) URL.revokeObjectURL(url);
      urls.clear();
    };
  }, []);
  const reload = useCallback(
    function load(fresh = false): Promise<void> {
      const controller = lifetime.current;
      if (!projectId || !controller || controller.signal.aborted)
        return Promise.resolve();
      const pending = pendingReload.current;
      if (pending?.controller === controller) {
        // 上传完成后，等待旧清单返回，再读取包含本批文件的新清单。
        return fresh ? pending.promise.then(() => load()) : pending.promise;
      }
      const promise = (async () => {
        const [fileResult, docsResult] = await Promise.allSettled([
          listWorkspaceFiles(projectId, controller.signal),
          fetchAllDocuments(projectId, controller.signal),
        ]);
        if (controller.signal.aborted || lifetime.current !== controller)
          return;
        if (fileResult.status === "fulfilled") {
          setFiles((previous) =>
            JSON.stringify(previous) === JSON.stringify(fileResult.value)
              ? previous
              : fileResult.value,
          );
          setError("");
        } else setError("项目资料暂时无法载入");
        if (docsResult.status === "fulfilled") {
          setDocuments((previous) =>
            JSON.stringify(previous) === JSON.stringify(docsResult.value)
              ? previous
              : docsResult.value,
          );
          const readyOrigins = new Set(
            docsResult.value
              .filter((doc) => doc.has_preview && doc.origin_sha256)
              .map((doc) => doc.origin_sha256),
          );
          setUploads((previous) => {
            if (
              !previous.some(
                (item) =>
                  item.status === "processing" &&
                  readyOrigins.has(item.originSha256),
              )
            )
              return previous;
            return previous.map((item) =>
              item.status === "processing" &&
              readyOrigins.has(item.originSha256)
                ? { ...item, status: "ready", previewUrl: undefined }
                : item,
            );
          });
        }
      })().finally(() => {
        if (pendingReload.current?.promise === promise)
          pendingReload.current = null;
      });
      pendingReload.current = { controller, promise };
      return promise;
    },
    [projectId],
  );
  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    return () => controller.abort();
  }, [reload]);
  useEffect(() => {
    // 此时新一帧已提交：有正式预览的卡片已经切换到服务端 URL。
    const readyOrigins = new Set(
      documents
        .filter((doc) => doc.has_preview)
        .map((doc) => doc.origin_sha256),
    );
    const active = new Set(
      uploads
        .filter(
          (item) => item.previewUrl && !readyOrigins.has(item.originSha256),
        )
        .map((item) => item.id),
    );
    for (const [id, url] of previewUrls.current) {
      if (active.has(id)) continue;
      URL.revokeObjectURL(url);
      previewUrls.current.delete(id);
    }
  }, [uploads, documents]);
  const pendingPdf = uploads.some((item) => item.status === "processing");
  useEffect(() => {
    void reload();
    const timer = projectId
      ? setInterval(
          () => {
            if (document.visibilityState === "visible") void reload();
          },
          running || pendingPdf ? 4000 : 15000,
        )
      : undefined;
    return () => clearInterval(timer);
  }, [running, pendingPdf, projectId, reload]);
  const upload = async (items: ImportFile[]) => {
    const controller = lifetime.current;
    if (
      !projectId ||
      !controller ||
      controller.signal.aborted ||
      inFlight.current ||
      !items.length
    )
      return;
    inFlight.current = true;
    setProgressVisible(true);
    setBusy(true);
    setError("");
    try {
      const result = await uploadBatch(
        projectId,
        items,
        (next) => {
          if (!controller.signal.aborted && lifetime.current === controller)
            setUploads((previous) => {
              const decorated = next.map((item) => {
                if (!item.parsing) return item;
                let url = previewUrls.current.get(item.id);
                if (!url) {
                  url = URL.createObjectURL(item.file);
                  previewUrls.current.set(item.id, url);
                }
                return { ...item, previewUrl: url };
              });
              return [
                ...previous.filter(
                  (item) =>
                    item.status === "processing" &&
                    !next.some((n) => n.id === item.id),
                ),
                ...decorated,
              ];
            });
        },
        controller.signal,
      );
      if (controller.signal.aborted || lifetime.current !== controller) return;
      await reload(true);
      return result;
    } catch {
      if (!controller.signal.aborted && lifetime.current === controller)
        setError("未能读取项目文件清单，请重试导入。");
    } finally {
      inFlight.current = false;
      if (!controller.signal.aborted && lifetime.current === controller)
        setBusy(false);
    }
  };
  return {
    files,
    documents,
    error,
    uploads,
    busy,
    progressVisible,
    reload,
    upload,
    dismiss: () => {
      setProgressVisible(false);
      setError("");
    },
  };
}
