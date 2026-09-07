"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { CircleHalfIcon, MoonIcon, SunIcon } from "@/components/ui/icons";
import {
  getAppearancePref,
  getAppearancePrefServer,
  getAppearanceResolved,
  getAppearanceResolvedServer,
  setAppearancePref,
  subscribeAppearance,
  type AppearancePref,
} from "@/lib/appearance";

// 外观切换：顶栏图标钮 + 凝玻璃菜单（跟随系统 / 浅色 / 深色）。
// 三档语汇沿用 macOS 系统设置；触发钮的字形跟随「当前实际外观」，
// 让用户一眼看出现在是哪一档，而不是只看到一个静态图标。
//
// 状态走 useSyncExternalStore 而非 useState+useEffect：偏好有三个来源
// （本页选菜单 / 系统日夜切换 / 另一标签页改动），且服务端读不到 localStorage
// 与 matchMedia——外部 store 的服务端快照恒为浅色，水合后再对齐，无不一致。
// 页面本身不会闪：<html> 的 data-appearance 由 layout 的首帧脚本先写好了。
//
// 菜单必须 portal 到 body，**不能**留在顶栏子树里：顶栏是霜玻璃，
// backdrop root 会落在它身上，菜单就只能采样到顶栏自己——即「玻璃不叠玻璃」那条，
// 实测 Chromium 会把这种嵌套的 backdrop-filter 直接算成 none，玻璃整面塌成平板。
// 挪到 body 下之后，菜单落在内容实底/壁纸上，凝玻璃 regular 才真正成立。
// 代价是要自己定位：按触发钮的视口坐标算 fixed 位置，滚动/改窗即关闭。

const OPTIONS: { value: AppearancePref; label: string; Icon: typeof SunIcon }[] = [
  { value: "system", label: "跟随系统", Icon: CircleHalfIcon },
  { value: "light", label: "浅色", Icon: SunIcon },
  { value: "dark", label: "深色", Icon: MoonIcon },
];

const MENU_W = 168;
const GAP = 8;

export function AppearanceMenu() {
  const pref = useSyncExternalStore(
    subscribeAppearance,
    getAppearancePref,
    getAppearancePrefServer,
  );
  const resolved = useSyncExternalStore(
    subscribeAppearance,
    getAppearanceResolved,
    getAppearanceResolvedServer,
  );
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const btnRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const open = pos !== null;

  const place = useCallback(() => {
    const r = btnRef.current?.getBoundingClientRect();
    if (!r) return null;
    // 右对齐触发钮；贴边时向内收，不越出视口
    const left = Math.max(GAP, Math.min(r.right - MENU_W, window.innerWidth - MENU_W - GAP));
    return { top: r.bottom + GAP, left };
  }, []);

  // 点击菜单外、Esc、滚动与改窗都收起
  useEffect(() => {
    if (!open) return;
    menuRef.current?.querySelector<HTMLElement>('[aria-checked="true"]')?.focus({ preventScroll: true });
    const onPointerDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (btnRef.current?.contains(t) || menuRef.current?.contains(t)) return;
      setPos(null);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); setPos(null); btnRef.current?.focus({ preventScroll: true }); }
      if (e.key === "Tab") { setPos(null); btnRef.current?.focus({ preventScroll: true }); return; }
      if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
      const items = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>("button") ?? []);
      if (!items.length) return;
      e.preventDefault();
      const current = items.indexOf(document.activeElement as HTMLButtonElement);
      const next = e.key === "Home" ? 0 : e.key === "End" ? items.length - 1 : (current + (e.key === "ArrowUp" ? -1 : 1) + items.length) % items.length;
      items[next]?.focus({ preventScroll: true });
    };
    const close = (event: Event) => {
      if (event.target instanceof Node && menuRef.current?.contains(event.target)) return;
      setPos(null);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", close);
    window.addEventListener("scroll", close, true);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("resize", close);
      window.removeEventListener("scroll", close, true);
    };
  }, [open]);

  const choose = useCallback((next: AppearancePref) => {
    setAppearancePref(next);
    btnRef.current?.focus({ preventScroll: true });
    setPos(null);
  }, []);

  const TriggerIcon = resolved === "dark" ? MoonIcon : SunIcon;
  const currentLabel = OPTIONS.find((o) => o.value === pref)?.label ?? "跟随系统";

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        className="icon-btn"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`外观：${currentLabel}`}
        title={`外观：${currentLabel}`}
        onClick={() => setPos(open ? null : place())}
      >
        <TriggerIcon width={16} height={16} />
      </button>

      {open &&
        createPortal(
          <div
            ref={menuRef}
            className="appearance-menu frost-glass frost-glass--lens"
            data-thick="regular"
            role="menu"
            style={{ top: pos.top, left: pos.left, width: MENU_W }}
          >
            {OPTIONS.map(({ value, label, Icon }) => (
              <button
                key={value}
                type="button"
                role="menuitemradio"
                aria-checked={pref === value}
                className={`appearance-item${pref === value ? " is-active" : ""}`}
                onClick={() => choose(value)}
              >
                <Icon width={15} height={15} />
                <span>{label}</span>
              </button>
            ))}
          </div>,
          document.body,
        )}
    </>
  );
}
