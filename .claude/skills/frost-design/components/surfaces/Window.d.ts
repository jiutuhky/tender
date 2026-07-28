import * as React from "react";

export interface WindowProps {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  /** Trailing toolbar slot — IconButtons, a Segmented control, etc. */
  actions?: React.ReactNode;
  /** Show the macOS traffic-light dots. */
  traffic?: boolean;
  /** Class for the toolbar surface — defaults to the glass toolbar; pass "" for solid. */
  toolbarClassName?: string;
  /** Window body content (often a sidebar + main + inspector grid). */
  children?: React.ReactNode;
  style?: React.CSSProperties;
}

/**
 * macOS window chrome: glass toolbar with traffic-light dots, title/subtitle,
 * a trailing actions slot, 12px corners, level-3 floating shadow. The frame for
 * any full app view; place it on a `.frost-wallpaper` background.
 */
export function Window(props: WindowProps): JSX.Element;
