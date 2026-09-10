import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

// 使用真实 hook 和可控的 effect / 网络时序，验证慢请求与卸载竞态。
const code = ts.transpileModule(
  readFileSync(
    new URL(
      "../../app/workspace/_components/canvas/spatial/useCanvasAssets.ts",
      import.meta.url,
    ),
    "utf8",
  ),
  {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  },
).outputText;

function setup() {
  const slots = [],
    pendingEffects = [],
    intervals = new Map(),
    requests = [],
    revoked = [];
  let cursor = 0,
    dirty = false,
    result,
    timerId = 0,
    blobId = 0;
  const same = (a, b) =>
    a && b && a.length === b.length && a.every((v, i) => v === b[i]);
  const react = {
    useState(initial) {
      const index = cursor++;
      slots[index] ??= { value: initial };
      return [
        slots[index].value,
        (next) => {
          const value =
            typeof next === "function" ? next(slots[index].value) : next;
          if (value !== slots[index].value) dirty = true;
          slots[index].value = value;
        },
      ];
    },
    useRef(current) {
      const index = cursor++;
      return (slots[index] ??= { current });
    },
    useCallback(fn, deps) {
      const index = cursor++;
      if (!same(slots[index]?.deps, deps)) slots[index] = { fn, deps };
      return slots[index].fn;
    },
    useEffect(fn, deps) {
      const index = cursor++;
      if (!same(slots[index]?.deps, deps))
        pendingEffects.push(() => {
          slots[index]?.cleanup?.();
          slots[index] = { deps, cleanup: fn() };
        });
    },
  };
  const request = (kind, signal) =>
    new Promise((resolve, reject) => {
      requests.push({ kind, signal, resolve });
      signal.addEventListener("abort", () => reject(signal.reason), {
        once: true,
      });
    });
  const exported = {};
  vm.runInNewContext(code, {
    exports: exported,
    require: (name) =>
      name === "react"
        ? react
        : name.includes("/hagent/api")
          ? {
              listWorkspaceFiles: (_project, signal) =>
                request("files", signal),
              fetchAllDocuments: (_project, signal) =>
                request("documents", signal),
            }
          : {
              uploadBatch: async (_project, items, change) => {
                const batch = items.map((item, i) => ({
                  ...item,
                  id: `upload-${blobId}-${i}`,
                  originSha256: item.file.name,
                  status: "processing",
                  parsing: true,
                }));
                change(batch);
                return batch;
              },
            },
    AbortController,
    Promise,
    URL: {
      createObjectURL: () => `blob:${++blobId}`,
      revokeObjectURL: (url) => revoked.push(url),
    },
    document: { visibilityState: "visible" },
    setInterval: (fn) => {
      intervals.set(++timerId, fn);
      return timerId;
    },
    clearInterval: (id) => intervals.delete(id),
  });
  const render = () => {
    dirty = false;
    cursor = 0;
    result = exported.useCanvasAssets("审查项目", true);
    pendingEffects.splice(0).forEach((effect) => effect());
  };
  const flush = async () => {
    for (let i = 0; i < 4; i++) {
      await new Promise((resolve) => setImmediate(resolve));
      if (dirty) render();
    }
  };
  render();
  return {
    requests,
    revoked,
    flush,
    get result() {
      return result;
    },
    tick: () => [...intervals.values()].forEach((fn) => fn()),
    settle(start, files = [], documents = []) {
      requests[start].resolve(files);
      requests[start + 1].resolve(documents);
    },
    unmount: () => slots.forEach((slot) => slot?.cleanup?.()),
  };
}

test("素材首轮只读取一次，慢请求跨过多轮定时器仍可提交结果", async () => {
  const app = setup();
  assert.equal(app.requests.length, 2);
  const first = app.result.reload();
  assert.strictEqual(first, app.result.reload());
  for (let i = 0; i < 6; i++) app.tick();
  assert.equal(app.requests.length, 2);
  app.settle(0, [{ path: "生成文稿.md", size: 42 }]);
  await app.flush();
  assert.equal(app.result.files[0].path, "生成文稿.md");
  const previous = app.result.files;
  app.tick();
  app.settle(2, [{ path: "生成文稿.md", size: 42 }]);
  await app.flush();
  assert.strictEqual(app.result.files, previous);
  app.unmount();
});

test("卸载取消文件与注册表读取，不把取消显示为载入失败", async () => {
  const app = setup();
  assert.strictEqual(app.requests[0].signal, app.requests[1].signal);
  app.unmount();
  await app.flush();
  assert.equal(app.requests[0].signal.aborted, true);
  assert.equal(app.result.error, "");
  assert.equal(app.result.files.length, 0);
});

test("上传后读取新清单，PDF 正式预览就绪才释放临时 Blob", async () => {
  const app = setup();
  app.settle(0);
  await app.flush();
  const uploading = app.result.upload([
    { path: "投标文件.pdf", file: { name: "原件摘要" } },
  ]);
  await app.flush();
  assert.equal(app.requests.length, 4);
  assert.equal(app.result.uploads[0].status, "processing");
  assert.equal(app.revoked.length, 0);
  app.settle(2, [], [{ origin_sha256: "原件摘要", has_preview: false }]);
  await uploading;
  await app.flush();
  assert.equal(app.revoked.length, 0);
  app.tick();
  app.settle(4, [], [{ origin_sha256: "原件摘要", has_preview: true }]);
  await app.flush();
  assert.equal(app.result.uploads[0].status, "ready");
  assert.equal(app.result.uploads[0].previewUrl, undefined);
  assert.equal(app.revoked.length, 1);
  app.unmount();
  assert.equal(app.revoked.length, 1);
});

test("上传完成遇到旧请求时，等待旧请求后补读一次清单", async () => {
  const app = setup();
  const uploading = app.result.upload([
    { path: "资料.pdf", file: { name: "另一份原件" } },
  ]);
  await app.flush();
  assert.equal(app.requests.length, 2);
  app.settle(0);
  await app.flush();
  assert.equal(app.requests.length, 4);
  app.settle(2, [{ path: "sources/资料.md", size: 200 }]);
  await uploading;
  await app.flush();
  assert.equal(app.result.files[0].size, 200);
  app.unmount();
});
