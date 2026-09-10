import test from "node:test";
import assert from "node:assert/strict";
import { emptySnapshot, resolveScene, handoffAnchorOffset } from "./model.ts";
import { demoSource } from "./demo.ts";
import { recoverNavigation, placementInContext } from "./navigation.ts";
import { PreviewCache } from "./preview-cache.ts";

test("撤销当前集合时回到有效上层并清除失效选择", () => {
  const scene = demoSource();
  const root = {
    folder: null,
    stack: null,
    camera: { x: 12, y: 34, z: 0.8 },
    selection: ["removed"],
  };
  const recovery = recoverNavigation(
    scene,
    { folder: "removed", stack: null },
    [root],
  );
  assert.deepEqual(recovery, { frame: { ...root, selection: [] }, frames: [] });
  assert.equal(
    recoverNavigation(scene, { folder: "materials", stack: null }, [root]),
    null,
  );
});

test("多层集合被撤销时跳过失效历史，正常空文件夹仍可停留", () => {
  const scene = demoSource(),
    frame = {
      folder: null,
      stack: null,
      camera: { x: 0, y: 0, z: 1 },
      selection: [],
    };
  const recovery = recoverNavigation(
    scene,
    { folder: "removed-child", stack: null },
    [frame, { ...frame, folder: "removed-parent" }],
  );
  assert.equal(recovery.frame.folder, null);
  assert.equal(recovery.frames.length, 0);
  const snapshot = emptySnapshot();
  snapshot.hidden = ["qualification"];
  assert.equal(
    recoverNavigation(
      resolveScene(scene, snapshot),
      { folder: "qualifications", stack: null },
      [frame],
    ),
    null,
  );
});

test("文件夹返回到嵌套堆叠时使用各层实际偏移", () => {
  const scene = demoSource();
  scene.collections.nested = {
    id: "nested",
    kind: "stack",
    title: "小节",
    color: "white",
  };
  scene.placements.nested = {
    id: "nested",
    entityId: "nested",
    parentId: "chapters",
    x: 80,
    y: 90,
    w: 280,
    h: 374,
  };
  const item = {
    id: "folder",
    entityId: "folder",
    parentId: "nested",
    x: 40,
    y: 70,
    w: 312,
    h: 266,
  };
  const point = placementInContext(scene, item, null);
  assert.equal(point.x, scene.placements.chapters.x + 80 + 40);
  assert.equal(point.y, scene.placements.chapters.y + 90 + 70 + 100);
});

test("动画中抓取恢复尺寸时，保留相同内容抓取点", () => {
  const matrix = { a: 0.6, b: 0.08, c: -0.1, d: 0.7, e: 120, f: 250 };
  const local = { x: 90, y: 130 },
    drag = { x: 40, y: 30 };
  const pointer = {
    x: matrix.e + matrix.a * local.x + matrix.c * local.y,
    y: matrix.f + matrix.b * local.x + matrix.d * local.y,
  };
  const offset = handoffAnchorOffset(matrix, pointer);
  assert.ok(
    Math.abs(matrix.e + drag.x + offset.x + local.x - pointer.x - drag.x) <
      1e-8,
  );
  assert.ok(
    Math.abs(matrix.f + drag.y + offset.y + local.y - pointer.y - drag.y) <
      1e-8,
  );
});

const tick = () => new Promise((resolve) => setImmediate(resolve));
test("预览共享解析，并在最后一个消费者取消后释放在途任务", async () => {
  const requests = [];
  const cache = new PreviewCache(
    (key, signal) =>
      new Promise((resolve, reject) => {
        requests.push({ key, signal, resolve });
        signal.addEventListener("abort", () => reject(signal.reason));
      }),
    () => {},
  );
  const first = new AbortController(),
    second = new AbortController();
  const a = cache.get("same", first.signal).catch((error) => error.name),
    b = cache.get("same", second.signal);
  await tick();
  assert.equal(requests.length, 1);
  first.abort();
  assert.equal(await a, "AbortError");
  assert.equal(requests[0].signal.aborted, false);
  requests[0].resolve("bitmap");
  assert.equal(await b, "bitmap");
  await tick();
  assert.equal(await cache.get("same", new AbortController().signal), "bitmap");
  assert.equal(requests.length, 1);
  const last = new AbortController(),
    pending = cache.get("cancelled", last.signal).catch((error) => error.name);
  await tick();
  last.abort();
  await pending;
  assert.equal(requests[1].signal.aborted, true);
});

test("PDF 预览限制并发并回收超出缓存容量的位图", async () => {
  const requests = [],
    disposed = [];
  const cache = new PreviewCache(
    (key) => new Promise((resolve) => requests.push({ key, resolve })),
    (value) => disposed.push(value),
    2,
    1,
  );
  const calls = ["a", "b", "c"].map((key) =>
    cache.get(key, new AbortController().signal),
  );
  await tick();
  assert.equal(requests.length, 1);
  requests[0].resolve("a");
  await calls[0];
  await tick();
  assert.equal(requests.length, 2);
  requests[1].resolve("b");
  await calls[1];
  await tick();
  assert.equal(requests.length, 3);
  requests[2].resolve("c");
  await calls[2];
  await tick();
  assert.deepEqual(disposed, ["a"]);
  assert.equal(await cache.get("b", new AbortController().signal), "b");
});

test("预览失败后立即重试同一文件会发起新任务", async () => {
  let calls = 0;
  const cache = new PreviewCache(
    async () => {
      if (++calls === 1) throw new Error("首次读取失败");
      return "新预览";
    },
    () => {},
    2,
    1,
  );
  const result = await cache
    .get("same", new AbortController().signal)
    .catch(() => cache.get("same", new AbortController().signal));
  assert.equal(result, "新预览");
  assert.equal(calls, 2);
});
