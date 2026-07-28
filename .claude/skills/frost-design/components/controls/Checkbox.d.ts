import * as React from "react";

export interface CheckboxProps {
  checked?: boolean;
  defaultChecked?: boolean;
  /** Mixed state — shows a minus glyph. */
  indeterminate?: boolean;
  onChange?: (checked: boolean) => void;
  disabled?: boolean;
  label?: React.ReactNode;
  style?: React.CSSProperties;
}

/**
 * Checkbox — 18px rounded box, blue gradient fill + white check when on.
 * Use inside forms and lists where a choice is confirmed; for instant-effect
 * settings prefer Switch.
 */
export function Checkbox(props: CheckboxProps): JSX.Element;
