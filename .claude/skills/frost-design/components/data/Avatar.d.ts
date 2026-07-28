import * as React from "react";

export interface AvatarProps {
  /** Image URL; falls back to initials when absent. */
  src?: string;
  /** Full name — used for initials and alt text. */
  name?: string;
  /** Pixel size (square). */
  size?: number;
  /** `squircle` (continuous corners, default) matches the icon language; `circle` for people-first contexts. */
  shape?: "squircle" | "circle";
  status?: "online" | "busy" | "away" | "offline";
  style?: React.CSSProperties;
}

/**
 * Rounded-square identity tile (continuous corners, in keeping with the icon
 * language). Shows an image or initials on a soft-blue tint; optional status dot.
 */
export function Avatar(props: AvatarProps): JSX.Element;
