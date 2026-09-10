"use client";

import {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
} from "react";
import Link from "next/link";
import { useWorkspaceStore } from "@/lib/store/workspace";
import {
  appendFiles,
  addCollection,
  addEntity,
  fileKind,
  matrixSource,
} from "@/lib/canvas/adapters";
import { demoSource } from "@/lib/canvas/demo";
import {
  bounds,
  canReparent,
  dissolve,
  intersects,
  reparent,
  worldPoint,
  type CanvasPlacement,
  type Rect,
} from "@/lib/canvas/model";
import {
  downloadEntity,
  filesFromDrop,
  saveLocalFile,
  type ImportFile,
} from "@/lib/canvas/files";
import {
  ArrowRightIcon,
  ArrowUpIcon,
  CheckIcon,
  ChevronLeftIcon,
  DownloadIcon,
  FileIcon,
  FileTextIcon,
  FolderSimpleIcon,
  FrameIcon,
  GridIcon,
  LayersIcon,
  MinusIcon,
  PenIcon,
  PlusIcon,
  RefreshCcwIcon,
  RefreshIcon,
  SearchIcon,
  UploadIcon,
  XIcon,
} from "@/components/ui/icons";
import { MessageWindow } from "../MessageWindow";
import { AgentBoard } from "./AgentBoard";
import { CanvasDock } from "./CanvasDock";
import { CanvasDrawer } from "./CanvasDrawer";
import { CardPreview } from "./CardPreview";
import { META } from "./cardMeta";
import { MATRIX_CARD_ORDER } from "./choreography";
import { SpatialCard } from "./spatial/SpatialCard";
import { SpatialReader } from "./spatial/SpatialReader";
import { useCanvasDocument } from "./spatial/useCanvasDocument";
import { useCanvasAssets } from "./spatial/useCanvasAssets";
import { useSpatialGestures } from "./spatial/useSpatialGestures";
import { useCollectionMotion } from "./spatial/useCollectionMotion";
import { useStableEvent } from "./spatial/useStableEvent";
import {
  placementInContext,
  recoverNavigation,
  type CanvasFrame as Frame,
} from "@/lib/canvas/navigation";
import type { MatrixType } from "@/lib/hagent/matrix";
import "./workspace-surface.css";
import "./spatial/spatial.css";

const EMPTY_MEMBERS: [] = [];
const COLORS = ["white", "blue", "green", "yellow", "pink", "violet", "slate"];
const COLOR_NAMES = ["白色", "蓝色", "绿色", "黄色", "粉色", "紫色", "灰蓝"];

/** 常驻浮层按各自订阅更新；画布相机、选择和布局变化停在此边界。 */
const WorkspaceChrome = memo(function WorkspaceChrome() {
  return (
    <>
      <div data-no-gesture className="sp-chat-chrome">
        <MessageWindow />
      </div>
      <div data-no-gesture className="sp-agent-chrome">
        <AgentBoard />
      </div>
      <div data-no-gesture className="sp-composer-chrome">
        <CanvasDock />
      </div>
    </>
  );
});

export function CanvasPane({ demo = false }: { demo?: boolean }) {
  const projectId = useWorkspaceStore((s) => s.projectId);
  return (
    <SpatialWorkspace
      key={demo ? "demo" : (projectId ?? "new")}
      demo={demo}
      projectId={demo ? null : projectId}
    />
  );
}

function SpatialWorkspace({
  demo,
  projectId,
}: {
  demo: boolean;
  projectId: string | null;
}) {
  const matrices = useWorkspaceStore((s) => s.matrices),
    phase = useWorkspaceStore((s) => s.phase),
    projectName = useWorkspaceStore((s) => s.projectName),
    streamSize = useWorkspaceStore((s) => s.streamSize);
  const running = [
    "creating",
    "uploading",
    "running",
    "loading_results",
  ].includes(phase);
  const [scenario, setScenario] = useState<
    "complete" | "working" | "partial" | "stress"
  >("complete");
  const assets = useCanvasAssets(projectId, running);
  const matrixData = useMemo(
    () => matrixSource(matrices, phase, Boolean(projectId)),
    [matrices, phase, projectId],
  );
  const source = useMemo(() => {
    if (demo) return demoSource(scenario);
    const base = matrixData;
    const uploaded = assets.uploads
      .filter((u) => u.status === "ready" && !u.parsing)
      .map((u) => ({ path: `sources/${u.path}`, size: u.file.size }));
    const allFiles = [
      ...new Map(
        [...assets.files, ...uploaded].map((f) => [f.path, f]),
      ).values(),
    ];
    const result = projectId
      ? appendFiles(base, projectId, allFiles, assets.documents)
      : base;
    if (assets.uploads.length && !result.collections.materials)
      addCollection(result, "materials", "项目资料", "folder", 0, 50);
    for (const item of assets.uploads) {
      if (!item.parsing || !item.originSha256) continue;
      const id = `pdf:${item.originSha256}`;
      if (result.entities[id]) continue;
      let parent = "materials";
      const parts = item.path.split("/").slice(0, -1);
      for (let i = 0; i < parts.length; i++) {
        const directoryId = `directory:${parts.slice(0, i + 1).join("/")}`;
        if (!result.collections[directoryId]) {
          const n = Object.values(result.placements).filter(
            (p) => p.parentId === parent,
          ).length;
          addCollection(
            result,
            directoryId,
            parts[i]!,
            "folder",
            (n % 4) * 350,
            Math.floor(n / 4) * 430,
            parent,
          );
        }
        parent = directoryId;
      }
      const n = Object.values(result.placements).filter(
        (p) => p.parentId === parent,
      ).length;
      addEntity(
        result,
        {
          id,
          kind: "document",
          title: item.file.name,
          path: `sources/${item.path}`,
          src: item.previewUrl,
          size: item.file.size,
          status: "working",
          statusText: "等待原文就绪",
          subtitle: "PDF 已上传",
        },
        (n % 4) * 350,
        Math.floor(n / 4) * 430,
        parent,
      );
    }
    if (assets.busy && result.collections.materials) {
      result.collections.materials.status = "working";
      result.collections.materials.subtitle = `正在导入 · ${assets.uploads.filter((u) => u.status === "ready" || u.status === "processing").length}/${assets.uploads.length}`;
    }
    return result;
  }, [
    demo,
    scenario,
    matrixData,
    projectId,
    assets.files,
    assets.documents,
    assets.uploads,
    assets.busy,
  ]);
  const doc = useCanvasDocument(demo ? "demo" : (projectId ?? "new"), source),
    { scene } = doc;
  const [viewMode, setViewMode] = useState<"canvas" | "overview">("canvas"),
    [selection, setSelection] = useState<string[]>([]);
  const [folder, setFolder] = useState<string | null>(null),
    [stack, setStack] = useState<string | null>(null),
    [frames, setFrames] = useState<Frame[]>([]);
  const [reader, setReader] = useState<{ id: string; origin?: Rect } | null>(
      null,
    ),
    [matrixReader, setMatrixReader] = useState<MatrixType | null>(null);
  const [palette, setPalette] = useState(false),
    [renaming, setRenaming] = useState<string | null>(null),
    [renameDraft, setRenameDraft] = useState("");
  const [toast, setToast] = useState(""),
    [dropOver, setDropOver] = useState(false),
    [query, setQuery] = useState(""),
    [showSearch, setShowSearch] = useState(false);
  const [editingNote, setEditingNote] = useState<string | null>(null);
  const [localBusy, setLocalBusy] = useState(false),
    [help, setHelp] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null),
    folderInput = useRef<HTMLInputElement>(null),
    imageInput = useRef<HTMLInputElement>(null),
    morph = useRef<HTMLDivElement>(null);
  const folderAnimation = useRef<Animation | null>(null),
    dropDepth = useRef(0),
    fitted = useRef(false),
    root = useRef<HTMLDivElement>(null),
    mounted = useRef(true),
    importLock = useRef(false),
    focusRequest = useRef(0);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      folderAnimation.current?.cancel();
      cancelAnimationFrame(focusRequest.current);
    };
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timeout = setTimeout(() => setToast(""), 3400);
    return () => clearTimeout(timeout);
  }, [toast]);
  const children = useMemo(() => {
    const result = new Map<string | null, CanvasPlacement[]>();
    for (const p of Object.values(scene.placements)) {
      const group = result.get(p.parentId) ?? [];
      group.push(p);
      result.set(p.parentId, group);
    }
    return result;
  }, [scene.placements]);
  const stackPlacement = useMemo(() => {
    const item = stack
      ? Object.values(scene.placements).find((p) => p.entityId === stack)
      : undefined;
    return item ? placementInContext(scene, item, folder) : undefined;
  }, [scene, folder, stack]);
  const cardMembers = useMemo(
    () =>
      new Map(
        [...children].map(([id, items]) => [
          id,
          items
            .slice(0, 3)
            .map((placement) => ({
              placement,
              entity: scene.entities[placement.entityId],
              collection: scene.collections[placement.entityId],
            })),
        ]),
      ),
    [children, scene.entities, scene.collections],
  );
  const displayed = useMemo(() => {
    const base = children.get(folder) ?? [];
    if (!stack || !stackPlacement) return base;
    return [
      ...base.filter((p) => p.entityId !== stack),
      ...(children.get(stack) ?? []).map((p) => ({
        ...p,
        x: p.x + stackPlacement.x,
        y: p.y + stackPlacement.y + 50,
      })),
    ];
  }, [children, folder, stack, stackPlacement]);
  const interactiveItems = stack
    ? displayed.filter((p) => p.parentId === stack)
    : displayed;
  const selected = selection
    .map((id) => scene.placements[id])
    .filter(
      (p): p is CanvasPlacement =>
        p !== undefined && p.parentId === (stack ?? folder),
    );
  const first = selected[0],
    selectedCollection = first ? scene.collections[first.entityId] : undefined;
  const commitPlacements = (
    items: CanvasPlacement[],
    dropId: string | null,
  ) => {
    const target = dropId ? scene.placements[dropId] : undefined;
    if (target) {
      collectionMotion.capture();
      doc.update((s) =>
        reparent(
          s,
          scene,
          items.map((i) => i.id),
          target.entityId,
        ),
      );
      setSelection([]);
      setToast(`已收入「${scene.collections[target.entityId]?.title}」`);
    } else
      doc.update((s) => {
        const placements = { ...s.placements };
        for (const item of items) {
          const current = scene.placements[item.id];
          if (!current) continue;
          placements[item.id] = {
            ...item,
            x:
              item.x -
              (stack && current.parentId === stack
                ? (stackPlacement?.x ?? 0)
                : 0),
            y:
              item.y -
              (stack && current.parentId === stack
                ? (stackPlacement?.y ?? 0) + 50
                : 0),
          };
        }
        return { ...s, placements };
      });
  };
  const gestures = useSpatialGestures({
    items: interactiveItems,
    selection,
    setSelection,
    interactive: !reader && !matrixReader && viewMode === "canvas",
    isMedia: (id) => {
      const e = scene.entities[scene.placements[id]?.entityId ?? ""];
      return e?.kind === "image" || e?.kind === "video";
    },
    canDrop: (ids, targetId) => {
      const target = scene.placements[targetId];
      return Boolean(
        target &&
        !ids.includes(targetId) &&
        scene.collections[target.entityId] &&
        canReparent(scene, ids, target.entityId),
      );
    },
    onCommit: commitPlacements,
    onCamera: (camera) => {
      if (!folder && !stack) doc.update((s) => ({ ...s, camera }), false);
    },
  });
  const collectionMotion = useCollectionMotion(gestures.world, gestures.camera);
  const focusCard = useCallback((id: string) => {
    setSelection((previous) => (previous.includes(id) ? previous : [id]));
  }, []);
  const captureOrigin = (id: string): Rect | undefined => {
    const rect = root.current
      ?.querySelector(`[data-placement="${CSS.escape(id)}"]`)
      ?.getBoundingClientRect();
    return rect
      ? { x: rect.left, y: rect.top, w: rect.width, h: rect.height }
      : undefined;
  };
  const animateFolder = (origin: Rect | undefined, opening: boolean) => {
    const element = morph.current,
      rect = gestures.viewport.current?.getBoundingClientRect();
    if (
      !element ||
      !rect ||
      !origin ||
      matchMedia("(prefers-reduced-motion: reduce)").matches
    )
      return;
    const current = folderAnimation.current
      ? getComputedStyle(element).transform
      : null;
    folderAnimation.current?.cancel();
    const small = `translate(${origin.x - rect.left}px,${origin.y - rect.top}px) scale(${origin.w / rect.width},${origin.h / rect.height})`,
      large = "translate(0px,0px) scale(1,1)";
    const animation = element.animate(
      [
        {
          transform: current || (opening ? small : large),
          opacity: 1,
          borderRadius: "22px",
        },
        {
          transform: opening ? large : small,
          opacity: 0.95,
          borderRadius: opening ? "0px" : "22px",
          offset: 0.7,
        },
        { transform: opening ? large : small, opacity: 0 },
      ],
      { duration: 760, easing: "cubic-bezier(.77,0,.175,1)", fill: "both" },
    );
    folderAnimation.current = animation;
    void animation.finished
      .then(() => {
        if (folderAnimation.current === animation) {
          animation.cancel();
          folderAnimation.current = null;
        }
      })
      .catch(() => {});
  };
  const restoreFocus = useCallback((ids: string[]) => {
    cancelAnimationFrame(focusRequest.current);
    focusRequest.current = requestAnimationFrame(() => {
      const target = ids
        .map((id) =>
          root.current?.querySelector<HTMLElement>(
            `[data-placement="${CSS.escape(id)}"]:not([inert])`,
          ),
        )
        .find(Boolean);
      (
        target ?? root.current?.querySelector<HTMLElement>(".sp-viewport")
      )?.focus({ preventScroll: true });
    });
  }, []);
  const enter = useStableEvent((id: string, keyboard = false) => {
    if (!keyboard && gestures.suppress.current) {
      gestures.suppress.current = false;
      return;
    }
    const p = displayed.find((item) => item.id === id) ?? scene.placements[id];
    if (!p) return;
    const collection = scene.collections[p.entityId];
    if (collection) {
      const members = (children.get(collection.id) ?? []).slice(
        0,
        gestures.view.width <= 600 ? 1 : 8,
      );
      collectionMotion.capture();
      setFrames((prev) => [
        ...prev,
        {
          folder,
          stack,
          camera: { ...gestures.camera.current },
          selection: [id],
        },
      ]);
      setSelection([]);
      setPalette(false);
      if (keyboard) restoreFocus(members.map((member) => member.id));
      if (collection.kind === "folder") {
        animateFolder(captureOrigin(id), true);
        setFolder(collection.id);
        setStack(null);
        gestures.fit(members);
      } else {
        setStack(collection.id);
        gestures.fit(
          members.map((child) => ({
            ...child,
            x: child.x + p.x,
            y: child.y + p.y + 50,
          })),
        );
      }
    } else if (scene.entities[p.entityId]?.kind === "note") {
      setEditingNote(p.entityId);
      setSelection([id]);
    } else if (scene.entities[p.entityId]) {
      root.current
        ?.querySelector<HTMLElement>(`[data-placement="${CSS.escape(id)}"]`)
        ?.focus({ preventScroll: true });
      setReader({ id: p.entityId, origin: captureOrigin(id) });
    }
  });
  const back = useStableEvent(() => {
    const frame = frames.at(-1);
    if (!frame) return;
    collectionMotion.capture();
    const item = Object.values(scene.placements).find(
      (p) => p.entityId === (stack ?? folder),
    );
    const container = item
      ? placementInContext(scene, item, frame.folder)
      : undefined;
    if (folder && !stack && container) {
      const vp = gestures.viewport.current?.getBoundingClientRect();
      if (vp)
        animateFolder(
          {
            x: vp.left + frame.camera.x + container.x * frame.camera.z,
            y: vp.top + frame.camera.y + container.y * frame.camera.z,
            w: container.w * frame.camera.z,
            h: container.h * frame.camera.z,
          },
          false,
        );
    }
    setFolder(frame.folder);
    setStack(frame.stack);
    setSelection(frame.selection);
    setFrames((prev) => prev.slice(0, -1));
    gestures.moveCamera(frame.camera);
    restoreFocus(frame.selection);
  });
  const recovery = useMemo(
    () => recoverNavigation(scene, { folder, stack }, frames),
    [scene, folder, stack, frames],
  );
  const recoverContext = useStableEvent(() => {
    if (!recovery) return;
    collectionMotion.clear();
    folderAnimation.current?.cancel();
    folderAnimation.current = null;
    setFolder(recovery.frame.folder);
    setStack(recovery.frame.stack);
    setFrames(recovery.frames);
    setSelection(recovery.frame.selection);
    setEditingNote(null);
    setPalette(false);
    gestures.moveCamera(recovery.frame.camera, false);
    restoreFocus(recovery.frame.selection);
  });
  useEffect(() => {
    if (!recovery) return;
    const frame = requestAnimationFrame(recoverContext);
    return () => cancelAnimationFrame(frame);
  }, [recovery, recoverContext]);
  const groupSelection = (kind: "folder" | "stack") => {
    if (selected.length < 2) return;
    const id = crypto.randomUUID(),
      rect = bounds(selected),
      parent = stack ?? folder;
    collectionMotion.capture();
    doc.update((s) => {
      const collection = {
        id,
        kind,
        title: kind === "folder" ? "新建文件夹" : "新建堆叠",
        color: "white",
      };
      const placements = {
        ...s.placements,
        [id]: {
          id,
          entityId: id,
          x: rect.x,
          y: rect.y,
          w: kind === "folder" ? 312 : 280,
          h: kind === "folder" ? 266 : 344,
          parentId: parent,
        },
      };
      selected.forEach((p, i) => {
        placements[p.id] = {
          ...p,
          parentId: id,
          x: (i % 4) * 324,
          y: Math.floor(i / 4) * 420,
        };
      });
      return {
        ...s,
        collections: { ...s.collections, [id]: collection },
        placements,
      };
    });
    setSelection([id]);
    setToast(kind === "folder" ? "已建立文件夹" : "已整理成堆叠");
  };
  const removeSelection = () => {
    if (!selection.length) return;
    doc.update((s) => {
      let next = s;
      for (const p of selected)
        if (scene.collections[p.entityId])
          next = dissolve(next, scene, p.entityId);
      return { ...next, hidden: [...new Set([...next.hidden, ...selection])] };
    });
    setSelection([]);
    setToast("已从画布移除，可撤销恢复");
  };
  const addNote = () => {
    const id = crypto.randomUUID(),
      p = worldPoint(
        { x: gestures.view.width / 2, y: gestures.view.height / 2 },
        gestures.camera.current,
      );
    const offset =
      stackPlacement && stack
        ? { x: stackPlacement.x, y: stackPlacement.y + 50 }
        : { x: 0, y: 0 };
    doc.update((s) => ({
      ...s,
      entities: {
        ...s.entities,
        [id]: { id, kind: "note", title: "新的笔记", body: "", editable: true },
      },
      placements: {
        ...s.placements,
        [id]: {
          id,
          entityId: id,
          parentId: stack ?? folder,
          x: p.x - offset.x,
          y: p.y - offset.y,
          w: 280,
          h: 280,
        },
      },
    }));
    setSelection([id]);
    setEditingNote(id);
  };
  const pin = () => {
    if (!first) return;
    if (
      Object.values(scene.placements).some(
        (p) => p.entityId === first.entityId && p.parentId === null,
      )
    ) {
      setToast("该内容已放在主画布");
      return;
    }
    const id = crypto.randomUUID(),
      rect = bounds(children.get(null) ?? []);
    doc.update((s) => ({
      ...s,
      placements: {
        ...s.placements,
        [id]: {
          ...first,
          id,
          parentId: null,
          x: rect.x + rect.w + 70,
          y: rect.y,
        },
      },
    }));
    setToast("已放到主画布，共享同一份内容");
  };
  const moveOut = () => {
    collectionMotion.capture();
    doc.update((s) =>
      reparent(
        s,
        scene,
        selection,
        frames.at(-1)?.stack ?? frames.at(-1)?.folder ?? null,
      ),
    );
    setSelection([]);
  };
  const importFiles = async (
    items: ImportFile[],
    targetParent = stack ?? folder,
  ) => {
    if (!items.length || assets.busy || importLock.current) return;
    if (!projectId && !demo) {
      setToast("先在下方添加招标文件，建立项目后即可导入素材");
      return;
    }
    if (projectId) {
      const uploaded = await assets.upload(items);
      if (targetParent && mounted.current && uploaded)
        doc.update((s) => {
          const placements = { ...s.placements };
          let n = (children.get(targetParent) ?? []).length;
          for (const item of uploaded) {
            if (item.status !== "ready" && item.status !== "processing")
              continue;
            const id = item.originSha256
                ? `pdf:${item.originSha256}`
                : `file:sources/${item.path}`,
              kind = fileKind(item.path);
            placements[id] = {
              id,
              entityId: id,
              parentId: targetParent,
              x: (n % 4) * 340,
              y: Math.floor(n / 4) * 430,
              w: 280,
              h: kind === "image" || kind === "video" ? 210 : 374,
            };
            n++;
          }
          return { ...s, placements };
        });
      return;
    }
    importLock.current = true;
    setLocalBusy(true);
    try {
      for (const item of items) {
        const id = `local-file:${crypto.randomUUID()}`;
        await saveLocalFile(id, item.file);
        if (!mounted.current) return;
        doc.update((s) => {
          let parent = targetParent;
          const collections = { ...s.collections },
            placements = { ...s.placements },
            directories = item.path.split("/").slice(0, -1);
          directories.forEach((name, i) => {
            const cid = `local-directory:${folder ?? "root"}:${directories.slice(0, i + 1).join("/")}`;
            if (!collections[cid]) {
              collections[cid] = {
                id: cid,
                title: name,
                kind: "folder",
                color: "white",
              };
              placements[cid] = {
                id: cid,
                entityId: cid,
                parentId: parent,
                x:
                  80 +
                  (Object.values(placements).filter(
                    (p) => p.parentId === parent,
                  ).length %
                    4) *
                    350,
                y: 100,
                w: 312,
                h: 266,
              };
            }
            parent = cid;
          });
          const n = Object.values({
              ...scene.placements,
              ...placements,
            }).filter((p) => p.parentId === parent).length,
            kind = fileKind(item.path);
          placements[id] = {
            id,
            entityId: id,
            parentId: parent,
            x: (n % 4) * 324,
            y: Math.floor(n / 4) * 420,
            w: 280,
            h: kind === "image" || kind === "video" ? 210 : 374,
          };
          return {
            ...s,
            collections,
            placements,
            entities: {
              ...s.entities,
              [id]: {
                id,
                kind,
                title: item.file.name,
                path: item.path,
                size: item.file.size,
                src: `local:${id}`,
              },
            },
          };
        });
      }
      setToast(`已导入 ${items.length} 项内容`);
    } catch {
      setToast("本地文件保存失败，请检查浏览器存储后重试");
    } finally {
      importLock.current = false;
      if (mounted.current) setLocalBusy(false);
    }
  };
  const inputFiles = (event: ChangeEvent<HTMLInputElement>) => {
    const items = Array.from(event.target.files ?? []).map((file) => ({
      file,
      path: file.webkitRelativePath || file.name,
    }));
    event.target.value = "";
    void importFiles(items);
  };
  const updateMediaSize = useStableEvent(
    (id: string, width: number, height: number) => {
      const placement = scene.placements[id],
        entity = placement && scene.entities[placement.entityId];
      if (
        (demo && !entity?.src?.startsWith("local:")) ||
        !width ||
        !height ||
        placement?.mediaRatio
      )
        return;
      doc.update((s) => {
        const current = s.placements[id] ?? placement;
        if (!current || current.mediaRatio) return s;
        const ratio = width / height,
          w = Math.min(current.w, 560 * ratio);
        return {
          ...s,
          placements: {
            ...s.placements,
            [id]: { ...current, w, h: w / ratio, mediaRatio: ratio },
          },
        };
      }, false);
    },
  );
  const cancelNoteEdit = useCallback(() => setEditingNote(null), []);
  const saveNote = useStableEvent((id: string, title: string, body: string) => {
    const entity = scene.entities[id];
    if (entity && (entity.title !== title || entity.body !== body))
      doc.update((s) => ({
        ...s,
        entities: {
          ...s.entities,
          [id]: { ...entity, title: title.trim() || "未命名笔记", body },
        },
      }));
    setEditingNote(null);
  });
  const navigateEntity = (entityId: string) => {
    if (scene.entities[entityId]) setReader({ id: entityId });
  };
  useLayoutEffect(() => {
    if (!doc.hydrated || fitted.current || !displayed.length) return;
    fitted.current = true;
    if (doc.present.camera) gestures.moveCamera(doc.present.camera, false);
    else gestures.fit(displayed, false);
  }, [doc.hydrated, doc.present.camera, displayed, gestures]);
  const compactBefore = useRef(false);
  useLayoutEffect(() => {
    const compact = gestures.view.width <= 600;
    if (
      compact &&
      !compactBefore.current &&
      doc.hydrated &&
      interactiveItems.length
    ) {
      const focus =
        interactiveItems.find((p) => selection.includes(p.id)) ??
        interactiveItems[0]!;
      gestures.fit([focus], false);
    }
    compactBefore.current = compact;
  }, [gestures, doc.hydrated, interactiveItems, selection]);
  const restoreCamera = gestures.moveCamera,
    cameraRef = gestures.camera;
  useLayoutEffect(() => {
    if (viewMode === "canvas") restoreCamera({ ...cameraRef.current }, false);
  }, [viewMode, restoreCamera, cameraRef]);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (
        reader ||
        matrixReader ||
        (event.target as HTMLElement).closest(
          "input,textarea,select,[contenteditable=true]",
        )
      )
        return;
      const mod = event.ctrlKey || event.metaKey;
      if (viewMode !== "canvas") {
        if (event.key === "Escape") {
          setHelp(false);
          setShowSearch(false);
        } else if (mod && event.key.toLowerCase() === "k") {
          event.preventDefault();
          setShowSearch((value) => !value);
        }
        return;
      }
      if (event.key === "Escape") {
        if (help) setHelp(false);
        else if (showSearch) setShowSearch(false);
        else if (palette) setPalette(false);
        else if (renaming) setRenaming(null);
        else if (frames.length) back();
        else setSelection([]);
      }
      if (mod && event.key.toLowerCase() === "z") {
        event.preventDefault();
        collectionMotion.capture();
        if (event.shiftKey) doc.redo();
        else doc.undo();
      }
      if (mod && event.key.toLowerCase() === "a") {
        event.preventDefault();
        setSelection(interactiveItems.map((p) => p.id));
      }
      if (mod && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setShowSearch((v) => !v);
      }
      if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        removeSelection();
      }
      if (!mod && event.key.toLowerCase() === "g") {
        event.preventDefault();
        groupSelection(event.shiftKey ? "folder" : "stack");
      }
      if (!mod && event.key.toLowerCase() === "n") {
        event.preventDefault();
        addNote();
      }
      if (!mod && event.key === "0") gestures.fit();
      if (!mod && event.key === "1") gestures.zoom(1, true);
      if (!mod && /^Arrow/.test(event.key) && selected.length) {
        event.preventDefault();
        const step = event.shiftKey ? 10 : 1;
        const dx =
            event.key === "ArrowRight"
              ? step
              : event.key === "ArrowLeft"
                ? -step
                : 0,
          dy =
            event.key === "ArrowDown"
              ? step
              : event.key === "ArrowUp"
                ? -step
                : 0;
        doc.update((s) => ({
          ...s,
          placements: {
            ...s.placements,
            ...Object.fromEntries(
              selected.map((p) => [p.id, { ...p, x: p.x + dx, y: p.y + dy }]),
            ),
          },
        }));
      }
    };
    const paste = (event: ClipboardEvent) => {
      if (
        reader ||
        matrixReader ||
        (event.target as HTMLElement).closest(
          "input,textarea,select,[contenteditable=true]",
        )
      )
        return;
      const files = Array.from(event.clipboardData?.files ?? []);
      if (files.length) {
        event.preventDefault();
        void importFiles(files.map((file) => ({ file, path: file.name })));
      } else {
        const text = event.clipboardData?.getData("text/plain");
        if (text) {
          event.preventDefault();
          const id = crypto.randomUUID();
          doc.update((s) => ({
            ...s,
            entities: {
              ...s.entities,
              [id]: {
                id,
                kind: "note",
                title: "剪贴笔记",
                body: text,
                editable: true,
              },
            },
            placements: {
              ...s.placements,
              [id]: {
                id,
                entityId: id,
                x: 120,
                y: 120,
                w: 280,
                h: 280,
                parentId: stack ?? folder,
              },
            },
          }));
          setSelection([id]);
        }
      }
    };
    window.addEventListener("keydown", key);
    window.addEventListener("paste", paste);
    return () => {
      window.removeEventListener("keydown", key);
      window.removeEventListener("paste", paste);
    };
  });
  const cameraRect = {
    x: (-gestures.view.x - 450) / gestures.view.z,
    y: (-gestures.view.y - 450) / gestures.view.z,
    w: (gestures.view.width + 900) / gestures.view.z,
    h: (gestures.view.height + 900) / gestures.view.z,
  };
  const visible = displayed.filter(
    (p) =>
      intersects(p, cameraRect) ||
      (selection.length === 1 && selection.includes(p.id)),
  );
  const selectedEntities = new Set(selected.map((p) => p.entityId));
  const relations = scene.relations.filter(
    (r) => selectedEntities.has(r.from) || selectedEntities.has(r.to),
  );
  const currentReader = reader ? scene.entities[reader.id] : undefined;
  const matchResults = query.trim()
    ? Object.values(scene.entities)
        .filter((e) =>
          `${e.title} ${e.body ?? ""}`
            .toLowerCase()
            .includes(query.toLowerCase()),
        )
        .slice(0, 20)
    : [];
  const busy = localBusy || assets.busy;
  const saveRename = () => {
    if (renaming && renameDraft.trim())
      doc.update((s) => ({
        ...s,
        collections: {
          ...s.collections,
          [renaming]: {
            ...scene.collections[renaming]!,
            title: renameDraft.trim(),
          },
        },
      }));
    setRenaming(null);
  };

  return (
    <div
      ref={root}
      className="canvas-pane workspace-surface sp-workspace"
      data-view={viewMode}
      data-stream={demo ? "min" : streamSize}
      data-demo={demo || undefined}
    >
      <header className="sp-toolbar">
        <div className="sp-space-title">
          <GridIcon />
          <span>{demo ? "标书编制空间" : projectName || "工作空间"}</span>
          {demo && <small>演示</small>}
        </div>
        <div className="sp-toolbar-right">
          {demo && (
            <select
              aria-label="演示场景"
              value={scenario}
              onChange={(e) => {
                setScenario(e.target.value as typeof scenario);
                setReader(null);
                setSelection([]);
              }}
            >
              <option value="complete">完整成果</option>
              <option value="working">正在生成</option>
              <option value="partial">部分失败</option>
              <option value="stress">大量资料</option>
            </select>
          )}
          <button
            aria-label="搜索画布"
            title="搜索 · ⌘ K"
            onClick={() => setShowSearch((v) => !v)}
          >
            <SearchIcon />
          </button>
          <div className="cv-view-switch" role="group" aria-label="结果视图">
            <button
              aria-pressed={viewMode === "canvas"}
              onClick={() => setViewMode("canvas")}
            >
              画布
            </button>
            <button
              aria-pressed={viewMode === "overview"}
              onClick={() => setViewMode("overview")}
            >
              概览
            </button>
          </div>
        </div>
      </header>
      <div
        className="canvas-viewport sp-viewport"
        ref={gestures.viewport}
        role="region"
        tabIndex={0}
        aria-label="标书资料画布"
        onDragEnter={(e) => {
          if (e.dataTransfer.types.includes("Files")) {
            e.preventDefault();
            dropDepth.current++;
            setDropOver(true);
          }
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          dropDepth.current = Math.max(0, dropDepth.current - 1);
          if (!dropDepth.current) setDropOver(false);
        }}
        onDragOver={(e) => {
          if (e.dataTransfer.types.includes("Files")) {
            e.preventDefault();
            e.dataTransfer.dropEffect = "copy";
          }
        }}
        onDrop={(e) => {
          e.preventDefault();
          dropDepth.current = 0;
          setDropOver(false);
          const cardId = (e.target as HTMLElement).closest<HTMLElement>(
            "[data-placement]",
          )?.dataset.placement;
          const candidate = cardId
            ? scene.placements[cardId]?.entityId
            : undefined;
          const parent =
            candidate && scene.collections[candidate]
              ? candidate
              : (stack ?? folder);
          void filesFromDrop(e.dataTransfer)
            .then((items) => importFiles(items, parent))
            .catch(() => setToast("无法读取文件夹，请重新选择"));
        }}
      >
        {viewMode === "canvas" && (
          <>
            <div
              ref={gestures.world}
              className="sp-world"
              style={{ visibility: doc.hydrated ? undefined : "hidden" }}
            >
              {visible.map((p) => (
                <SpatialCard
                  key={p.id}
                  placement={p}
                  entity={scene.entities[p.entityId]}
                  collection={scene.collections[p.entityId]}
                  selected={selection.includes(p.id)}
                  dimmed={Boolean(stack && p.parentId !== stack)}
                  count={children.get(p.entityId)?.length ?? 0}
                  members={cardMembers.get(p.entityId) ?? EMPTY_MEMBERS}
                  onOpen={enter}
                  onFocus={focusCard}
                  editing={editingNote === p.entityId}
                  onMediaSize={updateMediaSize}
                  onCancelEdit={cancelNoteEdit}
                  onSaveNote={saveNote}
                />
              ))}
              <svg className="sp-relations" aria-hidden="true">
                {relations.map((r) => {
                  const a = displayed.find((p) => p.entityId === r.from),
                    b = displayed.find((p) => p.entityId === r.to);
                  if (!a || !b) return null;
                  const x = a.x + a.w,
                    y = a.y + a.h / 2,
                    bx = b.x,
                    by = b.y + b.h / 2;
                  return (
                    <path
                      key={r.id}
                      d={`M ${x} ${y} C ${x + 70} ${y}, ${bx - 70} ${by}, ${bx} ${by}`}
                    />
                  );
                })}
              </svg>
            </div>
            <div className="sp-marquee" ref={gestures.marquee} />
            {!!frames.length && (
              <nav
                className="sp-breadcrumb"
                aria-label="集合导航"
                data-no-gesture
              >
                <button onClick={back}>
                  <ChevronLeftIcon />
                  返回{frames.at(-1)?.folder ? "文件夹" : "画布"}
                </button>
                <span>/</span>
                <strong>
                  {scene.collections[stack ?? folder ?? ""]?.title}
                </strong>
                <small>{children.get(stack ?? folder)?.length ?? 0} 项</small>
                {scene.collections[stack ?? folder ?? ""]?.matrixType && (
                  <button
                    onClick={() =>
                      setMatrixReader(
                        scene.collections[stack ?? folder ?? ""]!.matrixType!,
                      )
                    }
                  >
                    列表核验 <ArrowRightIcon />
                  </button>
                )}
              </nav>
            )}
            {!displayed.length && doc.hydrated && (
              <div className="sp-empty" data-no-gesture>
                <FolderSimpleIcon />
                <h1>
                  {folder || stack ? "让资料在这里相聚" : "从一份招标文件开始"}
                </h1>
                <p>
                  {folder || stack
                    ? "拖入文件，或添加一张笔记。"
                    : "把项目资料放到画布上，逐步形成你的投标文件。"}
                </p>
                {!demo && !projectId ? (
                  <Link href="/workspace?demo=1">
                    探索示例空间 <ArrowRightIcon />
                  </Link>
                ) : (
                  <button onClick={() => fileInput.current?.click()}>
                    导入文件 <UploadIcon />
                  </button>
                )}
              </div>
            )}
          </>
        )}
        {viewMode === "overview" && (
          <section
            className="cv-overview sp-overview"
            data-no-gesture
            aria-label="项目概览"
          >
            <header className="cv-overview-heading">
              <div>
                <p>项目资料与编制成果</p>
                <h1>
                  {demo ? "智慧园区数字化建设" : projectName || "新的投标项目"}
                </h1>
              </div>
              <Link href="/projects">
                全部项目 <ArrowRightIcon />
              </Link>
            </header>
            {!demo ? (
              <div className="cv-overview-grid">
                {MATRIX_CARD_ORDER.map((type) => (
                  <button
                    className="cv-overview-card"
                    key={type}
                    onClick={() => setMatrixReader(type)}
                  >
                    <span className="cv-face-head">
                      {META[type].title}
                      <ArrowRightIcon />
                    </span>
                    <CardPreview type={type} />
                  </button>
                ))}
              </div>
            ) : (
              <div className="sp-overview-demo">
                {Object.values(scene.collections)
                  .filter((c) => !scene.placements[c.id]?.parentId)
                  .map((c) => (
                    <button
                      key={c.id}
                      onClick={() => {
                        setViewMode("canvas");
                        enter(c.id);
                      }}
                    >
                      <LayersIcon />
                      <strong>{c.title}</strong>
                      <span>
                        {c.subtitle || `${children.get(c.id)?.length ?? 0} 项`}
                      </span>
                      <ArrowRightIcon />
                    </button>
                  ))}
              </div>
            )}
          </section>
        )}
        <div className="sp-folder-morph" ref={morph} aria-hidden="true" />
        {dropOver && (
          <div className="sp-drop-overlay">
            <FolderSimpleIcon />
            <span>{busy ? "正在导入，请稍候" : "松开，将资料放入空间"}</span>
          </div>
        )}
        {!demo && <WorkspaceChrome />}
        {viewMode === "canvas" && (
          <>
            <div
              className="sp-tools"
              role="toolbar"
              aria-label="画布工具"
              data-no-gesture
            >
              {selected.length > 0 && (
                <>
                  <span className="sp-selection-count">
                    {selected.length} 项
                  </span>
                  <button
                    title="打开"
                    aria-label="打开所选内容"
                    disabled={selected.length !== 1}
                    onClick={() => first && enter(first.id)}
                  >
                    <ArrowRightIcon />
                  </button>
                  {selectedCollection && (
                    <>
                      <button
                        title="重命名集合"
                        aria-label="重命名集合"
                        onClick={() => {
                          setRenameDraft(selectedCollection.title);
                          setRenaming(selectedCollection.id);
                          setPalette(false);
                        }}
                      >
                        <PenIcon />
                      </button>
                      <button
                        className="sp-color-trigger"
                        aria-label="文件夹颜色"
                        onClick={() => {
                          setPalette(!palette);
                          setRenaming(null);
                        }}
                      >
                        <span />
                      </button>
                      <button
                        title="解散集合"
                        aria-label="解散集合"
                        onClick={() => {
                          collectionMotion.capture();
                          doc.update((s) =>
                            dissolve(s, scene, selectedCollection.id),
                          );
                          setSelection([]);
                        }}
                      >
                        <LayersIcon />
                      </button>
                    </>
                  )}
                  {selected.length > 1 && (
                    <>
                      <button
                        aria-label="组成堆叠"
                        title="组成堆叠 · G"
                        onClick={() => groupSelection("stack")}
                      >
                        <LayersIcon />
                      </button>
                      <button
                        aria-label="组成文件夹"
                        title="组成文件夹 · Shift G"
                        onClick={() => groupSelection("folder")}
                      >
                        <FolderSimpleIcon />
                      </button>
                    </>
                  )}
                  {first?.parentId && (
                    <>
                      <button
                        title="放到主画布"
                        aria-label="放到主画布"
                        disabled={
                          selected.length !== 1 || Boolean(selectedCollection)
                        }
                        onClick={pin}
                      >
                        <PlusIcon />
                      </button>
                      <button
                        title="移出集合"
                        aria-label="移出集合"
                        onClick={moveOut}
                      >
                        <ArrowUpIcon />
                      </button>
                    </>
                  )}
                  {first &&
                    !selectedCollection &&
                    selected.length === 1 &&
                    (scene.entities[first.entityId]?.src ||
                      scene.entities[first.entityId]?.body) && (
                      <button
                        aria-label="下载所选内容"
                        title="下载所选内容"
                        onClick={() =>
                          void downloadEntity(
                            scene.entities[first.entityId]!,
                          ).catch(() => setToast("文件暂时无法下载，请重试"))
                        }
                      >
                        <DownloadIcon />
                      </button>
                    )}
                  {selected.length > 1 && (
                    <button
                      aria-label="整理所选内容"
                      title="整理所选内容"
                      onClick={() => {
                        collectionMotion.capture();
                        const area = bounds(selected);
                        doc.update((s) => ({
                          ...s,
                          placements: {
                            ...s.placements,
                            ...Object.fromEntries(
                              selected.map((p, i) => [
                                p.id,
                                {
                                  ...p,
                                  x: area.x + (i % 4) * 340,
                                  y: area.y + Math.floor(i / 4) * 430,
                                },
                              ]),
                            ),
                          },
                        }));
                      }}
                    >
                      <FrameIcon />
                    </button>
                  )}
                  <button
                    title="从画布移除"
                    aria-label="从画布移除"
                    onClick={removeSelection}
                  >
                    <XIcon />
                  </button>
                  <i />
                </>
              )}
              <button
                aria-label="添加笔记"
                title="添加笔记 · N"
                onClick={addNote}
              >
                <PenIcon />
              </button>
              <button
                aria-label="导入文件"
                title="导入文件"
                disabled={busy}
                onClick={() => fileInput.current?.click()}
              >
                <FileTextIcon />
              </button>
              <button
                aria-label="导入图片或视频"
                title="导入图片或视频"
                disabled={busy}
                onClick={() => imageInput.current?.click()}
              >
                <PlusIcon />
              </button>
              <button
                aria-label="导入文件夹"
                title="导入文件夹"
                disabled={busy}
                onClick={() => folderInput.current?.click()}
              >
                <FolderSimpleIcon />
              </button>
              <i />
              <button
                aria-label="撤销"
                title="撤销 · ⌘ Z"
                disabled={!doc.past.length}
                onClick={() => {
                  collectionMotion.capture();
                  doc.undo();
                }}
              >
                <RefreshCcwIcon />
              </button>
              <button
                aria-label="重做"
                title="重做 · ⇧ ⌘ Z"
                disabled={!doc.future.length}
                onClick={() => {
                  collectionMotion.capture();
                  doc.redo();
                }}
              >
                <RefreshIcon />
              </button>
              {palette && selectedCollection && (
                <div className="sp-palette">
                  {COLORS.map((color, i) => (
                    <button
                      aria-label={COLOR_NAMES[i]}
                      aria-pressed={selectedCollection.color === color}
                      key={color}
                      className={`color-${color}`}
                      onClick={() =>
                        doc.update((s) => ({
                          ...s,
                          collections: {
                            ...s.collections,
                            [selectedCollection.id]: {
                              ...selectedCollection,
                              color,
                            },
                          },
                        }))
                      }
                    >
                      {selectedCollection.color === color && <CheckIcon />}
                    </button>
                  ))}
                </div>
              )}
              {renaming && (
                <form
                  className="sp-rename"
                  onSubmit={(e) => {
                    e.preventDefault();
                    saveRename();
                  }}
                >
                  <input
                    aria-label="集合名称"
                    autoFocus
                    value={renameDraft}
                    onChange={(e) => setRenameDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Escape") setRenaming(null);
                    }}
                  />
                  <button type="submit">保存</button>
                </form>
              )}
            </div>
            <div className="sp-zoom" data-no-gesture>
              <button
                aria-label="缩小画布"
                onClick={() => gestures.zoom(1 / 1.2)}
              >
                <MinusIcon />
              </button>
              <button
                aria-label="恢复百分之百"
                onClick={() => gestures.zoom(1, true)}
              >
                {Math.round(gestures.view.z * 100)}%
              </button>
              <button aria-label="放大画布" onClick={() => gestures.zoom(1.2)}>
                <PlusIcon />
              </button>
              <i />
              <button aria-label="适应画布" onClick={() => gestures.fit()}>
                <FrameIcon />
              </button>
            </div>
            <button
              className="sp-help-button"
              aria-label="画布操作帮助"
              data-no-gesture
              onClick={() => setHelp(!help)}
            >
              ?
            </button>
          </>
        )}
        {!!relations.length && !reader && viewMode === "canvas" && (
          <aside
            className="sp-relation-list"
            data-no-gesture
            aria-label="所选内容的关联"
          >
            {relations.slice(0, 8).map((r) => {
              const other = selectedEntities.has(r.from) ? r.to : r.from;
              return (
                <button key={r.id} onClick={() => navigateEntity(other)}>
                  <span>
                    {r.kind === "source"
                      ? "原文依据"
                      : r.kind === "response"
                        ? "响应关联"
                        : "引用素材"}
                  </span>
                  <b>{scene.entities[other]?.title}</b>
                  <ArrowRightIcon />
                </button>
              );
            })}
          </aside>
        )}
        {((assets.uploads.length > 0 && assets.progressVisible) ||
          assets.error ||
          localBusy) && (
          <aside
            className="sp-upload-progress"
            data-no-gesture
            aria-label="导入进度"
          >
            <div>
              <UploadIcon />
              <strong>
                {busy
                  ? "正在导入资料"
                  : assets.error
                    ? "资料载入失败"
                    : assets.uploads.some(
                          (item) => item.status === "processing",
                        )
                      ? "文件已上传，等待原文就绪"
                      : "资料导入完成"}
              </strong>
              {!busy && (
                <button aria-label="关闭导入进度" onClick={assets.dismiss}>
                  <XIcon />
                </button>
              )}
            </div>
            {assets.error && (
              <p>
                {assets.error}
                <button onClick={() => void assets.reload()}>重新载入</button>
              </p>
            )}
            {assets.uploads.length > 0 && (
              <>
                <progress
                  max={assets.uploads.length}
                  value={
                    assets.uploads.filter(
                      (u) =>
                        u.status === "ready" ||
                        u.status === "processing" ||
                        u.status === "error",
                    ).length
                  }
                />
                <p>
                  {
                    assets.uploads.filter(
                      (u) => u.status === "ready" || u.status === "processing",
                    ).length
                  }{" "}
                  / {assets.uploads.length} 项已导入
                </p>
                {assets.uploads
                  .filter(
                    (u) =>
                      u.status === "working" ||
                      u.status === "processing" ||
                      u.status === "error",
                  )
                  .map((u) => (
                    <p key={u.id}>
                      {u.file.name}
                      <span>
                        {u.error ||
                          (u.status === "processing"
                            ? "等待原文就绪"
                            : "上传中")}
                      </span>
                    </p>
                  ))}
                {!busy && assets.uploads.some((u) => u.status === "error") && (
                  <button
                    onClick={() =>
                      void assets.upload(
                        assets.uploads
                          .filter((u) => u.status === "error")
                          .map((u) => ({ file: u.file, path: u.path })),
                      )
                    }
                  >
                    重试失败文件
                  </button>
                )}
              </>
            )}
          </aside>
        )}
        {toast && (
          <div className="sp-toast" role="status" data-no-gesture>
            <CheckIcon />
            {toast}
          </div>
        )}
        {doc.storageError && (
          <div className="sp-storage-warning" role="status">
            浏览器存储已满，当前布局暂未保存。
          </div>
        )}
        {showSearch && (
          <div className="sp-search" data-no-gesture>
            <div>
              <SearchIcon />
              <input
                autoFocus
                aria-label="搜索标题和正文"
                placeholder="搜索标题或正文…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Escape") setShowSearch(false);
                }}
              />
              <button
                aria-label="关闭搜索"
                onClick={() => setShowSearch(false)}
              >
                <XIcon />
              </button>
            </div>
            {matchResults.map((e) => (
              <button
                key={e.id}
                onClick={() => {
                  setShowSearch(false);
                  navigateEntity(e.id);
                }}
              >
                <FileIcon />
                {e.title}
                <ArrowRightIcon />
              </button>
            ))}
            {query && !matchResults.length && <p>没有找到相关内容</p>}
          </div>
        )}
        {help && (
          <aside className="sp-help" data-no-gesture>
            <button aria-label="关闭帮助" onClick={() => setHelp(false)}>
              <XIcon />
            </button>
            <h3>自由组织你的工作空间</h3>
            <p>
              单击选中，双击或 Enter 打开。
              <br />
              拖动空白处框选，Shift 点击多选。
              <br />
              空格拖动画布，滚轮平移，Ctrl / ⌘ 加滚轮缩放。
              <br />G 组成堆叠，Shift + G 组成文件夹。
              <br />N 添加笔记，0 适应画布，1 恢复 100%。
              <br />
              Escape 逐层返回，Ctrl / ⌘ + Z 撤销。
            </p>
          </aside>
        )}
        {demo && (
          <Link className="sp-demo-exit" href="/home" data-no-gesture>
            开始真实项目 <ArrowRightIcon />
          </Link>
        )}
        {currentReader && (
          <SpatialReader
            key={currentReader.id}
            entity={currentReader}
            origin={reader?.origin}
            entities={scene.entities}
            relations={scene.relations.filter(
              (r) => r.from === currentReader.id || r.to === currentReader.id,
            )}
            onClose={() => setReader(null)}
            onNavigate={navigateEntity}
            onEdit={(body, title) =>
              doc.update((s) => ({
                ...s,
                entities: {
                  ...s.entities,
                  [currentReader.id]: {
                    ...currentReader,
                    body,
                    title: title.trim() || "未命名笔记",
                  },
                },
              }))
            }
          />
        )}
        {matrixReader && (
          <CanvasDrawer
            type={matrixReader}
            cardType={matrixReader}
            title={META[matrixReader].title}
            spatial
            onClose={() => setMatrixReader(null)}
          />
        )}
        <input
          ref={fileInput}
          type="file"
          multiple
          hidden
          onChange={inputFiles}
        />
        <input
          ref={imageInput}
          type="file"
          multiple
          accept="image/*,video/*"
          hidden
          onChange={inputFiles}
        />
        <input
          ref={folderInput}
          type="file"
          multiple
          hidden
          {...{ webkitdirectory: "", directory: "" }}
          onChange={inputFiles}
        />
      </div>
    </div>
  );
}
