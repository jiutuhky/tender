import * as React from "react";

export interface CardProps {
  /** Render as glass instead of a solid surface (sits on the wallpaper).
   *  "lens" = 凝, refracting, for the control layer; "soft" = 霜, frosted, for chrome. */
  material?: "lens" | "soft";
  /** Glass thickness — blur, lens strength and shadow move together.
   *  Defaults to "regular", or "thick" when `panel` is set. */
  thickness?: "thin" | "regular" | "thick";
  /** Glass only: specular follows the pointer, press brightens + scales. Only for clickable things. */
  interactive?: boolean;
  /** Recessed gray fill with a hairline ring instead of a raised surface. */
  inset?: boolean;
  /** Level-2 elevation (popover/raised). */
  raised?: boolean;
  /** Panel radius (18px; 20px on glass) + larger padding. */
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
 * fills, `material` to make it glass (never for content — documents, tables and
 * the composer stay solid).
 */
export function Card(props: CardProps): JSX.Element;
