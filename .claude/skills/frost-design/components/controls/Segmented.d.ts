import * as React from "react";

export interface SegmentedOption {
  value: string;
  label: React.ReactNode;
}

export interface SegmentedProps {
  /** Options as plain strings or `{ value, label }` objects. */
  options: Array<string | SegmentedOption>;
  /** Controlled selected value. */
  value?: string;
  /** Initial value when uncontrolled. */
  defaultValue?: string;
  onChange?: (value: string) => void;
  style?: React.CSSProperties;
}

/**
 * macOS segmented control — a recessed track with a white slider on the active
 * segment. Use for 2–4 mutually exclusive view modes (编制 / 预览 / 对照).
 */
export function Segmented(props: SegmentedProps): JSX.Element;
