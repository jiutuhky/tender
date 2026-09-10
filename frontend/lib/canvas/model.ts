import type { MatrixType, SourceRef } from "@/lib/hagent/matrix";

/** 业务对象与空间实例分离：多个实例共享同一份内容、来源和核验状态。 */
export type EntityKind =
  | "summary"
  | "requirement"
  | "scoring"
  | "outline"
  | "chapter"
  | "final"
  | "document"
  | "image"
  | "video"
  | "note";
export interface CanvasEntity {
  id: string;
  kind: EntityKind;
  title: string;
  body?: string;
  subtitle?: string;
  number?: string;
  score?: number;
  status?: "working" | "ready" | "error" | "interrupted";
  statusText?: string;
  confirmed?: boolean;
  responseText?: string;
  group?: string;
  sourceRefs?: SourceRef[];
  matrixType?: MatrixType;
  itemId?: string;
  src?: string;
  downloadSrc?: string;
  path?: string;
  size?: number;
  editable?: boolean;
  outline?: Array<{ title: string; depth: number; entityId?: string }>;
}
export interface CanvasCollection {
  id: string;
  kind: "stack" | "folder";
  title: string;
  subtitle?: string;
  color: string;
  matrixType?: MatrixType;
  metric?: string;
  status?: CanvasEntity["status"];
  statusText?: string;
}
export interface Point {
  x: number;
  y: number;
}
export interface Rect extends Point {
  w: number;
  h: number;
}
export interface Camera extends Point {
  z: number;
}
export interface CanvasPlacement extends Rect {
  id: string;
  entityId: string;
  parentId: string | null;
  mediaRatio?: number;
}
export interface CanvasRelation {
  id: string;
  from: string;
  to: string;
  kind: "source" | "response" | "reference";
}
export interface CanvasSource {
  entities: Record<string, CanvasEntity>;
  collections: Record<string, CanvasCollection>;
  placements: Record<string, CanvasPlacement>;
  relations: CanvasRelation[];
}
export interface CanvasSnapshot {
  version: 1;
  placements: Record<string, CanvasPlacement>;
  collections: Record<string, CanvasCollection>;
  entities: Record<string, CanvasEntity>;
  hidden: string[];
  camera?: Camera;
}
export interface CanvasHistory {
  past: CanvasSnapshot[];
  present: CanvasSnapshot;
  future: CanvasSnapshot[];
}
export const emptySnapshot = (): CanvasSnapshot => ({
  version: 1,
  placements: {},
  collections: {},
  entities: {},
  hidden: [],
});
export const emptySource = (): CanvasSource => ({
  entities: {},
  collections: {},
  placements: {},
  relations: [],
});
export const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value));
export const worldPoint = (point: Point, camera: Camera): Point => ({
  x: (point.x - camera.x) / camera.z,
  y: (point.y - camera.y) / camera.z,
});
export const screenPoint = (point: Point, camera: Camera): Point => ({
  x: point.x * camera.z + camera.x,
  y: point.y * camera.z + camera.y,
});

export interface CardTransform {
  a: number;
  b: number;
  c: number;
  d: number;
  e: number;
  f: number;
}
/** 动画中抓取的位置在恢复正常尺寸后仍落在同一个内容点。 */
export function handoffAnchorOffset(
  matrix: CardTransform,
  pointer: Point,
): Point {
  const determinant = matrix.a * matrix.d - matrix.b * matrix.c;
  if (Math.abs(determinant) < 1e-8) return { x: 0, y: 0 };
  const x = pointer.x - matrix.e,
    y = pointer.y - matrix.f;
  const localX = (matrix.d * x - matrix.c * y) / determinant;
  const localY = (matrix.a * y - matrix.b * x) / determinant;
  return { x: x - localX, y: y - localY };
}
export const intersects = (a: Rect, b: Rect) =>
  a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
export function bounds(items: Rect[]): Rect {
  if (!items.length) return { x: 0, y: 0, w: 900, h: 600 };
  const x = Math.min(...items.map((p) => p.x)),
    y = Math.min(...items.map((p) => p.y));
  return {
    x,
    y,
    w: Math.max(...items.map((p) => p.x + p.w)) - x,
    h: Math.max(...items.map((p) => p.y + p.h)) - y,
  };
}
export function resolveScene(
  source: CanvasSource,
  snapshot: CanvasSnapshot,
): CanvasSource {
  const entities = { ...source.entities, ...snapshot.entities };
  const collections = { ...source.collections, ...snapshot.collections };
  for (const [id, current] of Object.entries(source.collections)) {
    const saved = snapshot.collections[id];
    if (saved)
      collections[id] = { ...current, title: saved.title, color: saved.color };
  }
  const hidden = new Set(snapshot.hidden);
  const placements = Object.fromEntries(
    Object.entries({ ...source.placements, ...snapshot.placements }).filter(
      ([id, p]) =>
        !hidden.has(id) &&
        Boolean(entities[p.entityId] || collections[p.entityId]),
    ),
  );
  // 集合解散之后到达的新产物沿最近仍可见的父层出现。
  const visibleContainers = new Set(
    Object.values(placements)
      .filter((p) => collections[p.entityId])
      .map((p) => p.entityId),
  );
  const allPlacements = Object.values({
    ...source.placements,
    ...snapshot.placements,
  });
  for (const [id, placement] of Object.entries(placements)) {
    let p = placement;
    const visited = new Set<string>();
    while (
      p.parentId &&
      !visibleContainers.has(p.parentId) &&
      !visited.has(p.parentId)
    ) {
      visited.add(p.parentId);
      const parent = allPlacements.find(
        (candidate) => candidate.entityId === p.parentId,
      );
      p = {
        ...p,
        parentId: parent?.parentId ?? null,
        x: p.x + (parent?.x ?? 0),
        y: p.y + (parent?.y ?? 0),
      };
    }
    placements[id] = p;
  }
  return { entities, collections, placements, relations: source.relations };
}
/** 拒绝把集合放入自己或后代；收纳仅改变画布实例。 */
export function canReparent(
  scene: CanvasSource,
  ids: string[],
  parentId: string | null,
): boolean {
  if (!parentId) return true;
  if (!scene.collections[parentId]) return false;
  const moving = new Set(ids.map((id) => scene.placements[id]?.entityId));
  const visited = new Set<string>();
  let current: string | null = parentId;
  while (current) {
    if (moving.has(current) || visited.has(current)) return false;
    visited.add(current);
    current =
      Object.values(scene.placements).find((p) => p.entityId === current)
        ?.parentId ?? null;
  }
  return true;
}
export function reparent(
  snapshot: CanvasSnapshot,
  scene: CanvasSource,
  ids: string[],
  parentId: string | null,
  anchor: Point = { x: 60, y: 80 },
): CanvasSnapshot {
  if (!canReparent(scene, ids, parentId)) return snapshot;
  const next = { ...snapshot, placements: { ...snapshot.placements } };
  const count = Object.values(scene.placements).filter(
    (p) => p.parentId === parentId && !ids.includes(p.id),
  ).length;
  ids.forEach((id, i) => {
    const p = scene.placements[id];
    if (p)
      next.placements[id] = {
        ...p,
        parentId,
        x: anchor.x + ((count + i) % 4) * 324,
        y: anchor.y + Math.floor((count + i) / 4) * 420,
      };
  });
  return next;
}
export function dissolve(
  snapshot: CanvasSnapshot,
  scene: CanvasSource,
  collectionId: string,
): CanvasSnapshot {
  const container = Object.values(scene.placements).find(
    (p) => p.entityId === collectionId,
  );
  if (!container) return snapshot;
  const children = Object.values(scene.placements).filter(
    (p) => p.parentId === collectionId,
  );
  const placements = { ...snapshot.placements };
  for (const p of children)
    placements[p.id] = {
      ...p,
      parentId: container.parentId,
      x: container.x + p.x,
      y: container.y + p.y,
    };
  return {
    ...snapshot,
    placements,
    hidden: [...new Set([...snapshot.hidden, container.id])],
  };
}
export function commitHistory(
  history: CanvasHistory,
  next: CanvasSnapshot,
): CanvasHistory {
  if (next === history.present) return history;
  return {
    past: [...history.past.slice(-49), history.present],
    present: next,
    future: [],
  };
}
export function undoHistory(history: CanvasHistory): CanvasHistory {
  const previous = history.past.at(-1);
  return previous
    ? {
        past: history.past.slice(0, -1),
        present: previous,
        future: [history.present, ...history.future],
      }
    : history;
}
export function redoHistory(history: CanvasHistory): CanvasHistory {
  const next = history.future[0];
  return next
    ? {
        past: [...history.past, history.present],
        present: next,
        future: history.future.slice(1),
      }
    : history;
}
export function uniquePath(path: string, taken: Set<string>): string {
  const normalized = path
    .replaceAll("\\", "/")
    .split("/")
    .filter((p) => p && p !== "." && p !== "..")
    .join("/");
  const dot = normalized.lastIndexOf("."),
    slash = normalized.lastIndexOf("/");
  const base = dot > slash ? normalized.slice(0, dot) : normalized;
  const extension = dot > slash ? normalized.slice(dot) : "";
  let candidate = normalized,
    index = 2;
  while (taken.has(candidate)) candidate = `${base} (${index++})${extension}`;
  taken.add(candidate);
  return candidate;
}
export function resizeRect(
  rect: Rect,
  corner: string,
  delta: Point,
  ratioLocked: boolean,
): Rect {
  const left = corner.includes("w"),
    top = corner.includes("n");
  let w = clamp(rect.w + delta.x * (left ? -1 : 1), 160, 1000);
  let h = clamp(rect.h + delta.y * (top ? -1 : 1), 120, 1200);
  if (ratioLocked) {
    const scale = Math.max(w / rect.w, h / rect.h);
    w = rect.w * scale;
    h = rect.h * scale;
  }
  return {
    x: left ? rect.x + rect.w - w : rect.x,
    y: top ? rect.y + rect.h - h : rect.y,
    w,
    h,
  };
}
