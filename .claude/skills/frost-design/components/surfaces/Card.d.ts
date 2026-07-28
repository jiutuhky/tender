import * as React from "react";

export interface CardProps {
  /** Render as a glass material grade instead of a solid surface (sits on wallpaper). */
  material?: "sidebar" | "toolbar" | "popover" | "sheet";
  /** Recessed gray fill with a hairline ring instead of a raised surface. */
  inset?: boolean;
  /** Level-2 elevation (popover/raised). */
  raised?: boolean;
  /** Panel radius (18px) + larger padding. */
  panel?: boolean;
  /** Padding override. */
  pad?: "sm" | "lg";
  /** Optional bold title rendered above the body. */
  title?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * The basic raised surface — white fill, level-1 shadow, 14px radius. Depth and
 * radius scale together: pass `panel` for large surfaces, `inset` for recessed
 * fills, `material` to make it glass.
 */
export function Card(props: CardProps): JSX.Element;
