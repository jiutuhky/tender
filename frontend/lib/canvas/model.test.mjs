import test from "node:test";
import assert from "node:assert/strict";
import {
  emptySnapshot,
  resolveScene,
  reparent,
  canReparent,
  dissolve,
  commitHistory,
  undoHistory,
  redoHistory,
  uniquePath,
  worldPoint,
  screenPoint,
  resizeRect,
} from "./model.ts";
import { demoSource } from "./demo.ts";
import { appendFiles, matrixSource } from "./adapters.ts";
import { byteRange } from "./range.ts";

test("不同缩放与平移下，抓取点往返保持相同坐标", () => {
  for (const z of [0.15, 0.5, 1, 2.5]) {
    const camera = { x: -523, y: 98, z },
      point = { x: 456, y: -329 };
    const actual = screenPoint(worldPoint(point, camera), camera);
    assert.ok(Math.abs(actual.x - point.x) < 1e-9);
    assert.ok(Math.abs(actual.y - point.y) < 1e-9);
  }
});
test("素材收纳后业务内容保持不变，拒绝循环包含", () => {
  const source = demoSource(),
    snapshot = emptySnapshot();
  const next = reparent(snapshot, source, ["score-0"], "materials");
  const scene = resolveScene(source, next);
  assert.equal(scene.placements["score-0"].parentId, "materials");
  assert.strictEqual(scene.entities["score-0"], source.entities["score-0"]);
  assert.equal(canReparent(scene, ["materials"], "qualifications"), false);
  assert.strictEqual(reparent(next, scene, ["materials"], "materials"), next);
});
test("解散集合保留所有成员，可完整撤销与重做", () => {
  const source = demoSource(),
    initial = emptySnapshot();
  const next = dissolve(initial, source, "materials");
  const history = commitHistory(
    { past: [], present: initial, future: [] },
    next,
  );
  const scene = resolveScene(source, next);
  assert.equal(scene.placements.materials, undefined);
  assert.equal(scene.placements.qualifications.parentId, null);
  assert.equal(scene.placements.qualification.parentId, "qualifications");
  const undone = undoHistory(history);
  assert.deepEqual(resolveScene(source, undone.present), source);
  assert.deepEqual(redoHistory(undone).present, next);
});
test("主画布引用共享实体，服务端更新不会重复卡片或覆盖手动位置", () => {
  const source = demoSource(),
    snapshot = emptySnapshot();
  snapshot.placements.alias = {
    ...source.placements["score-0"],
    id: "alias",
    parentId: null,
    x: 42,
    y: 99,
  };
  const updated = {
    ...source,
    entities: {
      ...source.entities,
      "score-0": { ...source.entities["score-0"], confirmed: true },
    },
  };
  const scene = resolveScene(updated, snapshot);
  assert.equal(scene.entities[scene.placements.alias.entityId].confirmed, true);
  assert.equal(scene.placements.alias.x, 42);
  assert.equal(
    Object.keys(scene.entities).length,
    Object.keys(source.entities).length,
  );
});
test("集合名称与颜色恢复时仍保留新的服务端进度", () => {
  const source = demoSource(),
    snapshot = emptySnapshot();
  snapshot.collections.scoring = {
    ...source.collections.scoring,
    title: "重点评审",
    color: "blue",
    status: "working",
  };
  source.collections.scoring.status = "ready";
  source.collections.scoring.metric = "120 分";
  const scene = resolveScene(source, snapshot);
  assert.equal(scene.collections.scoring.title, "重点评审");
  assert.equal(scene.collections.scoring.status, "ready");
  assert.equal(scene.collections.scoring.metric, "120 分");
});
test("解散系统集合之后到达的新资料仍然可见", () => {
  const source = demoSource(),
    snapshot = dissolve(emptySnapshot(), source, "materials");
  source.entities.new = { id: "new", kind: "document", title: "后到的资料" };
  source.placements.new = {
    id: "new",
    entityId: "new",
    parentId: "materials",
    x: 40,
    y: 50,
    w: 280,
    h: 374,
  };
  const scene = resolveScene(source, snapshot);
  assert.equal(scene.placements.new.parentId, null);
  assert.equal(scene.placements.new.y, source.placements.materials.y + 50);
});
test("文件列表保留目录与媒体，文档注册表只建立来源关系", () => {
  const source = demoSource();
  source.entities["score-0"].sourceRefs = [
    { document_id: "doc-1", line_span: [1, 4] },
  ];
  const result = appendFiles(
    source,
    "项目一",
    [
      { path: "sources/企业/证明.pdf", size: 123 },
      { path: "sources/图片.png", size: 456 },
      { path: "sources/视频.mp4", size: 789 },
    ],
    [{ id: "doc-1", path: "sources/企业/证明.pdf" }],
  );
  assert.equal(
    result.placements["file:sources/企业/证明.pdf"].parentId,
    "directory:企业",
  );
  assert.equal(result.entities["file:sources/图片.png"].kind, "image");
  assert.ok(
    result.relations.some(
      (r) => r.from === "score-0" && r.to === "file:sources/企业/证明.pdf",
    ),
  );
});
test("真实空项目不混入大纲、章节或演示成果；缺少分值不伪造零分", () => {
  const slot = { status: "empty", data: null };
  const slots = {
    basic_info: slot,
    business: slot,
    technical: slot,
    scoring: {
      status: "ready",
      data: { items: [{ id: "s1", title: "完整性" }] },
    },
  };
  assert.equal(
    Object.keys(matrixSource(slots, "idle", false).entities).length,
    0,
  );
  const scene = matrixSource(slots, "done", true);
  assert.equal(scene.entities["scoring:s1"].score, undefined);
  assert.deepEqual(Object.keys(scene.entities), ["scoring:s1"]);
});
test("目录同名文件按完整相对路径去重，不覆盖已有素材", () => {
  const taken = new Set(["企业/资质.pdf", "企业/资质 (2).pdf"]);
  assert.equal(uniquePath("企业/资质.pdf", taken), "企业/资质 (3).pdf");
  assert.equal(uniquePath("项目/资质.pdf", taken), "项目/资质.pdf");
  assert.equal(uniquePath("企业/资质.pdf", taken), "企业/资质 (4).pdf");
});
test("媒体缩放保持比例与对角锚点", () => {
  const p = { x: 10, y: 20, w: 300, h: 200 },
    resized = resizeRect(p, "nw", { x: -120, y: -40 }, true);
  assert.equal(resized.w / resized.h, 1.5);
  assert.equal(resized.x + resized.w, 310);
  assert.equal(resized.y + resized.h, 220);
});
test("单段 Range 支持尾段、截断和越界", () => {
  assert.deepEqual(byteRange("bytes=2-5", 10), { start: 2, end: 5 });
  assert.deepEqual(byteRange("bytes=-4", 10), { start: 6, end: 9 });
  assert.deepEqual(byteRange("bytes=8-30", 10), { start: 8, end: 9 });
  assert.equal(byteRange("bytes=10-", 10), null);
  assert.equal(byteRange("bytes=0-0", 0), null);
  assert.equal(byteRange("bytes=0-1,3-4", 10), null);
});
test("大量资料场景包含 200 条评分和 100 个素材", () => {
  const entities = Object.values(demoSource("stress").entities);
  assert.equal(entities.filter((e) => e.kind === "scoring").length, 200);
  assert.equal(
    entities.filter((e) => ["document", "image", "video"].includes(e.kind))
      .length,
    100,
  );
});

test("PDF 原件通过独立接口展示，OCR 结果合并为同一素材", () => {
  const base = demoSource();
  base.entities["score-0"].sourceRefs = [
    { document_id: "pdf-doc", line_span: [1, 3] },
  ];
  const docs = [
    {
      id: "pdf-doc",
      path: "sources/资料/原文.md",
      origin_sha256: "abc123",
      has_preview: true,
    },
  ];
  const scene = appendFiles(
    base,
    "project",
    [{ path: "sources/资料/原文.md", size: 999 }],
    docs,
  );
  assert.equal(scene.entities["pdf:abc123"].title, "原文.pdf");
  assert.equal(
    scene.entities["pdf:abc123"].src,
    "/api/hagent/projects/project/documents/pdf-doc/preview",
  );
  assert.equal(
    scene.entities["pdf:abc123"].downloadSrc,
    "/api/hagent/projects/project/documents/pdf-doc/original",
  );
  assert.equal(scene.entities["file:sources/资料/原文.md"], undefined);
  assert.ok(
    scene.relations.some((r) => r.from === "score-0" && r.to === "pdf:abc123"),
  );
  const delayedList = appendFiles(base, "project", [], docs);
  assert.ok(delayedList.entities["pdf:abc123"]);
});
