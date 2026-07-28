import * as React from "react";

export interface BadgeProps {
  /** Semantic tone. Soft variants use the text-color of each pair on a tint. */
  tone?: "neutral" | "blue" | "green" | "orange" | "red";
  /** Solid fill in the graphic color with white text. */
  solid?: boolean;
  /** Leading status dot in the graphic color. */
  dot?: boolean;
  children?: React.ReactNode;
  style?: React.CSSProperties;
}

/**
 * Small status pill. Default (soft) variant pairs the darkened text color with a
 * tint of the saturated graphic color — the system's graphic/text color rule.
 */
export function Badge(props: BadgeProps): JSX.Element;
