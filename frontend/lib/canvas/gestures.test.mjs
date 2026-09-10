import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";
import * as geometry from "./model.ts";

// 使用真实 hook 重放 StrictMode 的 effect 生命周期，验证裁剪窗口的外部行为。
test("effect 重新挂载后，滚轮平移仍更新裁剪窗口", () => {
  const code = ts.transpileModule(
    readFileSync(
      new URL(
        "../../app/workspace/_components/canvas/spatial/useSpatialGestures.ts",
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
  const slots = [],
    effects = [],
    timers = new Map(),
    listeners = new Map();
  let cursor = 0,
    nextTimer = 0,
    result;
  const same = (a, b) =>
    a && b && a.length === b.length && a.every((v, i) => v === b[i]);
  const react = {
    useRef(current) {
      const i = cursor++;
      return (slots[i] ??= { current });
    },
    useState(initial) {
      const i = cursor++;
      slots[i] ??= { value: initial };
      return [
        slots[i].value,
        (next) => {
          slots[i].value =
            typeof next === "function" ? next(slots[i].value) : next;
        },
      ];
    },
    useCallback(fn, deps) {
      const i = cursor++;
      if (!same(slots[i]?.deps, deps)) slots[i] = { fn, deps };
      return slots[i].fn;
    },
    useEffect(fn, deps) {
      const i = cursor++;
      if (!same(slots[i]?.deps, deps)) {
        slots[i] = { deps };
        effects.push({ fn });
      }
    },
  };
  const exported = {};
  vm.runInNewContext(code, {
    exports: exported,
    require: (name) =>
      name === "react"
        ? react
        : name === "gsap"
          ? { gsap: { to: () => ({ kill() {} }) } }
          : geometry,
    window: {
      addEventListener() {},
      removeEventListener() {},
      matchMedia: () => ({ matches: false }),
    },
    ResizeObserver: class {
      observe() {}
      disconnect() {}
    },
    setTimeout: (fn) => {
      timers.set(++nextTimer, fn);
      return nextTimer;
    },
    clearTimeout: (id) => timers.delete(id),
    requestAnimationFrame: () => 0,
    cancelAnimationFrame() {},
    CSS: { escape: (text) => text },
    performance,
  });
  const options = {
    items: [],
    selection: [],
    setSelection() {},
    isMedia: () => false,
    canDrop: () => false,
    onCommit() {},
    onCamera() {},
    interactive: true,
  };
  const render = () => {
    cursor = 0;
    result = exported.useSpatialGestures(options);
  };
  render();
  result.viewport.current = {
    style: {},
    classList: { add() {}, remove() {} },
    getBoundingClientRect: () => ({
      left: 0,
      top: 0,
      width: 1440,
      height: 900,
    }),
    addEventListener: (name, fn) => listeners.set(name, fn),
    removeEventListener: (name) => listeners.delete(name),
  };
  result.world.current = { style: {}, querySelector: () => null };
  effects.forEach((effect) => {
    effect.cleanup = effect.fn();
  });
  effects.forEach((effect) => effect.cleanup?.());
  effects.forEach((effect) => {
    effect.cleanup = effect.fn();
  });
  listeners.get("wheel")({
    target: { closest: () => null },
    preventDefault() {},
    deltaX: 20,
    deltaY: 900,
    ctrlKey: false,
    metaKey: false,
  });
  for (const [id, fn] of [...timers]) {
    timers.delete(id);
    fn();
  }
  render();
  assert.equal(result.view.x, 40);
  assert.equal(result.view.y, -815);
  assert.equal(result.view.width, 1440);
  effects.forEach((effect) => effect.cleanup?.());
});
