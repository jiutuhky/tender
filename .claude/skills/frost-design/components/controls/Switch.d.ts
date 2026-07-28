import * as React from "react";

export interface SwitchProps {
  /** Controlled on/off. */
  checked?: boolean;
  defaultChecked?: boolean;
  onChange?: (checked: boolean) => void;
  disabled?: boolean;
  /** Optional trailing label; renders the switch + text as one clickable row. */
  label?: React.ReactNode;
  id?: string;
  "aria-label"?: string;
  style?: React.CSSProperties;
}

/**
 * macOS toggle switch. Track turns blue when on, knob slides with the float
 * easing. Pass `label` for a labelled row, or `aria-label` for a bare switch.
 */
export function Switch(props: SwitchProps): JSX.Element;
