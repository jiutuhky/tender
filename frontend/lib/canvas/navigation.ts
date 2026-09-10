import type { Camera, CanvasPlacement, CanvasSource } from "./model";

export interface CanvasFrame {
  folder: string | null;
  stack: string | null;
  camera: Camera;
  selection: string[];
}

/** 嵌套堆叠的局部坐标转换到当前文件夹工作面。 */
export function placementInContext(
  scene: CanvasSource,
  item: CanvasPlacement,
  folder: string | null,
): CanvasPlacement {
  const byEntity = new Map(
    Object.values(scene.placements).map((p) => [p.entityId, p]),
  );
  let point = item,
    parent = item.parentId;
  const visited = new Set<string>();
  while (parent && parent !== folder && !visited.has(parent)) {
    visited.add(parent);
    const ancestor = byEntity.get(parent);
    if (!ancestor) break;
    point = {
      ...point,
      x: point.x + ancestor.x,
      y:
        point.y +
        ancestor.y +
        (scene.collections[parent]?.kind === "stack" ? 50 : 0),
    };
    parent = ancestor.parentId;
  }
  return point;
}

/** 撤销或外部更新移除当前集合时，回到最近仍存在的上下文。 */
export function recoverNavigation(
  scene: CanvasSource,
  current: Pick<CanvasFrame, "folder" | "stack">,
  frames: CanvasFrame[],
): { frame: CanvasFrame; frames: CanvasFrame[] } | null {
  const visible = new Set(
    Object.values(scene.placements)
      .filter((p) => scene.collections[p.entityId])
      .map((p) => p.entityId),
  );
  const valid = (frame: Pick<CanvasFrame, "folder" | "stack">) =>
    (!frame.folder || visible.has(frame.folder)) &&
    (!frame.stack || visible.has(frame.stack));
  if (valid(current)) return null;
  for (let i = frames.length - 1; i >= 0; i--) {
    const frame = frames[i]!;
    if (valid(frame))
      return {
        frame: {
          ...frame,
          selection: frame.selection.filter((id) =>
            Boolean(scene.placements[id]),
          ),
        },
        frames: frames.slice(0, i),
      };
  }
  return {
    frame: {
      folder: null,
      stack: null,
      camera: frames[0]?.camera ?? { x: 60, y: 85, z: 0.75 },
      selection: [],
    },
    frames: [],
  };
}
