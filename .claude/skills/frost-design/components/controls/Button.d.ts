import * as React from "react";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual role. `primary` = blue gradient (the single emphasis); `default` = white raised; `plain` = text-blue; `danger` = red gradient for destructive actions. */
  variant?: "primary" | "default" | "plain" | "danger";
  /** Control height. `md` = 32px (default), `sm` = 28px, `lg` = 38px. */
  size?: "sm" | "md" | "lg";
  /** Phosphor icon name (without the `ph-` prefix) rendered before the label. */
  icon?: string;
  /** Phosphor icon name rendered after the label. */
  iconRight?: string;
  disabled?: boolean;
  children?: React.ReactNode;
}

/**
 * Frost button. Primary carries the only accent in the system — reserve it for
 * the one affirmative action per view; everything else is default or plain.
 *
 * @dsCard group="Components"
 * @startingPoint section="Controls" subtitle="Primary / default / plain / danger, three sizes" viewport="700x150"
 */
export function Button(props: ButtonProps): JSX.Element;
