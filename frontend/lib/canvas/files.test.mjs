import test from "node:test";
import assert from "node:assert/strict";
import { readTextPreview, uploadBatch } from "./files.ts";
import { fetchAllDocuments } from "../hagent/api.ts";

test("文稿缓存短期复用，过期与全文强制读取取得最新内容", async (t) => {
  let reads = 0,
    now = 1000;
  t.mock.method(Date, "now", () => now);
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response(`版本 ${++reads}`),
  );
  const signal = new AbortController().signal;
  assert.equal(await readTextPreview("/审查文稿.md", signal), "版本 1");
  assert.equal(await readTextPreview("/审查文稿.md", signal), "版本 1");
  now += 15_001;
  assert.equal(await readTextPreview("/审查文稿.md", signal), "版本 2");
  assert.equal(
    await readTextPreview("/审查文稿.md", signal, 48_000, 0),
    "版本 3",
  );
});

test("文档注册表每一页透传取消信号，取消后停止翻页", async (t) => {
  const controller = new AbortController();
  let reads = 0;
  t.mock.method(globalThis, "fetch", async (_url, options) => {
    reads++;
    assert.strictEqual(options.signal, controller.signal);
    controller.abort();
    return Response.json({ documents: [], has_more: true, next_offset: 100 });
  });
  await assert.rejects(fetchAllDocuments("审查项目", controller.signal), {
    name: "AbortError",
  });
  assert.equal(reads, 1);
});

test("卸载取消正在上传的文件，不启动队列后续文件", async (t) => {
  const controller = new AbortController();
  let uploads = 0;
  t.mock.method(globalThis, "fetch", async (_url, options) => {
    assert.strictEqual(options.signal, controller.signal);
    if (options.method !== "POST") return Response.json([]);
    uploads++;
    controller.abort();
    options.signal.throwIfAborted();
  });
  const files = ["甲.txt", "乙.txt"].map((path) => ({
    path,
    file: new File([path], path),
  }));
  await assert.rejects(
    uploadBatch("审查项目", files, () => {}, controller.signal),
    { name: "AbortError" },
  );
  assert.equal(uploads, 1);
});
