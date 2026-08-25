// 外观（浅色 / 深色）的单一事实来源。
//
// Frost 的暗色不是反色：token 层在 [data-appearance="dark"] 作用域整体换挡
// （见 app/globals.css 与 app/frost-materials.css），组件、圆角、投影几何不变。
// 这里只负责「选哪一档」与「把结果写到 <html> 上」。
//
// 三档沿用 macOS 系统设置的语汇：跟随系统 / 浅色 / 深色。
// 「跟随系统」不写 data-appearance 的持久值，而是实时跟随 prefers-color-scheme。

export type AppearancePref = "system" | "light" | "dark";
/** 实际生效的外观——"system" 解析后只会是这两者之一 */
export type AppearanceResolved = "light" | "dark";

export const APPEARANCE_STORAGE_KEY = "prose-appearance";

/** 把偏好解析成实际外观（system → 读系统偏好） */
export function resolveAppearance(pref: AppearancePref): AppearanceResolved {
  if (pref !== "system") return pref;
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** 读取已持久化的偏好；无值或值非法一律回落「跟随系统」 */
export function readAppearancePref(): AppearancePref {
  if (typeof window === "undefined") return "system";
  try {
    const v = window.localStorage.getItem(APPEARANCE_STORAGE_KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    /* 隐私模式 / 禁用站点数据：按「跟随系统」处理 */
  }
  return "system";
}

/** 把偏好写进 localStorage；写不进去不影响本次会话内的切换 */
export function persistAppearancePref(pref: AppearancePref): void {
  try {
    window.localStorage.setItem(APPEARANCE_STORAGE_KEY, pref);
  } catch {
    /* 同上，静默降级 */
  }
}

/**
 * 把结果落到 <html> 上。
 * 浅色不写属性（:root 即浅色档），深色写 data-appearance="dark" —— 与规范的作用域一致。
 */
export function applyAppearance(resolved: AppearanceResolved): void {
  const html = document.documentElement;
  if (resolved === "dark") html.dataset.appearance = "dark";
  else delete html.dataset.appearance;
}

/**
 * 首帧脚本：在 body 渲染前同步执行，避免浅色闪一下再切深色（FOUC）。
 * 必须是自包含的字符串——它跑在任何模块加载之前。
 */
export const APPEARANCE_BOOT_SCRIPT = `(function(){try{
var p=localStorage.getItem(${JSON.stringify(APPEARANCE_STORAGE_KEY)});
if(p!=="light"&&p!=="dark"&&p!=="system"){p="system"}
var d=p==="dark"||(p==="system"&&matchMedia("(prefers-color-scheme: dark)").matches);
if(d){document.documentElement.dataset.appearance="dark"}
}catch(e){}})();`;

// ---- 订阅式外观 store ----
// 供 useSyncExternalStore 使用：偏好既可能被本页改（选菜单），也可能被系统改
// （「跟随系统」档下 macOS 日夜切换）或被另一个标签页改（storage 事件），
// 三个来源统一收敛到这里，组件只读快照。

let cachedPref: AppearancePref | null = null;
const listeners = new Set<() => void>();

function emit(): void {
  for (const l of listeners) l();
}

/** 供 useSyncExternalStore 的 subscribe */
export function subscribeAppearance(onChange: () => void): () => void {
  listeners.add(onChange);
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const onSystem = () => {
    // 只有「跟随系统」档才受系统偏好影响；其余档位系统切换不改变结果
    if (getAppearancePref() === "system") {
      applyAppearance(resolveAppearance("system"));
      emit();
    }
  };
  const onStorage = (e: StorageEvent) => {
    if (e.key !== APPEARANCE_STORAGE_KEY) return;
    cachedPref = null;                       // 让下次快照重新读
    applyAppearance(resolveAppearance(getAppearancePref()));
    emit();
  };
  mq.addEventListener("change", onSystem);
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(onChange);
    mq.removeEventListener("change", onSystem);
    window.removeEventListener("storage", onStorage);
  };
}

/** 当前偏好快照。必须返回稳定值——useSyncExternalStore 会按引用比较。 */
export function getAppearancePref(): AppearancePref {
  if (cachedPref === null) cachedPref = readAppearancePref();
  return cachedPref;
}

/** 服务端快照：读不到 localStorage 与 matchMedia，一律「跟随系统」 */
export function getAppearancePrefServer(): AppearancePref {
  return "system";
}

/** 当前实际外观快照（"light" | "dark"，均为稳定字面量） */
export function getAppearanceResolved(): AppearanceResolved {
  return resolveAppearance(getAppearancePref());
}

export function getAppearanceResolvedServer(): AppearanceResolved {
  return "light";
}

/** 选档：落盘 + 落 <html> + 通知订阅者 */
export function setAppearancePref(pref: AppearancePref): void {
  cachedPref = pref;
  persistAppearancePref(pref);
  applyAppearance(resolveAppearance(pref));
  emit();
}
