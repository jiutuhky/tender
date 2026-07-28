import * as React from "react";

export interface TooltipProps {
  /** Tooltip text. */
  label: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  /** The single trigger element. */
  children: React.ReactNode;
  style?: React.CSSProperties;
}

/**
 * Small dark label shown on hover/focus of its child. Wraps one trigger and
 * positions above by default. CSS-driven, no timers.
 */
export function Tooltip(props: TooltipProps): JSX.Element;
