import * as React from "react";

export interface ToastProps {
  tone?: "info" | "success" | "warning" | "danger";
  /** Override the default tone icon (Phosphor name). */
  icon?: string;
  title?: React.ReactNode;
  detail?: React.ReactNode;
  /** Inline text action label. */
  action?: React.ReactNode;
  onAction?: () => void;
  /** When provided, renders a dismiss button. */
  onClose?: () => void;
  style?: React.CSSProperties;
}

/**
 * Floating notification on popover glass. Leading status icon in the semantic
 * color; title + optional detail, inline action, and dismiss.
 */
export function Toast(props: ToastProps): JSX.Element;
