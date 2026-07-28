import * as React from "react";

export interface MenuItemSpec {
  icon?: string;
  label?: React.ReactNode;
  /** Keyboard hint shown right-aligned in monospace. */
  kbd?: string;
  danger?: boolean;
  /** Pre-highlighted row (full-width blue). */
  active?: boolean;
  disabled?: boolean;
  onSelect?: () => void;
  /** Mark this entry as a separator. */
  separator?: boolean;
}

export interface MenuProps {
  /** Declarative item list. Use the string "---" or `{ separator: true }` for a divider. */
  items?: Array<MenuItemSpec | "---">;
  /** Or compose with Menu.Item / Menu.Separator children. */
  children?: React.ReactNode;
  style?: React.CSSProperties;
}

/**
 * Popover-glass context menu. Rows take an icon, label, and optional keyboard
 * hint; the hovered (or `active`) row fills full-width blue.
 */
export function Menu(props: MenuProps): JSX.Element & {
  Item: (p: MenuItemSpec) => JSX.Element;
  Separator: () => JSX.Element;
};
