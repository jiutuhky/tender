// 只在浏览器中按需导入引擎；服务端不执行 PDF.js。
export const PDFJS_VERSION = "6.3.289";
export const PDFJS_ASSETS = `/pdfjs/${PDFJS_VERSION}/`;
let engine: Promise<typeof import("pdfjs-dist/legacy/build/pdf.mjs")> | null = null;
export function getPdfEngine() {
  if (!engine) {
    engine = import("pdfjs-dist/legacy/build/pdf.mjs").then((pdfjs) => {
      pdfjs.GlobalWorkerOptions.workerSrc = `${PDFJS_ASSETS}pdf.worker.min.mjs`;
      return pdfjs;
    }).catch((error: unknown) => { engine = null; throw error; });
  }
  return engine;
}

export function documentAssetUrl(pid: string, docId: string, kind: "preview" | "original" | "sidecar") {
  return `/api/hagent/projects/${encodeURIComponent(pid)}/documents/${encodeURIComponent(docId)}/${kind}`;
}
