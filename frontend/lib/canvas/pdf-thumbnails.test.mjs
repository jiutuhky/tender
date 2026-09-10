import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";
import { PreviewCache } from "./preview-cache.ts";
import { untilAborted } from "./abort.ts";

test("底层 PDF 下载取消后不结束，也会释放缩略图并发槽", async () => {
  const code = ts.transpileModule(
    readFileSync(new URL("./pdf-thumbnails.ts", import.meta.url), "utf8"),
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
    },
  ).outputText;
  const started = [],
    destroyed = [];
  const engine = {
    getDocument({ url }) {
      started.push(url);
      return {
        promise: url.startsWith("slow")
          ? new Promise(() => {})
          : Promise.resolve({
              getPage: async () => ({
                getViewport: ({ scale }) => ({
                  width: 200 * scale,
                  height: 300 * scale,
                }),
                render: () => ({ promise: Promise.resolve() }),
              }),
            }),
        destroy: async () => {
          destroyed.push(url);
        },
      };
    },
  };
  const exported = {};
  vm.runInNewContext(code, {
    exports: exported,
    require: (name) =>
      name.includes("pdf-runtime")
        ? { getPdfEngine: async () => engine, PDFJS_ASSETS: "/pdfjs/" }
        : name.endsWith("preview-cache")
          ? { PreviewCache }
          : name.endsWith("abort")
            ? { untilAborted }
            : { loadLocalFile: async () => undefined },
    document: { createElement: () => ({ width: 0, height: 0 }) },
    URL,
  });
  const a = new AbortController(),
    b = new AbortController();
  const first = exported
    .getPdfThumbnail("slow-a", a.signal)
    .catch((error) => error.name);
  const second = exported
    .getPdfThumbnail("slow-b", b.signal)
    .catch((error) => error.name);
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(started, ["slow-a", "slow-b"]);
  a.abort();
  b.abort();
  assert.equal(await first, "AbortError");
  assert.equal(await second, "AbortError");
  const ready = await exported.getPdfThumbnail(
    "ready",
    new AbortController().signal,
  );
  assert.equal(ready.width, 400);
  assert.equal(ready.height, 600);
  assert.equal(destroyed.filter((key) => key === "slow-a").length, 1);
  assert.equal(destroyed.filter((key) => key === "slow-b").length, 1);
});
