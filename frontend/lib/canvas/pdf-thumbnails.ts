import { getPdfEngine, PDFJS_ASSETS } from "@/lib/trace/pdf-runtime";
import { PreviewCache } from "./preview-cache";
import { untilAborted } from "./abort";
import { loadLocalFile } from "./files";

async function renderThumbnail(
  source: string,
  signal: AbortSignal,
): Promise<HTMLCanvasElement> {
  const engine = await untilAborted(getPdfEngine(), signal);
  signal.throwIfAborted();
  let localUrl: string | undefined;
  if (source.startsWith("local:")) {
    const file = await untilAborted(loadLocalFile(source.slice(6)), signal);
    signal.throwIfAborted();
    if (!file) throw new Error("本地文件暂时不可用");
    localUrl = URL.createObjectURL(file);
  }
  const task = engine.getDocument({
    url: localUrl ?? source,
    cMapUrl: `${PDFJS_ASSETS}cmaps/`,
    cMapPacked: true,
    standardFontDataUrl: `${PDFJS_ASSETS}standard_fonts/`,
    wasmUrl: `${PDFJS_ASSETS}wasm/`,
  });
  let destruction: Promise<void> | undefined;
  const destroy = () => (destruction ??= task.destroy());
  const abort = () => {
    void destroy().catch(() => {});
  };
  signal.addEventListener("abort", abort, { once: true });
  try {
    // PDF.js 的 destroy 不保证 loadingTask.promise 结束，显式响应取消。
    const pdf = await untilAborted(task.promise, signal);
    const page = await untilAborted(pdf.getPage(1), signal),
      pageSize = page.getViewport({ scale: 1 });
    const viewport = page.getViewport({
      scale: Math.min(400 / pageSize.width, 640 / pageSize.height),
    });
    const canvas = document.createElement("canvas");
    canvas.width = Math.ceil(viewport.width);
    canvas.height = Math.ceil(viewport.height);
    await untilAborted(page.render({ canvas, viewport }).promise, signal);
    signal.throwIfAborted();
    return canvas;
  } finally {
    signal.removeEventListener("abort", abort);
    try {
      await destroy();
    } finally {
      if (localUrl) URL.revokeObjectURL(localUrl);
    }
  }
}

// 每张位图不超过 400×640；最多保留 24 张，PDF worker 在首次渲染后即释放。
const thumbnails = new PreviewCache(renderThumbnail, (canvas) => {
  canvas.width = 0;
  canvas.height = 0;
});
export const getPdfThumbnail = (
  url: string,
  signal: AbortSignal,
  localIdentity?: string,
) =>
  thumbnails.get(
    localIdentity?.startsWith("local:") ? localIdentity : url,
    signal,
  );
