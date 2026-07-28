import * as React from "react";

export interface SidebarItemProps {
  /** Phosphor icon name. */
  icon?: string;
  label?: React.ReactNode;
  /** Active row — soft-blue backing, blue icon, semibold. */
  active?: boolean;
  /** Trailing slot — a Badge, count, etc. */
  trailing?: React.ReactNode;
  onClick?: () => void;
  style?: React.CSSProperties;
}

export interface SidebarGroupProps {
  children?: React.ReactNode;
}

/**
 * A row in the glass sidebar — icon + label, optional trailing slot. The active
 * row gets the soft-blue backing and a blue icon.
 */
export function SidebarItem(props: SidebarItemProps): JSX.Element;

/** Section header above a run of SidebarItems (项目 / 知识库). */
export function SidebarGroup(props: SidebarGroupProps): JSX.Element;
