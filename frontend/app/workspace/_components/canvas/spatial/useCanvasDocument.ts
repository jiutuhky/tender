"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
} from "react";
import { createStore } from "zustand/vanilla";
import { useStore } from "zustand";
import {
  commitHistory,
  emptySnapshot,
  redoHistory,
  resolveScene,
  undoHistory,
  type CanvasHistory,
  type CanvasSnapshot,
  type CanvasSource,
} from "@/lib/canvas/model";

interface DocumentState extends CanvasHistory {
  hydrated: boolean;
  storageError: boolean;
}

function parseSnapshot(value: string | null): CanvasSnapshot | null {
  if (!value) return null;
  try {
    const data = JSON.parse(value) as CanvasSnapshot;
    if (
      data.version !== 1 ||
      !data.placements ||
      !data.collections ||
      !data.entities ||
      !Array.isArray(data.hidden)
    )
      return null;
    for (const p of Object.values(data.placements))
      if (
        ![p.x, p.y, p.w, p.h].every(Number.isFinite) ||
        p.w <= 0 ||
        p.h <= 0 ||
        typeof p.id !== "string"
      )
        return null;
    if (
      data.camera &&
      (![data.camera.x, data.camera.y, data.camera.z].every(Number.isFinite) ||
        data.camera.z < 0.15 ||
        data.camera.z > 2.5)
    )
      delete data.camera;
    return data;
  } catch {
    return null;
  }
}

/** 只保存空间操作和本地笔记；业务内容由适配器每次重新投影。 */
export function useCanvasDocument(key: string, source: CanvasSource) {
  const [store] = useState(() =>
    createStore<DocumentState>(() => ({
      past: [],
      present: emptySnapshot(),
      future: [],
      hydrated: false,
      storageError: false,
    })),
  );
  const state = useStore(store);
  useLayoutEffect(() => {
    const current = store.getState();
    if (!current.hydrated) return;
    const additions = Object.fromEntries(
      Object.entries(source.placements).filter(
        ([id]) =>
          !current.present.placements[id] &&
          !current.present.hidden.includes(id),
      ),
    );
    if (!Object.keys(additions).length) return;
    // 首次出现的位置成为空间基线；文件清单排序和后续发布不重排既有卡片。
    const merge = (snapshot: CanvasSnapshot): CanvasSnapshot => ({
      ...snapshot,
      placements: { ...additions, ...snapshot.placements },
    });
    store.setState({
      present: merge(current.present),
      past: current.past.map(merge),
      future: current.future.map(merge),
    });
  }, [source.placements, state.hydrated, store]);
  useEffect(() => {
    const storageKey = `prose.canvas.v1:${key}`;
    let failed = false,
      saved: CanvasSnapshot | null = null;
    try {
      saved = parseSnapshot(localStorage.getItem(storageKey));
    } catch {
      failed = true;
    }
    store.setState({
      present: saved ?? emptySnapshot(),
      hydrated: true,
      storageError: failed,
    });
    let timer: ReturnType<typeof setTimeout> | undefined;
    const save = () => {
      try {
        localStorage.setItem(
          storageKey,
          JSON.stringify(store.getState().present),
        );
      } catch {
        if (!store.getState().storageError)
          store.setState({ storageError: true });
      }
    };
    const unsubscribe = store.subscribe((next, prev) => {
      if (next.present === prev.present) return;
      clearTimeout(timer);
      timer = setTimeout(save, 280);
    });
    window.addEventListener("pagehide", save);
    return () => {
      clearTimeout(timer);
      save();
      unsubscribe();
      window.removeEventListener("pagehide", save);
    };
  }, [key, store]);
  const { placements, collections, entities, hidden } = state.present;
  const scene = useMemo(
    () =>
      resolveScene(source, {
        version: 1,
        placements,
        collections,
        entities,
        hidden,
      }),
    [source, placements, collections, entities, hidden],
  );
  const update = useCallback(
    (fn: (snapshot: CanvasSnapshot) => CanvasSnapshot, history = true) => {
      const current = store.getState(),
        next = fn(current.present);
      store.setState(
        history ? commitHistory(current, next) : { present: next },
      );
    },
    [store],
  );
  return {
    ...state,
    scene,
    update,
    undo: () => store.setState(undoHistory(store.getState())),
    redo: () => store.setState(redoHistory(store.getState())),
  };
}
