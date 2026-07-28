import * as React from "react";

export interface FieldProps {
  /** Phosphor icon name shown at the leading edge. */
  icon?: string;
  /** Trailing slot — e.g. an IconButton send control. */
  trailing?: React.ReactNode;
  /** `md` = 36px hairline field; `lg` = 44px raised composer field. */
  size?: "md" | "lg";
  type?: string;
  value?: string;
  defaultValue?: string;
  placeholder?: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  disabled?: boolean;
  /** Extra props spread onto the inner <input>. */
  inputProps?: React.InputHTMLAttributes<HTMLInputElement>;
  style?: React.CSSProperties;
}

/**
 * Text / search field. Inset hairline at rest, blue ring + halo on focus.
 * Use `size="lg"` with a trailing send button for the agent composer.
 *
 * @startingPoint section="Forms" subtitle="Search & composer fields" viewport="700x150"
 */
export function Field(props: FieldProps): JSX.Element;
